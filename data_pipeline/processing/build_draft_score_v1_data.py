#!/usr/bin/env python3

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .match_data import (
    RANK_SEGMENTS,
    get_rank_segment,
    iter_with_progress,
    load_heroes,
    load_match_batch,
    parse_radiant_win,
    parse_team,
)


@dataclass
class SegmentStats:
    base_appearances: list
    base_wins: list
    synergy_appearances: list
    synergy_wins: list
    counter_appearances: list
    counter_wins: list

    @classmethod
    def create(cls, hero_count):
        def create_matrix():
            return [[0] * hero_count for _ in range(hero_count)]

        return cls(
            base_appearances=[0] * hero_count,
            base_wins=[0] * hero_count,
            synergy_appearances=create_matrix(),
            synergy_wins=create_matrix(),
            counter_appearances=create_matrix(),
            counter_wins=create_matrix(),
        )


def normalize_team(hero_ids, hero_indexes):
    normalized_team = []
    seen_hero_ids = set()

    for hero_id in hero_ids:
        if hero_id not in hero_indexes or hero_id in seen_hero_ids:
            continue

        seen_hero_ids.add(hero_id)
        normalized_team.append(hero_indexes[hero_id])

    return normalized_team


def update_team_stats(stats, team, won):
    for hero_index in team:
        stats.base_appearances[hero_index] += 1

        if won:
            stats.base_wins[hero_index] += 1

        for teammate_index in team:
            if teammate_index == hero_index:
                continue

            stats.synergy_appearances[hero_index][teammate_index] += 1

            if won:
                stats.synergy_wins[hero_index][teammate_index] += 1


def update_counter_stats(stats, radiant_team, dire_team, radiant_win):
    for radiant_index in radiant_team:
        for dire_index in dire_team:
            stats.counter_appearances[radiant_index][dire_index] += 1
            stats.counter_appearances[dire_index][radiant_index] += 1

            if radiant_win:
                stats.counter_wins[radiant_index][dire_index] += 1
            else:
                stats.counter_wins[dire_index][radiant_index] += 1


def calculate_stats(batch_paths, heroes):
    hero_ids = sorted(heroes)
    hero_indexes = {
        hero_id: hero_index
        for hero_index, hero_id in enumerate(hero_ids)
    }
    segment_names = [segment_name for segment_name, _ in RANK_SEGMENTS]
    segment_stats = {
        segment_name: SegmentStats.create(len(hero_ids))
        for segment_name in segment_names
    }
    total_match_count = 0
    ranked_match_count = 0
    skipped_match_count = 0

    for batch_path in iter_with_progress(
        batch_paths,
        "Building draft data",
        "batch",
    ):
        matches = load_match_batch(batch_path)

        for match in matches:
            total_match_count += 1

            if not isinstance(match, dict):
                skipped_match_count += 1
                continue

            rank_segment = get_rank_segment(match.get("avg_rank_tier"))

            if rank_segment is None:
                skipped_match_count += 1
                continue

            try:
                radiant_win = parse_radiant_win(match.get("radiant_win"))
            except ValueError:
                skipped_match_count += 1
                continue

            radiant_team = normalize_team(
                parse_team(match.get("radiant_team")),
                hero_indexes,
            )
            dire_team = normalize_team(
                parse_team(match.get("dire_team")),
                hero_indexes,
            )

            if not radiant_team or not dire_team:
                skipped_match_count += 1
                continue

            stats = segment_stats[rank_segment]
            update_team_stats(stats, radiant_team, radiant_win)
            update_team_stats(stats, dire_team, not radiant_win)
            update_counter_stats(
                stats,
                radiant_team,
                dire_team,
                radiant_win,
            )
            ranked_match_count += 1

    return {
        "hero_ids": hero_ids,
        "segment_stats": segment_stats,
        "total_match_count": total_match_count,
        "ranked_match_count": ranked_match_count,
        "skipped_match_count": skipped_match_count,
    }


def calculate_win_rate(wins, appearances):
    if appearances == 0:
        return None

    return wins / appearances


def create_database_schema(connection):
    connection.executescript(
        """
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE heroes (
            hero_id INTEGER PRIMARY KEY,
            hero_name TEXT NOT NULL
        );

        CREATE TABLE base_stats (
            rank_segment TEXT NOT NULL,
            hero_id INTEGER NOT NULL,
            appearances INTEGER NOT NULL,
            wins INTEGER NOT NULL,
            win_rate REAL,
            PRIMARY KEY (rank_segment, hero_id)
        );

        CREATE TABLE synergy_matrix (
            rank_segment TEXT NOT NULL,
            hero_id INTEGER NOT NULL,
            teammate_id INTEGER NOT NULL,
            appearances INTEGER NOT NULL,
            wins INTEGER NOT NULL,
            win_rate REAL,
            PRIMARY KEY (rank_segment, hero_id, teammate_id)
        );

        CREATE TABLE counter_matrix (
            rank_segment TEXT NOT NULL,
            hero_id INTEGER NOT NULL,
            enemy_id INTEGER NOT NULL,
            appearances INTEGER NOT NULL,
            wins INTEGER NOT NULL,
            win_rate REAL,
            PRIMARY KEY (rank_segment, hero_id, enemy_id)
        );
        """
    )


