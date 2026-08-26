#!/usr/bin/env python3

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


RANK_SEGMENTS = [
    ("Herald", range(10, 16)),
    ("Guardian", range(20, 26)),
    ("Crusader", range(30, 36)),
    ("Archon", range(40, 46)),
    ("Legend", range(50, 56)),
    ("Ancient", range(60, 66)),
    ("Divine", range(70, 76)),
    ("Immortal", range(80, 81)),
]


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_heroes(path):
    """
    兼容以下几种 heroes.json 格式：

    [
        {"id": 1, "localized_name": "Anti-Mage"},
        ...
    ]

    或：

    {
        "heroes": [
            {"id": 1, "name": "Anti-Mage"}
        ]
    }

    或：

    {
        "1": {"id": 1, "localized_name": "Anti-Mage"}
    }
    """
    data = load_json(path)

    if isinstance(data, dict):
        nested_data = data.get("heroes", data.get("data"))

        if nested_data is not None:
            data = nested_data

        if isinstance(data, dict):
            data = list(data.values())

    if not isinstance(data, list):
        raise ValueError("heroes.json 应该是英雄数组或以英雄 ID 为键的对象")

    heroes = {}

    for hero in data:
        if not isinstance(hero, dict):
            continue

        hero_id = hero.get("id")

        if hero_id is None:
            continue

        hero_name = (
            hero.get("localized_name")
            or hero.get("name")
            or hero.get("localizedName")
            or str(hero_id)
        )

        heroes[int(hero_id)] = hero_name

    return heroes


def parse_team(value):
    """
    解析 radiant_team / dire_team。

    OpenDota 数据中可能出现以下格式：

    - [1, 2, 3, 4, 5]
    - "1,2,3,4,5"
    - "[1, 2, 3, 4, 5]"
    - None
    """
    if value is None:
        return []

    if isinstance(value, list):
        result = []

        for item in value:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                continue

        return result

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return []

        # 处理类似 "[1, 2, 3, 4, 5]" 的字符串
        value = value.strip("[]()")

        result = []

        for item in re.split(r"[,\s]+", value):
            item = item.strip("\"'")

            if not item:
                continue

            try:
                result.append(int(item))
            except ValueError:
                continue

        return result

    return []


def get_rank_segment(avg_rank_tier):
    if avg_rank_tier is None:
        return None

    try:
        rank_tier = int(avg_rank_tier)
    except (TypeError, ValueError):
        return None

    for segment_name, rank_values in RANK_SEGMENTS:
        if rank_tier in rank_values:
            return segment_name

    return None


def parse_radiant_win(value):
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    if isinstance(value, str):
        normalized_value = value.strip().lower()

        if normalized_value in {"true", "1", "yes"}:
            return True

        if normalized_value in {"false", "0", "no"}:
            return False

    raise ValueError(f"无法解析 radiant_win：{value!r}")


def create_stat():
    return {
        "appearances": 0,
        "wins": 0,
    }


def win_rate(stat):
    if stat["appearances"] == 0:
        return 0.0

    return stat["wins"] / stat["appearances"] * 100


def iter_with_progress(items, description, unit):
    """
    优先使用 tqdm；如果没有安装 tqdm，则使用普通进度输出。
    """
    try:
        from tqdm import tqdm

        return tqdm(items, desc=description, unit=unit)
    except ImportError:
        total = len(items)

        def generator():
            for index, item in enumerate(items, start=1):
                if index == 1 or index % 1000 == 0 or index == total:
                    print(
                        f"\r{description}: {index}/{total}",
                        end="",
                        file=sys.stderr,
                    )

                yield item

            print(file=sys.stderr)

        return generator()


def load_match_batch(path):
    matches = load_json(path)

    if isinstance(matches, dict):
        matches = matches.get("rows", matches.get("data", []))

    if not isinstance(matches, list):
        raise ValueError(
            f"比赛批次应该是数组，或者包含 rows/data 数组：{path}"
        )

    return matches


