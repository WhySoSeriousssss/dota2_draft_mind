from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from ..schemas import (
    AppConfigResponse,
    DraftRecommendationRequest,
    DraftRecommendationResponse,
    DraftV2RecommendationRequest,
    DraftV2RecommendationResponse,
    HealthResponse,
    LeaderboardResponse,
    ModelStatusResponse,
)
from ..services.draft_service import DraftService


router = APIRouter(prefix="/api/v1")


def get_draft_service(request: Request):
    return request.app.state.draft_service


@router.get("/config", response_model=AppConfigResponse)
async def get_config(service: DraftService = Depends(get_draft_service)):
    return service.get_config()


@router.post("/recommend", response_model=DraftRecommendationResponse)
async def recommend(
    payload: DraftRecommendationRequest,
    service: DraftService = Depends(get_draft_service),
):
    return service.recommend(payload)


@router.post(
    "/recommend/v2",
    response_model=DraftV2RecommendationResponse,
)
async def recommend_v2(
    payload: DraftV2RecommendationRequest,
    service: DraftService = Depends(get_draft_service),
):
    return service.recommend_v2(payload)


@router.get(
    "/models/draft-score-v2",
    response_model=ModelStatusResponse,
)
async def get_v2_model_status(
    service: DraftService = Depends(get_draft_service),
):
    return service.get_v2_model_status()


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    rank: str = Query(default="All", min_length=1, max_length=32),
    sort_by: Literal[
        "name", "pick_rate", "win_rate", "appearances"
    ] = "win_rate",
    order: Literal["asc", "desc"] = "desc",
    service: DraftService = Depends(get_draft_service),
):
    return service.get_leaderboard(rank, sort_by, order)


@router.get("/healthz", response_model=HealthResponse)
async def health(service: DraftService = Depends(get_draft_service)):
    return service.health()
