import json
import shutil

import pytest

from tools.position_editor.app import (
    DEFAULT_HEROES_PATH,
    DEFAULT_POSITIONS_PATH,
    format_position_config,
    load_editor_data,
    save_position_update,
    validate_position_update,
)


def load_positions(path=DEFAULT_POSITIONS_PATH):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def test_editor_data_covers_every_hero():
    data = load_editor_data(DEFAULT_HEROES_PATH, DEFAULT_POSITIONS_PATH)

    assert len(data["heroes"]) == 127
    assert [position["key"] for position in data["positions"]] == [
        "carry",
        "mid",
        "offlane",
        "support",
    ]
    assert sum(data["counts"].values()) > len(data["heroes"])


def test_editor_formats_each_mapping_on_one_line():
    formatted = format_position_config(load_positions())

    assert '    "0": {"key": "carry", "name": "Carry"},' in formatted
    assert '    "82": [0, 1],' in formatted
    assert '"82": [\n' not in formatted


def test_editor_rejects_hero_without_position():
    update = load_positions()["heroes"]
    update["82"] = []

    with pytest.raises(ValueError, match="英雄 82 至少需要一个位置"):
        validate_position_update(
            update,
            DEFAULT_HEROES_PATH,
            DEFAULT_POSITIONS_PATH,
        )


def test_editor_saves_atomically_and_creates_backup(tmp_path):
    heroes_path = tmp_path / "heroes.json"
    positions_path = tmp_path / "hero_positions.json"
    backup_directory = tmp_path / "backups"
    shutil.copy2(DEFAULT_HEROES_PATH, heroes_path)
    shutil.copy2(DEFAULT_POSITIONS_PATH, positions_path)
    update = load_positions(positions_path)["heroes"]
    update["82"] = [1]

    result = save_position_update(
        update,
        heroes_path,
        positions_path,
        backup_directory,
    )
    saved = load_positions(positions_path)
    backups = list(backup_directory.glob("hero_positions_*.json"))

    assert result["changed"] is True
    assert saved["heroes"]["82"] == [1]
    assert len(backups) == 1
    assert load_positions(backups[0])["heroes"]["82"] == [0, 1]


def test_editor_skips_write_when_unchanged(tmp_path):
    heroes_path = tmp_path / "heroes.json"
    positions_path = tmp_path / "hero_positions.json"
    backup_directory = tmp_path / "backups"
    shutil.copy2(DEFAULT_HEROES_PATH, heroes_path)
    shutil.copy2(DEFAULT_POSITIONS_PATH, positions_path)
    update = load_positions(positions_path)["heroes"]

    result = save_position_update(
        update,
        heroes_path,
        positions_path,
        backup_directory,
    )

    assert result == {"changed": False, "backup": None}
    assert not backup_directory.exists()