def analyze_matches(batch_paths, heroes):
    stats = defaultdict(
        lambda: {
            "total": create_stat(),
            "segments": defaultdict(create_stat),
        }
    )
    match_count = 0

    for batch_path in iter_with_progress(
        batch_paths,
        "Analyzing batches",
        "batch",
    ):
        matches = load_match_batch(batch_path)

        for match in matches:
            if not isinstance(match, dict):
                continue

            match_count += 1
            radiant_team = parse_team(match.get("radiant_team"))
            dire_team = parse_team(match.get("dire_team"))

            try:
                radiant_win = parse_radiant_win(match.get("radiant_win"))
            except ValueError:
                continue

            rank_segment = get_rank_segment(match.get("avg_rank_tier"))

            # 防止同一个英雄在异常数据中重复出现
            radiant_team = set(radiant_team)
            dire_team = set(dire_team)

            for hero_id in radiant_team:
                if hero_id not in heroes:
                    continue

                hero_stat = stats[hero_id]["total"]
                hero_stat["appearances"] += 1

                if radiant_win:
                    hero_stat["wins"] += 1

                if rank_segment is not None:
                    segment_stat = stats[hero_id]["segments"][rank_segment]
                    segment_stat["appearances"] += 1

                    if radiant_win:
                        segment_stat["wins"] += 1

            for hero_id in dire_team:
                if hero_id not in heroes:
                    continue

                hero_stat = stats[hero_id]["total"]
                hero_stat["appearances"] += 1

                if not radiant_win:
                    hero_stat["wins"] += 1

                if rank_segment is not None:
                    segment_stat = stats[hero_id]["segments"][rank_segment]
                    segment_stat["appearances"] += 1

                    if not radiant_win:
                        segment_stat["wins"] += 1

    return stats, match_count


def write_csv(path, heroes, stats):
    fieldnames = [
        "hero_id",
        "hero_name",
        "total_appearances",
        "total_win_rate",
    ]

    for segment_name, _ in RANK_SEGMENTS:
        fieldnames.append(f"{segment_name}_appearances")
        fieldnames.append(f"{segment_name}_win_rate")

    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for hero_id in sorted(heroes):
            hero_stats = stats[hero_id]
            total_stat = hero_stats["total"]

            row = {
                "hero_id": hero_id,
                "hero_name": heroes[hero_id],
                "total_appearances": total_stat["appearances"],
                "total_win_rate": f"{win_rate(total_stat):.2f}",
            }

            for segment_name, _ in RANK_SEGMENTS:
                segment_stat = hero_stats["segments"][segment_name]

                row[f"{segment_name}_appearances"] = segment_stat["appearances"]
                row[f"{segment_name}_win_rate"] = (
                    f"{win_rate(segment_stat):.2f}"
                )

            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(
        description="统计各英雄在不同天梯分段的出场次数和胜率"
    )

    parser.add_argument(
        "--matches-dir",
        "--matches",
        dest="matches_dir",
        required=True,
        help="包含 batch_*.json 的比赛批次目录",
    )

    parser.add_argument(
        "--heroes",
        default="constants/heroes.json",
        help="英雄映射 JSON 文件路径",
    )

    parser.add_argument(
        "--output",
        default="hero_rank_stats.csv",
        help="输出 CSV 文件路径",
    )

    args = parser.parse_args()

    matches_directory = Path(args.matches_dir)
    heroes_path = Path(args.heroes)

    if not matches_directory.is_dir():
        raise NotADirectoryError(f"找不到比赛批次目录：{matches_directory}")

    if not heroes_path.exists():
        raise FileNotFoundError(f"找不到英雄文件：{heroes_path}")

    batch_paths = sorted(matches_directory.glob("batch_*.json"))

    if not batch_paths:
        raise FileNotFoundError(
            f"目录中找不到 batch_*.json：{matches_directory}"
        )

    heroes = load_heroes(heroes_path)

    print(f"英雄数量：{len(heroes)}")
    print(f"批次数量：{len(batch_paths)}")

    stats, match_count = analyze_matches(batch_paths, heroes)
    write_csv(args.output, heroes, stats)

    print(f"比赛数量：{match_count}")
    print(f"统计完成，结果已写入：{args.output}")


if __name__ == "__main__":
    main()
