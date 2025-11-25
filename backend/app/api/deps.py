"""Common FastAPI dependencies."""

from __future__ import annotations

from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.user import User
from app.services.auth import AuthService


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""

    async for session in get_session():  # pragma: no cover - generator semantics
        yield session


# Optional bearer token - returns None if not provided
optional_bearer = HTTPBearer(auto_error=False)

# Required bearer token - raises 401 if not provided
required_bearer = HTTPBearer()


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer),
    session: AsyncSession = Depends(get_db_session),
) -> Optional[User]:
    """
    Get the current user from bearer token if provided.
    Returns None if no token is present (for anonymous endpoints).
    """
    if credentials is None:
        return None

    auth_service = AuthService(session)
    user = await auth_service.get_user_from_token(credentials.credentials)
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(required_bearer),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Get the current authenticated user from bearer token.
    Raises 401 Unauthorized if token is missing or invalid.
    """
    auth_service = AuthService(session)
    user = await auth_service.get_user_from_token(credentials.credentials)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
