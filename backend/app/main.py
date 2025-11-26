"""BeatSight FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.routes import admin, ai_jobs, auth, billing, health, karma, map_edits, metadata, roles, songs, storage, sync, verifier, websocket
from app.config import get_settings
from app.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("startup", environment=settings.environment)
    yield
    # Shutdown (nothing to do currently)


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    description="""
## BeatSight Web API

BeatSight is an AI-powered drum beatmap generation platform. This API provides:

### Features
- **Authentication**: JWT-based auth with access/refresh tokens
- **Songs**: Upload, manage, and organize your music library
- **AI Jobs**: Queue songs for AI beatmap generation with real-time progress
- **Cloud Sync**: Sync preferences and progress across devices
- **Storage**: Secure file upload with presigned URLs

### Authentication
Most endpoints require authentication. Include the JWT token in the Authorization header:
```
Authorization: Bearer <access_token>
```

### Rate Limits
- Standard users: 100 requests/minute
- Premium users: 500 requests/minute
- AI job quota: Based on subscription tier
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "BeatSight Support",
        "url": "https://beatsight.app/support",
        "email": "support@beatsight.app",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {
            "name": "health",
            "description": "Health check endpoints for monitoring and load balancers",
        },
        {
            "name": "auth",
            "description": "Authentication endpoints: login, register, token refresh, logout",
        },
        {
            "name": "songs",
            "description": "Song library management: upload, list, update, delete songs",
        },
        {
            "name": "ai-jobs",
            "description": "AI beatmap generation jobs: queue, monitor progress, retrieve results",
        },
        {
            "name": "storage",
            "description": "File storage: presigned upload URLs, file management",
        },
        {
            "name": "sync",
            "description": "Cloud sync: preferences, progress, client registration",
        },
        {
            "name": "roles",
            "description": "Role-based access control: permissions, role management",
        },
        {
            "name": "karma",
            "description": "User karma system: reputation, community contributions",
        },
        {
            "name": "metadata",
            "description": "Song metadata: AcoustID lookup, metadata enrichment",
        },
        {
            "name": "admin",
            "description": "Admin endpoints: user management, system configuration",
        },
        {
            "name": "Billing",
            "description": "Payment and subscription: checkout, portal, webhooks",
        },
    ],
)

# Set up Prometheus metrics (conditionally to avoid import errors in tests)
try:
    from app.services.metrics import setup_metrics
    setup_metrics(app)
    logger.info("metrics_enabled", endpoint="/metrics")
except ImportError:
    logger.warning("metrics_disabled", reason="prometheus_client not installed")

# Set up rate limiting (conditionally based on Redis availability)
if settings.environment != "test":
    try:
        from app.services.rate_limit import setup_rate_limiting
        from app.api.deps import get_redis
        setup_rate_limiting(app, get_redis)
    except ImportError:
        logger.warning("rate_limiting_disabled", reason="dependencies not installed")

app.include_router(health.router)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(songs.router, prefix=settings.api_prefix)
app.include_router(ai_jobs.router, prefix=settings.api_prefix)
app.include_router(karma.router, prefix=settings.api_prefix)
app.include_router(storage.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(roles.router, prefix=settings.api_prefix)
app.include_router(metadata.router, prefix=settings.api_prefix)
app.include_router(sync.router, prefix=settings.api_prefix)
app.include_router(billing.router, prefix=settings.api_prefix)
app.include_router(verifier.router, prefix=settings.api_prefix)
app.include_router(map_edits.router, prefix=settings.api_prefix)
app.include_router(websocket.router)  # No prefix - /ws/jobs


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Return API service metadata."""

    return {"service": settings.app_name, "environment": settings.environment}
