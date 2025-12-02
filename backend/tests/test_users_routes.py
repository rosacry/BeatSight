"""Comprehensive tests for users API routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user, get_db_session
from app.models.user import User


# =============================================================================
# Test Fixtures
# =============================================================================

def create_mock_user(
    user_id: uuid.UUID | None = None,
    email: str = "test@example.com",
    display_name: str = "Test User",
    email_verified: bool = True,
    karma_score: int = 100,
    hashed_password: str | None = "hashed_password_123",
) -> MagicMock:
    """Create a mock user object."""
    user = MagicMock(spec=User)
    user.id = user_id or uuid.uuid4()
    user.email = email
    user.display_name = display_name
    user.email_verified = email_verified
    user.karma_score = karma_score
    user.hashed_password = hashed_password
    user.created_at = datetime.utcnow()
    return user


def create_mock_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


# =============================================================================
# Test Get Current User Profile
# =============================================================================

class TestGetCurrentUserProfile:
    """Tests for GET /users/me endpoint."""

    def test_get_profile_success(self):
        """Test successfully getting current user profile."""
        mock_user = create_mock_user()
        
        def override_get_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = override_get_user
        
        try:
            client = TestClient(app)
            response = client.get("/api/users/me")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(mock_user.id)
            assert data["email"] == mock_user.email
            assert data["display_name"] == mock_user.display_name
            assert data["email_verified"] == mock_user.email_verified
            assert data["karma_score"] == mock_user.karma_score
        finally:
            app.dependency_overrides.clear()

    def test_get_profile_unauthorized(self):
        """Test getting profile without authentication."""
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/users/me")
        
        # Should return 401 or 403 when not authenticated
        assert response.status_code in [401, 403]

    def test_get_profile_returns_all_fields(self):
        """Test that all expected fields are returned."""
        mock_user = create_mock_user(
            email_verified=False,
            karma_score=500,
        )
        
        def override_get_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = override_get_user
        
        try:
            client = TestClient(app)
            response = client.get("/api/users/me")
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify all expected fields are present
            required_fields = ["id", "email", "display_name", "email_verified", "karma_score", "created_at"]
            for field in required_fields:
                assert field in data
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Test Update Current User
# =============================================================================

class TestUpdateCurrentUser:
    """Tests for PATCH /users/me endpoint."""

    def test_update_display_name_success(self):
        """Test successfully updating display name."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        # Track display_name changes
        original_name = mock_user.display_name
        
        async def refresh_mock(user):
            pass
        mock_session.refresh = refresh_mock
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.patch(
                "/api/users/me",
                json={"display_name": "New Name"}
            )
            
            assert response.status_code == 200
            # Verify the user's display_name was updated
            assert mock_user.display_name == "New Name"
        finally:
            app.dependency_overrides.clear()

    def test_update_empty_request(self):
        """Test update with empty request body."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        async def refresh_mock(user):
            pass
        mock_session.refresh = refresh_mock
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.patch(
                "/api/users/me",
                json={}
            )
            
            # Empty update should still succeed
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_update_display_name_too_short(self):
        """Test update with display name too short."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.patch(
                "/api/users/me",
                json={"display_name": "A"}  # min_length=2
            )
            
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_update_display_name_too_long(self):
        """Test update with display name too long."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.patch(
                "/api/users/me",
                json={"display_name": "A" * 121}  # max_length=120
            )
            
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_update_unauthorized(self):
        """Test update without authentication."""
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.patch(
            "/api/users/me",
            json={"display_name": "New Name"}
        )
        
        assert response.status_code in [401, 403]


# =============================================================================
# Test Change Password
# =============================================================================

class TestChangePassword:
    """Tests for POST /users/me/password endpoint."""

    def test_change_password_success(self):
        """Test successfully changing password."""
        # Create user with a valid bcrypt hash
        import bcrypt
        current_password = "current_password_123"
        hashed = bcrypt.hashpw(current_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        mock_user = create_mock_user(hashed_password=hashed)
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.post(
                "/api/users/me/password",
                json={
                    "current_password": current_password,
                    "new_password": "new_secure_password_456"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Password changed successfully"
        finally:
            app.dependency_overrides.clear()

    def test_change_password_oauth_user(self):
        """Test changing password for OAuth user (no password set)."""
        mock_user = create_mock_user(hashed_password=None)  # OAuth user
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.post(
                "/api/users/me/password",
                json={
                    "current_password": "any_password",
                    "new_password": "new_password_123"
                }
            )
            
            assert response.status_code == 400
            assert "OAuth users" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_change_password_incorrect_current(self):
        """Test changing password with incorrect current password."""
        import bcrypt
        correct_password = "correct_password"
        hashed = bcrypt.hashpw(correct_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        mock_user = create_mock_user(hashed_password=hashed)
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.post(
                "/api/users/me/password",
                json={
                    "current_password": "wrong_password",
                    "new_password": "new_password_123"
                }
            )
            
            assert response.status_code == 400
            assert "incorrect" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_change_password_same_as_current(self):
        """Test changing password to same as current."""
        import bcrypt
        password = "my_password_123"
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        mock_user = create_mock_user(hashed_password=hashed)
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.post(
                "/api/users/me/password",
                json={
                    "current_password": password,
                    "new_password": password  # Same password
                }
            )
            
            assert response.status_code == 400
            assert "different" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_change_password_too_short(self):
        """Test changing password with new password too short."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.post(
                "/api/users/me/password",
                json={
                    "current_password": "current",
                    "new_password": "short"  # min_length=8
                }
            )
            
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_change_password_unauthorized(self):
        """Test changing password without authentication."""
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/users/me/password",
            json={
                "current_password": "current",
                "new_password": "new_password_123"
            }
        )
        
        assert response.status_code in [401, 403]


