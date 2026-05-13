"""Focused tests for public users profile/hover-card endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_db_session, get_current_user_optional
from app.api.routes import users as users_routes
from app.main import app
from app.models.user import User


def _make_public_user() -> MagicMock:
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.user_number = 123
    user.display_name = "Public User"
    user.avatar_url = None
    user.banner_url = None
    user.karma_score = 42
    user.created_at = datetime.now(timezone.utc)
    user.email_verified = True
    user.restriction_level = "none"
    user.country_code = "US"
    user.bio = "bio"
    user.roles = []
    user.tags = []
    user.last_active_at = datetime.now(timezone.utc)
    user.karma_score_achieved_at = datetime.now(timezone.utc)
    return user


class _MockResult:
    def __init__(
        self,
        *,
        scalar_value: int | None = None,
        one_value: object | None = None,
        scalar_one_or_none_value: object | None = None,
    ) -> None:
        self._scalar_value = scalar_value
        self._one_value = one_value
        self._scalar_one_or_none_value = scalar_one_or_none_value

    def scalar(self):
        return self._scalar_value

    def one(self):
        return self._one_value

    def scalar_one_or_none(self):
        return self._scalar_one_or_none_value


def test_get_user_hover_card_sets_online_from_recent_activity(monkeypatch) -> None:
    user = _make_public_user()
    user.last_active_at = datetime.now(timezone.utc) - timedelta(minutes=2)

    async def fake_get_user_by_identifier_with_roles(_user_id: str, _session):
        return user

    async def override_session():
        return AsyncMock()

    def override_current_user_optional():
        return None

    monkeypatch.setattr(
        users_routes,
        "_get_user_by_identifier_with_roles",
        fake_get_user_by_identifier_with_roles,
    )

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_current_user_optional] = override_current_user_optional

    try:
        client = TestClient(app)
        response = client.get("/api/users/123/hover-card")
        assert response.status_code == 200
        data = response.json()
        assert data["is_online"] is True
        assert data["user_number"] == 123
    finally:
        app.dependency_overrides.clear()


def test_get_public_user_profile_returns_verified_map_and_achievement_counts(
    monkeypatch,
) -> None:
    user = _make_public_user()
    user.last_active_at = datetime.now(timezone.utc) - timedelta(minutes=20)

    async def fake_get_user_for_profile(_user_id: str, _session):
        return user

    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _MockResult(scalar_value=5),  # songs uploaded
            _MockResult(
                one_value=SimpleNamespace(maps_generated_count=9, maps_verified_count=2)
            ),
            _MockResult(scalar_value=7),  # forum posts
            _MockResult(scalar_value=11),  # contribution count
            _MockResult(scalar_value=3),  # achievements count
            _MockResult(scalar_value=1),  # karma rank users above
            _MockResult(scalar_value=0),  # approved contributions
            _MockResult(scalar_one_or_none_value=None),  # nth contribution ts
        ]
    )

    async def override_session():
        return session

    def override_current_user_optional():
        return None

    monkeypatch.setattr(users_routes, "_get_user_for_profile", fake_get_user_for_profile)

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_current_user_optional] = override_current_user_optional

    try:
        client = TestClient(app)
        response = client.get("/api/users/123/profile")
        assert response.status_code == 200
        data = response.json()
        assert data["songs_uploaded"] == 5
        assert data["maps_generated"] == 9
        assert data["maps_verified"] == 2
        assert data["achievements_count"] == 3
        assert data["forum_posts"] == 7
        assert data["contribution_count"] == 11
    finally:
        app.dependency_overrides.clear()
