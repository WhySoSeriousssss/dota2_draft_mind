from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.v1 import router as api_v1_router
from .config import Settings
from .repositories.draft_repository import DraftRepository
from .services.draft_service import DraftService


def create_app(settings=None):
    settings = settings or Settings.from_environment()
    settings.validate()
    repository = DraftRepository(
        database_path=settings.database_path,
        heroes_path=settings.heroes_path,
        hero_positions_path=settings.hero_positions_path,
    )
    app = FastAPI(
        title="DOTA 2 Draft Mind API",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.draft_service = DraftService(repository)
    app.include_router(api_v1_router)
    app.mount(
        "/assets",
        StaticFiles(directory=settings.frontend_directory / "assets"),
        name="frontend-assets",
    )

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(settings.frontend_directory / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "NOT_FOUND", "message": "接口不存在"}},
            )
        return FileResponse(settings.frontend_directory / "index.html")

    @app.exception_handler(ValueError)
    async def handle_value_error(_request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "INVALID_DRAFT",
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "请求参数不合法",
                    "details": exc.errors(),
                }
            },
        )

    return app


app = create_app()
