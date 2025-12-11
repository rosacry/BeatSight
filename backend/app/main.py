"""BeatSight FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    accuracy,
    achievements,
    admin,
    ai_jobs,
    auth,
    billing,
    contributions,
    credits,
    forum,
    health,
    karma,
    map_edits,
    maps,
    metadata,
    phone,
    roles,
    search,
    social,
    songs,
    storage,
    sync,
    twofa,
    users,
    verifier,
    votes,
    websocket,
)
from app.config import get_settings
from app.logging import configure_logging, get_logger
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

configure_logging()
logger = get_logger(__name__)

settings = get_settings()

# Initialize Sentry for error tracking
if settings.sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=f"beatsight-backend@{settings.app_version if hasattr(settings, 'app_version') else '0.1.0'}",
        traces_sample_rate=0.1 if settings.environment == "production" else 1.0,
        profiles_sample_rate=0.1 if settings.environment == "production" else 1.0,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
    )
    logger.info(
        "sentry_initialized", dsn_configured=True, environment=settings.environment
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("startup", environment=settings.environment)

    # SECURITY: Validate production secrets
    validation_errors = settings.validate_production_secrets()
    for error in validation_errors:
        if error.startswith("CRITICAL"):
            logger.critical("security_validation_failed", error=error)
            if settings.is_production:
                raise RuntimeError(error)
        else:
            logger.warning("security_validation_warning", warning=error)

    # Start Grafana Cloud metrics pusher if enabled
    if settings.grafana_cloud_enabled:
        from app.services.grafana_cloud import start_grafana_cloud_pusher

        if settings.grafana_cloud_instance_id and settings.grafana_cloud_api_key:
            await start_grafana_cloud_pusher(
                instance_id=settings.grafana_cloud_instance_id,
                api_key=settings.grafana_cloud_api_key,
                push_interval=settings.grafana_cloud_push_interval,
                enabled=True,
            )
            logger.info("grafana_cloud_pusher_started")
        else:
            logger.warning(
                "grafana_cloud_enabled_but_missing_credentials",
                has_instance_id=bool(settings.grafana_cloud_instance_id),
                has_api_key=bool(settings.grafana_cloud_api_key),
            )

    yield

    # Shutdown
    if settings.grafana_cloud_enabled:
        from app.services.grafana_cloud import stop_grafana_cloud_pusher

        await stop_grafana_cloud_pusher()
        logger.info("grafana_cloud_pusher_stopped")


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
        "url": "https://beatsight.io/support",
        "email": "support@beatsight.io",
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
            "name": "accuracy",
            "description": "Beatmap accuracy verification: multi-verifier consensus system",
        },
        {
            "name": "votes",
            "description": "Map voting: upvote/downvote maps for community curation",
        },
        {
            "name": "forum",
            "description": "Community forums: topics, posts, voting, polls",
        },
        {
            "name": "maps",
            "description": "Map management: verification, archiving, state control",
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

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)
logger.info("cors_middleware_enabled", origins=settings.cors_origins)

# Add request ID middleware for request tracing
app.add_middleware(RequestIdMiddleware)
logger.info("request_id_middleware_enabled")

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)
logger.info("security_headers_middleware_enabled")

# Add request logging middleware (skip in test environment)
if settings.environment not in ("test", "testing"):
    app.add_middleware(RequestLoggingMiddleware)
    logger.info("request_logging_middleware_enabled")

# Set up Prometheus metrics (conditionally to avoid import errors in tests)
try:
    from app.services.metrics import setup_metrics

    setup_metrics(app)
    logger.info("metrics_enabled", endpoint="/metrics")
except ImportError:
    logger.warning("metrics_disabled", reason="prometheus_client not installed")

# Set up rate limiting (conditionally based on Redis availability)
if settings.environment not in ("test", "testing"):
    try:
        from app.services.rate_limit import setup_rate_limiting
        from app.api.deps import get_redis

        setup_rate_limiting(app, get_redis)
    except ImportError:
        logger.warning("rate_limiting_disabled", reason="dependencies not installed")

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(accuracy.router, prefix=settings.api_prefix)
app.include_router(achievements.router, prefix=settings.api_prefix)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(twofa.router, prefix=settings.api_prefix)
app.include_router(phone.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(songs.router, prefix=settings.api_prefix)
app.include_router(ai_jobs.router, prefix=settings.api_prefix)
app.include_router(karma.router, prefix=settings.api_prefix)
app.include_router(storage.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(roles.router, prefix=settings.api_prefix)
app.include_router(metadata.router, prefix=settings.api_prefix)
app.include_router(sync.router, prefix=settings.api_prefix)
app.include_router(billing.router, prefix=settings.api_prefix)
app.include_router(credits.router, prefix=settings.api_prefix)
app.include_router(verifier.router, prefix=settings.api_prefix)
app.include_router(map_edits.router, prefix=settings.api_prefix)
app.include_router(maps.router, prefix=settings.api_prefix)
app.include_router(votes.router, prefix=settings.api_prefix)
app.include_router(forum.router, prefix=settings.api_prefix)
app.include_router(social.router, prefix=settings.api_prefix)
app.include_router(search.router, prefix=settings.api_prefix)
app.include_router(contributions.router, prefix=settings.api_prefix)
app.include_router(websocket.router)  # No prefix - /ws/jobs


# Global exception handler to prevent internal error details from leaking
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions without leaking internal details.

    In production, returns a generic error message.
    In development, includes the exception details for debugging.
    """
    request_id = getattr(request.state, "request_id", None)

    # Log the full exception for debugging
    logger.exception(
        "unhandled_exception",
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        exc_type=type(exc).__name__,
        exc_message=str(exc),
    )

    # Build CORS headers for error responses
    origin = request.headers.get("origin")
    cors_headers = {}
    if origin and origin in settings.cors_origins:
        cors_headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }

    if settings.is_production:
        # In production, don't leak internal details
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An internal error occurred. Please try again later.",
                "request_id": request_id,
            },
            headers=cors_headers,
        )
    else:
        # In development, include exception details
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "type": type(exc).__name__,
                "request_id": request_id,
            },
            headers=cors_headers,
        )


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Return API service metadata."""

    return {"service": settings.app_name, "environment": settings.environment}
