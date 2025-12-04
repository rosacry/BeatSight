"""Pytest configuration and shared fixtures for backend tests.

Created: December 3, 2025
References: ENGINEERING_ACTION_TRACKER.md item 4.9

This module provides:
- Test database setup with SQLite (in-memory)
- Test client fixtures
- Mock services
- Authenticated user fixtures
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.main import app
from app.models.user import User
from app.models.song import Song, SongStatus
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus


# Suppress coroutine warnings from unittest.mock
pytestmark = pytest.mark.filterwarnings(
    "ignore:coroutine 'AsyncMockMixin._execute_mock_call' was never awaited:RuntimeWarning"
)


# =============================================================================
# Event Loop Configuration
# =============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create a single event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def test_engine() -> AsyncEngine:
    """Create a test database engine using SQLite in-memory."""
    # Use SQLite for testing (synchronous but works for unit tests)
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    return engine


@pytest_asyncio.fixture(scope="function")
async def test_db(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create and populate a test database for each test."""
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session = async_sessionmaker(
        test_engine, expire_on_commit=False, autoflush=False
    )

    async with async_session() as session:
        yield session

    # Cleanup - drop tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# =============================================================================
# Test User Fixtures
# =============================================================================


@pytest.fixture
def test_user_id() -> str:
    """Generate a unique test user ID."""
    return str(uuid4())


@pytest.fixture
def mock_user(test_user_id: str) -> User:
    """Create a mock User object for testing."""
    user = MagicMock(spec=User)
    user.id = test_user_id
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.password_hash = "hashed_password"
    user.is_active = True
    user.is_verified = True
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    user.roles = ["user"]
    return user


@pytest.fixture
def mock_admin_user() -> User:
    """Create a mock admin User object."""
    user = MagicMock(spec=User)
    user.id = str(uuid4())
    user.email = "admin@example.com"
    user.display_name = "Admin User"
    user.password_hash = "hashed_password"
    user.is_active = True
    user.is_verified = True
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    user.roles = ["user", "admin"]
    return user


@pytest.fixture
def mock_pro_subscription(mock_user: User) -> Subscription:
    """Create a mock Pro subscription."""
    sub = MagicMock(spec=Subscription)
    sub.id = str(uuid4())
    sub.user_id = mock_user.id
    sub.plan_code = SubscriptionPlan.PRO_MONTHLY
    sub.status = SubscriptionStatus.ACTIVE
    sub.current_period_end = datetime.now(timezone.utc)
    sub.created_at = datetime.now(timezone.utc)
    return sub


# =============================================================================
# Test Song Fixtures
# =============================================================================


@pytest.fixture
def mock_song(mock_user: User) -> Song:
    """Create a mock Song object."""
    song = MagicMock(spec=Song)
    song.id = str(uuid4())
    song.user_id = mock_user.id
    song.title = "Test Song"
    song.artist = "Test Artist"
    song.duration = 180.0
    song.status = SongStatus.PENDING
    song.audio_url = "https://storage.example.com/songs/test.mp3"
    song.created_at = datetime.now(timezone.utc)
    song.updated_at = datetime.now(timezone.utc)
    return song


# =============================================================================
# HTTP Client Fixtures
# =============================================================================


@pytest.fixture
def client() -> TestClient:
    """Create a synchronous test client."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for async endpoint testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers(mock_user: User) -> dict[str, str]:
    """Create authentication headers for a test user."""
    # Mock token - in real tests would be generated properly
    return {"Authorization": "Bearer test-token-for-user"}


@pytest.fixture
def admin_auth_headers(mock_admin_user: User) -> dict[str, str]:
    """Create authentication headers for an admin user."""
    return {"Authorization": "Bearer test-token-for-admin"}


# =============================================================================
# Mock Service Fixtures
# =============================================================================


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.scalars = AsyncMock()
    session.delete = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.setex = AsyncMock()
    redis.delete = AsyncMock()
    redis.incr = AsyncMock()
    redis.expire = AsyncMock()
    redis.ttl = AsyncMock(return_value=-1)
    redis.exists = AsyncMock(return_value=0)
    redis.hget = AsyncMock(return_value=None)
    redis.hset = AsyncMock()
    redis.hdel = AsyncMock()
    redis.pipeline = MagicMock()
    return redis


@pytest.fixture
def mock_storage_service() -> AsyncMock:
    """Create a mock storage service."""
    storage = AsyncMock()
    storage.upload_file = AsyncMock(return_value="https://storage.example.com/test-file")
    storage.generate_presigned_url = AsyncMock(
        return_value="https://storage.example.com/presigned-url"
    )
    storage.delete_file = AsyncMock()
    return storage


@pytest.fixture
def mock_email_service() -> AsyncMock:
    """Create a mock email service."""
    email = AsyncMock()
    email.send_verification_email = AsyncMock()
    email.send_password_reset_email = AsyncMock()
    email.send_welcome_email = AsyncMock()
    return email


@pytest.fixture
def mock_stripe_service() -> AsyncMock:
    """Create a mock Stripe service."""
    stripe = AsyncMock()
    stripe.create_checkout_session = AsyncMock(return_value={"id": "cs_test_123"})
    stripe.create_portal_session = AsyncMock(return_value={"url": "https://portal.stripe.com"})
    stripe.cancel_subscription = AsyncMock()
    return stripe


# =============================================================================
# Helper Functions
# =============================================================================


def make_mock_result(items: list) -> MagicMock:
    """Create a mock SQLAlchemy result with given items."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    result.scalar_one_or_none.return_value = items[0] if items else None
    result.scalar.return_value = items[0] if items else None
    return result


def make_mock_paginated_result(items: list, total: int = None) -> MagicMock:
    """Create a mock paginated result."""
    if total is None:
        total = len(items)
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    result.scalar.return_value = total
    return result
