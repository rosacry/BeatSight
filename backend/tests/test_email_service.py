"""Tests for email service.

Covers token verification, email sending, and template methods.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from jose import jwt

from app.services.email import EmailService


class TestEmailServiceInit:
    """Tests for EmailService initialization."""

    def test_init_loads_settings(self):
        """Test that settings are loaded on init."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = "test-key"
            mock_settings.return_value.email_from = "test@example.com"
            mock_settings.return_value.frontend_url = "https://test.com"
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
        
        assert service.api_key == "test-key"
        assert service.from_email == "test@example.com"

    def test_init_default_email(self):
        """Test default from email when not configured."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = None
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
        
        assert service.from_email == "noreply@beatsight.io"


class TestIsConfigured:
    """Tests for is_configured method."""

    def test_configured_with_api_key(self):
        """Test returns True when API key is set."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = "SG.test"
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = None
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
            assert service.is_configured() is True

    def test_not_configured_without_api_key(self):
        """Test returns False when API key is not set."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = None
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
            assert service.is_configured() is False


class TestCreatePasswordResetToken:
    """Tests for _create_password_reset_token method."""

    def test_creates_valid_token(self):
        """Test that a valid JWT token is created."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = None
            mock_settings.return_value.jwt_secret_key = "test_secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
            user_id = uuid.uuid4()
            email = "user@example.com"
            
            token = service._create_password_reset_token(user_id, email)
        
        # Decode and verify
        payload = jwt.decode(token, "test_secret", algorithms=["HS256"])
        assert payload["sub"] == str(user_id)
        assert payload["email"] == email
        assert payload["type"] == "password_reset"


class TestCreateEmailVerificationToken:
    """Tests for _create_email_verification_token method."""

    def test_creates_valid_token(self):
        """Test that a valid email verification JWT is created."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = None
            mock_settings.return_value.jwt_secret_key = "test_secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
            user_id = uuid.uuid4()
            email = "verify@example.com"
            
            token = service._create_email_verification_token(user_id, email)
        
        payload = jwt.decode(token, "test_secret", algorithms=["HS256"])
        assert payload["type"] == "email_verification"


class TestVerifyPasswordResetToken:
    """Tests for verify_password_reset_token method."""

    def test_valid_token(self):
        """Test verifying a valid password reset token."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = None
            mock_settings.return_value.jwt_secret_key = "test_secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
            user_id = uuid.uuid4()
            
            token = service._create_password_reset_token(user_id, "test@test.com")
            result = service.verify_password_reset_token(token)
        
        assert result is not None
        assert result["sub"] == str(user_id)
        assert result["type"] == "password_reset"

    def test_wrong_token_type(self):
        """Test that email verification token fails password reset verification."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = None
            mock_settings.return_value.jwt_secret_key = "test_secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
            
            # Create email verification token, try to use as password reset
            token = service._create_email_verification_token(uuid.uuid4(), "test@test.com")
            result = service.verify_password_reset_token(token)
        
        assert result is None

    def test_invalid_token(self):
        """Test verifying an invalid token returns None."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = None
            mock_settings.return_value.jwt_secret_key = "test_secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
            result = service.verify_password_reset_token("invalid.token.here")
        
        assert result is None


class TestVerifyEmailVerificationToken:
    """Tests for verify_email_verification_token method."""

    def test_valid_token(self):
        """Test verifying a valid email verification token."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = None
            mock_settings.return_value.jwt_secret_key = "test_secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
            user_id = uuid.uuid4()
            
            token = service._create_email_verification_token(user_id, "test@test.com")
            result = service.verify_email_verification_token(token)
        
        assert result is not None
        assert result["type"] == "email_verification"

    def test_wrong_token_type(self):
        """Test that password reset token fails email verification."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = None
            mock_settings.return_value.jwt_secret_key = "test_secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
            
            token = service._create_password_reset_token(uuid.uuid4(), "test@test.com")
            result = service.verify_email_verification_token(token)
        
        assert result is None


