# BeatSight Backend

FastAPI-based backend services supporting the BeatSight web platform. This module bootstraps the API gateway, data models, and service scaffolding aligned with `docs/web_backend_architecture.md` and `docs/web_mvp_prd.md`.

## Features (initial skeleton)
- FastAPI application with modular routers.
- SQLAlchemy 2.0 async models matching the canonical schema.
- Pydantic v2 schemas for API payloads.
- Dependency wiring for async database sessions and Redis cache.
- Structured logging via `structlog`.

## Getting Started
```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

Configuration is handled through environment variables (see `app/config.py`).
