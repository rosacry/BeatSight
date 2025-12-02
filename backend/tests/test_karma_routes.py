"""Comprehensive tests for karma API routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user, get_db_session, require_karma
from app.models.user import User
from app.services.karma import KarmaService, KarmaError


# =============================================================================
# Test Fixtures
# =============================================================================

def create_mock_user(user_id: uuid.UUID | None = None) -> MagicMock:
    """Create a mock user object."""
    user = MagicMock(spec=User)
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    user.display_name = "Test User"
    return user


def create_mock_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def override_require_karma():
    """Override require_karma to bypass feature flag check."""
    pass  # Do nothing - allow access


# =============================================================================
# Test Get My Karma
# =============================================================================

class TestGetMyKarma:
    """Tests for GET /karma/me endpoint."""

    def test_get_my_karma_success(self):
        """Test successfully getting user's karma."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        mock_stats = {
            "current_score": 150,
            "rank": 42,
            "daily_ai_quota": 10,
            "eligible_roles": ["fixer"],
            "current_roles": [],
            "breakdown": {}
        }
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "get_karma_stats", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_stats
                
                client = TestClient(app)
                response = client.get("/api/karma/me")
                
                assert response.status_code == 200
                data = response.json()
                assert data["user_id"] == str(mock_user.id)
                assert data["karma_score"] == 150
                assert data["rank"] == 42
                assert data["daily_ai_quota"] == 10
                assert data["eligible_roles"] == ["fixer"]
                assert data["current_roles"] == []
        finally:
            app.dependency_overrides.clear()

    def test_get_my_karma_unauthorized(self):
        """Test getting karma without authentication."""
        app.dependency_overrides.clear()
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/karma/me")
            
            assert response.status_code in [401, 403]
        finally:
            app.dependency_overrides.clear()

    def test_get_my_karma_feature_disabled(self):
        """Test getting karma when feature is disabled."""
        app.dependency_overrides.clear()
        # Don't override require_karma - let it check the feature flag
        
        client = TestClient(app, raise_server_exceptions=False)
        # May return 404 if karma feature is disabled
        response = client.get("/api/karma/me")
        
        # Either auth error or feature disabled
        assert response.status_code in [401, 403, 404]


# =============================================================================
# Test Get My Karma Stats
# =============================================================================

class TestGetMyKarmaStats:
    """Tests for GET /karma/me/stats endpoint."""

    def test_get_my_stats_success(self):
        """Test successfully getting detailed karma stats."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        mock_stats = {
            "current_score": 250,
            "rank": 15,
            "daily_ai_quota": 20,
            "eligible_roles": ["fixer", "verifier"],
            "current_roles": ["fixer"],
            "breakdown": {
                "vote_given": {"total": 50, "count": 50},
                "beatmap_verified": {"total": 200, "count": 20}
            }
        }
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "get_karma_stats", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_stats
                
                client = TestClient(app)
                response = client.get("/api/karma/me/stats")
                
                assert response.status_code == 200
                data = response.json()
                assert data["current_score"] == 250
                assert data["rank"] == 15
                assert len(data["breakdown"]) == 2
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Test Get My Karma History
# =============================================================================

class TestGetMyKarmaHistory:
    """Tests for GET /karma/me/history endpoint."""

    def test_get_history_success(self):
        """Test successfully getting karma history."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        mock_entry = MagicMock()
        mock_entry.id = uuid.uuid4()
        mock_entry.delta = 10
        mock_entry.reason_code = MagicMock()
        mock_entry.reason_code.value = "vote_given"
        mock_entry.related_entity_type = "vote"
        mock_entry.related_entity_id = uuid.uuid4()
        mock_entry.recorded_at = datetime.utcnow()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "get_karma_history", new_callable=AsyncMock) as mock_get, \
                 patch.object(KarmaService, "get_karma_history_count", new_callable=AsyncMock) as mock_count:
                mock_get.return_value = [mock_entry]
                mock_count.return_value = 1
                
                client = TestClient(app)
                response = client.get("/api/karma/me/history")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data["items"]) == 1
                assert data["total_count"] == 1
                assert data["items"][0]["delta"] == 10
                assert data["items"][0]["reason"] == "vote_given"
        finally:
            app.dependency_overrides.clear()

    def test_get_history_pagination(self):
        """Test karma history pagination."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "get_karma_history", new_callable=AsyncMock) as mock_get, \
                 patch.object(KarmaService, "get_karma_history_count", new_callable=AsyncMock) as mock_count:
                mock_get.return_value = []
                mock_count.return_value = 100
                
                client = TestClient(app)
                response = client.get("/api/karma/me/history?limit=20&offset=40")
                
                assert response.status_code == 200
                data = response.json()
                assert data["limit"] == 20
                assert data["offset"] == 40
        finally:
            app.dependency_overrides.clear()

    def test_get_history_invalid_pagination(self):
        """Test karma history with invalid pagination params."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            client = TestClient(app)
            
            # Test invalid limit
            response = client.get("/api/karma/me/history?limit=0")
            assert response.status_code == 422
            
            # Test limit too high
            response = client.get("/api/karma/me/history?limit=200")
            assert response.status_code == 422
            
            # Test negative offset
            response = client.get("/api/karma/me/history?offset=-1")
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Test Get My Quota
# =============================================================================

