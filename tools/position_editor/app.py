#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HEROES_PATH = PROJECT_ROOT / "metadata/heroes.json"
DEFAULT_POSITIONS_PATH = PROJECT_ROOT / "metadata/hero_positions.json"
FRONTEND_DIRECTORY = Path(__file__).resolve().parent / "frontend"
IMAGE_CDN = "https://cdn.cloudflare.steamstatic.com"


class PositionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heroes: dict[str, list[int]]


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def format_position_config(config):
    lines = ["{", '  "positions": {']
    position_items = list(config["positions"].items())

    for index, (position_id, position) in enumerate(position_items):
        comma = "," if index < len(position_items) - 1 else ""
        value = json.dumps(position, ensure_ascii=False, separators=(", ", ": "))
        lines.append(f'    {json.dumps(position_id)}: {value}{comma}')

    lines.extend(['  },', '  "heroes": {'])
    hero_items = list(config["heroes"].items())

    for index, (hero_id, position_ids) in enumerate(hero_items):
        comma = "," if index < len(hero_items) - 1 else ""
        value = json.dumps(position_ids, ensure_ascii=False, separators=(", ", ": "))
        lines.append(f'    {json.dumps(hero_id)}: {value}{comma}')

    lines.extend(["  }", "}"])
    return "\n".join(lines) + "\n"


def load_editor_data(heroes_path, positions_path):
    raw_heroes = load_json(heroes_path)
    raw_positions = load_json(positions_path)
    heroes = raw_heroes.values() if isinstance(raw_heroes, dict) else raw_heroes
    hero_positions = raw_positions["heroes"]
    editor_heroes = []

    for hero in heroes:
        hero_id = str(hero["id"])
        image_path = hero.get("img") or ""
        editor_heroes.append(
            {
                "id": int(hero_id),
                "name": hero.get("localized_name") or hero.get("name"),
                "attribute": hero.get("primary_attr") or "unknown",
                "image": f"{IMAGE_CDN}{image_path}" if image_path else "",
                "position_ids": hero_positions.get(hero_id, []),
            }
        )

    editor_heroes.sort(key=lambda hero: hero["name"])
    positions = [
        {
            "id": int(position_id),
            **position,
        }
        for position_id, position in raw_positions["positions"].items()
    ]
    positions.sort(key=lambda position: position["id"])
    return {
        "positions": positions,
        "heroes": editor_heroes,
        "counts": count_positions(editor_heroes, positions),
    }


def count_positions(heroes, positions):
    return {
        str(position["id"]): sum(
            position["id"] in hero["position_ids"]
            for hero in heroes
        )
        for position in positions
    }


def validate_position_update(update, heroes_path, positions_path):
    raw_heroes = load_json(heroes_path)
    raw_positions = load_json(positions_path)
    known_hero_ids = {
        str(hero["id"])
        for hero in (
            raw_heroes.values()
            if isinstance(raw_heroes, dict)
            else raw_heroes
        )
    }
    submitted_hero_ids = set(update)
    known_position_ids = {
        int(position_id)
        for position_id in raw_positions["positions"]
    }

    if submitted_hero_ids != known_hero_ids:
        missing = sorted(known_hero_ids - submitted_hero_ids, key=int)
        unknown = sorted(submitted_hero_ids - known_hero_ids, key=int)
        raise ValueError(
            f"英雄集合不完整：缺失 {missing}；未知 {unknown}"
        )

    normalized = {}

    for hero_id in sorted(known_hero_ids, key=int):
        position_ids = list(dict.fromkeys(update[hero_id]))
        invalid = set(position_ids) - known_position_ids

        if not position_ids:
            raise ValueError(f"英雄 {hero_id} 至少需要一个位置")

        if invalid:
            raise ValueError(
                f"英雄 {hero_id} 包含未知位置：{sorted(invalid)}"
            )

        normalized[hero_id] = sorted(position_ids)

    return raw_positions, normalized


def save_position_update(update, heroes_path, positions_path, backup_directory):
    positions_path = Path(positions_path)
    backup_directory = Path(backup_directory)
    raw_positions, normalized = validate_position_update(
        update,
        heroes_path,
        positions_path,
    )

    if raw_positions["heroes"] == normalized:
        return {"changed": False, "backup": None}

    backup_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = backup_directory / f"hero_positions_{timestamp}.json"
    shutil.copy2(positions_path, backup_path)
    updated_config = {
        "positions": raw_positions["positions"],
        "heroes": normalized,
    }
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=positions_path.parent,
            prefix=".hero_positions_",
            suffix=".json.tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(format_position_config(updated_config))
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)

        os.replace(temporary_path, positions_path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()

    try:
        reported_backup_path = backup_path.relative_to(PROJECT_ROOT)
    except ValueError:
        reported_backup_path = backup_path

    return {
        "changed": True,
        "backup": str(reported_backup_path),
    }


def create_app(
    heroes_path=DEFAULT_HEROES_PATH,
    positions_path=DEFAULT_POSITIONS_PATH,
    backup_directory=None,
):
    heroes_path = Path(heroes_path)
    positions_path = Path(positions_path)
    backup_directory = Path(
        backup_directory
        or positions_path.parent / "backups"
    )
    app = FastAPI(
        title="Hero Position Debug Tool",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.mount(
        "/static",
        StaticFiles(directory=FRONTEND_DIRECTORY / "static"),
        name="static",
    )

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(FRONTEND_DIRECTORY / "index.html")

    @app.get("/api/data")
    async def get_data():
        return load_editor_data(heroes_path, positions_path)

    @app.put("/api/data")
    async def save_data(payload: PositionUpdate):
        try:
            result = save_position_update(
                payload.heroes,
                heroes_path,
                positions_path,
                backup_directory,
            )
        except ValueError as error:
            return JSONResponse(
                status_code=400,
                content={"error": str(error)},
            )

        return {
            **result,
            **load_editor_data(heroes_path, positions_path),
        }

    return app


def main():
    parser = argparse.ArgumentParser(
        description="本地审核和编辑 hero_positions.json",
    )
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--heroes", type=Path, default=DEFAULT_HEROES_PATH)
    parser.add_argument(
        "--positions",
        type=Path,
        default=DEFAULT_POSITIONS_PATH,
    )
    arguments = parser.parse_args()
    app = create_app(arguments.heroes, arguments.positions)
    uvicorn.run(app, host="127.0.0.1", port=arguments.port)


if __name__ == "__main__":
    main()