class TestSendEmail:
    """Tests for _send_email method."""

    @pytest.mark.asyncio
    async def test_not_configured_logs_and_returns_true(self):
        """Test email not sent when not configured, but returns success."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = None
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
        
        with patch("app.services.email.logger") as mock_logger:
            result = await service._send_email(
                "test@test.com",
                "Subject",
                "<p>HTML</p>",
            )
        
        assert result is True
        mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_sendgrid_success(self):
        """Test successful email sending via SendGrid."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = "SG.test"
            mock_settings.return_value.email_from = "from@test.com"
            mock_settings.return_value.frontend_url = "https://test.com"
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
        
        mock_sg = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg.send.return_value = mock_response
        
        with patch.dict("sys.modules", {"sendgrid": MagicMock(), "sendgrid.helpers.mail": MagicMock()}):
            with patch("sendgrid.SendGridAPIClient", return_value=mock_sg):
                result = await service._send_email(
                    "to@test.com",
                    "Test Subject",
                    "<p>Content</p>",
                    "Text content",
                )
        
        assert result is True

    @pytest.mark.asyncio
    async def test_sendgrid_error_status(self):
        """Test handling SendGrid error status codes."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = "SG.test"
            mock_settings.return_value.email_from = "from@test.com"
            mock_settings.return_value.frontend_url = "https://test.com"
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
        
        mock_sg = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400  # Error
        mock_sg.send.return_value = mock_response
        
        with patch.dict("sys.modules", {"sendgrid": MagicMock(), "sendgrid.helpers.mail": MagicMock()}):
            with patch("sendgrid.SendGridAPIClient", return_value=mock_sg):
                result = await service._send_email(
                    "to@test.com",
                    "Test",
                    "<p>Content</p>",
                )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_sendgrid_import_error(self):
        """Test handling missing sendgrid package."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = "SG.test"
            mock_settings.return_value.email_from = "from@test.com"
            mock_settings.return_value.frontend_url = "https://test.com"
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
        
        with patch("builtins.__import__", side_effect=ImportError("No sendgrid")):
            result = await service._send_email(
                "to@test.com",
                "Test",
                "<p>Content</p>",
            )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_sendgrid_exception(self):
        """Test handling SendGrid exception."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = "SG.test"
            mock_settings.return_value.email_from = "from@test.com"
            mock_settings.return_value.frontend_url = "https://test.com"
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
        
        with patch.dict("sys.modules", {"sendgrid": MagicMock(), "sendgrid.helpers.mail": MagicMock()}):
            with patch("sendgrid.SendGridAPIClient") as mock_client:
                mock_client.side_effect = Exception("Network error")
                
                result = await service._send_email(
                    "to@test.com",
                    "Test",
                    "<p>Content</p>",
                )
        
        assert result is False


class TestSendPasswordReset:
    """Tests for send_password_reset method."""

    @pytest.mark.asyncio
    async def test_sends_password_reset_email(self):
        """Test sending password reset email."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = "https://app.beatsight.io"
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
        
        with patch.object(service, "_send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            user_id = uuid.uuid4()
            result = await service.send_password_reset(
                user_id, "user@test.com", "TestUser"
            )
        
        assert result is True
        mock_send.assert_called_once()
        
        # Check email content includes user name and reset URL
        call_args = mock_send.call_args
        assert "TestUser" in call_args[0][2]  # HTML content
        assert "reset-password" in call_args[0][2]


class TestSendWelcome:
    """Tests for send_welcome method."""

    @pytest.mark.asyncio
    async def test_sends_welcome_email(self):
        """Test sending welcome email."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = "https://app.beatsight.io"
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
        
        with patch.object(service, "_send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            result = await service.send_welcome("new@user.com", "NewUser")
        
        assert result is True
        mock_send.assert_called_once()
        
        # Check subject includes welcome
        call_args = mock_send.call_args
        assert "Welcome" in call_args[0][1]


class TestSendEmailVerification:
    """Tests for send_email_verification method."""

    @pytest.mark.asyncio
    async def test_sends_verification_email(self):
        """Test sending email verification."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = "https://app.beatsight.io"
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"
            
            service = EmailService()
        
        with patch.object(service, "_send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            user_id = uuid.uuid4()
            result = await service.send_email_verification(
            user_id, "verify@test.com", "VerifyUser"
            )

        assert result is True


class TestSendSubscriptionConfirmation:
    """Tests for send_subscription_confirmation method."""

    @pytest.mark.asyncio
    async def test_sends_subscription_email(self):
        """Test sending subscription confirmation email."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = "https://app.beatsight.io"
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"

            service = EmailService()

        with patch.object(service, "_send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await service.send_subscription_confirmation(
                "sub@test.com", "SubUser", "Pro"
            )

        assert result is True

        # Check email mentions the plan
        call_args = mock_send.call_args
        assert "Pro" in call_args[0][2]  # HTML content contains plan name

    @pytest.mark.asyncio
    async def test_subscription_email_contains_features(self):
        """Test subscription email lists features."""
        with patch("app.services.email.get_settings") as mock_settings:
            mock_settings.return_value.sendgrid_api_key = None
            mock_settings.return_value.email_from = None
            mock_settings.return_value.frontend_url = "https://app.beatsight.io"
            mock_settings.return_value.jwt_secret_key = "secret"
            mock_settings.return_value.jwt_algorithm = "HS256"

            service = EmailService()

        with patch.object(service, "_send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            await service.send_subscription_confirmation(
                "sub@test.com", "SubUser", "Pro Monthly"
            )

        call_args = mock_send.call_args
        html_content = call_args[0][2]  # Third arg is HTML (to_email, subject, html, text)
        # Check key features are mentioned
        assert "quota" in html_content.lower() or "Subscription Confirmed" in html_content