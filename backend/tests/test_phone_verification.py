"""Tests for phone verification routes and service.

Tests cover:
- Sending verification codes (rate limiting, validation)
- Verifying codes (expiry, attempts, success)
- Karma bonus award when both email+phone verified
- Phone removal
"""

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.phone_verification import PhoneVerificationAttempt, PhoneVerificationCode
from app.models.user import User
from app.services.sms import SMSService, get_sms_service


class TestSMSService:
    """Tests for SMS service."""

    def test_generate_verification_code(self):
        """Should generate a 6-digit numeric code."""
        sms_service = SMSService()
        code = sms_service.generate_verification_code()
        
        assert len(code) == 6
        assert code.isdigit()

    def test_generate_verification_code_custom_length(self):
        """Should support custom code length."""
        sms_service = SMSService()
        code = sms_service.generate_verification_code(length=8)
        
        assert len(code) == 8
        assert code.isdigit()

    def test_normalize_phone_number_with_country_code(self):
        """Should preserve country code."""
        sms_service = SMSService()
        
        assert sms_service.normalize_phone_number("+14155551234") == "+14155551234"
        assert sms_service.normalize_phone_number("+442071234567") == "+442071234567"

    def test_normalize_phone_number_with_formatting(self):
        """Should strip formatting characters."""
        sms_service = SMSService()
        
        assert sms_service.normalize_phone_number("+1 (415) 555-1234") == "+14155551234"
        assert sms_service.normalize_phone_number("+1-415-555-1234") == "+14155551234"
        assert sms_service.normalize_phone_number("+1.415.555.1234") == "+14155551234"

    def test_normalize_phone_number_assumes_us(self):
        """Should assume US (+1) for 10-digit numbers without country code."""
        sms_service = SMSService()
        
        assert sms_service.normalize_phone_number("4155551234") == "+14155551234"
        assert sms_service.normalize_phone_number("(415) 555-1234") == "+14155551234"

    def test_validate_phone_number_valid(self):
        """Should accept valid phone numbers."""
        sms_service = SMSService()
        
        is_valid, error = sms_service.validate_phone_number("+14155551234")
        assert is_valid is True
        assert error == ""
        
        is_valid, error = sms_service.validate_phone_number("+442071234567")
        assert is_valid is True
        assert error == ""

    def test_validate_phone_number_too_short(self):
        """Should reject phone numbers that are too short."""
        sms_service = SMSService()
        
        is_valid, error = sms_service.validate_phone_number("+1234")
        assert is_valid is False
        assert "too short" in error.lower()

    def test_validate_phone_number_too_long(self):
        """Should reject phone numbers that are too long."""
        sms_service = SMSService()
        
        is_valid, error = sms_service.validate_phone_number("+1234567890123456789")
        assert is_valid is False
        assert "too long" in error.lower()

    def test_is_configured_without_credentials(self):
        """Should return False when Twilio is not configured."""
        with patch.object(SMSService, '__init__', lambda self: None):
            sms_service = SMSService()
            sms_service.account_sid = None
            sms_service.auth_token = None
            sms_service.from_number = None
            
            assert sms_service.is_configured() is False

    def test_is_configured_with_credentials(self):
        """Should return True when Twilio is configured."""
        with patch.object(SMSService, '__init__', lambda self: None):
            sms_service = SMSService()
            sms_service.account_sid = "test_sid"
            sms_service.auth_token = "test_token"
            sms_service.from_number = "+15005550006"
            
            assert sms_service.is_configured() is True

    @pytest.mark.asyncio
    async def test_send_verification_code_not_configured(self):
        """Should log and return True when not configured (dev mode)."""
        with patch.object(SMSService, '__init__', lambda self: None):
            sms_service = SMSService()
            sms_service.account_sid = None
            sms_service.auth_token = None
            sms_service.from_number = None
            
            result = await sms_service.send_verification_code("+14155551234", "123456")
            assert result is True  # Returns True in dev mode


