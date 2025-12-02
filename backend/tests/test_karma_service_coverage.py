"""Additional tests for karma service to improve coverage.

Covers missing lines: 106-138, 208-227, 231-236, 251-274, 283-296, 305-316, 345-367
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.karma import KarmaReason
from app.services.karma import (
    KarmaService,
    KarmaError,
)


class TestAwardKarmaDeepCoverage:
    """Tests for award_karma covering lines 106-138."""

    @pytest.mark.asyncio
    async def test_award_karma_with_custom_delta(self):
        """Test awarding karma with a custom delta override."""
        mock_session = AsyncMock()
        # session.add() is synchronous in SQLAlchemy AsyncSession
        mock_session.add = MagicMock()
        user_id = uuid.uuid4()

        # Mock user lookup
        mock_user = MagicMock()
        mock_user.karma_score = 100
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        # Patch _update_role_eligibility to avoid complex mocking
        with patch.object(service, "_update_role_eligibility", new_callable=AsyncMock):
            result = await service.award_karma(
                user_id=user_id,
                reason=KarmaReason.FIX_ACCEPTED,
                delta=50,  # Custom delta override
            )

        # User started at 100, gained 50
        assert result == 150
        assert mock_user.karma_score == 150

    @pytest.mark.asyncio
    async def test_award_karma_with_zero_delta_returns_early(self):
        """Test that delta=0 returns current karma without changes."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        service = KarmaService(mock_session)

        # Mock get_user_karma to return current value
        with patch.object(service, "get_user_karma", return_value=200):
            result = await service.award_karma(
                user_id=user_id,
                reason=KarmaReason.FIX_ACCEPTED,
                delta=0,  # Zero delta should short-circuit
            )

        assert result == 200
        # Session.add should not be called for zero delta
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_award_karma_with_related_entity(self):
        """Test awarding karma with related entity tracking."""
        mock_session = AsyncMock()
        # session.add() is synchronous in SQLAlchemy AsyncSession
        mock_session.add = MagicMock()
        user_id = uuid.uuid4()
        map_id = uuid.uuid4()

        # Mock user lookup
        mock_user = MagicMock()
        mock_user.karma_score = 50
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        with patch.object(service, "_update_role_eligibility", new_callable=AsyncMock):
            await service.award_karma(
                user_id=user_id,
                reason=KarmaReason.MAP_UPVOTED,
                related_entity_type="map",
                related_entity_id=map_id,
            )

        # Verify ledger entry was added with entity info
        mock_session.add.assert_called_once()
        ledger_entry = mock_session.add.call_args[0][0]
        assert ledger_entry.related_entity_type == "map"
        assert ledger_entry.related_entity_id == map_id

    @pytest.mark.asyncio
    async def test_award_karma_user_not_found_raises(self):
        """Test that awarding karma to non-existent user raises error."""
        mock_session = AsyncMock()
        # session.add() is synchronous in SQLAlchemy AsyncSession
        mock_session.add = MagicMock()
        user_id = uuid.uuid4()

        # First call for ledger entry, second for user lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # User not found
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        with pytest.raises(KarmaError, match="not found"):
            await service.award_karma(
                user_id=user_id,
                reason=KarmaReason.FIX_ACCEPTED,
            )

    @pytest.mark.asyncio
    async def test_award_karma_negative_floors_at_zero(self):
        """Test that karma cannot go below zero."""
        mock_session = AsyncMock()
        # session.add() is synchronous in SQLAlchemy AsyncSession
        mock_session.add = MagicMock()
        user_id = uuid.uuid4()

        # User has 5 karma, penalty is -10
        mock_user = MagicMock()
        mock_user.karma_score = 5
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        with patch.object(service, "_update_role_eligibility", new_callable=AsyncMock):
            result = await service.award_karma(
                user_id=user_id,
                reason=KarmaReason.FIX_REJECTED,  # -10 penalty
            )

        # Should floor at 0
        assert result == 0
        assert mock_user.karma_score == 0


