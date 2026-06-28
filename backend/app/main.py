from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_app_logging
from app.db.session import prewarm_database_connection


def create_app() -> FastAPI:
    configure_app_logging()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Photovoltaic O&M document QA system API.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    @app.on_event("startup")
    async def startup() -> None:
        prewarm_database_connection()

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
