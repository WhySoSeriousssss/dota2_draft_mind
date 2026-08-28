from dataclasses import dataclass
from functools import cached_property


FEATURE_FORMAT = "draft_score_v2_lightgbm_features"
FEATURE_VERSION = 1


@dataclass(frozen=True)
class FeatureSchema:
    hero_ids: tuple[int, ...]
    rank_segments: tuple[str, ...]

    def __post_init__(self):
        if not self.hero_ids or len(set(self.hero_ids)) != len(self.hero_ids):
            raise ValueError("英雄特征列表不能为空或重复")

        if not self.rank_segments or len(set(self.rank_segments)) != len(
            self.rank_segments
        ):
            raise ValueError("分段特征列表不能为空或重复")

    @cached_property
    def hero_indexes(self):
        return {
            hero_id: index for index, hero_id in enumerate(self.hero_ids)
        }

    @cached_property
    def rank_indexes(self):
        return {
            rank: index for index, rank in enumerate(self.rank_segments)
        }

    @cached_property
    def feature_names(self):
        names = []

        for field in ("candidate", "ally", "enemy"):
            names.extend(
                f"{field}_hero_{hero_id}" for hero_id in self.hero_ids
            )

        names.extend(f"rank_{rank}" for rank in self.rank_segments)
        names.extend(("is_radiant", "ally_count", "enemy_count"))
        return tuple(names)

    @property
    def num_features(self):
        return len(self.feature_names)

    def encode_sparse(
        self,
        candidate_id,
        allies,
        enemies,
        rank_segment,
        is_radiant,
    ):
        hero_count = len(self.hero_ids)

        try:
            candidate_index = self.hero_indexes[int(candidate_id)]
            ally_indexes = [self.hero_indexes[int(hero_id)] for hero_id in allies]
            enemy_indexes = [
                self.hero_indexes[int(hero_id)] for hero_id in enemies
            ]
            rank_index = self.rank_indexes[rank_segment]
        except KeyError as error:
            raise ValueError(f"特征包含未知值：{error.args[0]}") from error

        features = {candidate_index: 1.0}

        for hero_index in ally_indexes:
            features[hero_count + hero_index] = 1.0

        for hero_index in enemy_indexes:
            features[hero_count * 2 + hero_index] = 1.0

        rank_offset = hero_count * 3
        features[rank_offset + rank_index] = 1.0
        metadata_offset = rank_offset + len(self.rank_segments)

        if is_radiant:
            features[metadata_offset] = 1.0

        if ally_indexes:
            features[metadata_offset + 1] = float(len(ally_indexes))

        # Keep the final zero-based feature index present in every LibSVM row.
        features[metadata_offset + 2] = float(len(enemy_indexes))

        return features

    def encode_dense(self, *args, **kwargs):
        row = [0.0] * self.num_features

        for feature_index, value in self.encode_sparse(
            *args,
            **kwargs,
        ).items():
            row[feature_index] = value

        return row

    def to_dict(self):
        return {
            "format": FEATURE_FORMAT,
            "version": FEATURE_VERSION,
            "hero_ids": list(self.hero_ids),
            "rank_segments": list(self.rank_segments),
            "feature_names": list(self.feature_names),
            "num_features": self.num_features,
        }

    @classmethod
    def from_dict(cls, value):
        if value.get("format") != FEATURE_FORMAT:
            raise ValueError(f"未知特征格式：{value.get('format')}")

        if value.get("version") != FEATURE_VERSION:
            raise ValueError(f"未知特征版本：{value.get('version')}")

        schema = cls(
            hero_ids=tuple(int(hero_id) for hero_id in value["hero_ids"]),
            rank_segments=tuple(value["rank_segments"]),
        )

        if value.get("feature_names") != list(schema.feature_names):
            raise ValueError("特征名称或顺序与当前实现不一致")

        if value.get("num_features") != schema.num_features:
            raise ValueError("特征数量与当前实现不一致")

        return schema


def format_libsvm_row(label, features):
    values = " ".join(
        f"{feature_index}:{value:g}"
        for feature_index, value in sorted(features.items())
    )
    return f"{int(bool(label))} {values}\n"
