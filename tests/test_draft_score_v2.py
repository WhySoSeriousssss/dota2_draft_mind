import json

import pytest

from backend.app.main import create_app
from backend.app.schemas import DraftV2RecommendationRequest
from algorithms.v2.features import FeatureSchema, format_libsvm_row
from algorithms.v2.model import ModelNotReadyError
from data_pipeline.processing.build_draft_score_v2_data import (
    build_dataset,
    select_random_split,
)


def test_feature_schema_is_stable_and_uses_zero_based_libsvm():
    schema = FeatureSchema(
        hero_ids=(1, 2, 3),
        rank_segments=("Legend", "Ancient"),
    )
    features = schema.encode_sparse(
        candidate_id=2,
        allies=[1],
        enemies=[3],
        rank_segment="Legend",
        is_radiant=True,
    )

    assert schema.num_features == 14
    assert schema.feature_names[:4] == (
        "candidate_hero_1",
        "candidate_hero_2",
        "candidate_hero_3",
        "ally_hero_1",
    )
    assert format_libsvm_row(1, features).startswith("1 1:1 3:1 8:1 9:1")
    assert FeatureSchema.from_dict(schema.to_dict()) == schema


def test_dataset_builder_splits_by_match_time_and_balances_sides(tmp_path):
    batch_path = tmp_path / "batch_000001.json"
    matches = [
        {
            "match_id": match_id,
            "start_time": start_time,
            "avg_rank_tier": 52,
            "radiant_win": radiant_win,
            "radiant_team": [1, 2, 3, 4, 5],
            "dire_team": [6, 7, 8, 9, 10],
        }
        for match_id, start_time, radiant_win in (
            (1, 100, True),
            (2, 200, False),
            (3, 300, True),
        )
    ]
    batch_path.write_text(json.dumps(matches), encoding="utf-8")
    output_directory = tmp_path / "dataset"
    metadata = build_dataset(
        batch_paths=[batch_path],
        heroes={hero_id: str(hero_id) for hero_id in range(1, 11)},
        output_directory=output_directory,
        validation_start=150,
        test_start=250,
        samples_per_side=1,
        split_strategy="time",
    )

    assert metadata["accepted_matches"] == 3
    assert metadata["split_strategy"] == "time"
    assert metadata["splits"]["train"] == {
        "matches": 1,
        "samples": 2,
        "positive_samples": 1,
    }
    assert metadata["splits"]["validation"]["samples"] == 2
    assert metadata["splits"]["test"]["samples"] == 2

    for split in ("train", "validation", "test"):
        labels = [
            line.split(maxsplit=1)[0]
            for line in (output_directory / f"{split}.libsvm")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        assert sorted(labels) == ["0", "1"]


def test_random_split_is_deterministic_and_approximately_80_10_10():
    assignments = [
        select_random_split(
            match_id,
            seed=20260828,
            validation_ratio=0.1,
            test_ratio=0.1,
        )
        for match_id in range(10_000)
    ]

    assert assignments == [
        select_random_split(
            match_id,
            seed=20260828,
            validation_ratio=0.1,
            test_ratio=0.1,
        )
        for match_id in range(10_000)
    ]
    assert 7_700 <= assignments.count("train") <= 8_300
    assert 850 <= assignments.count("validation") <= 1_150
    assert 850 <= assignments.count("test") <= 1_150


def test_v2_service_reports_missing_model(tmp_path):
    service = create_app().state.draft_service
    service.v2_model_directory = tmp_path / "missing-model"
    service._v2_model = None

    with pytest.raises(ModelNotReadyError, match="模型尚未训练"):
        service.recommend_v2(
            DraftV2RecommendationRequest(rank="Legend", top_k=3)
        )


def test_v2_service_filters_candidates_and_sorts_probabilities():
    service = create_app().state.draft_service
    hero_ids = tuple(sorted(hero["id"] for hero in service.repository.heroes))

    class FakeModel:
        schema = FeatureSchema(
            hero_ids=hero_ids,
            rank_segments=tuple(service.repository.rank_segments),
        )
        model_version = "draft_score_v2_test"
        dataset_version = "test-dataset"

        @staticmethod
        def predict_probabilities(candidate_ids, **_kwargs):
            return [hero_id / 1000 for hero_id in candidate_ids]

    service._v2_model = FakeModel()
    response = service.recommend_v2(
        DraftV2RecommendationRequest(
            rank="legend",
            allies=[25],
            enemies=[26],
            excluded_hero_ids=[155],
            position_ids=[1],
            top_k=3,
        )
    )
    result_ids = [result.hero_id for result in response.results]
    allowed_ids = set(service.repository.position_heroes[1])

    assert response.rank == "Legend"
    assert response.model_version == "draft_score_v2_test"
    assert result_ids == sorted(result_ids, reverse=True)
    assert set(result_ids) <= allowed_ids
    assert not {25, 26, 155} & set(result_ids)
