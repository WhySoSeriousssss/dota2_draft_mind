import json
from pathlib import Path

from .features import FeatureSchema


MODEL_FORMAT = "draft_score_v2_lightgbm_model"
MODEL_VERSION = 1


class ModelNotReadyError(RuntimeError):
    pass


class LightGBMDraftModel:
    def __init__(self, model_directory):
        self.model_directory = Path(model_directory)
        model_path = self.model_directory / "model.txt"
        metadata_path = self.model_directory / "metadata.json"

        if not model_path.is_file() or not metadata_path.is_file():
            raise ModelNotReadyError(
                f"Draft Score V2 模型尚未训练：{self.model_directory}"
            )

        try:
            import lightgbm as lgb
            import numpy as np
        except ImportError as error:
            raise ModelNotReadyError(
                "运行 Draft Score V2 需要安装 ML 依赖："
                'python3 -m pip install -e ".[ml]"'
            ) from error

        self._numpy = np
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        if self.metadata.get("format") != MODEL_FORMAT:
            raise ModelNotReadyError("Draft Score V2 模型格式不兼容")

        if self.metadata.get("version") != MODEL_VERSION:
            raise ModelNotReadyError("Draft Score V2 模型版本不兼容")

        self.schema = FeatureSchema.from_dict(
            self.metadata["feature_schema"]
        )
        self.booster = lgb.Booster(model_file=str(model_path))

        if self.booster.num_feature() != self.schema.num_features:
            raise ModelNotReadyError("模型特征数量与元数据不一致")

        if tuple(self.booster.feature_name()) != self.schema.feature_names:
            raise ModelNotReadyError("模型特征顺序与元数据不一致")

        calibration = self.metadata.get("calibration", {})
        self.calibration_slope = float(calibration.get("slope", 1.0))
        self.calibration_intercept = float(
            calibration.get("intercept", 0.0)
        )
        self.best_iteration = int(self.metadata.get("best_iteration") or 0)

    @property
    def model_version(self):
        return self.metadata.get("model_version", "draft_score_v2_lightgbm")

    @property
    def dataset_version(self):
        return self.metadata.get("dataset", {}).get("generated_at")

    def predict_probabilities(
        self,
        candidate_ids,
        allies,
        enemies,
        rank_segment,
        side=None,
    ):
        if not candidate_ids:
            return []

        if side not in {None, "radiant", "dire"}:
            raise ValueError(f"未知阵营：{side}")

        sides = (
            (True, False)
            if side is None
            else (side == "radiant",)
        )
        rows = [
            self.schema.encode_dense(
                candidate_id=candidate_id,
                allies=allies,
                enemies=enemies,
                rank_segment=rank_segment,
                is_radiant=is_radiant,
            )
            for candidate_id in candidate_ids
            for is_radiant in sides
        ]
        matrix = self._numpy.asarray(rows, dtype=self._numpy.float32)
        raw_scores = self.booster.predict(
            matrix,
            raw_score=True,
            num_iteration=self.best_iteration or None,
        )
        calibrated_logits = (
            self.calibration_slope * raw_scores
            + self.calibration_intercept
        )
        probabilities = 1.0 / (
            1.0 + self._numpy.exp(-self._numpy.clip(
                calibrated_logits,
                -50,
                50,
            ))
        )

        if len(sides) == 2:
            probabilities = probabilities.reshape(-1, 2).mean(axis=1)

        return [float(value) for value in probabilities]


def expected_model_files(model_directory):
    model_directory = Path(model_directory)
    return (
        model_directory / "model.txt",
        model_directory / "metadata.json",
    )


def model_files_exist(model_directory):
    return all(path.is_file() for path in expected_model_files(model_directory))
