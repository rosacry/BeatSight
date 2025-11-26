"""Tests for authentication endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.services.email import get_email_service


# Suppress warnings from unittest.mock's internal handling of async mocks
# This is a known issue: https://github.com/python/cpython/issues/100572
pytestmark = pytest.mark.filterwarnings(
    "ignore:coroutine 'AsyncMockMixin._execute_mock_call' was never awaited:RuntimeWarning"
)


class TestForgotPassword:
    """Tests for forgot password endpoint."""

    def test_forgot_password_success(self):
        """Test forgot password returns success message."""
        client = TestClient(app)
        
        with patch("app.api.routes.auth.AuthService") as MockAuthService:
            # Mock getting user by email
            mock_service = AsyncMock()
            mock_user = MagicMock(spec=User)
            mock_user.id = uuid4()
            mock_user.email = "test@example.com"
            mock_user.display_name = "Test User"
            mock_service.get_user_by_email.return_value = mock_user
            MockAuthService.return_value = mock_service
            
            response = client.post(
                "/api/auth/forgot-password",
                json={"email": "test@example.com"},
            )
            
        assert response.status_code == 200
        data = response.json()
        assert "password reset link" in data["message"].lower()

    def test_forgot_password_nonexistent_email(self):
        """Test forgot password for non-existent email (should still succeed)."""
        client = TestClient(app)
        
        with patch("app.api.routes.auth.AuthService") as MockAuthService:
            mock_service = AsyncMock()
            mock_service.get_user_by_email.return_value = None
            MockAuthService.return_value = mock_service
            
            response = client.post(
                "/api/auth/forgot-password",
                json={"email": "nobody@example.com"},
            )
            
        # Should return success to prevent email enumeration
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_forgot_password_invalid_email_format(self):
        """Test forgot password with invalid email format."""
        client = TestClient(app)
        
        response = client.post(
            "/api/auth/forgot-password",
            json={"email": "not-an-email"},
        )
        
        assert response.status_code == 422


class TestResetPassword:
    """Tests for password reset endpoint."""

    def test_reset_password_invalid_token(self):
        """Test password reset fails with invalid token."""
        client = TestClient(app)
        
        with patch("app.api.routes.auth.get_email_service") as mock_get_email:
            mock_email_service = MagicMock()
            mock_email_service.verify_password_reset_token.return_value = None
            mock_get_email.return_value = mock_email_service
            
            response = client.post(
                "/api/auth/reset-password",
                json={
                    "token": "invalid-token",
                    "new_password": "NewSecurePassword123",
                },
            )
            
        assert response.status_code == 400
        assert "Invalid or expired" in response.json()["detail"]

    def test_reset_password_weak_password(self):
        """Test password reset fails with weak password."""
        client = TestClient(app)
        
        response = client.post(
            "/api/auth/reset-password",
            json={
                "token": "some-token",
                "new_password": "short",
            },
        )
        
        # Pydantic validation should catch this
        assert response.status_code == 422

    def test_reset_password_success(self):
        """Test successful password reset."""
        client = TestClient(app)
        user_id = uuid4()
        
        with patch("app.api.routes.auth.get_email_service") as mock_get_email, \
             patch("app.api.routes.auth.AuthService") as MockAuthService:
            
            # Mock email service token verification
            mock_email_service = MagicMock()
            mock_email_service.verify_password_reset_token.return_value = {
                "sub": str(user_id),
                "email": "test@example.com",
                "type": "password_reset",
            }
            mock_get_email.return_value = mock_email_service
            
            # Mock auth service
            mock_auth = AsyncMock()
            mock_user = MagicMock(spec=User)
            mock_user.id = user_id
            mock_user.email = "test@example.com"
            mock_auth.get_user_by_id.return_value = mock_user
            mock_auth.hash_password.return_value = "hashed_password"
            MockAuthService.return_value = mock_auth
            
            response = client.post(
                "/api/auth/reset-password",
                json={
                    "token": "valid-token",
                    "new_password": "NewSecurePassword123",
                },
            )
            
        assert response.status_code == 200
        data = response.json()
        assert "reset successfully" in data["message"].lower()

    def test_reset_password_user_not_found(self):
        """Test password reset fails when user not found."""
        client = TestClient(app)
        user_id = uuid4()
        
        with patch("app.api.routes.auth.get_email_service") as mock_get_email, \
             patch("app.api.routes.auth.AuthService") as MockAuthService:
            
            mock_email_service = MagicMock()
            mock_email_service.verify_password_reset_token.return_value = {
                "sub": str(user_id),
                "email": "test@example.com",
                "type": "password_reset",
            }
            mock_get_email.return_value = mock_email_service
            
            mock_auth = AsyncMock()
            mock_auth.get_user_by_id.return_value = None
            MockAuthService.return_value = mock_auth
            
            response = client.post(
                "/api/auth/reset-password",
                json={
                    "token": "valid-token",
                    "new_password": "NewSecurePassword123",
                },
            )
            
        assert response.status_code == 400
        assert "User not found" in response.json()["detail"]

    def test_reset_password_email_mismatch(self):
        """Test password reset fails if token email doesn't match user."""
        client = TestClient(app)
        user_id = uuid4()
        
        with patch("app.api.routes.auth.get_email_service") as mock_get_email, \
             patch("app.api.routes.auth.AuthService") as MockAuthService:
            
            # Token has different email
            mock_email_service = MagicMock()
            mock_email_service.verify_password_reset_token.return_value = {
                "sub": str(user_id),
                "email": "wrong@example.com",
                "type": "password_reset",
            }
            mock_get_email.return_value = mock_email_service
            
            mock_auth = AsyncMock()
            mock_user = MagicMock(spec=User)
            mock_user.id = user_id
            mock_user.email = "test@example.com"  # Different from token
            mock_auth.get_user_by_id.return_value = mock_user
            MockAuthService.return_value = mock_auth
            
            response = client.post(
                "/api/auth/reset-password",
                json={
                    "token": "valid-token",
                    "new_password": "NewSecurePassword123",
                },
            )
            
        assert response.status_code == 400
        assert "does not match" in response.json()["detail"]


