import json
import sqlite3
from pathlib import Path


IMAGE_CDN = "https://cdn.cloudflare.steamstatic.com"
RANK_ORDER = [
    "Herald",
    "Guardian",
    "Crusader",
    "Archon",
    "Legend",
    "Ancient",
    "Divine",
    "Immortal",
]


class DraftRepository:
    def __init__(
        self,
        database_path: Path,
        heroes_path: Path,
        hero_positions_path: Path,
    ):
        self.database_path = Path(database_path)
        self.heroes_path = Path(heroes_path)
        self.hero_positions_path = Path(hero_positions_path)
        self._heroes = self._load_heroes()
        (
            self._positions,
            self._hero_positions,
            self._position_heroes,
        ) = self._load_hero_positions()
        self._rank_segments, self._metadata = self._load_database_info()

    @property
    def heroes(self):
        return self._heroes

    @property
    def rank_segments(self):
        return self._rank_segments

    @property
    def positions(self):
        return self._positions

    @property
    def hero_positions(self):
        return self._hero_positions

    @property
    def position_heroes(self):
        return self._position_heroes

    @property
    def dataset_version(self):
        return self._metadata.get("generated_at")

    def get_leaderboard_data(self, rank_segment):
        normalized_rank = rank_segment.strip().lower()

        if normalized_rank == "all":
            selected_rank = "All"
        else:
            rank_lookup = {
                rank.lower(): rank for rank in self.rank_segments
            }

            if normalized_rank not in rank_lookup:
                available = ", ".join(["All", *self.rank_segments])
                raise ValueError(
                    f"未知分段：{rank_segment}；可选分段：{available}"
                )

            selected_rank = rank_lookup[normalized_rank]

        connection = sqlite3.connect(self.database_path)

        try:
            if selected_rank == "All":
                base_rows = connection.execute(
                    """
                    SELECT hero_id, SUM(appearances), SUM(wins)
                    FROM base_stats
                    GROUP BY hero_id
                    """
                ).fetchall()
                matchup_rows = connection.execute(
                    """
                    SELECT hero_id, enemy_id,
                           SUM(appearances), SUM(wins)
                    FROM counter_matrix
                    GROUP BY hero_id, enemy_id
                    """
                ).fetchall()
            else:
                base_rows = connection.execute(
                    """
                    SELECT hero_id, appearances, wins
                    FROM base_stats
                    WHERE rank_segment = ?
                    """,
                    (selected_rank,),
                ).fetchall()
                matchup_rows = connection.execute(
                    """
                    SELECT hero_id, enemy_id, appearances, wins
                    FROM counter_matrix
                    WHERE rank_segment = ?
                    """,
                    (selected_rank,),
                ).fetchall()
        finally:
            connection.close()

        total_hero_picks = sum(row[1] for row in base_rows)
        return {
            "rank": selected_rank,
            "total_matches": total_hero_picks // 10,
            "base_rows": base_rows,
            "matchup_rows": matchup_rows,
        }

    def _load_heroes(self):
        with self.heroes_path.open("r", encoding="utf-8") as file:
            raw_heroes = json.load(file)

        if isinstance(raw_heroes, dict):
            raw_heroes = raw_heroes.values()

        heroes = []

        for hero in raw_heroes:
            if not isinstance(hero, dict) or hero.get("id") is None:
                continue

            image_path = hero.get("img") or ""
            icon_path = hero.get("icon") or image_path
            heroes.append(
                {
                    "id": int(hero["id"]),
                    "name": (
                        hero.get("localized_name")
                        or hero.get("name")
                        or str(hero["id"])
                    ),
                    "attribute": hero.get("primary_attr") or "unknown",
                    "roles": hero.get("roles") or [],
                    "image": f"{IMAGE_CDN}{image_path}" if image_path else "",
                    "icon": f"{IMAGE_CDN}{icon_path}" if icon_path else "",
                }
            )

        return sorted(heroes, key=lambda hero: hero["name"])

    def _load_hero_positions(self):
        with self.hero_positions_path.open("r", encoding="utf-8") as file:
            raw_config = json.load(file)

        positions = [
            {
                "id": int(position_id),
                "key": position["key"],
                "name": position["name"],
            }
            for position_id, position in raw_config["positions"].items()
        ]
        positions.sort(key=lambda position: position["id"])
        position_ids = {position["id"] for position in positions}
        hero_ids = {hero["id"] for hero in self.heroes}
        hero_positions = {
            int(hero_id): list(dict.fromkeys(position_values))
            for hero_id, position_values in raw_config["heroes"].items()
        }
        configured_hero_ids = set(hero_positions)

        if configured_hero_ids != hero_ids:
            missing = sorted(hero_ids - configured_hero_ids)
            unknown = sorted(configured_hero_ids - hero_ids)
            raise ValueError(
                "英雄位置配置与英雄元数据不一致："
                f"缺失 {missing}；未知 {unknown}"
            )

        for hero_id, configured_positions in hero_positions.items():
            invalid_positions = set(configured_positions) - position_ids

            if not configured_positions or invalid_positions:
                raise ValueError(
                    f"英雄 {hero_id} 的位置配置无效：{configured_positions}"
                )

        position_heroes = {
            position_id: [
                hero_id
                for hero_id, configured_positions in hero_positions.items()
                if position_id in configured_positions
            ]
            for position_id in position_ids
        }
        return positions, hero_positions, position_heroes

    def _load_database_info(self):
        connection = sqlite3.connect(self.database_path)

        try:
            available_segments = {
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT rank_segment FROM base_stats"
                )
            }
            metadata = dict(
                connection.execute("SELECT key, value FROM metadata")
            )
        finally:
            connection.close()

        rank_segments = [
            rank for rank in RANK_ORDER if rank in available_segments
        ]
        return rank_segments, metadata
