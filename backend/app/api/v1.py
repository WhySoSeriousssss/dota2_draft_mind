from fastapi import APIRouter, Depends, Request

from ..schemas import (
    AppConfigResponse,
    DraftRecommendationRequest,
    DraftRecommendationResponse,
    HealthResponse,
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


@router.get("/healthz", response_model=HealthResponse)
async def health(service: DraftService = Depends(get_draft_service)):
    return service.health()
