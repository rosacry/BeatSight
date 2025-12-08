"""Authentication service with JWT token management."""

from __future__ import annotations

import logging
import uuid
import warnings
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

# Suppress passlib bcrypt version warning before importing CryptContext
# This warning appears because passlib hasn't been updated for bcrypt 4.1+
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message=".*bcrypt.*")
    from passlib.context import CryptContext

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User

settings = get_settings()

# Suppress passlib's internal bcrypt warning at runtime
logging.getLogger("passlib").setLevel(logging.ERROR)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service for authentication and token management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password for storage."""
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(
        user_id: uuid.UUID,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create a JWT access token."""
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=settings.access_token_expires_minutes)
        )
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "type": "access",
        }
        return jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

    @staticmethod
    def create_refresh_token(
        user_id: uuid.UUID,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create a JWT refresh token."""
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(days=settings.refresh_token_expires_days)
        )
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "type": "refresh",
        }
        return jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

    @staticmethod
    def decode_token(token: str) -> dict | None:
        """Decode and validate a JWT token. Returns payload or None if invalid."""
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            return payload
        except JWTError:
            return None

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        """Retrieve a user by their ID."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        """Retrieve a user by their email address."""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def authenticate_user(self, email: str, password: str) -> User | None:
        """Authenticate a user by email and password."""
        user = await self.get_user_by_email(email)
        if not user or not user.hashed_password:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

    async def get_user_from_token(self, token: str) -> User | None:
        """Get user from a valid access token."""
        payload = self.decode_token(token)
        if payload is None:
            return None

        if payload.get("type") != "access":
            return None

        user_id_str = payload.get("sub")
        if not user_id_str:
            return None

        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError:
            return None

        return await self.get_user_by_id(user_id)
