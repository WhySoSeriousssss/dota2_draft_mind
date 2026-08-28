#!/usr/bin/env python3

import argparse
import hashlib
import json
import random
import shutil
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

from algorithms.v2.features import FeatureSchema, format_libsvm_row
from .match_data import (
    RANK_SEGMENTS,
    get_rank_segment,
    iter_with_progress,
    load_heroes,
    load_match_batch,
    parse_radiant_win,
    parse_team,
)


SPLIT_NAMES = ("train", "validation", "test")


def parse_utc_timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return int(parsed.timestamp())


def select_time_split(start_time, validation_start, test_start):
    if start_time >= test_start:
        return "test"

    if start_time >= validation_start:
        return "validation"

    return "train"


def select_random_split(match_id, seed, validation_ratio, test_ratio):
    digest = hashlib.blake2b(
        f"{seed}:{match_id}".encode("utf-8"),
        digest_size=8,
    ).digest()
    fraction = int.from_bytes(digest, "big") / 2**64

    if fraction < test_ratio:
        return "test"

    if fraction < test_ratio + validation_ratio:
        return "validation"

    return "train"


def normalize_full_team(value, valid_hero_ids):
    team = parse_team(value)

    if (
        len(team) != 5
        or len(set(team)) != 5
        or any(hero_id not in valid_hero_ids for hero_id in team)
    ):
        return None

    return team


def create_masked_example(
    schema,
    match_id,
    seed,
    repeat_index,
    side,
    team,
    opponents,
    rank_segment,
    won,
):
    randomizer = random.Random(
        f"{seed}:{match_id}:{repeat_index}:{side}"
    )
    candidate_id = randomizer.choice(team)
    available_allies = [
        hero_id for hero_id in team if hero_id != candidate_id
    ]
    ally_count = randomizer.randint(0, len(available_allies))
    enemy_count = randomizer.randint(0, len(opponents))
    allies = sorted(randomizer.sample(available_allies, ally_count))
    enemies = sorted(randomizer.sample(opponents, enemy_count))
    features = schema.encode_sparse(
        candidate_id=candidate_id,
        allies=allies,
        enemies=enemies,
        rank_segment=rank_segment,
        is_radiant=side == "radiant",
    )
    return format_libsvm_row(won, features)


def prepare_output_directory(output_directory, overwrite):
    output_directory = Path(output_directory)

    if output_directory.exists() and not overwrite:
        raise FileExistsError(
            f"输出目录已存在，使用 --overwrite 覆盖：{output_directory}"
        )

    temporary_directory = output_directory.with_name(
        output_directory.name + ".tmp"
    )

    if temporary_directory.exists():
        shutil.rmtree(temporary_directory)

    temporary_directory.mkdir(parents=True)
    return output_directory, temporary_directory


