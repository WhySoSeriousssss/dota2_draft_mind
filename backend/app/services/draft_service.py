from dataclasses import asdict
from threading import Lock

from draft_score_v1 import DraftScoreV1

from ..repositories.draft_repository import DraftRepository
from ..schemas import (
    AppConfigResponse,
    ConfigDefaults,
    DraftRecommendationRequest,
    DraftRecommendationResponse,
    DraftWeights,
    HealthResponse,
    RecommendationResult,
)


class DraftService:
    def __init__(self, repository: DraftRepository):
        self.repository = repository
        self._scorer_cache = {}
        self._cache_lock = Lock()

    def get_config(self):
        default_rank = (
            "Legend"
            if "Legend" in self.repository.rank_segments
            else self.repository.rank_segments[0]
        )
        return AppConfigResponse(
            heroes=self.repository.heroes,
            rank_segments=self.repository.rank_segments,
            defaults=ConfigDefaults(
                rank=default_rank,
                weights=DraftWeights(),
                top_k=10,
            ),
            dataset_version=self.repository.dataset_version,
        )

    def health(self):
        return HealthResponse(
            status="ok",
            heroes=len(self.repository.heroes),
            rank_segments=len(self.repository.rank_segments),
        )

    def recommend(self, request: DraftRecommendationRequest):
        scorer = self._get_scorer(request.rank)
        excluded_hero_ids = set(request.excluded_hero_ids)
        unknown_exclusions = excluded_hero_ids - set(scorer.heroes)

        if unknown_exclusions:
            unknown_text = ", ".join(
                str(hero_id) for hero_id in sorted(unknown_exclusions)
            )
            raise ValueError(f"未知排除英雄 ID：{unknown_text}")

        all_results = scorer.recommend(
            allies=request.allies,
            enemies=request.enemies,
            alpha=request.weights.alpha,
            beta=request.weights.beta,
            gamma=request.weights.gamma,
            top_k=len(scorer.heroes),
        )
        filtered_results = [
            result
            for result in all_results
            if result.hero_id not in excluded_hero_ids
        ][: request.top_k]
        response_results = []

        for result in filtered_results:
            item = asdict(result)
            item.update(
                {
                    "base_component": (
                        request.weights.alpha * result.base_score
                    ),
                    "counter_component": (
                        request.weights.beta * result.counter_sum
                    ),
                    "synergy_component": (
                        request.weights.gamma * result.synergy_sum
                    ),
                }
            )
            response_results.append(RecommendationResult(**item))

        return DraftRecommendationResponse(
            rank=scorer.rank_segment,
            weights=request.weights,
            results=response_results,
            dataset_version=self.repository.dataset_version,
        )

    def _get_scorer(self, rank_segment):
        cache_key = rank_segment.strip().lower()
        scorer = self._scorer_cache.get(cache_key)

        if scorer is not None:
            return scorer

        with self._cache_lock:
            scorer = self._scorer_cache.get(cache_key)

            if scorer is None:
                scorer = DraftScoreV1(
                    self.repository.database_path,
                    rank_segment,
                )
                self._scorer_cache[scorer.rank_segment.lower()] = scorer

        return scorer
