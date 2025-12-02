"""Tests for karma service."""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.karma import KarmaReason
from app.services.karma import (
    KarmaService,
    KarmaError,
    InsufficientKarmaError,
    RoleCode,
    ROLE_KARMA_THRESHOLDS,
    KARMA_REWARDS,
    AI_GENERATION_QUOTAS,
)


class TestKarmaExceptions:
    """Tests for karma exception classes."""

    def test_karma_error_is_exception(self):
        """Test that KarmaError is an Exception."""
        error = KarmaError("test")
        assert isinstance(error, Exception)

    def test_insufficient_karma_error_attributes(self):
        """Test InsufficientKarmaError stores required and current."""
        error = InsufficientKarmaError(required=100, current=50)

        assert error.required == 100
        assert error.current == 50
        assert "100" in str(error)
        assert "50" in str(error)

    def test_insufficient_karma_inherits(self):
        """Test that InsufficientKarmaError inherits from KarmaError."""
        error = InsufficientKarmaError(100, 50)
        assert isinstance(error, KarmaError)


class TestRoleCode:
    """Tests for RoleCode enum."""

    def test_role_codes_exist(self):
        """Test that all role codes exist."""
        assert RoleCode.FIXER == "fixer"
        assert RoleCode.VERIFIER == "verifier"
        assert RoleCode.CURATOR == "curator"
        assert RoleCode.ADMIN == "admin"

    def test_role_thresholds_defined(self):
        """Test that all roles have karma thresholds."""
        for role in RoleCode:
            assert role in ROLE_KARMA_THRESHOLDS


class TestKarmaRewards:
    """Tests for karma reward constants."""

    def test_rewards_positive_for_good_actions(self):
        """Test positive karma for good actions."""
        assert KARMA_REWARDS[KarmaReason.FIX_ACCEPTED] > 0
        assert KARMA_REWARDS[KarmaReason.VERIFICATION_COMPLETE] > 0
        assert KARMA_REWARDS[KarmaReason.SUBSCRIPTION_BONUS] > 0
        assert KARMA_REWARDS[KarmaReason.MAP_UPVOTED] > 0

    def test_penalties_negative(self):
        """Test negative karma for bad actions."""
        assert KARMA_REWARDS[KarmaReason.FIX_REJECTED] < 0
        assert KARMA_REWARDS[KarmaReason.VERIFICATION_REJECTED] < 0
        assert KARMA_REWARDS[KarmaReason.MAP_DOWNVOTED] < 0


class TestAIGenerationQuotas:
    """Tests for AI generation quota tiers."""

    def test_quotas_increase_with_karma(self):
        """Test that quotas increase with higher karma."""
        thresholds = sorted(AI_GENERATION_QUOTAS.keys())

        # Get quotas in order (treating -1 as "infinite")
        quotas = [
            AI_GENERATION_QUOTAS[t] if AI_GENERATION_QUOTAS[t] >= 0 else float("inf")
            for t in thresholds
        ]

        # Ensure quotas are non-decreasing
        for i in range(1, len(quotas)):
            assert quotas[i] >= quotas[i - 1]

    def test_base_quota_exists(self):
        """Test that a base (0 karma) quota exists."""
        assert 0 in AI_GENERATION_QUOTAS
        assert AI_GENERATION_QUOTAS[0] > 0


class TestKarmaServiceInit:
    """Tests for KarmaService initialization."""

    def test_init_stores_session(self):
        """Test that service stores the session."""
        mock_session = MagicMock()
        service = KarmaService(mock_session)
        assert service.session is mock_session


class TestGetUserKarma:
    """Tests for get_user_karma method."""

    @pytest.mark.asyncio
    async def test_returns_karma_score(self):
        """Test returning user's karma score."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 500
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        result = await service.get_user_karma(uuid.uuid4())

        assert result == 500

    @pytest.mark.asyncio
    async def test_returns_zero_for_missing_user(self):
        """Test that None karma returns 0."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        result = await service.get_user_karma(uuid.uuid4())

        assert result == 0


class TestGetDailyAIQuota:
    """Tests for get_daily_ai_quota method."""

    @pytest.mark.asyncio
    async def test_base_quota_for_low_karma(self):
        """Test base quota for users with low karma."""
        mock_session = AsyncMock()
        service = KarmaService(mock_session)

        with patch.object(service, "get_user_karma", return_value=50):
            result = await service.get_daily_ai_quota(uuid.uuid4())

        assert result == AI_GENERATION_QUOTAS[0]

    @pytest.mark.asyncio
    async def test_higher_quota_for_high_karma(self):
        """Test increased quota for high karma users."""
        mock_session = AsyncMock()
        service = KarmaService(mock_session)

        with patch.object(service, "get_user_karma", return_value=2500):
            result = await service.get_daily_ai_quota(uuid.uuid4())

        # Should get curator quota
        assert result == AI_GENERATION_QUOTAS[2000]


