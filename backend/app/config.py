import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_path: Path
    heroes_path: Path
    hero_positions_path: Path
    frontend_directory: Path

    @classmethod
    def from_environment(cls):
        return cls(
            database_path=Path(
                os.getenv(
                    "DRAFT_DATABASE_PATH",
                    PROJECT_ROOT / "data/derived/draft_score_v1.sqlite3",
                )
            ),
            heroes_path=Path(
                os.getenv(
                    "DRAFT_HEROES_PATH",
                    PROJECT_ROOT / "metadata/heroes.json",
                )
            ),
            hero_positions_path=Path(
                os.getenv(
                    "DRAFT_HERO_POSITIONS_PATH",
                    PROJECT_ROOT / "metadata/hero_positions.json",
                )
            ),
            frontend_directory=Path(
                os.getenv(
                    "DRAFT_FRONTEND_PATH",
                    PROJECT_ROOT / "frontend/dist",
                )
            ),
        )

    def validate(self):
        required_paths = {
            "评分数据库": self.database_path,
            "英雄元数据": self.heroes_path,
            "英雄位置配置": self.hero_positions_path,
            "前端目录": self.frontend_directory,
            "前端入口": self.frontend_directory / "index.html",
            "前端静态资源": self.frontend_directory / "assets",
        }

        for label, path in required_paths.items():
            if not path.exists():
                raise FileNotFoundError(f"找不到{label}：{path}")