class TestEmailService:
    """Tests for email service."""

    def test_password_reset_token_creation(self):
        """Test password reset token creation and verification."""
        email_service = get_email_service()
        user_id = uuid4()
        
        token = email_service._create_password_reset_token(
            user_id, "test@example.com"
        )

        payload = email_service.verify_password_reset_token(token)
        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "password_reset"

    def test_email_verification_token_creation(self):
        """Test email verification token creation and verification."""
        email_service = get_email_service()
        user_id = uuid4()
        
        token = email_service._create_email_verification_token(
            user_id, "test@example.com"
        )

        payload = email_service.verify_email_verification_token(token)
        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "email_verification"

    def test_invalid_token_verification(self):
        """Test that invalid tokens are rejected."""
        email_service = get_email_service()
        
        payload = email_service.verify_password_reset_token("invalid-token")
        assert payload is None

    def test_wrong_token_type_rejected(self):
        """Test that using wrong token type fails."""
        email_service = get_email_service()
        user_id = uuid4()
        
        # Create email verification token
        email_token = email_service._create_email_verification_token(
            user_id, "test@example.com"
        )
        
        # Try to use it as password reset token
        payload = email_service.verify_password_reset_token(email_token)
        assert payload is None

    def test_is_configured_without_api_key(self):
        """Test is_configured returns False without API key."""
        with patch("app.services.email.get_settings") as mock_settings:
            settings = MagicMock()
            settings.sendgrid_api_key = None
            settings.email_from = "noreply@test.com"
            settings.frontend_url = "http://localhost"
            settings.jwt_secret_key = "test-secret"
            settings.jwt_algorithm = "HS256"
            mock_settings.return_value = settings
            
            from app.services.email import EmailService
            service = EmailService()
            assert service.is_configured() is False

    def test_is_configured_with_api_key(self):
        """Test is_configured returns True with API key."""
        with patch("app.services.email.get_settings") as mock_settings:
            settings = MagicMock()
            settings.sendgrid_api_key = "SG.test_key"
            settings.email_from = "noreply@test.com"
            settings.frontend_url = "http://localhost"
            settings.jwt_secret_key = "test-secret"
            settings.jwt_algorithm = "HS256"
            mock_settings.return_value = settings
            
            from app.services.email import EmailService
            service = EmailService()
            assert service.is_configured() is True


class TestRegisterWithWelcomeEmail:
    """Tests for registration with welcome email."""

    @pytest.mark.asyncio
    async def test_register_sends_welcome_email(self):
        """Test that registration triggers welcome email via background task."""
        from app.api.routes.auth import register, RegisterRequest
        from fastapi import BackgroundTasks
        
        # Create mock session with proper sync/async method configuration
        mock_session = MagicMock()
        mock_session.add = MagicMock()  # sync method
        mock_session.commit = AsyncMock()  # async method
        mock_session.refresh = AsyncMock()  # async method
        
        # Create mock user that session.refresh will "populate"
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid4()
        mock_user.email = "newuser@example.com"
        mock_user.display_name = "New User"
        
        async def mock_refresh(user):
            user.id = mock_user.id
            user.email = mock_user.email
            user.display_name = mock_user.display_name
        
        mock_session.refresh = mock_refresh
        
        # Track background tasks
        background_tasks = BackgroundTasks()
        tasks_added = []
        def track_add_task(func, *args, **kwargs):
            tasks_added.append((func, args, kwargs))
        background_tasks.add_task = track_add_task
        
        with patch("app.api.routes.auth.AuthService") as MockAuthService, \
             patch("app.api.routes.auth.get_email_service") as mock_get_email:
            
            # Mock auth service
            mock_auth = MagicMock()
            mock_auth.get_user_by_email = AsyncMock(return_value=None)  # No existing user
            mock_auth.hash_password.return_value = "hashed_password"
            mock_auth.create_access_token.return_value = "access_token"
            mock_auth.create_refresh_token.return_value = "refresh_token"
            MockAuthService.return_value = mock_auth
            
            # Mock email service
            mock_email = MagicMock()
            mock_email.send_welcome = AsyncMock()
            mock_get_email.return_value = mock_email
            
            # Create request
            request = RegisterRequest(
                email="newuser@example.com",
                password="SecurePassword123",
                display_name="New User",
            )
            
            # Call register directly (bypassing TestClient)
            result = await register(request, background_tasks, mock_session)
        
        # Verify tokens returned
        assert result.access_token == "access_token"
        assert result.refresh_token == "refresh_token"
        
        # Verify background task was added for welcome email
        assert len(tasks_added) == 1
        task_func, task_args, _ = tasks_added[0]
        assert task_func == mock_email.send_welcome
        assert task_args == ("newuser@example.com", "New User")
