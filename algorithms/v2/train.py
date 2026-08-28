#!/usr/bin/env python3

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .features import FeatureSchema
from .model import MODEL_FORMAT, MODEL_VERSION


def expected_calibration_error(labels, probabilities, bins=15):
    import numpy as np

    boundaries = np.linspace(0.0, 1.0, bins + 1)
    result = 0.0

    for index in range(bins):
        lower = boundaries[index]
        upper = boundaries[index + 1]
        mask = (
            (probabilities >= lower)
            & (
                probabilities <= upper
                if index == bins - 1
                else probabilities < upper
            )
        )

        if not mask.any():
            continue

        result += float(mask.mean()) * abs(
            float(labels[mask].mean())
            - float(probabilities[mask].mean())
        )

    return result


def calculate_metrics(labels, probabilities):
    from sklearn.metrics import (
        brier_score_loss,
        log_loss,
        roc_auc_score,
    )

    metrics = {
        "log_loss": float(log_loss(labels, probabilities, labels=[0, 1])),
        "brier_score": float(brier_score_loss(labels, probabilities)),
        "ece_15": expected_calibration_error(labels, probabilities, 15),
    }

    if len(set(labels.tolist())) == 2:
        metrics["auc"] = float(roc_auc_score(labels, probabilities))

    return metrics


def sigmoid(values):
    import numpy as np

    return 1.0 / (1.0 + np.exp(-np.clip(values, -50, 50)))


def prepare_output_directory(output_directory, overwrite):
    output_directory = Path(output_directory)

    if output_directory.exists() and not overwrite:
        raise FileExistsError(
            f"模型目录已存在，使用 --overwrite 覆盖：{output_directory}"
        )

    temporary_directory = output_directory.with_name(
        output_directory.name + ".tmp"
    )

    if temporary_directory.exists():
        shutil.rmtree(temporary_directory)

    temporary_directory.mkdir(parents=True)
    return output_directory, temporary_directory


