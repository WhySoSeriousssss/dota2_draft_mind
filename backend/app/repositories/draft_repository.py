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
    def __init__(self, database_path: Path, heroes_path: Path):
        self.database_path = Path(database_path)
        self.heroes_path = Path(heroes_path)
        self._heroes = self._load_heroes()
        self._rank_segments, self._metadata = self._load_database_info()

    @property
    def heroes(self):
        return self._heroes

    @property
    def rank_segments(self):
        return self._rank_segments

    @property
    def dataset_version(self):
        return self._metadata.get("generated_at")

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