def write_database(output_path, source_directory, heroes, result, overwrite):
    output_path = Path(output_path)

    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"输出数据库已存在，使用 --overwrite 覆盖：{output_path}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")

    if temporary_path.exists():
        temporary_path.unlink()

    connection = sqlite3.connect(temporary_path)

    try:
        connection.execute("PRAGMA journal_mode = OFF")
        connection.execute("PRAGMA synchronous = OFF")
        create_database_schema(connection)

        segment_names = [segment_name for segment_name, _ in RANK_SEGMENTS]
        metadata = {
            "format": "draft_score_v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_directory": str(Path(source_directory).resolve()),
            "rank_segments": json.dumps(segment_names),
            "total_match_count": str(result["total_match_count"]),
            "ranked_match_count": str(result["ranked_match_count"]),
            "skipped_match_count": str(result["skipped_match_count"]),
        }
        connection.executemany(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            metadata.items(),
        )
        connection.executemany(
            "INSERT INTO heroes (hero_id, hero_name) VALUES (?, ?)",
            sorted(heroes.items()),
        )

        hero_ids = result["hero_ids"]

        for segment_name in segment_names:
            stats = result["segment_stats"][segment_name]
            base_rows = []
            synergy_rows = []
            counter_rows = []

            for hero_index, hero_id in enumerate(hero_ids):
                base_appearances = stats.base_appearances[hero_index]
                base_wins = stats.base_wins[hero_index]
                base_rows.append(
                    (
                        segment_name,
                        hero_id,
                        base_appearances,
                        base_wins,
                        calculate_win_rate(base_wins, base_appearances),
                    )
                )

                for other_index, other_hero_id in enumerate(hero_ids):
                    if hero_id == other_hero_id:
                        continue

                    synergy_appearances = (
                        stats.synergy_appearances[hero_index][other_index]
                    )
                    synergy_wins = stats.synergy_wins[hero_index][other_index]
                    synergy_rows.append(
                        (
                            segment_name,
                            hero_id,
                            other_hero_id,
                            synergy_appearances,
                            synergy_wins,
                            calculate_win_rate(
                                synergy_wins,
                                synergy_appearances,
                            ),
                        )
                    )

                    counter_appearances = (
                        stats.counter_appearances[hero_index][other_index]
                    )
                    counter_wins = stats.counter_wins[hero_index][other_index]
                    counter_rows.append(
                        (
                            segment_name,
                            hero_id,
                            other_hero_id,
                            counter_appearances,
                            counter_wins,
                            calculate_win_rate(
                                counter_wins,
                                counter_appearances,
                            ),
                        )
                    )

            connection.executemany(
                """
                INSERT INTO base_stats (
                    rank_segment,
                    hero_id,
                    appearances,
                    wins,
                    win_rate
                ) VALUES (?, ?, ?, ?, ?)
                """,
                base_rows,
            )
            connection.executemany(
                """
                INSERT INTO synergy_matrix (
                    rank_segment,
                    hero_id,
                    teammate_id,
                    appearances,
                    wins,
                    win_rate
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                synergy_rows,
            )
            connection.executemany(
                """
                INSERT INTO counter_matrix (
                    rank_segment,
                    hero_id,
                    enemy_id,
                    appearances,
                    wins,
                    win_rate
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                counter_rows,
            )

        connection.commit()
    except Exception:
        connection.close()

        if temporary_path.exists():
            temporary_path.unlink()

        raise
    else:
        connection.close()

    temporary_path.replace(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="构建 draft_score_v1 所需的分段胜率和组合矩阵"
    )
    parser.add_argument(
        "--matches-dir",
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
        default="data/derived/draft_score_v1.sqlite3",
        help="输出 SQLite 数据库路径",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="覆盖已存在的输出数据库",
    )
    args = parser.parse_args()

    matches_directory = Path(args.matches_dir)
    heroes_path = Path(args.heroes)

    if not matches_directory.is_dir():
        raise NotADirectoryError(f"找不到比赛批次目录：{matches_directory}")

    if not heroes_path.is_file():
        raise FileNotFoundError(f"找不到英雄文件：{heroes_path}")

    batch_paths = sorted(matches_directory.glob("batch_*.json"))

    if not batch_paths:
        raise FileNotFoundError(
            f"目录中找不到 batch_*.json：{matches_directory}"
        )

    heroes = load_heroes(heroes_path)
    print(f"英雄数量：{len(heroes)}")
    print(f"批次数量：{len(batch_paths)}")

    result = calculate_stats(batch_paths, heroes)
    write_database(
        args.output,
        matches_directory,
        heroes,
        result,
        args.overwrite,
    )

    print(f"比赛记录：{result['total_match_count']}")
    print(f"有效分段比赛：{result['ranked_match_count']}")
    print(f"跳过比赛：{result['skipped_match_count']}")
    print(f"基础数据已写入：{args.output}")


if __name__ == "__main__":
    main()
