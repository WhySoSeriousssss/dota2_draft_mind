import pytest

from backend.app.main import create_app
from backend.app.schemas import DraftRecommendationRequest


def create_service():
    return create_app().state.draft_service


def test_config_returns_all_heroes_and_rank_segments():
    config = create_service().get_config()

    assert len(config.heroes) == 127
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
