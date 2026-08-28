from dataclasses import asdict
from threading import Lock

from algorithms.v1 import DraftScoreV1
from algorithms.v2.model import (
    LightGBMDraftModel,
    ModelNotReadyError,
    model_files_exist,
)

from ..repositories.draft_repository import DraftRepository
from ..schemas import (
    AppConfigResponse,
    ConfigDefaults,
    DraftRecommendationRequest,
    DraftRecommendationResponse,
    DraftV2RecommendationRequest,
    DraftV2RecommendationResponse,
    DraftWeights,
    HealthResponse,
    LeaderboardHero,
    LeaderboardMatchup,
    LeaderboardResponse,
    ModelStatusResponse,
    RecommendationResult,
    V2RecommendationResult,
)


class DraftService:
    def __init__(self, repository: DraftRepository, v2_model_directory=None):
        self.repository = repository
        self.v2_model_directory = v2_model_directory
        self._v2_model = None
        self._scorer_cache = {}
        self._leaderboard_cache = {}
        self._cache_lock = Lock()

    def get_v2_model_status(self):
        if not self.v2_model_directory or not model_files_exist(
            self.v2_model_directory
        ):
            return ModelStatusResponse(
                status="missing",
                detail="模型尚未训练或 DRAFT_V2_MODEL_PATH 配置不正确",
            )

        try:
            model = self._get_v2_model()
        except ModelNotReadyError as error:
            return ModelStatusResponse(
                status="unavailable",
                detail=str(error),
            )

        return ModelStatusResponse(
            status="ready",
            model_version=model.model_version,
        )

    def get_config(self):
        default_rank = (
            "Legend"
            if "Legend" in self.repository.rank_segments
            else self.repository.rank_segments[0]
        )
        return AppConfigResponse(
            heroes=self.repository.heroes,
            positions=[
                {
                    **position,
                    "hero_ids": self.repository.position_heroes[position["id"]],
                }
                for position in self.repository.positions
            ],
            rank_segments=self.repository.rank_segments,
            defaults=ConfigDefaults(
                rank=default_rank,
                weights=DraftWeights(),
                top_k=15,
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
        selected_position_ids = set(request.position_ids)
        available_position_ids = set(self.repository.position_heroes)
        unknown_position_ids = selected_position_ids - available_position_ids
        unknown_exclusions = excluded_hero_ids - set(scorer.heroes)
        unknown_proficiency_heroes = (
            set(request.hero_proficiencies) - set(scorer.heroes)
        )

        if unknown_position_ids:
            unknown_text = ", ".join(
                str(position_id)
                for position_id in sorted(unknown_position_ids)
            )
            raise ValueError(f"未知位置 ID：{unknown_text}")

        if unknown_exclusions:
            unknown_text = ", ".join(
                str(hero_id) for hero_id in sorted(unknown_exclusions)
            )
            raise ValueError(f"未知排除英雄 ID：{unknown_text}")

        if unknown_proficiency_heroes:
            unknown_text = ", ".join(
                str(hero_id)
                for hero_id in sorted(unknown_proficiency_heroes)
            )
            raise ValueError(f"未知熟练度英雄 ID：{unknown_text}")

        candidate_hero_ids = None

        if selected_position_ids:
            candidate_hero_ids = sorted(
                {
                    hero_id
                    for position_id in selected_position_ids
                    for hero_id in self.repository.position_heroes[position_id]
                }
                - excluded_hero_ids
            )

        all_results = scorer.recommend(
            allies=request.allies,
            enemies=request.enemies,
            alpha=request.weights.alpha,
            beta=request.weights.beta,
            gamma=request.weights.gamma,
            delta=request.weights.delta,
            hero_proficiencies=request.hero_proficiencies,
            top_k=len(scorer.heroes),
            candidate_hero_ids=candidate_hero_ids,
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
                    "proficiency_component": (
                        request.weights.delta * result.proficiency_score
                    ),
                }
            )
            response_results.append(RecommendationResult(**item))

        return DraftRecommendationResponse(
            rank=scorer.rank_segment,
            position_ids=request.position_ids,
            weights=request.weights,
            results=response_results,
            dataset_version=self.repository.dataset_version,
        )

    def recommend_v2(self, request: DraftV2RecommendationRequest):
        rank_segment = self._validate_v2_request(request)
        model = self._get_v2_model()
        repository_hero_ids = {
            hero["id"] for hero in self.repository.heroes
        }

        if set(model.schema.hero_ids) != repository_hero_ids:
            raise ModelNotReadyError("V2 模型英雄列表与当前元数据不一致")

        if rank_segment not in model.schema.rank_segments:
            raise ModelNotReadyError(
                f"V2 模型不支持当前分段：{rank_segment}"
            )

        picked_hero_ids = set(request.allies) | set(request.enemies)
        excluded_hero_ids = set(request.excluded_hero_ids)

        if request.position_ids:
            candidate_ids = {
                hero_id
                for position_id in request.position_ids
                for hero_id in self.repository.position_heroes[position_id]
            }
        else:
            candidate_ids = repository_hero_ids

        candidate_ids = sorted(
            candidate_ids - picked_hero_ids - excluded_hero_ids
        )
        probabilities = model.predict_probabilities(
            candidate_ids=candidate_ids,
            allies=request.allies,
            enemies=request.enemies,
            rank_segment=rank_segment,
            side=request.side,
        )
        hero_names = {
            hero["id"]: hero["name"] for hero in self.repository.heroes
        }
        results = sorted(
            (
                V2RecommendationResult(
                    hero_id=hero_id,
                    hero_name=hero_names[hero_id],
                    win_probability=probability,
                )
                for hero_id, probability in zip(
                    candidate_ids,
                    probabilities,
                )
            ),
            key=lambda result: (
                result.win_probability,
                -result.hero_id,
            ),
            reverse=True,
        )[: request.top_k]
        return DraftV2RecommendationResponse(
            rank=rank_segment,
            position_ids=request.position_ids,
            side=request.side,
            results=results,
            model_version=model.model_version,
            dataset_version=model.dataset_version,
        )

    def _validate_v2_request(self, request):
        hero_ids = {hero["id"] for hero in self.repository.heroes}
        rank_lookup = {
            rank.lower(): rank for rank in self.repository.rank_segments
        }
        normalized_rank = request.rank.strip().lower()

        if normalized_rank not in rank_lookup:
            available = ", ".join(self.repository.rank_segments)
            raise ValueError(
                f"未知分段：{request.rank}；可选分段：{available}"
            )

        if len(set(request.allies)) != len(request.allies):
            raise ValueError("我方英雄 ID 不能重复")

        if len(set(request.enemies)) != len(request.enemies):
            raise ValueError("敌方英雄 ID 不能重复")

        if set(request.allies) & set(request.enemies):
            raise ValueError("同一个英雄不能同时出现在双方阵容中")

        unknown_picks = (
            set(request.allies) | set(request.enemies)
        ) - hero_ids

        if unknown_picks:
            raise ValueError(f"未知英雄 ID：{min(unknown_picks)}")

        unknown_exclusions = set(request.excluded_hero_ids) - hero_ids

        if unknown_exclusions:
            raise ValueError(
                f"未知排除英雄 ID：{min(unknown_exclusions)}"
            )

        unknown_positions = set(request.position_ids) - set(
            self.repository.position_heroes
        )

        if unknown_positions:
            raise ValueError(f"未知位置 ID：{min(unknown_positions)}")

        return rank_lookup[normalized_rank]

    def _get_v2_model(self):
        if self._v2_model is not None:
            return self._v2_model

        if not self.v2_model_directory:
            raise ModelNotReadyError("Draft Score V2 模型目录未配置")

        with self._cache_lock:
            if self._v2_model is None:
                self._v2_model = LightGBMDraftModel(
                    self.v2_model_directory
                )

        return self._v2_model

    def get_leaderboard(self, rank_segment, sort_by, order):
        normalized_rank = rank_segment.strip().lower()
        leaderboard = self._leaderboard_cache.get(normalized_rank)

        if leaderboard is None:
            with self._cache_lock:
                leaderboard = self._leaderboard_cache.get(normalized_rank)

                if leaderboard is None:
                    leaderboard = self._build_leaderboard(rank_segment)
                    self._leaderboard_cache[normalized_rank] = leaderboard

        heroes = list(leaderboard.heroes)
        reverse = order == "desc"

        if sort_by == "name":
            heroes.sort(
                key=lambda hero: hero.hero_name.lower(),
                reverse=reverse,
            )
        else:
            available = [
                hero for hero in heroes
                if getattr(hero, sort_by) is not None
            ]
            unavailable = [
                hero for hero in heroes
                if getattr(hero, sort_by) is None
            ]
            available.sort(
                key=lambda hero: (
                    getattr(hero, sort_by),
                    hero.appearances,
                    -hero.hero_id,
                ),
                reverse=reverse,
            )
            heroes = available + unavailable

        return leaderboard.model_copy(update={"heroes": heroes})

    def _build_leaderboard(self, rank_segment):
        data = self.repository.get_leaderboard_data(rank_segment)
        hero_metadata = {
            hero["id"]: hero for hero in self.repository.heroes
        }
        base_stats = {
            hero_id: {
                "appearances": appearances,
                "win_rate": wins / appearances if appearances else None,
            }
            for hero_id, appearances, wins in data["base_rows"]
        }
        matchups_by_hero = {}

        for hero_id, enemy_id, appearances, wins in data["matchup_rows"]:
            base_stat = base_stats.get(hero_id)

            if (
                appearances < 20
                or not base_stat
                or base_stat["win_rate"] is None
                or enemy_id not in hero_metadata
            ):
                continue

            matchup_win_rate = wins / appearances
            enemy = hero_metadata[enemy_id]
            matchup = LeaderboardMatchup(
                hero_id=enemy_id,
                hero_name=enemy["name"],
                image=enemy["image"],
                appearances=appearances,
                win_rate=matchup_win_rate,
                advantage=matchup_win_rate - base_stat["win_rate"],
            )
            matchups_by_hero.setdefault(hero_id, []).append(matchup)

        heroes = []

        for hero_id, hero in hero_metadata.items():
            base_stat = base_stats.get(
                hero_id,
                {"appearances": 0, "win_rate": None},
            )
            matchups = matchups_by_hero.get(hero_id, [])
            counters = sorted(
                [item for item in matchups if item.advantage > 0],
                key=lambda item: (item.advantage, item.appearances),
                reverse=True,
            )[:5]
            countered_by = sorted(
                [item for item in matchups if item.advantage < 0],
                key=lambda item: (item.advantage, -item.appearances),
            )[:5]
            pick_rate = (
                base_stat["appearances"] / data["total_matches"]
                if data["total_matches"]
                else 0.0
            )
            heroes.append(
                LeaderboardHero(
                    hero_id=hero_id,
                    hero_name=hero["name"],
                    image=hero["image"],
                    appearances=base_stat["appearances"],
                    pick_rate=pick_rate,
                    win_rate=base_stat["win_rate"],
                    counters=counters,
                    countered_by=countered_by,
                )
            )

        return LeaderboardResponse(
            rank=data["rank"],
            total_matches=data["total_matches"],
            heroes=heroes,
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
