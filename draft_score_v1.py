#!/usr/bin/env python3

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScoreResult:
    hero_id: int
    hero_name: str
    score: float
    base_score: float
    counter_sum: float
    synergy_sum: float
    base_appearances: int


class DraftScoreV1:
    def __init__(self, database_path, rank_segment):
        self.database_path = Path(database_path)

        if not self.database_path.is_file():
            raise FileNotFoundError(f"找不到基础数据：{self.database_path}")

        connection = sqlite3.connect(self.database_path)

        try:
            self.heroes = dict(
                connection.execute(
                    "SELECT hero_id, hero_name FROM heroes ORDER BY hero_id"
                )
            )
            available_segments = [
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT rank_segment FROM base_stats"
                )
            ]
            segment_lookup = {
                segment_name.lower(): segment_name
                for segment_name in available_segments
            }
            normalized_segment = rank_segment.strip().lower()

            if normalized_segment not in segment_lookup:
                available_text = ", ".join(sorted(available_segments))
                raise ValueError(
                    f"未知分段：{rank_segment}；可选分段：{available_text}"
                )

            self.rank_segment = segment_lookup[normalized_segment]
            self.base_stats = {
                hero_id: {
                    "appearances": appearances,
                    "win_rate": win_rate,
                }
                for hero_id, appearances, win_rate in connection.execute(
                    """
                    SELECT hero_id, appearances, win_rate
                    FROM base_stats
                    WHERE rank_segment = ?
                    """,
                    (self.rank_segment,),
                )
            }
            self.synergy_matrix = {
                (hero_id, teammate_id): (appearances, win_rate)
                for hero_id, teammate_id, appearances, win_rate
                in connection.execute(
                    """
                    SELECT hero_id, teammate_id, appearances, win_rate
                    FROM synergy_matrix
                    WHERE rank_segment = ? AND appearances > 0
                    """,
                    (self.rank_segment,),
                )
            }
            self.counter_matrix = {
                (hero_id, enemy_id): (appearances, win_rate)
                for hero_id, enemy_id, appearances, win_rate
                in connection.execute(
                    """
                    SELECT hero_id, enemy_id, appearances, win_rate
                    FROM counter_matrix
                    WHERE rank_segment = ? AND appearances > 0
                    """,
                    (self.rank_segment,),
                )
            }
        finally:
            connection.close()

    def validate_picks(self, allies, enemies, candidate_id=None):
        all_ids = allies + enemies

        if len(set(allies)) != len(allies):
            raise ValueError("我方英雄 ID 不能重复")

        if len(set(enemies)) != len(enemies):
            raise ValueError("敌方英雄 ID 不能重复")

        if set(allies) & set(enemies):
            raise ValueError("同一个英雄不能同时出现在双方阵容中")

        if len(allies) > 4:
            raise ValueError("推荐候选英雄时，我方已选英雄不能超过 4 个")

        if len(enemies) > 5:
            raise ValueError("敌方已选英雄不能超过 5 个")

        for hero_id in all_ids:
            if hero_id not in self.heroes:
                raise ValueError(f"未知英雄 ID：{hero_id}")

        if candidate_id is not None:
            if candidate_id not in self.heroes:
                raise ValueError(f"未知英雄 ID：{candidate_id}")

            if candidate_id in all_ids:
                raise ValueError(f"候选英雄已经被选择：{candidate_id}")

    @staticmethod
    def calculate_pair_sum(matrix, hero_id, other_ids, base_score):
        pair_sum = 0.0

        for other_id in other_ids:
            pair_stat = matrix.get((hero_id, other_id))

            if pair_stat is None:
                continue

            _, pair_win_rate = pair_stat

            if pair_win_rate is not None:
                pair_sum += pair_win_rate - base_score

        return pair_sum

    def score_hero(
        self,
        hero_id,
        allies,
        enemies,
        alpha,
        beta,
        gamma,
    ):
        self.validate_picks(allies, enemies, candidate_id=hero_id)
        base_stat = self.base_stats.get(hero_id)

        if not base_stat or base_stat["win_rate"] is None:
            raise ValueError(
                f"英雄 {hero_id} 在 {self.rank_segment} 分段没有基础数据"
            )

        base_score = base_stat["win_rate"]
        counter_sum = self.calculate_pair_sum(
            self.counter_matrix,
            hero_id,
            enemies,
            base_score,
        )
        synergy_sum = self.calculate_pair_sum(
            self.synergy_matrix,
            hero_id,
            allies,
            base_score,
        )
        score = (
            alpha * base_score
            + beta * counter_sum
            + gamma * synergy_sum
        )

        return ScoreResult(
            hero_id=hero_id,
            hero_name=self.heroes[hero_id],
            score=score,
            base_score=base_score,
            counter_sum=counter_sum,
            synergy_sum=synergy_sum,
            base_appearances=base_stat["appearances"],
        )

    def recommend(
        self,
        allies,
        enemies,
        alpha,
        beta,
        gamma,
        top_k,
    ):
        self.validate_picks(allies, enemies)
        picked_hero_ids = set(allies) | set(enemies)
        results = []

        for hero_id in self.heroes:
            if hero_id in picked_hero_ids:
                continue

            base_stat = self.base_stats.get(hero_id)

            if not base_stat or base_stat["win_rate"] is None:
                continue

            results.append(
                self.score_hero(
                    hero_id,
                    allies,
                    enemies,
                    alpha,
                    beta,
                    gamma,
                )
            )

        results.sort(
            key=lambda result: (
                result.score,
                result.base_appearances,
                -result.hero_id,
            ),
            reverse=True,
        )
        return results[:top_k]


