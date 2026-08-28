import json
import re
import sys


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
        if not isinstance(hero, dict) or hero.get("id") is None:
            continue

        hero_id = int(hero["id"])
        heroes[hero_id] = (
            hero.get("localized_name")
            or hero.get("name")
            or hero.get("localizedName")
            or str(hero_id)
        )

    return heroes


def parse_team(value):
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
        result = []

        for item in re.split(r"[,\s]+", value.strip().strip("[]()")):
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


def iter_with_progress(items, description, unit):
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