class TestGetEligibleRoles:
    """Tests for get_eligible_roles covering lines 208-227."""

    @pytest.mark.asyncio
    async def test_eligible_roles_checks_phone_verification(self):
        """Test that phone verification requirement is checked."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        # Create mock role that requires phone verification
        mock_role = MagicMock()
        mock_role.code = "verifier"
        mock_role.min_karma = 100
        mock_role.requires_phone_verification = True

        # Setup mock responses
        def execute_side_effect(query):
            result = MagicMock()
            # Determine which query this is based on the query object
            query_str = str(query)
            if "phone_verified" in query_str:
                result.scalar_one_or_none.return_value = False  # Not verified
            else:
                # Roles query
                result.scalars.return_value.all.return_value = [mock_role]
            return result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        service = KarmaService(mock_session)

        with patch.object(service, "get_user_karma", return_value=500):
            eligible = await service.get_eligible_roles(user_id)

        # Role requires phone verification, user not verified
        assert "verifier" not in eligible

    @pytest.mark.asyncio
    async def test_eligible_roles_with_verified_phone(self):
        """Test roles are eligible when phone is verified."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        mock_role = MagicMock()
        mock_role.code = "verifier"
        mock_role.min_karma = 100
        mock_role.requires_phone_verification = True

        def execute_side_effect(query):
            result = MagicMock()
            query_str = str(query)
            if "phone_verified" in query_str:
                result.scalar_one_or_none.return_value = True  # Verified
            else:
                result.scalars.return_value.all.return_value = [mock_role]
            return result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        service = KarmaService(mock_session)

        with patch.object(service, "get_user_karma", return_value=500):
            eligible = await service.get_eligible_roles(user_id)

        assert "verifier" in eligible

    @pytest.mark.asyncio
    async def test_eligible_roles_karma_too_low(self):
        """Test roles excluded when karma is too low."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        mock_role = MagicMock()
        mock_role.code = "curator"
        mock_role.min_karma = 2000
        mock_role.requires_phone_verification = False

        def execute_side_effect(query):
            result = MagicMock()
            query_str = str(query)
            if "phone_verified" in query_str:
                result.scalar_one_or_none.return_value = True
            else:
                result.scalars.return_value.all.return_value = [mock_role]
            return result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        service = KarmaService(mock_session)

        with patch.object(service, "get_user_karma", return_value=100):
            eligible = await service.get_eligible_roles(user_id)

        assert "curator" not in eligible


class TestGetUserRoles:
    """Tests for get_user_roles covering lines 231-236."""

    @pytest.mark.asyncio
    async def test_returns_user_role_codes(self):
        """Test that user role codes are returned."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["fixer", "verifier"]
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        roles = await service.get_user_roles(user_id)

        assert roles == ["fixer", "verifier"]

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_roles(self):
        """Test empty list when user has no roles."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        roles = await service.get_user_roles(user_id)

        assert roles == []


class TestAssignRole:
    """Tests for assign_role covering lines 251-274."""

    @pytest.mark.asyncio
    async def test_assign_role_when_eligible(self):
        """Test assigning a role to an eligible user."""
        mock_session = AsyncMock()
        # session.add() is synchronous, so use MagicMock
        mock_session.add = MagicMock()
        user_id = uuid.uuid4()
        role_id = uuid.uuid4()

        # Mock role lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = role_id
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        with (
            patch.object(service, "get_eligible_roles", return_value=["fixer"]),
            patch.object(service, "get_user_roles", return_value=[]),
        ):
            result = await service.assign_role(user_id, "fixer")

        assert result is True
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_assign_role_not_eligible(self):
        """Test that ineligible users cannot be assigned roles."""
        mock_session = AsyncMock()
        # session.add() is synchronous, so use MagicMock
        mock_session.add = MagicMock()
        user_id = uuid.uuid4()

        service = KarmaService(mock_session)

        with patch.object(service, "get_eligible_roles", return_value=[]):
            result = await service.assign_role(user_id, "admin")

        assert result is False
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_assign_role_already_has_role(self):
        """Test that already-assigned roles return False."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        service = KarmaService(mock_session)

        with (
            patch.object(service, "get_eligible_roles", return_value=["fixer"]),
            patch.object(service, "get_user_roles", return_value=["fixer"]),
        ):
            result = await service.assign_role(user_id, "fixer")

        assert result is False

    @pytest.mark.asyncio
    async def test_assign_role_not_found(self):
        """Test assigning a non-existent role returns False."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        # Role lookup returns None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        with (
            patch.object(service, "get_eligible_roles", return_value=["nonexistent"]),
            patch.object(service, "get_user_roles", return_value=[]),
        ):
            result = await service.assign_role(user_id, "nonexistent")

        assert result is False


class TestRemoveRole:
    """Tests for remove_role covering lines 283-296."""

    @pytest.mark.asyncio
    async def test_remove_role_success(self):
        """Test successfully removing a role."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        mock_user_role = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user_role
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        result = await service.remove_role(user_id, "fixer")

        assert result is True
        mock_session.delete.assert_called_once_with(mock_user_role)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_role_not_assigned(self):
        """Test removing a role the user doesn't have."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = KarmaService(mock_session)

        result = await service.remove_role(user_id, "admin")

        assert result is False
        mock_session.delete.assert_not_called()


class TestUpdateRoleEligibility:
    """Tests for _update_role_eligibility covering lines 305-316."""

    @pytest.mark.asyncio
    async def test_auto_assigns_newly_eligible_roles(self):
        """Test that roles are auto-assigned when becoming eligible."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        service = KarmaService(mock_session)

        with (
            patch.object(
                service, "get_eligible_roles", return_value=["fixer", "verifier"]
            ),
            patch.object(service, "get_user_roles", return_value=["fixer"]),
            patch.object(service, "assign_role", new_callable=AsyncMock) as mock_assign,
            patch.object(service, "remove_role", new_callable=AsyncMock),
        ):
            await service._update_role_eligibility(user_id, 600)

        # Should assign verifier (newly eligible)
        mock_assign.assert_called_once_with(user_id, "verifier")

    @pytest.mark.asyncio
    async def test_removes_ineligible_roles(self):
        """Test that roles are removed when no longer eligible."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        service = KarmaService(mock_session)

        with (
            patch.object(service, "get_eligible_roles", return_value=["fixer"]),
            patch.object(service, "get_user_roles", return_value=["fixer", "verifier"]),
            patch.object(service, "assign_role", new_callable=AsyncMock),
            patch.object(service, "remove_role", new_callable=AsyncMock) as mock_remove,
        ):
            await service._update_role_eligibility(user_id, 100)

        # Should remove verifier (no longer eligible)
        mock_remove.assert_called_once_with(user_id, "verifier")


class TestGetKarmaStats:
    """Tests for get_karma_stats covering lines 345-367."""

    @pytest.mark.asyncio
    async def test_returns_full_stats(self):
        """Test that full karma stats are returned."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        # Mock breakdown query result
        mock_breakdown_row = MagicMock()
        mock_breakdown_row.reason_code = KarmaReason.FIX_ACCEPTED
        mock_breakdown_row.total = 250
        mock_breakdown_row.count = 10

        # Mock rank query result
        mock_rank_result = MagicMock()
        mock_rank_result.scalar.return_value = 5

        def execute_side_effect(query):
            query_str = str(query)
            result = MagicMock()
            if "group_by" in query_str.lower() or "GROUP BY" in query_str:
                result.all.return_value = [mock_breakdown_row]
            elif "count" in query_str.lower():
                result.scalar.return_value = 5
            return result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        service = KarmaService(mock_session)

        with (
            patch.object(service, "get_user_karma", return_value=500),
            patch.object(service, "get_eligible_roles", return_value=["fixer"]),
            patch.object(service, "get_user_roles", return_value=["fixer"]),
            patch.object(service, "get_daily_ai_quota", return_value=10),
        ):
            stats = await service.get_karma_stats(user_id)

        assert stats["current_score"] == 500
        assert stats["rank"] == 6  # 5 users above + 1
        assert stats["eligible_roles"] == ["fixer"]
        assert stats["current_roles"] == ["fixer"]
        assert stats["daily_ai_quota"] == 10
        assert "breakdown" in stats

    @pytest.mark.asyncio
    async def test_rank_with_no_users_above(self):
        """Test rank is 1 when no users have higher karma."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()

        def execute_side_effect(query):
            result = MagicMock()
            result.all.return_value = []
            result.scalar.return_value = 0
            return result

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        service = KarmaService(mock_session)

        with (
            patch.object(service, "get_user_karma", return_value=10000),
            patch.object(service, "get_eligible_roles", return_value=["admin"]),
            patch.object(service, "get_user_roles", return_value=["admin"]),
            patch.object(service, "get_daily_ai_quota", return_value=-1),
        ):
            stats = await service.get_karma_stats(user_id)

        assert stats["rank"] == 1


class TestDailyAIQuotaEdgeCases:
    """Additional quota tests."""

    @pytest.mark.asyncio
    async def test_unlimited_quota_for_admin_karma(self):
        """Test unlimited quota for admin-level karma."""
        mock_session = AsyncMock()
        service = KarmaService(mock_session)

        with patch.object(service, "get_user_karma", return_value=15000):
            result = await service.get_daily_ai_quota(uuid.uuid4())

        assert result == -1  # Unlimited