def train_model(args):
    try:
        import lightgbm as lgb
        from sklearn.datasets import load_svmlight_file
        from sklearn.linear_model import LogisticRegression
    except ImportError as error:
        raise RuntimeError(
            '请先安装训练依赖：python3 -m pip install -e ".[train]"'
        ) from error

    dataset_directory = Path(args.dataset)
    dataset_metadata_path = dataset_directory / "metadata.json"

    if not dataset_metadata_path.is_file():
        raise FileNotFoundError(
            f"找不到训练数据元数据：{dataset_metadata_path}"
        )

    dataset_metadata = json.loads(
        dataset_metadata_path.read_text(encoding="utf-8")
    )

    if dataset_metadata.get("format") != "draft_score_v2_lightgbm_dataset":
        raise ValueError("训练数据格式不兼容")

    schema = FeatureSchema.from_dict(dataset_metadata["feature_schema"])
    paths = {
        split: dataset_directory / f"{split}.libsvm"
        for split in ("train", "validation", "test")
    }

    for split, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"找不到 {split} 数据：{path}")

    output_directory, temporary_directory = prepare_output_directory(
        args.output,
        args.overwrite,
    )
    dataset_params = {"max_bin": args.max_bin}

    try:
        train_data = lgb.Dataset(
            str(paths["train"]),
            feature_name=list(schema.feature_names),
            params=dataset_params,
        )
        validation_data = lgb.Dataset(
            str(paths["validation"]),
            reference=train_data,
            feature_name=list(schema.feature_names),
            params=dataset_params,
        )
        params = {
            "objective": "binary",
            "metric": ["binary_logloss", "auc"],
            "learning_rate": args.learning_rate,
            "num_leaves": args.num_leaves,
            "max_depth": args.max_depth,
            "min_data_in_leaf": args.min_data_in_leaf,
            "feature_fraction": args.feature_fraction,
            "bagging_fraction": args.bagging_fraction,
            "bagging_freq": 1,
            "lambda_l1": args.lambda_l1,
            "lambda_l2": args.lambda_l2,
            "max_bin": args.max_bin,
            "num_threads": args.num_threads,
            "seed": args.seed,
            "feature_fraction_seed": args.seed,
            "bagging_seed": args.seed,
            "data_random_seed": args.seed,
            "verbosity": -1,
        }
        booster = lgb.train(
            params,
            train_data,
            num_boost_round=args.num_boost_round,
            valid_sets=[validation_data],
            valid_names=["validation"],
            callbacks=[
                lgb.early_stopping(
                    args.early_stopping_rounds,
                    first_metric_only=True,
                ),
                lgb.log_evaluation(args.log_every),
            ],
        )
        best_iteration = booster.best_iteration or booster.current_iteration()
        validation_features, validation_labels = load_svmlight_file(
            paths["validation"],
            n_features=schema.num_features,
            zero_based=True,
        )
        test_features, test_labels = load_svmlight_file(
            paths["test"],
            n_features=schema.num_features,
            zero_based=True,
        )
        validation_raw = booster.predict(
            validation_features,
            raw_score=True,
            num_iteration=best_iteration,
        )
        calibrator = LogisticRegression(C=1_000_000, solver="lbfgs")
        calibrator.fit(validation_raw.reshape(-1, 1), validation_labels)
        slope = float(calibrator.coef_[0][0])
        intercept = float(calibrator.intercept_[0])
        test_raw = booster.predict(
            test_features,
            raw_score=True,
            num_iteration=best_iteration,
        )
        uncalibrated_probabilities = sigmoid(test_raw)
        calibrated_probabilities = sigmoid(slope * test_raw + intercept)
        split_importance = booster.feature_importance(
            importance_type="split",
            iteration=best_iteration,
        )
        gain_importance = booster.feature_importance(
            importance_type="gain",
            iteration=best_iteration,
        )
        top_features = sorted(
            (
                {
                    "name": feature_name,
                    "split": int(split_value),
                    "gain": float(gain_value),
                }
                for feature_name, split_value, gain_value in zip(
                    schema.feature_names,
                    split_importance,
                    gain_importance,
                )
            ),
            key=lambda item: item["gain"],
            reverse=True,
        )[:50]
        metadata = {
            "format": MODEL_FORMAT,
            "version": MODEL_VERSION,
            "model_version": "draft_score_v2_lightgbm",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "best_iteration": best_iteration,
            "feature_schema": schema.to_dict(),
            "dataset": dataset_metadata,
            "parameters": params,
            "calibration": {
                "method": "platt",
                "slope": slope,
                "intercept": intercept,
            },
            "test_metrics": {
                "uncalibrated": calculate_metrics(
                    test_labels,
                    uncalibrated_probabilities,
                ),
                "calibrated": calculate_metrics(
                    test_labels,
                    calibrated_probabilities,
                ),
            },
            "top_feature_importance": top_features,
        }
        booster.save_model(
            str(temporary_directory / "model.txt"),
            num_iteration=best_iteration,
        )
        (temporary_directory / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        if output_directory.exists():
            shutil.rmtree(output_directory)

        temporary_directory.replace(output_directory)
    except Exception:
        if temporary_directory.exists():
            shutil.rmtree(temporary_directory)
        raise

    return metadata


def main():
    parser = argparse.ArgumentParser(
        description="训练 Draft Score V2 LightGBM 模型"
    )
    parser.add_argument(
        "--dataset",
        default="data/derived/draft_score_v2_dataset",
    )
    parser.add_argument(
        "--output",
        default="models/draft_score_v2_lightgbm",
    )
    parser.add_argument("--num-boost-round", type=int, default=2000)
    parser.add_argument("--early-stopping-rounds", type=int, default=100)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--num-leaves", type=int, default=63)
    parser.add_argument("--max-depth", type=int, default=-1)
    parser.add_argument("--min-data-in-leaf", type=int, default=200)
    parser.add_argument("--feature-fraction", type=float, default=0.9)
    parser.add_argument("--bagging-fraction", type=float, default=0.9)
    parser.add_argument("--lambda-l1", type=float, default=0.1)
    parser.add_argument("--lambda-l2", type=float, default=1.0)
    parser.add_argument("--max-bin", type=int, default=63)
    parser.add_argument("--num-threads", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260828)
    parser.add_argument("--log-every", type=int, default=25)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.num_boost_round < 1 or args.early_stopping_rounds < 1:
        parser.error("训练轮数和早停轮数必须大于 0")

    metadata = train_model(args)
    print(json.dumps(metadata["test_metrics"], indent=2))
    print(f"模型已写入：{args.output}")


if __name__ == "__main__":
    main()
