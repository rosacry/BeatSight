"""Tests for auth service."""

import pytest
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.auth import AuthService


class TestPasswordHashing:
    """Tests for password hashing functionality."""

    def test_hash_password_returns_string(self):
        """Test that hash_password returns a hashed string."""
        with patch(
            "app.services.auth.pwd_context.hash", return_value="$2b$12$hashedvalue"
        ):
            result = AuthService.hash_password("testpassword123")

        assert isinstance(result, str)
        assert result.startswith("$2b$")

    def test_verify_password_correct(self):
        """Test that correct password verifies."""
        with patch("app.services.auth.pwd_context.verify", return_value=True):
            result = AuthService.verify_password("password", "hashed")

        assert result is True

    def test_verify_password_incorrect(self):
        """Test that incorrect password fails verification."""
        with patch("app.services.auth.pwd_context.verify", return_value=False):
            result = AuthService.verify_password("wrongpassword", "hashed")

        assert result is False


class TestTokenCreation:
    """Tests for JWT token creation."""

    def test_create_access_token_returns_string(self):
        """Test that access token is a string."""
        user_id = uuid.uuid4()

        token = AuthService.create_access_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_custom_expiry(self):
        """Test creating access token with custom expiry."""
        user_id = uuid.uuid4()

        token = AuthService.create_access_token(
            user_id, expires_delta=timedelta(hours=2)
        )

        assert isinstance(token, str)

    def test_create_refresh_token_returns_string(self):
        """Test that refresh token is a string."""
        user_id = uuid.uuid4()

        token = AuthService.create_refresh_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token_with_custom_expiry(self):
        """Test creating refresh token with custom expiry."""
        user_id = uuid.uuid4()

        token = AuthService.create_refresh_token(
            user_id, expires_delta=timedelta(days=14)
        )

        assert isinstance(token, str)

    def test_access_and_refresh_tokens_different(self):
        """Test that access and refresh tokens are different."""
        user_id = uuid.uuid4()

        access = AuthService.create_access_token(user_id)
        refresh = AuthService.create_refresh_token(user_id)

        assert access != refresh


class TestTokenDecoding:
    """Tests for JWT token decoding."""

    def test_decode_valid_access_token(self):
        """Test decoding a valid access token."""
        user_id = uuid.uuid4()
        token = AuthService.create_access_token(user_id)

        payload = AuthService.decode_token(token)

        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_decode_valid_refresh_token(self):
        """Test decoding a valid refresh token."""
        user_id = uuid.uuid4()
        token = AuthService.create_refresh_token(user_id)

        payload = AuthService.decode_token(token)

        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"

    def test_decode_invalid_token(self):
        """Test that invalid token returns None."""
        payload = AuthService.decode_token("invalid.token.here")

        assert payload is None

    def test_decode_malformed_token(self):
        """Test that malformed token returns None."""
        payload = AuthService.decode_token("not-a-jwt")

        assert payload is None


class TestAuthServiceInit:
    """Tests for AuthService initialization."""

    def test_init_stores_session(self):
        """Test that service stores the session."""
        mock_session = MagicMock()
        service = AuthService(mock_session)

        assert service.session is mock_session


class TestGetUserById:
    """Tests for get_user_by_id method."""

    @pytest.mark.asyncio
    async def test_user_found(self):
        """Test returning user when found."""
        mock_session = AsyncMock()
        mock_user = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        service = AuthService(mock_session)

        result = await service.get_user_by_id(uuid.uuid4())

        assert result is mock_user

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        """Test returning None when user not found."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AuthService(mock_session)

        result = await service.get_user_by_id(uuid.uuid4())

        assert result is None


class TestGetUserByEmail:
    """Tests for get_user_by_email method."""

    @pytest.mark.asyncio
    async def test_user_found(self):
        """Test returning user when found by email."""
        mock_session = AsyncMock()
        mock_user = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        service = AuthService(mock_session)

        result = await service.get_user_by_email("test@example.com")

        assert result is mock_user

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        """Test returning None when email not found."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = AuthService(mock_session)

        result = await service.get_user_by_email("unknown@example.com")

        assert result is None


class TestAuthenticateUser:
    """Tests for authenticate_user method."""

    @pytest.mark.asyncio
    async def test_successful_authentication(self):
        """Test successful email/password authentication."""
        mock_session = AsyncMock()

        mock_user = MagicMock()
        mock_user.hashed_password = "$2b$12$hashedpassword"

        service = AuthService(mock_session)

        with patch.object(service, "get_user_by_email", return_value=mock_user):
            with patch.object(AuthService, "verify_password", return_value=True):
                result = await service.authenticate_user("test@example.com", "password")

        assert result is mock_user

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        """Test authentication fails when user not found."""
        mock_session = AsyncMock()
        service = AuthService(mock_session)

        with patch.object(service, "get_user_by_email", return_value=None):
            result = await service.authenticate_user("unknown@example.com", "password")

        assert result is None

    @pytest.mark.asyncio
    async def test_wrong_password(self):
        """Test authentication fails with wrong password."""
        mock_session = AsyncMock()

        mock_user = MagicMock()
        mock_user.hashed_password = "$2b$12$hashedpassword"

        service = AuthService(mock_session)

        with patch.object(service, "get_user_by_email", return_value=mock_user):
            with patch.object(AuthService, "verify_password", return_value=False):
                result = await service.authenticate_user(
                    "test@example.com", "wrongpassword"
                )

        assert result is None

    @pytest.mark.asyncio
    async def test_no_password_set(self):
        """Test authentication fails when user has no password (OAuth user)."""
        mock_session = AsyncMock()

        mock_user = MagicMock()
        mock_user.hashed_password = None

        service = AuthService(mock_session)

        with patch.object(service, "get_user_by_email", return_value=mock_user):
            result = await service.authenticate_user("oauth@example.com", "anypassword")

        assert result is None


class TestGetUserFromToken:
    """Tests for get_user_from_token method."""

    @pytest.mark.asyncio
    async def test_valid_access_token(self):
        """Test getting user from valid access token."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()
        mock_user = MagicMock()

        token = AuthService.create_access_token(user_id)

        service = AuthService(mock_session)

        with patch.object(service, "get_user_by_id", return_value=mock_user):
            result = await service.get_user_from_token(token)

        assert result is mock_user

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        """Test that invalid token returns None."""
        mock_session = AsyncMock()
        service = AuthService(mock_session)

        result = await service.get_user_from_token("invalid.token")

        assert result is None

    @pytest.mark.asyncio
    async def test_refresh_token_rejected(self):
        """Test that refresh token is rejected for user lookup."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        token = AuthService.create_refresh_token(user_id)

        service = AuthService(mock_session)

        result = await service.get_user_from_token(token)

        assert result is None

    @pytest.mark.asyncio
    async def test_token_missing_sub(self):
        """Test that token without sub claim returns None."""
        mock_session = AsyncMock()
        service = AuthService(mock_session)

        with patch.object(AuthService, "decode_token", return_value={"type": "access"}):
            result = await service.get_user_from_token("token")

        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_uuid_in_token(self):
        """Test that invalid UUID in token returns None."""
        mock_session = AsyncMock()
        service = AuthService(mock_session)

        with patch.object(
            AuthService,
            "decode_token",
            return_value={"sub": "not-a-uuid", "type": "access"},
        ):
            result = await service.get_user_from_token("token")

        assert result is None