class TestGetMyQuota:
    """Tests for GET /karma/me/quota endpoint."""

    def test_get_quota_success(self):
        """Test successfully getting AI quota."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "get_user_karma", new_callable=AsyncMock) as mock_karma, \
                 patch.object(KarmaService, "get_daily_ai_quota", new_callable=AsyncMock) as mock_quota:
                mock_karma.return_value = 50
                mock_quota.return_value = 5
                
                client = TestClient(app)
                response = client.get("/api/karma/me/quota")
                
                assert response.status_code == 200
                data = response.json()
                assert data["karma_score"] == 50
                assert data["daily_quota"] == 5
                # Should show next tier info
                assert "next_tier_karma" in data
                assert "next_tier_quota" in data
        finally:
            app.dependency_overrides.clear()

    def test_get_quota_max_tier(self):
        """Test quota response when at max tier."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "get_user_karma", new_callable=AsyncMock) as mock_karma, \
                 patch.object(KarmaService, "get_daily_ai_quota", new_callable=AsyncMock) as mock_quota:
                mock_karma.return_value = 100000  # Very high karma
                mock_quota.return_value = 100
                
                client = TestClient(app)
                response = client.get("/api/karma/me/quota")
                
                assert response.status_code == 200
                data = response.json()
                # At max tier, next tier info may be None
                assert data["karma_score"] == 100000
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Test Get Leaderboard
# =============================================================================

class TestGetLeaderboard:
    """Tests for GET /karma/leaderboard endpoint."""

    def test_get_leaderboard_success(self):
        """Test successfully getting leaderboard."""
        mock_session = create_mock_session()
        
        entries = [
            (uuid.uuid4(), "TopPlayer", 5000),
            (uuid.uuid4(), "SecondPlace", 4500),
            (uuid.uuid4(), "ThirdPlace", 4000),
        ]
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "get_karma_leaderboard", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = entries
                
                client = TestClient(app)
                response = client.get("/api/karma/leaderboard")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data["entries"]) == 3
                assert data["entries"][0]["rank"] == 1
                assert data["entries"][0]["karma_score"] == 5000
                assert data["entries"][1]["rank"] == 2
                assert data["entries"][2]["rank"] == 3
        finally:
            app.dependency_overrides.clear()

    def test_get_leaderboard_pagination(self):
        """Test leaderboard pagination."""
        mock_session = create_mock_session()
        
        entries = [(uuid.uuid4(), f"Player{i}", 5000 - i * 100) for i in range(10)]
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "get_karma_leaderboard", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = entries
                
                client = TestClient(app)
                response = client.get("/api/karma/leaderboard?limit=10&offset=50")
                
                assert response.status_code == 200
                data = response.json()
                assert data["limit"] == 10
                assert data["offset"] == 50
                # Ranks should start at offset + 1
                assert data["entries"][0]["rank"] == 51
        finally:
            app.dependency_overrides.clear()

    def test_get_leaderboard_empty(self):
        """Test leaderboard when empty."""
        mock_session = create_mock_session()
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "get_karma_leaderboard", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = []
                
                client = TestClient(app)
                response = client.get("/api/karma/leaderboard")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data["entries"]) == 0
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Test Get Roles Info
# =============================================================================

class TestGetRolesInfo:
    """Tests for GET /karma/roles endpoint."""

    def test_get_roles_info_success(self):
        """Test successfully getting roles information."""
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            client = TestClient(app)
            response = client.get("/api/karma/roles")
            
            assert response.status_code == 200
            data = response.json()
            assert "roles" in data
            assert len(data["roles"]) > 0
            
            # Each role should have required fields
            for role in data["roles"]:
                assert "role" in role
                assert "min_karma" in role
        finally:
            app.dependency_overrides.clear()

    def test_get_roles_info_no_auth_required(self):
        """Test that roles info doesn't require authentication."""
        app.dependency_overrides.clear()
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            client = TestClient(app)
            response = client.get("/api/karma/roles")
            
            # Should succeed without auth
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Test Claim Role
# =============================================================================

