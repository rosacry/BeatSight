# BeatSight Backend

FastAPI-based backend services supporting the BeatSight web platform. This module bootstraps the API gateway, data models, and service scaffolding aligned with `docs/web_backend_architecture.md` and `docs/web_mvp_prd.md`.

## Features (initial skeleton)
- FastAPI application with modular routers.
- SQLAlchemy 2.0 async models matching the canonical schema.
- Pydantic v2 schemas for API payloads.
- Dependency wiring for async database sessions and Redis cache.
- Structured logging via `structlog`.
- JWT authentication with access/refresh tokens.

## Getting Started

### Option 1: Docker (Recommended)

```bash
cd backend

# Start all services (API, PostgreSQL, Redis)
docker-compose up -d

# Run migrations
docker-compose --profile migrate up migrations

# View logs
docker-compose logs -f api
```

The API will be available at `http://localhost:8000`.

### Option 2: Local Development

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

Requires PostgreSQL and Redis running locally. Configuration is handled through environment variables (see `app/config.py`).

## Testing

```bash
# Run tests
poetry run pytest

# With coverage
poetry run pytest --cov=app --cov-report=html
```

## Documentation
- **API Reference**: See `docs/API_REFERENCE.md` for endpoint documentation.
- **Deployment**: See `docs/DEPLOYMENT.md` for production deployment guide.