def build_dataset(
    batch_paths,
    heroes,
    output_directory,
    validation_start=None,
    test_start=None,
    samples_per_side=1,
    seed=20260828,
    overwrite=False,
    max_matches=None,
    split_strategy="random",
    validation_ratio=0.1,
    test_ratio=0.1,
):
    if split_strategy not in {"random", "time"}:
        raise ValueError(f"未知切分策略：{split_strategy}")

    if split_strategy == "time":
        if validation_start is None or test_start is None:
            raise ValueError("时间切分必须指定 validation_start 和 test_start")

        if validation_start >= test_start:
            raise ValueError("validation_start 必须早于 test_start")
    elif (
        validation_ratio <= 0
        or test_ratio <= 0
        or validation_ratio + test_ratio >= 1
    ):
        raise ValueError(
            "validation_ratio 和 test_ratio 必须大于 0，且总和小于 1"
        )

    if samples_per_side < 1:
        raise ValueError("samples_per_side 必须大于 0")

    output_directory, temporary_directory = prepare_output_directory(
        output_directory,
        overwrite,
    )
    rank_segments = tuple(name for name, _values in RANK_SEGMENTS)
    schema = FeatureSchema(tuple(sorted(heroes)), rank_segments)
    valid_hero_ids = set(schema.hero_ids)
    counts = {
        split: {"matches": 0, "samples": 0, "positive_samples": 0}
        for split in SPLIT_NAMES
    }
    scanned_matches = 0
    accepted_matches = 0
    skipped_matches = 0

    try:
        with ExitStack() as stack:
            outputs = {
                split: stack.enter_context(
                    (temporary_directory / f"{split}.libsvm").open(
                        "w",
                        encoding="utf-8",
                    )
                )
                for split in SPLIT_NAMES
            }

            for batch_path in iter_with_progress(
                batch_paths,
                "Building V2 dataset",
                "batch",
            ):
                for match in load_match_batch(batch_path):
                    scanned_matches += 1

                    if not isinstance(match, dict):
                        skipped_matches += 1
                        continue

                    rank_segment = get_rank_segment(
                        match.get("avg_rank_tier")
                    )
                    radiant_team = normalize_full_team(
                        match.get("radiant_team"),
                        valid_hero_ids,
                    )
                    dire_team = normalize_full_team(
                        match.get("dire_team"),
                        valid_hero_ids,
                    )

                    try:
                        radiant_win = parse_radiant_win(
                            match.get("radiant_win")
                        )
                    except ValueError:
                        skipped_matches += 1
                        continue

                    if (
                        rank_segment is None
                        or radiant_team is None
                        or dire_team is None
                        or set(radiant_team) & set(dire_team)
                    ):
                        skipped_matches += 1
                        continue

                    match_id = match.get("match_id", scanned_matches)

                    if split_strategy == "time":
                        try:
                            start_time = int(match.get("start_time"))
                        except (TypeError, ValueError):
                            skipped_matches += 1
                            continue

                        split = select_time_split(
                            start_time,
                            validation_start,
                            test_start,
                        )
                    else:
                        split = select_random_split(
                            match_id,
                            seed,
                            validation_ratio,
                            test_ratio,
                        )

                    for repeat_index in range(samples_per_side):
                        radiant_row = create_masked_example(
                            schema,
                            match_id,
                            seed,
                            repeat_index,
                            "radiant",
                            radiant_team,
                            dire_team,
                            rank_segment,
                            radiant_win,
                        )
                        dire_row = create_masked_example(
                            schema,
                            match_id,
                            seed,
                            repeat_index,
                            "dire",
                            dire_team,
                            radiant_team,
                            rank_segment,
                            not radiant_win,
                        )
                        outputs[split].write(radiant_row)
                        outputs[split].write(dire_row)
                        counts[split]["samples"] += 2
                        counts[split]["positive_samples"] += 1

                    counts[split]["matches"] += 1
                    accepted_matches += 1

                    if max_matches and accepted_matches >= max_matches:
                        break

                if max_matches and accepted_matches >= max_matches:
                    break

        empty_splits = [
            split for split in SPLIT_NAMES if counts[split]["samples"] == 0
        ]

        if empty_splits:
            raise ValueError(
                "以下数据集为空，请检查切分参数或增加比赛数量："
                + ", ".join(empty_splits)
            )

        split_config = (
            {
                "validation_start": datetime.fromtimestamp(
                    validation_start,
                    timezone.utc,
                ).isoformat(),
                "test_start": datetime.fromtimestamp(
                    test_start,
                    timezone.utc,
                ).isoformat(),
            }
            if split_strategy == "time"
            else {
                "train_ratio": 1 - validation_ratio - test_ratio,
                "validation_ratio": validation_ratio,
                "test_ratio": test_ratio,
            }
        )
        metadata = {
            "format": "draft_score_v2_lightgbm_dataset",
            "version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "split_strategy": split_strategy,
            "split_config": split_config,
            "samples_per_side": samples_per_side,
            "seed": seed,
            "scanned_matches": scanned_matches,
            "accepted_matches": accepted_matches,
            "skipped_matches": skipped_matches,
            "splits": counts,
            "feature_schema": schema.to_dict(),
        }
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
        description="构建 Draft Score V2 LightGBM 训练数据"
    )
    parser.add_argument(
        "--matches-dir",
        required=True,
        help="包含 batch_*.json 的比赛批次目录",
    )
    parser.add_argument(
        "--heroes",
        default="metadata/heroes.json",
        help="英雄元数据 JSON",
    )
    parser.add_argument(
        "--output",
        default="data/derived/draft_score_v2_dataset",
        help="输出数据集目录",
    )
    parser.add_argument(
        "--split-strategy",
        choices=("random", "time"),
        default="random",
        help="切分方式，默认按 match_id 确定性随机切分",
    )
    parser.add_argument(
        "--validation-start",
        help="时间切分时的验证集开始时间，UTC ISO 日期或时间",
    )
    parser.add_argument(
        "--test-start",
        help="时间切分时的测试集开始时间，UTC ISO 日期或时间",
    )
    parser.add_argument("--validation-ratio", type=float, default=0.1)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument("--samples-per-side", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260828)
    parser.add_argument("--max-matches", type=int)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    matches_directory = Path(args.matches_dir)
    batch_paths = sorted(matches_directory.glob("batch_*.json"))

    if not matches_directory.is_dir():
        raise NotADirectoryError(f"找不到比赛批次目录：{matches_directory}")

    if not batch_paths:
        raise FileNotFoundError(
            f"目录中找不到 batch_*.json：{matches_directory}"
        )

    if args.split_strategy == "time" and (
        not args.validation_start or not args.test_start
    ):
        parser.error(
            "--split-strategy time 必须同时指定 "
            "--validation-start 和 --test-start"
        )

    heroes = load_heroes(args.heroes)
    metadata = build_dataset(
        batch_paths=batch_paths,
        heroes=heroes,
        output_directory=args.output,
        validation_start=(
            parse_utc_timestamp(args.validation_start)
            if args.validation_start
            else None
        ),
        test_start=(
            parse_utc_timestamp(args.test_start)
            if args.test_start
            else None
        ),
        samples_per_side=args.samples_per_side,
        seed=args.seed,
        overwrite=args.overwrite,
        max_matches=args.max_matches,
        split_strategy=args.split_strategy,
        validation_ratio=args.validation_ratio,
        test_ratio=args.test_ratio,
    )
    print(json.dumps(metadata["splits"], ensure_ascii=False, indent=2))
    print(f"训练数据已写入：{args.output}")


if __name__ == "__main__":
    main()