class TestClaimRole:
    """Tests for POST /karma/me/roles/{role_code} endpoint."""

    def test_claim_role_requires_auth(self):
        """Test claiming role requires authentication."""
        app.dependency_overrides.clear()
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/api/karma/me/roles/fixer")
            
            assert response.status_code in [401, 403]
        finally:
            app.dependency_overrides.clear()

    def test_claim_role_invalid_code(self):
        """Test claiming role with invalid role code."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            client = TestClient(app)
            response = client.post("/api/karma/me/roles/invalid_role")
            
            assert response.status_code == 400
            assert "Invalid role code" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_claim_role_success(self):
        """Test successfully claiming a role."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "assign_role", new_callable=AsyncMock) as mock_assign:
                mock_assign.return_value = True
                
                client = TestClient(app)
                response = client.post("/api/karma/me/roles/fixer")
                
                assert response.status_code == 201
                data = response.json()
                assert "successfully" in data["message"]
        finally:
            app.dependency_overrides.clear()

    def test_claim_role_already_has(self):
        """Test claiming role user already has."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "assign_role", new_callable=AsyncMock) as mock_assign, \
                 patch.object(KarmaService, "get_eligible_roles", new_callable=AsyncMock) as mock_eligible, \
                 patch.object(KarmaService, "get_user_roles", new_callable=AsyncMock) as mock_roles:
                mock_assign.return_value = False
                mock_eligible.return_value = ["fixer"]
                mock_roles.return_value = ["fixer"]  # Already has role
                
                client = TestClient(app)
                response = client.post("/api/karma/me/roles/fixer")
                
                assert response.status_code == 409
                assert "already have" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_claim_role_insufficient_karma(self):
        """Test claiming role with insufficient karma."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "assign_role", new_callable=AsyncMock) as mock_assign, \
                 patch.object(KarmaService, "get_eligible_roles", new_callable=AsyncMock) as mock_eligible, \
                 patch.object(KarmaService, "get_user_roles", new_callable=AsyncMock) as mock_roles, \
                 patch.object(KarmaService, "get_user_karma", new_callable=AsyncMock) as mock_karma:
                mock_assign.return_value = False
                mock_eligible.return_value = []  # Not eligible
                mock_roles.return_value = []
                mock_karma.return_value = 10  # Low karma
                
                client = TestClient(app)
                response = client.post("/api/karma/me/roles/fixer")
                
                assert response.status_code == 403
                assert "Insufficient karma" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Test Get User Karma (Public)
# =============================================================================

class TestGetUserKarma:
    """Tests for GET /karma/users/{user_id} endpoint."""

    def test_get_user_karma_success(self):
        """Test successfully getting another user's karma."""
        user_id = uuid.uuid4()
        mock_session = create_mock_session()
        
        mock_stats = {
            "current_score": 300,
            "rank": 50,
            "daily_ai_quota": 15,
            "eligible_roles": ["fixer"],
            "current_roles": ["fixer"],
            "breakdown": {}
        }
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "get_user_karma", new_callable=AsyncMock) as mock_karma, \
                 patch.object(KarmaService, "get_karma_stats", new_callable=AsyncMock) as mock_stats_call:
                mock_karma.return_value = 300
                mock_stats_call.return_value = mock_stats
                
                client = TestClient(app)
                response = client.get(f"/api/karma/users/{user_id}")
                
                assert response.status_code == 200
                data = response.json()
                assert data["user_id"] == str(user_id)
                assert data["karma_score"] == 300
        finally:
            app.dependency_overrides.clear()

    def test_get_user_karma_not_found(self):
        """Test getting karma for non-existent user."""
        user_id = uuid.uuid4()
        mock_session = create_mock_session()
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "get_user_karma", new_callable=AsyncMock) as mock_karma:
                mock_karma.side_effect = KarmaError("User not found")
                
                client = TestClient(app)
                response = client.get(f"/api/karma/users/{user_id}")
                
                assert response.status_code == 404
                assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_get_user_karma_invalid_uuid(self):
        """Test getting karma with invalid user UUID."""
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            client = TestClient(app)
            response = client.get("/api/karma/users/invalid-uuid")
            
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_get_user_karma_no_auth_required(self):
        """Test that public user karma doesn't require auth."""
        user_id = uuid.uuid4()
        mock_session = create_mock_session()
        
        mock_stats = {
            "current_score": 100,
            "rank": 100,
            "daily_ai_quota": 5,
            "eligible_roles": [],
            "current_roles": [],
            "breakdown": {}
        }
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides.clear()
        app.dependency_overrides[get_db_session] = override_get_session
        app.dependency_overrides[require_karma] = override_require_karma
        
        try:
            with patch.object(KarmaService, "get_user_karma", new_callable=AsyncMock) as mock_karma, \
                 patch.object(KarmaService, "get_karma_stats", new_callable=AsyncMock) as mock_stats_call:
                mock_karma.return_value = 100
                mock_stats_call.return_value = mock_stats
                
                client = TestClient(app)
                response = client.get(f"/api/karma/users/{user_id}")
                
                # Should succeed without auth
                assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()
