import pytest

from backend.app.main import create_app
from backend.app.schemas import DraftRecommendationRequest


def create_service():
    return create_app().state.draft_service


def test_config_returns_all_heroes_and_rank_segments():
    config = create_service().get_config()

    assert len(config.heroes) == 127
    assert [position.key for position in config.positions] == [
        "carry",
        "mid",
        "offlane",
        "support",
    ]
    assert config.rank_segments == [
        "Herald",
        "Guardian",
        "Crusader",
        "Archon",
        "Legend",
        "Ancient",
        "Divine",
        "Immortal",
    ]
    assert config.defaults.top_k == 15


def test_recommendation_defaults_to_fifteen_results():
    request = DraftRecommendationRequest(rank="Legend")
    response = create_service().recommend(request)

    assert request.top_k == 15
    assert len(response.results) == 15


def test_recommendation_preserves_existing_result():
    request = DraftRecommendationRequest.model_validate(
        {
            "rank": "Legend",
            "allies": [25, 26],
            "enemies": [89, 12],
            "weights": {"alpha": 1, "beta": 0.5, "gamma": 0.8},
            "top_k": 3,
        }
    )
    response = create_service().recommend(request)

    assert [result.hero_name for result in response.results] == [
        "Leshrac",
        "Dazzle",
        "Grimstroke",
    ]
    assert all(result.proficiency_component == 0 for result in response.results)


def test_proficiency_changes_score_and_ranking():
    request = DraftRecommendationRequest.model_validate(
        {
            "rank": "Legend",
            "hero_proficiencies": {"50": 1, "52": -1},
            "weights": {
                "alpha": 1,
                "beta": 0,
                "gamma": 0,
                "delta": 0.05,
            },
            "top_k": 127,
        }
    )
    response = create_service().recommend(request)
    results = {result.hero_id: result for result in response.results}

    assert response.results[0].hero_id == 50
    assert results[50].proficiency_score == 1
    assert results[50].proficiency_component == pytest.approx(0.05)
    assert results[52].proficiency_score == -1
    assert results[52].proficiency_component == pytest.approx(-0.05)


def test_unknown_proficiency_hero_is_rejected():
    request = DraftRecommendationRequest(
        rank="Legend",
        hero_proficiencies={999: 1},
    )

    with pytest.raises(ValueError, match="未知熟练度英雄 ID：999"):
        create_service().recommend(request)


def test_excluded_heroes_are_not_recommended():
    request = DraftRecommendationRequest.model_validate(
        {
            "rank": "Legend",
            "allies": [25, 26],
            "enemies": [89, 12],
            "excluded_hero_ids": [52, 50],
            "weights": {"alpha": 1, "beta": 0.5, "gamma": 0.8},
            "top_k": 3,
        }
    )
    response = create_service().recommend(request)

    result_ids = {result.hero_id for result in response.results}
    assert 52 not in result_ids
    assert 50 not in result_ids


def test_position_filter_only_scores_matching_heroes():
    service = create_service()
    request = DraftRecommendationRequest.model_validate(
        {
            "rank": "Legend",
            "position_ids": [0, 1],
            "top_k": 127,
        }
    )
    response = service.recommend(request)
    allowed_hero_ids = (
        set(service.repository.position_heroes[0])
        | set(service.repository.position_heroes[1])
    )
    result_ids = {result.hero_id for result in response.results}

    assert service.repository.hero_positions[82] == [0, 1]
    assert response.position_ids == [0, 1]
    assert result_ids
    assert result_ids <= allowed_hero_ids
    assert 82 in allowed_hero_ids
    assert 5 not in result_ids


def test_unknown_position_is_rejected():
    request = DraftRecommendationRequest(
        rank="Legend",
        position_ids=[9],
    )

    with pytest.raises(ValueError, match="未知位置 ID：9"):
        create_service().recommend(request)


def test_invalid_draft_is_rejected():
    request = DraftRecommendationRequest.model_validate(
        {
            "rank": "Legend",
            "allies": [25],
            "enemies": [25],
        }
    )

    with pytest.raises(
        ValueError,
        match="同一个英雄不能同时出现在双方阵容中",
    ):
        create_service().recommend(request)


def test_all_rank_leaderboard_aggregates_every_match():
    leaderboard = create_service().get_leaderboard(
        "All",
        "win_rate",
        "desc",
    )

    assert leaderboard.total_matches == 3_729_537
    assert len(leaderboard.heroes) == 127
    assert sum(hero.pick_rate for hero in leaderboard.heroes) == pytest.approx(10)
    win_rates = [
        hero.win_rate for hero in leaderboard.heroes
        if hero.win_rate is not None
    ]
    assert win_rates == sorted(win_rates, reverse=True)


def test_leaderboard_includes_reliable_matchups():
    leaderboard = create_service().get_leaderboard(
        "Legend",
        "pick_rate",
        "desc",
    )
    hero = next(item for item in leaderboard.heroes if item.counters)

    assert leaderboard.total_matches == 821_344
    assert len(hero.counters) <= 5
    assert len(hero.countered_by) <= 5
    assert all(matchup.appearances >= 20 for matchup in hero.counters)
    assert all(matchup.advantage > 0 for matchup in hero.counters)
    assert all(matchup.advantage < 0 for matchup in hero.countered_by)
