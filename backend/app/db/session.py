"""Database session management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


settings = get_settings()

engine: AsyncEngine = create_async_engine(settings.database_dsn, echo=False, future=True)

async_session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def get_session() -> AsyncSession:
    """FastAPI dependency that yields a database session."""

    async with async_session_factory() as session:  # pragma: no cover - generator semantics
        yield session
