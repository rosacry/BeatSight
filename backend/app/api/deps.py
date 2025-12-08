"""Common FastAPI dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncGenerator, Callable, Optional

from fastapi import Depends, HTTPException, Query, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session
from app.models.user import User
from app.services.auth import AuthService

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from app.services.rbac import RBACService


# =============================================================================
# Feature Flag Dependencies
# =============================================================================


def require_feature(feature_name: str) -> Callable[[], None]:
    """
    Create a dependency that checks if a feature flag is enabled.

    Usage:
        @router.get("/sync", dependencies=[Depends(require_feature("cloud_sync"))])
        async def sync_endpoint():
            ...

    Args:
        feature_name: Name of the feature (without 'feature_' prefix).
                      Maps to settings.feature_{feature_name}

    Raises:
        HTTPException 404 if feature is disabled
    """

    def check_feature() -> None:
        settings = get_settings()
        flag_name = f"feature_{feature_name}"
        is_enabled = getattr(settings, flag_name, False)

        if not is_enabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="This feature is not currently available",
            )

    return check_feature


def require_beta() -> None:
    """Dependency that requires beta features to be enabled."""
    settings = get_settings()
    if not settings.feature_beta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This feature is in beta and not yet available",
        )


def require_community() -> None:
    """Dependency that requires community features to be enabled."""
    settings = get_settings()
    if not settings.feature_community:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community features are not currently available",
        )


def require_karma() -> None:
    """Dependency that requires karma system to be enabled."""
    settings = get_settings()
    if not settings.feature_karma:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Karma system is not currently available",
        )


def require_cloud_sync() -> None:
    """Dependency that requires cloud sync to be enabled."""
    settings = get_settings()
    if not settings.feature_cloud_sync:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cloud sync is not currently available",
        )


# =============================================================================
# Database Session
# =============================================================================


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


async def get_current_user_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
) -> User:
    """
    Get the current user for WebSocket connections.
    Token is passed as query parameter: ws://host/ws/jobs?token=<jwt>
    """
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        raise HTTPException(status_code=401, detail="Missing token")

    async for session in get_session():
        auth_service = AuthService(session)
        user = await auth_service.get_user_from_token(token)

        if user is None:
            await websocket.close(code=4001, reason="Invalid authentication token")
            raise HTTPException(status_code=401, detail="Invalid token")

        return user

    raise HTTPException(status_code=500, detail="Database error")


async def get_redis() -> "Redis":
    """
    Get Redis connection for pub/sub operations.
    """
    from app.db.redis import get_redis as get_redis_client

    return await get_redis_client()


async def get_rbac_service(
    session: AsyncSession = Depends(get_db_session),
) -> "RBACService":
    """
    Get RBAC service instance for permission checks.
    """
    from app.services.rbac import RBACService

    return RBACService(session)
