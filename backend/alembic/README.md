# Alembic Migrations

This directory contains database migrations for the BeatSight backend.

## Setup

Migrations use Alembic with async SQLAlchemy support.

## Running Migrations

```bash
# Run all pending migrations
DATABASE_DSN="postgresql+asyncpg://user:pass@host/db" poetry run alembic upgrade head

# Rollback one migration
DATABASE_DSN="..." poetry run alembic downgrade -1

# Generate a new migration (after modifying models)
DATABASE_DSN="..." poetry run alembic revision --autogenerate -m "description"

# Show migration history
poetry run alembic history
```

## Docker

Migrations run automatically in docker-compose via the `migrate` service.

## Migration History

| Revision | Description |
|----------|-------------|
| `001_worker_heartbeat` | Add AI job worker heartbeat tracking fields |
