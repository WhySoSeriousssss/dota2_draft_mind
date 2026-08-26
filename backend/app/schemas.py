from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class HeroResponse(StrictModel):
    id: int
    name: str
    attribute: str
    roles: list[str]
    image: str
    icon: str


class DraftWeights(StrictModel):
    alpha: float = Field(default=1.0, ge=0.0, le=5.0)
    beta: float = Field(default=0.5, ge=0.0, le=5.0)
    gamma: float = Field(default=0.8, ge=0.0, le=5.0)


class ConfigDefaults(StrictModel):
    rank: str
    weights: DraftWeights
    top_k: int


class AppConfigResponse(StrictModel):
    heroes: list[HeroResponse]
    rank_segments: list[str]
    defaults: ConfigDefaults
    dataset_version: str | None = None


class DraftRecommendationRequest(StrictModel):
    rank: str = Field(min_length=1, max_length=32)
    allies: list[int] = Field(default_factory=list, max_length=4)
    enemies: list[int] = Field(default_factory=list, max_length=5)
    excluded_hero_ids: list[int] = Field(default_factory=list, max_length=127)
    weights: DraftWeights = Field(default_factory=DraftWeights)
    top_k: int = Field(default=15, ge=1, le=127)


class RecommendationResult(StrictModel):
    hero_id: int
    hero_name: str
    score: float
    base_score: float
    counter_sum: float
    synergy_sum: float
    base_appearances: int
    base_component: float
    counter_component: float
    synergy_component: float


class DraftRecommendationResponse(StrictModel):
    rank: str
    weights: DraftWeights
    results: list[RecommendationResult]
    model_version: str = "draft_score_v1"
    dataset_version: str | None = None


class HealthResponse(StrictModel):
    status: str
    heroes: int
    rank_segments: int


class ErrorDetail(StrictModel):
    code: str
    message: str
    details: list | dict | None = None


class ErrorResponse(StrictModel):
    error: ErrorDetail