class TestCheckKarmaRequirement:
    """Tests for check_karma_requirement method."""

    @pytest.mark.asyncio
    async def test_meets_requirement(self):
        """Test True when karma meets requirement."""
        mock_session = AsyncMock()
        service = KarmaService(mock_session)

        with patch.object(service, "get_user_karma", return_value=500):
            result = await service.check_karma_requirement(uuid.uuid4(), 100)

        assert result is True

    @pytest.mark.asyncio
    async def test_fails_requirement(self):
        """Test False when karma doesn't meet requirement."""
        mock_session = AsyncMock()
        service = KarmaService(mock_session)

        with patch.object(service, "get_user_karma", return_value=50):
            result = await service.check_karma_requirement(uuid.uuid4(), 100)

        assert result is False

    @pytest.mark.asyncio
    async def test_exact_requirement(self):
        """Test True when karma exactly equals requirement."""
        mock_session = AsyncMock()
        service = KarmaService(mock_session)

        with patch.object(service, "get_user_karma", return_value=100):
            result = await service.check_karma_requirement(uuid.uuid4(), 100)

        assert result is True


class TestRequireKarma:
    """Tests for require_karma method."""

    @pytest.mark.asyncio
    async def test_passes_with_sufficient_karma(self):
        """Test no exception when karma is sufficient."""
        mock_session = AsyncMock()
        service = KarmaService(mock_session)

        with patch.object(service, "get_user_karma", return_value=500):
            # Should not raise
            await service.require_karma(uuid.uuid4(), 100)

    @pytest.mark.asyncio
    async def test_raises_with_insufficient_karma(self):
        """Test InsufficientKarmaError when karma is insufficient."""
        mock_session = AsyncMock()
        service = KarmaService(mock_session)

        with patch.object(service, "get_user_karma", return_value=50):
            with pytest.raises(InsufficientKarmaError) as exc_info:
                await service.require_karma(uuid.uuid4(), 100)

            assert exc_info.value.required == 100
            assert exc_info.value.current == 50


class TestHasRole:
    """Tests for has_role method."""

    @pytest.mark.asyncio
    async def test_has_role_true(self):
        """Test True when user has the role."""
        mock_session = AsyncMock()
        service = KarmaService(mock_session)

        with patch.object(
            service, "get_user_roles", return_value=["fixer", "verifier"]
        ):
            result = await service.has_role(uuid.uuid4(), "fixer")

        assert result is True

    @pytest.mark.asyncio
    async def test_has_role_false(self):
        """Test False when user doesn't have the role."""
        mock_session = AsyncMock()
        service = KarmaService(mock_session)

        with patch.object(service, "get_user_roles", return_value=["fixer"]):
            result = await service.has_role(uuid.uuid4(), "admin")

        assert result is False


class TestGetKarmaLeaderboard:
    """Tests for get_karma_leaderboard method."""

    @pytest.mark.asyncio
    async def test_returns_leaderboard_list(self):
        """Test that leaderboard returns list of tuples."""
        mock_session = AsyncMock()

        user_id = uuid.uuid4()
        mock_data = [(user_id, "TopPlayer", 5000)]

        mock_result = MagicMock()
        mock_result.all.return_value = mock_data
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        result = await service.get_karma_leaderboard(limit=10)

        assert len(result) == 1
        assert result[0][0] == user_id
        assert result[0][1] == "TopPlayer"
        assert result[0][2] == 5000


class TestGetKarmaHistoryCount:
    """Tests for get_karma_history_count method."""

    @pytest.mark.asyncio
    async def test_returns_count(self):
        """Test that history count is returned."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 42
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        result = await service.get_karma_history_count(uuid.uuid4())

        assert result == 42


class TestGetKarmaHistory:
    """Tests for get_karma_history method."""

    @pytest.mark.asyncio
    async def test_returns_history_list(self):
        """Test that history returns list of ledger entries."""
        mock_session = AsyncMock()

        mock_entry = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        result = await service.get_karma_history(uuid.uuid4())

        assert len(result) == 1
        assert result[0] is mock_entry