# =============================================================================
# Test Delete Account
# =============================================================================

class TestDeleteAccount:
    """Tests for DELETE /users/me endpoint."""

    def test_delete_account_success(self):
        """Test successfully deleting account."""
        import bcrypt
        password = "my_password_123"
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        mock_user = create_mock_user(hashed_password=hashed)
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.request(
                "DELETE",
                "/api/users/me",
                json={
                    "confirmation": "DELETE",
                    "password": password
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Account deleted successfully"
        finally:
            app.dependency_overrides.clear()

    def test_delete_account_oauth_user(self):
        """Test deleting OAuth user account (no password verification needed)."""
        mock_user = create_mock_user(hashed_password=None)  # OAuth user
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.request(
                "DELETE",
                "/api/users/me",
                json={
                    "confirmation": "DELETE",
                    "password": ""  # Empty for OAuth users
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Account deleted successfully"
        finally:
            app.dependency_overrides.clear()

    def test_delete_account_wrong_confirmation(self):
        """Test deleting account with wrong confirmation text."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.request(
                "DELETE",
                "/api/users/me",
                json={
                    "confirmation": "delete",  # Wrong case
                    "password": "password123"
                }
            )
            
            assert response.status_code == 400
            assert "DELETE" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_delete_account_wrong_password(self):
        """Test deleting account with wrong password."""
        import bcrypt
        password = "correct_password"
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        mock_user = create_mock_user(hashed_password=hashed)
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.request(
                "DELETE",
                "/api/users/me",
                json={
                    "confirmation": "DELETE",
                    "password": "wrong_password"
                }
            )
            
            assert response.status_code == 400
            assert "incorrect" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_delete_account_missing_confirmation(self):
        """Test deleting account without confirmation field."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.request(
                "DELETE",
                "/api/users/me",
                json={
                    "password": "password123"
                }
            )
            
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    def test_delete_account_unauthorized(self):
        """Test deleting account without authentication."""
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.request(
            "DELETE",
            "/api/users/me",
            json={
                "confirmation": "DELETE",
                "password": "password123"
            }
        )
        
        assert response.status_code in [401, 403]


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestUserEdgeCases:
    """Edge case tests for user routes."""

    def test_user_with_special_characters_in_name(self):
        """Test user with special characters in display name."""
        mock_user = create_mock_user(display_name="User™ 测试 🎵")
        
        def override_get_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = override_get_user
        
        try:
            client = TestClient(app)
            response = client.get("/api/users/me")
            
            assert response.status_code == 200
            data = response.json()
            assert data["display_name"] == "User™ 测试 🎵"
        finally:
            app.dependency_overrides.clear()

    def test_update_with_unicode_name(self):
        """Test updating display name with unicode characters."""
        mock_user = create_mock_user()
        mock_session = create_mock_session()
        
        async def refresh_mock(user):
            pass
        mock_session.refresh = refresh_mock
        
        def override_get_user():
            return mock_user
        
        def override_get_session():
            return mock_session
        
        app.dependency_overrides[get_current_user] = override_get_user
        app.dependency_overrides[get_db_session] = override_get_session
        
        try:
            client = TestClient(app)
            response = client.patch(
                "/api/users/me",
                json={"display_name": "新しい名前"}  # Japanese characters
            )
            
            assert response.status_code == 200
            assert mock_user.display_name == "新しい名前"
        finally:
            app.dependency_overrides.clear()

    def test_user_with_zero_karma(self):
        """Test user profile with zero karma score."""
        mock_user = create_mock_user(karma_score=0)
        
        def override_get_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = override_get_user
        
        try:
            client = TestClient(app)
            response = client.get("/api/users/me")
            
            assert response.status_code == 200
            data = response.json()
            assert data["karma_score"] == 0
        finally:
            app.dependency_overrides.clear()

    def test_user_with_negative_karma(self):
        """Test user profile with negative karma score."""
        mock_user = create_mock_user(karma_score=-50)
        
        def override_get_user():
            return mock_user
        
        app.dependency_overrides[get_current_user] = override_get_user
        
        try:
            client = TestClient(app)
            response = client.get("/api/users/me")
            
            assert response.status_code == 200
            data = response.json()
            assert data["karma_score"] == -50
        finally:
            app.dependency_overrides.clear()