class TestPhoneVerificationRoutes:
    """Tests for phone verification API routes."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user."""
        user = MagicMock(spec=User)
        user.id = uuid4()
        user.email = "test@example.com"
        user.email_verified = True
        user.phone_number = None
        user.phone_verified = False
        user.karma_score = 50
        return user

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.add = MagicMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_get_phone_status_no_phone(self, mock_user, mock_session):
        """Should return unverified status when no phone set."""
        from app.api.routes.phone import get_phone_status
        
        mock_session.execute.return_value.scalar.return_value = 0  # No rate limit hits
        
        with patch('app.api.routes.phone._check_rate_limit', return_value=(True, None)):
            response = await get_phone_status(mock_user, mock_session)
        
        assert response.phone_number is None
        assert response.phone_verified is False
        assert response.can_send_code is True

    @pytest.mark.asyncio
    async def test_get_phone_status_verified(self, mock_user, mock_session):
        """Should return verified status when phone is verified."""
        from app.api.routes.phone import get_phone_status
        
        mock_user.phone_number = "+14155551234"
        mock_user.phone_verified = True
        
        with patch('app.api.routes.phone._check_rate_limit', return_value=(True, None)):
            response = await get_phone_status(mock_user, mock_session)
        
        assert response.phone_number == "***1234"  # Masked
        assert response.phone_verified is True
        assert response.can_send_code is False  # Already verified

    @pytest.mark.asyncio
    async def test_send_code_already_verified(self, mock_user, mock_session):
        """Should reject sending code if already verified with same number."""
        from app.api.routes.phone import send_verification_code, SendCodeRequest
        
        mock_user.phone_number = "+14155551234"
        mock_user.phone_verified = True
        
        request = SendCodeRequest(phone_number="+14155551234")
        http_request = MagicMock()
        http_request.client.host = "127.0.0.1"
        
        with pytest.raises(HTTPException) as exc_info:
            await send_verification_code(request, http_request, mock_user, mock_session)
        
        assert exc_info.value.status_code == 400
        assert "already verified" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_send_code_rate_limited(self, mock_user, mock_session):
        """Should reject when rate limited."""
        from app.api.routes.phone import send_verification_code, SendCodeRequest
        
        request = SendCodeRequest(phone_number="+14155551234")
        http_request = MagicMock()
        http_request.client.host = "127.0.0.1"
        
        next_allowed = datetime.now(timezone.utc) + timedelta(minutes=30)
        
        with patch('app.api.routes.phone._check_rate_limit', return_value=(False, next_allowed)):
            with pytest.raises(HTTPException) as exc_info:
                await send_verification_code(request, http_request, mock_user, mock_session)
        
        assert exc_info.value.status_code == 429
        assert "too many" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_code_no_pending(self, mock_user, mock_session):
        """Should reject when no pending code exists."""
        from app.api.routes.phone import verify_code, VerifyCodeRequest
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        request = VerifyCodeRequest(code="123456")
        http_request = MagicMock()
        http_request.client.host = "127.0.0.1"
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_code(request, http_request, mock_user, mock_session)
        
        assert exc_info.value.status_code == 400
        assert "no pending" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_code_expired(self, mock_user, mock_session):
        """Should reject when code is expired."""
        from app.api.routes.phone import verify_code, VerifyCodeRequest
        
        pending_code = MagicMock(spec=PhoneVerificationCode)
        pending_code.user_id = mock_user.id
        pending_code.phone_number = "+14155551234"
        pending_code.code_hash = hashlib.sha256(b"123456").hexdigest()
        pending_code.attempts = 0
        pending_code.is_used = False
        pending_code.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)  # Expired
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pending_code
        mock_session.execute.return_value = mock_result
        
        request = VerifyCodeRequest(code="123456")
        http_request = MagicMock()
        http_request.client.host = "127.0.0.1"
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_code(request, http_request, mock_user, mock_session)
        
        assert exc_info.value.status_code == 400
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_code_too_many_attempts(self, mock_user, mock_session):
        """Should reject when too many failed attempts."""
        from app.api.routes.phone import verify_code, VerifyCodeRequest
        
        pending_code = MagicMock(spec=PhoneVerificationCode)
        pending_code.user_id = mock_user.id
        pending_code.phone_number = "+14155551234"
        pending_code.code_hash = hashlib.sha256(b"123456").hexdigest()
        pending_code.attempts = 5  # Max attempts reached
        pending_code.is_used = False
        pending_code.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pending_code
        mock_session.execute.return_value = mock_result
        
        request = VerifyCodeRequest(code="123456")
        http_request = MagicMock()
        http_request.client.host = "127.0.0.1"
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_code(request, http_request, mock_user, mock_session)
        
        assert exc_info.value.status_code == 400
        assert "too many" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_code_invalid(self, mock_user, mock_session):
        """Should reject invalid code and increment attempts."""
        from app.api.routes.phone import verify_code, VerifyCodeRequest
        
        pending_code = MagicMock(spec=PhoneVerificationCode)
        pending_code.user_id = mock_user.id
        pending_code.phone_number = "+14155551234"
        pending_code.code_hash = hashlib.sha256(b"654321").hexdigest()  # Different code
        pending_code.attempts = 2
        pending_code.is_used = False
        pending_code.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pending_code
        mock_session.execute.return_value = mock_result
        
        request = VerifyCodeRequest(code="123456")  # Wrong code
        http_request = MagicMock()
        http_request.client.host = "127.0.0.1"
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_code(request, http_request, mock_user, mock_session)
        
        assert exc_info.value.status_code == 400
        assert "invalid" in exc_info.value.detail.lower()
        assert pending_code.attempts == 3  # Incremented

    @pytest.mark.asyncio
    async def test_verify_code_success(self, mock_user, mock_session):
        """Should verify code and update user."""
        from app.api.routes.phone import verify_code, VerifyCodeRequest
        
        code = "123456"
        pending_code = MagicMock(spec=PhoneVerificationCode)
        pending_code.user_id = mock_user.id
        pending_code.phone_number = "+14155551234"
        pending_code.code_hash = hashlib.sha256(code.encode()).hexdigest()
        pending_code.attempts = 0
        pending_code.is_used = False
        pending_code.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pending_code
        mock_session.execute.return_value = mock_result
        
        request = VerifyCodeRequest(code=code)
        http_request = MagicMock()
        http_request.client.host = "127.0.0.1"
        
        # Mock the karma service to avoid actual DB calls
        with patch('app.api.routes.phone.MapAccuracyService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.award_verification_bonus = AsyncMock(return_value=True)
            mock_service_class.return_value = mock_service
            
            response = await verify_code(request, http_request, mock_user, mock_session)
        
        assert response.success is True
        assert response.phone_verified is True
        assert mock_user.phone_verified is True
        assert mock_user.phone_number == "+14155551234"
        assert pending_code.is_used is True

    @pytest.mark.asyncio
    async def test_verify_code_awards_karma_bonus(self, mock_user, mock_session):
        """Should award karma bonus when both email and phone verified."""
        from app.api.routes.phone import verify_code, VerifyCodeRequest
        
        code = "123456"
        mock_user.email_verified = True  # Email already verified
        
        pending_code = MagicMock(spec=PhoneVerificationCode)
        pending_code.user_id = mock_user.id
        pending_code.phone_number = "+14155551234"
        pending_code.code_hash = hashlib.sha256(code.encode()).hexdigest()
        pending_code.attempts = 0
        pending_code.is_used = False
        pending_code.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = pending_code
        mock_session.execute.return_value = mock_result
        
        request = VerifyCodeRequest(code=code)
        http_request = MagicMock()
        http_request.client.host = "127.0.0.1"
        
        with patch('app.api.routes.phone.MapAccuracyService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.award_verification_bonus = AsyncMock(return_value=True)
            mock_service_class.return_value = mock_service
            
            response = await verify_code(request, http_request, mock_user, mock_session)
        
        assert response.karma_bonus_awarded is True
        assert response.karma_bonus_amount == 200
        mock_service.award_verification_bonus.assert_called_once_with(mock_user.id)


class TestCodeHashSecurity:
    """Tests for verification code security."""

    def test_code_hash_is_deterministic(self):
        """Same code should produce same hash."""
        from app.api.routes.phone import _hash_code
        
        code = "123456"
        hash1 = _hash_code(code)
        hash2 = _hash_code(code)
        
        assert hash1 == hash2

    def test_different_codes_produce_different_hashes(self):
        """Different codes should produce different hashes."""
        from app.api.routes.phone import _hash_code
        
        hash1 = _hash_code("123456")
        hash2 = _hash_code("654321")
        
        assert hash1 != hash2

    def test_hash_is_not_reversible(self):
        """Hash should not contain the original code."""
        from app.api.routes.phone import _hash_code
        
        code = "123456"
        hashed = _hash_code(code)
        
        assert code not in hashed
        assert len(hashed) == 64  # SHA256 hex length


class TestPhoneValidation:
    """Tests for phone number validation in request models."""

    def test_valid_phone_numbers(self):
        """Should accept valid E.164 phone numbers."""
        from app.api.routes.phone import SendCodeRequest
        
        # These should all work
        SendCodeRequest(phone_number="+14155551234")
        SendCodeRequest(phone_number="+442071234567")
        SendCodeRequest(phone_number="+81312345678")

    def test_invalid_phone_too_short(self):
        """Should reject phone numbers that are too short."""
        from app.api.routes.phone import SendCodeRequest
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            SendCodeRequest(phone_number="+123")

    def test_invalid_verification_code_format(self):
        """Should reject non-numeric verification codes."""
        from app.api.routes.phone import VerifyCodeRequest
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            VerifyCodeRequest(code="12345a")  # Contains letter
        
        with pytest.raises(ValidationError):
            VerifyCodeRequest(code="12345")  # Too short
        
        with pytest.raises(ValidationError):
            VerifyCodeRequest(code="1234567")  # Too long
