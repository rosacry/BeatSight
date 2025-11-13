"""BeatSight FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import ai_jobs, health, songs
from app.config import get_settings
from app.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(health.router)
app.include_router(songs.router, prefix=settings.api_prefix)
app.include_router(ai_jobs.router, prefix=settings.api_prefix)


@app.on_event("startup")
async def on_startup() -> None:
    """Log application startup."""

    logger.info("startup", environment=settings.environment)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Return API service metadata."""

    return {"service": settings.app_name, "environment": settings.environment}