def print_results(results, rank_segment, alpha, beta, gamma):
    print(f"Rank: {rank_segment}")
    print(f"Weights: alpha={alpha}, beta={beta}, gamma={gamma}")
    print(
        f"{'#':>3}  {'ID':>4}  {'Hero':<24}  {'Score':>9}  "
        f"{'Base':>9}  {'Counter':>9}  {'Synergy':>9}  {'Games':>8}"
    )

    for index, result in enumerate(results, start=1):
        print(
            f"{index:>3}  {result.hero_id:>4}  "
            f"{result.hero_name:<24.24}  "
            f"{result.score:>9.5f}  "
            f"{result.base_score:>9.5f}  "
            f"{result.counter_sum:>9.5f}  "
            f"{result.synergy_sum:>9.5f}  "
            f"{result.base_appearances:>8}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="根据 draft_score_v1 公式推荐未选择英雄"
    )
    parser.add_argument(
        "--data",
        default="data/derived/draft_score_v1.sqlite3",
        help="第一阶段生成的 SQLite 数据库",
    )
    parser.add_argument(
        "--rank",
        required=True,
        help="分段，例如 Herald、Guardian、Archon、Immortal",
    )
    parser.add_argument(
        "--hero-id",
        type=int,
        default=None,
        help="只计算指定英雄；不指定时输出推荐 Top K",
    )
    parser.add_argument(
        "--allies",
        nargs="*",
        type=int,
        default=[],
        help="我方已经选择的英雄 ID",
    )
    parser.add_argument(
        "--enemies",
        nargs="*",
        type=int,
        default=[],
        help="敌方已经选择的英雄 ID",
    )
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--beta", type=float, default=1.0)
    parser.add_argument("--gamma", type=float, default=1.0)
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    if args.top_k <= 0:
        parser.error("--top-k 必须大于 0")

    scorer = DraftScoreV1(args.data, args.rank)

    if args.hero_id is not None:
        results = [
            scorer.score_hero(
                args.hero_id,
                args.allies,
                args.enemies,
                args.alpha,
                args.beta,
                args.gamma,
            )
        ]
    else:
        results = scorer.recommend(
            args.allies,
            args.enemies,
            args.alpha,
            args.beta,
            args.gamma,
            args.top_k,
        )

    print_results(
        results,
        scorer.rank_segment,
        args.alpha,
        args.beta,
        args.gamma,
    )


if __name__ == "__main__":
    main()
