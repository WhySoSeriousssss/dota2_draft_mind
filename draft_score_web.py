#!/usr/bin/env python3

import argparse
import json
import sqlite3
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from draft_score_v1 import DraftScoreV1


ROOT_DIRECTORY = Path(__file__).resolve().parent
HTML_PATH = ROOT_DIRECTORY / "draft_score_v1.html"
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


def load_hero_metadata(path):
    with open(path, "r", encoding="utf-8") as file:
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


def load_rank_segments(database_path):
    connection = sqlite3.connect(database_path)

    try:
        available = {
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT rank_segment FROM base_stats"
            )
        }
    finally:
        connection.close()

    return [rank for rank in RANK_ORDER if rank in available]


class DraftScoreRequestHandler(BaseHTTPRequestHandler):
    database_path = None
    hero_metadata = []
    rank_segments = []
    scorer_cache = {}

    def send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self):
        body = HTML_PATH.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        if path in {"/", "/draft_score_v1.html"}:
            self.send_html()
            return

        if path == "/api/config":
            self.send_json(
                200,
                {
                    "heroes": self.hero_metadata,
                    "rankSegments": self.rank_segments,
                    "defaults": {
                        "rank": "Legend",
                        "alpha": 1.0,
                        "beta": 0.5,
                        "gamma": 0.8,
                        "topK": 10,
                    },
                },
            )
            return

        self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/recommend":
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))

            if content_length <= 0 or content_length > 65536:
                raise ValueError("请求内容大小不合法")

            payload = json.loads(self.rfile.read(content_length))
            rank = str(payload.get("rank", "")).strip()
            allies = [int(hero_id) for hero_id in payload.get("allies", [])]
            enemies = [int(hero_id) for hero_id in payload.get("enemies", [])]
            alpha = float(payload.get("alpha", 1.0))
            beta = float(payload.get("beta", 1.0))
            gamma = float(payload.get("gamma", 1.0))
            top_k = int(payload.get("topK", 10))

            if top_k < 1 or top_k > 20:
                raise ValueError("Top K 必须在 1 到 20 之间")

            scorer = self.scorer_cache.get(rank.lower())

            if scorer is None:
                scorer = DraftScoreV1(self.database_path, rank)
                self.scorer_cache[scorer.rank_segment.lower()] = scorer

            results = scorer.recommend(
                allies=allies,
                enemies=enemies,
                alpha=alpha,
                beta=beta,
                gamma=gamma,
                top_k=top_k,
            )
            response_results = []

            for result in results:
                item = asdict(result)
                item["base_component"] = alpha * result.base_score
                item["counter_component"] = beta * result.counter_sum
                item["synergy_component"] = gamma * result.synergy_sum
                response_results.append(item)

            self.send_json(
                200,
                {
                    "rank": scorer.rank_segment,
                    "weights": {
                        "alpha": alpha,
                        "beta": beta,
                        "gamma": gamma,
                    },
                    "results": response_results,
                },
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"error": f"计算失败：{exc}"})

    def log_message(self, format_text, *args):
        print(f"{self.address_string()} - {format_text % args}")


def main():
    parser = argparse.ArgumentParser(description="启动 draft_score_v1 Web 页面")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--data",
        default="data/derived/draft_score_v1.sqlite3",
        help="draft_score_v1 SQLite 数据库",
    )
    parser.add_argument(
        "--heroes",
        default="metadata/heroes.json",
        help="英雄信息 JSON",
    )
    args = parser.parse_args()

    database_path = Path(args.data)
    heroes_path = Path(args.heroes)

    if not HTML_PATH.is_file():
        raise FileNotFoundError(f"找不到页面文件：{HTML_PATH}")

    if not database_path.is_file():
        raise FileNotFoundError(f"找不到评分数据库：{database_path}")

    if not heroes_path.is_file():
        raise FileNotFoundError(f"找不到英雄信息：{heroes_path}")

    DraftScoreRequestHandler.database_path = database_path
    DraftScoreRequestHandler.hero_metadata = load_hero_metadata(heroes_path)
    DraftScoreRequestHandler.rank_segments = load_rank_segments(database_path)
    server = ThreadingHTTPServer(
        (args.host, args.port),
        DraftScoreRequestHandler,
    )

    print(f"Draft Score V1: http://{args.host}:{args.port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
