"""Common FastAPI dependencies."""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""

    async for session in get_session():  # pragma: no cover - generator semantics
        yield session
