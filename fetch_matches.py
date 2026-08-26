#!/usr/bin/env python3
"""
获取指定日期范围内发生的所有天梯比赛。

示例：
    python fetch_matches.py \
        --after 2024-01-01 \
        --before 2024-02-01

如果 OpenDota API 需要 API Key：
    python fetch_matches.py \
        --after 2024-01-01 \
        --before 2024-02-01 \
        --api-key YOUR_API_KEY
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests


OPENDOTA_EXPLORER_URL = "https://api.opendota.com/api/explorer"


def parse_date(date_text: str) -> int:
    """
    将 YYYY-MM-DD 转换为 UTC Unix 时间戳。
    """
    try:
        date_value = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(
            f"日期格式错误：{date_text}，正确格式应为 YYYY-MM-DD"
        ) from exc

    date_value = date_value.replace(tzinfo=timezone.utc)
    return int(date_value.timestamp())


def build_output_directory(
    after_timestamp: int,
    before_timestamp: int,
    output_root: Path,
) -> Path:
    after_text = datetime.fromtimestamp(
        after_timestamp,
        tz=timezone.utc,
    ).strftime("%y%m%d")
    before_text = datetime.fromtimestamp(
        before_timestamp,
        tz=timezone.utc,
    ).strftime("%y%m%d")

    return output_root / f"ranked_matches_{after_text}_{before_text}"


def write_batch(output_directory: Path, batch_number: int, rows) -> Path:
    output_path = output_directory / f"batch_{batch_number:06d}.json"
    temporary_path = output_path.with_suffix(".json.tmp")

    with open(temporary_path, "w", encoding="utf-8") as output_file:
        json.dump(
            rows,
            output_file,
            ensure_ascii=False,
            indent=4,
        )

    temporary_path.replace(output_path)
    return output_path


def request_matches(
    session: requests.Session,
    sql: str,
    api_key: str | None = None,
    retries: int = 3,
) -> List[Dict[str, Any]]:
    """
    请求 OpenDota Explorer API，并返回 rows。
    """
    params = {"sql": sql}

    if api_key:
        params["api_key"] = api_key

    last_error = None

    for attempt in range(1, retries + 1):
        try:
            response = session.get(
                OPENDOTA_EXPLORER_URL,
                params=params,
                timeout=60,
            )
            response.raise_for_status()

            result = response.json()

            if "error" in result:
                raise RuntimeError(result["error"])

            rows = result.get("rows", [])

            if not isinstance(rows, list):
                raise RuntimeError("OpenDota 返回的数据格式不正确：rows 不是数组")

            return rows

        except (requests.RequestException, ValueError, RuntimeError) as exc:
            last_error = exc

            if attempt < retries:
                wait_seconds = attempt * 2
                print(
                    f"请求失败，第 {attempt} 次重试，"
                    f"{wait_seconds} 秒后继续：{exc}",
                    file=sys.stderr,
                )
                time.sleep(wait_seconds)

    raise RuntimeError(f"请求 OpenDota API 失败：{last_error}")


def fetch_matches(
    after_date: str,
    before_date: str,
    batch_size: int = 10000,
    api_key: str | None = None,
    limit: int | None = None,
    output_root: Path = Path("data/raw"),
) -> tuple[int, Path]:
    """
    获取指定日期范围内的全部天梯比赛。

    after_date 为包含边界，before_date 为不包含边界。

    lobby_type = 7 表示 Ranked。
    """
    after_timestamp = parse_date(after_date)
    before_timestamp = parse_date(before_date)

    if before_timestamp <= after_timestamp:
        raise ValueError("--before 必须晚于 --after")

    output_directory = build_output_directory(
        after_timestamp,
        before_timestamp,
        Path(output_root),
    )
    output_directory.mkdir(parents=True, exist_ok=True)

    if next(output_directory.glob("batch_*.json"), None) is not None:
        raise FileExistsError(
            f"输出目录已包含批次文件，请先处理现有文件：{output_directory}"
        )

    total_matches = 0
    seen_match_ids = set()
    offset = 0
    batch_number = 0

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "opendota-ranked-match-fetcher/1.0",
            "Accept": "application/json",
        }
    )

    while True:
        if limit is not None:
            if total_matches >= limit:
                print(f"已达到限制：{limit} 场比赛，停止获取。")
                break

            request_limit = min(limit - total_matches, batch_size)
        else:
            request_limit = batch_size

        sql = f"""
SELECT *
FROM public_matches
WHERE
    lobby_type = 7
    AND start_time >= {after_timestamp}
    AND start_time < {before_timestamp}
ORDER BY start_time DESC
LIMIT {request_limit}
OFFSET {offset}
"""

        print(f"正在获取第 {offset} 至 {offset + request_limit} 条记录...")
        rows = request_matches(session, sql, api_key=api_key)

        if not rows:
            break

        batch_matches = []

        for row in rows:
            match_id = row.get("match_id")

            # 避免分页过程中出现重复记录
            if match_id is not None:
                if match_id in seen_match_ids:
                    continue
                seen_match_ids.add(match_id)

            batch_matches.append(row)

        if batch_matches:
            batch_number += 1
            output_path = write_batch(
                output_directory,
                batch_number,
                batch_matches,
            )
            total_matches += len(batch_matches)
            print(
                f"已保存 {len(batch_matches)} 场到 {output_path}，"
                f"累计 {total_matches} 场"
            )

        if len(rows) < request_limit:
            break

        offset += len(rows)

    return total_matches, output_directory


def main() -> None:
    parser = argparse.ArgumentParser(
        description="获取指定日期范围内的 OpenDota 天梯比赛并保存为 JSON"
    )

    parser.add_argument(
        "--after",
        required=True,
        help="起始日期，格式为 YYYY-MM-DD，例如 2024-01-01",
    )

    parser.add_argument(
        "--before",
        required=True,
        help=(
            "截止日期（不包含当天），格式为 YYYY-MM-DD；"
            "例如 2024-02-01 表示只获取该日期之前的比赛"
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="每次请求的记录数，默认：10000",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="最多获取多少场比赛，默认获取全部比赛",
    )

    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenDota API Key，可选",
    )

    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("--batch-size 必须大于 0")

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit 必须大于 0")

    try:
        match_count, output_directory = fetch_matches(
            after_date=args.after,
            before_date=args.before,
            batch_size=args.batch_size,
            api_key=args.api_key,
            limit=args.limit,
        )

        print(f"完成：共保存 {match_count} 场比赛到 {output_directory}")

    except Exception as exc:
        print(f"执行失败：{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
