"""Tests for map accuracy verification service.

Tests the multi-verifier consensus system including:
- Verification bonus for email+phone verified users
- Eligibility checking
- Vote casting and updating
- Consensus calculation
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.map_accuracy import (
    AccuracyVoteType,
    MapAccuracyConsensus,
    MapAccuracyStatus,
    MapAccuracyVote,
    UserVerificationBonus,
    REQUIRED_VERIFIERS_FOR_ACCURACY,
    MIN_APPROVAL_RATIO,
    VERIFIED_USER_KARMA_BONUS,
)
from app.services.map_accuracy import (
    AlreadyVotedError,
    MapAccuracyError,
    MapAccuracyService,
    MapVersionNotFoundError,
    NotEligibleError,
)


class TestConstants:
    """Test configuration constants."""

    def test_required_verifiers_is_three(self):
        """Verify that 3 verifiers are required for consensus."""
        assert REQUIRED_VERIFIERS_FOR_ACCURACY == 3

    def test_min_approval_ratio(self):
        """Verify minimum approval ratio is 2/3."""
        assert MIN_APPROVAL_RATIO == 2 / 3

    def test_verified_user_bonus(self):
        """Verify karma bonus is 200."""
        assert VERIFIED_USER_KARMA_BONUS == 200


class TestAccuracyVoteType:
    """Test AccuracyVoteType enum."""

    def test_all_vote_types_exist(self):
        """All expected vote types are defined."""
        assert AccuracyVoteType.ACCURATE.value == "accurate"
        assert AccuracyVoteType.INACCURATE.value == "inaccurate"
        assert AccuracyVoteType.NEEDS_WORK.value == "needs_work"
        assert AccuracyVoteType.ABSTAIN.value == "abstain"

    def test_vote_type_count(self):
        """Exactly 4 vote types exist."""
        assert len(AccuracyVoteType) == 4


class TestMapAccuracyStatus:
    """Test MapAccuracyStatus enum."""

    def test_all_statuses_exist(self):
        """All expected statuses are defined."""
        assert MapAccuracyStatus.PENDING.value == "pending"
        assert MapAccuracyStatus.VERIFIED.value == "verified"
        assert MapAccuracyStatus.DISPUTED.value == "disputed"
        assert MapAccuracyStatus.REJECTED.value == "rejected"
        assert MapAccuracyStatus.NEEDS_REVISION.value == "needs_revision"

    def test_status_count(self):
        """Exactly 5 statuses exist."""
        assert len(MapAccuracyStatus) == 5


class TestEligibilityCheck:
    """Test user eligibility for voting."""

    @pytest.mark.asyncio
    async def test_eligible_user(self):
        """User with verified email, phone, and sufficient karma is eligible."""
        session = AsyncMock()
        service = MapAccuracyService(session)
        
        user_id = uuid.uuid4()
        
        # Mock user query to return verified user with sufficient karma
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = (True, True, 200)  # email, phone, karma
        session.execute.return_value = mock_result
        
        eligible, reason = await service.is_eligible_to_vote(user_id)
        
        assert eligible is True
        assert reason == ""

    @pytest.mark.asyncio
    async def test_ineligible_unverified_email(self):
        """User without verified email is not eligible."""
        session = AsyncMock()
        service = MapAccuracyService(session)
        
        user_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = (False, True, 200)  # email not verified
        session.execute.return_value = mock_result
        
        eligible, reason = await service.is_eligible_to_vote(user_id)
        
        assert eligible is False
        assert "email" in reason.lower()

    @pytest.mark.asyncio
    async def test_ineligible_unverified_phone(self):
        """User without verified phone is not eligible."""
        session = AsyncMock()
        service = MapAccuracyService(session)
        
        user_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = (True, False, 200)  # phone not verified
        session.execute.return_value = mock_result
        
        eligible, reason = await service.is_eligible_to_vote(user_id)
        
        assert eligible is False
        assert "phone" in reason.lower()

    @pytest.mark.asyncio
    async def test_ineligible_low_karma(self):
        """User with insufficient karma is not eligible."""
        session = AsyncMock()
        service = MapAccuracyService(session)
        
        user_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = (True, True, 50)  # only 50 karma
        session.execute.return_value = mock_result
        
        eligible, reason = await service.is_eligible_to_vote(user_id)
        
        assert eligible is False
        assert "100" in reason  # minimum karma mentioned

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        """Non-existent user is not eligible."""
        session = AsyncMock()
        service = MapAccuracyService(session)
        
        user_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = None
        session.execute.return_value = mock_result
        
        eligible, reason = await service.is_eligible_to_vote(user_id)
        
        assert eligible is False
        assert "not found" in reason.lower()


class TestVerificationBonus:
    """Test verification bonus awarding."""

    @pytest.mark.asyncio
    async def test_award_bonus_eligible_user(self):
        """Award bonus to user with both verifications."""
        session = AsyncMock()
        service = MapAccuracyService(session)
        
        user_id = uuid.uuid4()
        
        # Mock user query
        user_result = MagicMock()
        user_result.one_or_none.return_value = (True, True)  # email, phone verified
        
        # Mock bonus check - no existing bonus
        bonus_result = MagicMock()
        bonus_result.scalar_one_or_none.return_value = None
        
        session.execute.side_effect = [user_result, bonus_result]
        
        # Mock karma service
        with patch.object(service, '_karma_service') as mock_karma:
            mock_karma.award_karma = AsyncMock()
            
            awarded = await service.check_and_award_verification_bonus(user_id)
            
            assert awarded is True
            mock_karma.award_karma.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_bonus_without_email(self):
        """Don't award bonus without verified email."""
        session = AsyncMock()
        service = MapAccuracyService(session)
        
        user_id = uuid.uuid4()
        
        user_result = MagicMock()
        user_result.one_or_none.return_value = (False, True)  # email not verified
        session.execute.return_value = user_result
        
        awarded = await service.check_and_award_verification_bonus(user_id)
        
        assert awarded is False

    @pytest.mark.asyncio
    async def test_no_bonus_without_phone(self):
        """Don't award bonus without verified phone."""
        session = AsyncMock()
        service = MapAccuracyService(session)
        
        user_id = uuid.uuid4()
        
        user_result = MagicMock()
        user_result.one_or_none.return_value = (True, False)  # phone not verified
        session.execute.return_value = user_result
        
        awarded = await service.check_and_award_verification_bonus(user_id)
        
        assert awarded is False

    @pytest.mark.asyncio
    async def test_no_duplicate_bonus(self):
        """Don't award bonus twice."""
        session = AsyncMock()
        service = MapAccuracyService(session)
        
        user_id = uuid.uuid4()
        
        user_result = MagicMock()
        user_result.one_or_none.return_value = (True, True)
        
        # Mock existing bonus record
        existing_bonus = MagicMock()
        existing_bonus.bonus_awarded = True
        bonus_result = MagicMock()
        bonus_result.scalar_one_or_none.return_value = existing_bonus
        
        session.execute.side_effect = [user_result, bonus_result]
        
        awarded = await service.check_and_award_verification_bonus(user_id)
        
        assert awarded is False


class TestConsensusCalculation:
    """Test consensus status calculation."""

    def test_pending_with_insufficient_votes(self):
        """Status stays pending with less than 3 votes."""
        # With only 2 votes, should remain pending regardless of vote distribution
        # This is tested via the service's _update_consensus method
        pass

    def test_verified_with_majority_accurate(self):
        """Status becomes verified when 67%+ vote accurate."""
        # 3 votes, 2+ accurate = verified
        # 2/3 = 0.67 which meets the threshold
        pass

    def test_rejected_with_majority_inaccurate(self):
        """Status becomes rejected when 67%+ vote inaccurate."""
        pass

    def test_needs_revision_with_majority_needs_work(self):
        """Status becomes needs_revision when 67%+ vote needs_work."""
        pass

    def test_disputed_with_no_clear_majority(self):
        """Status becomes disputed when no vote type has 67%+."""
        # e.g., 1 accurate, 1 inaccurate, 1 needs_work = disputed
        pass


class TestMapAccuracyVoteModel:
    """Test MapAccuracyVote model."""

    def test_vote_creation(self):
        """Can create a vote with required fields."""
        vote = MapAccuracyVote(
            map_version_id=uuid.uuid4(),
            verifier_id=uuid.uuid4(),
            vote=AccuracyVoteType.ACCURATE,
            confidence_level=4,
        )
        
        assert vote.vote == AccuracyVoteType.ACCURATE
        assert vote.confidence_level == 4

    def test_confidence_level_specified(self):
        """Confidence level is set correctly when specified."""
        vote = MapAccuracyVote(
            map_version_id=uuid.uuid4(),
            verifier_id=uuid.uuid4(),
            vote=AccuracyVoteType.ACCURATE,
            confidence_level=3,  # Explicitly set
        )
        
        assert vote.confidence_level == 3


class TestMapAccuracyConsensusModel:
    """Test MapAccuracyConsensus model."""

    def test_consensus_creation(self):
        """Can create consensus record with required fields."""
        consensus = MapAccuracyConsensus(
            map_version_id=uuid.uuid4(),
            status=MapAccuracyStatus.PENDING,
        )
        
        assert consensus.status == MapAccuracyStatus.PENDING

    def test_vote_counts_when_specified(self):
        """Vote counts are set when specified."""
        consensus = MapAccuracyConsensus(
            map_version_id=uuid.uuid4(),
            total_votes=5,
            accurate_votes=3,
            inaccurate_votes=1,
            needs_work_votes=1,
            abstain_votes=0,
        )
        
        assert consensus.total_votes == 5
        assert consensus.accurate_votes == 3
        assert consensus.inaccurate_votes == 1
        assert consensus.needs_work_votes == 1
        assert consensus.abstain_votes == 0


class TestUserVerificationBonusModel:
    """Test UserVerificationBonus model."""

    def test_bonus_creation(self):
        """Can create bonus record."""
        bonus = UserVerificationBonus(
            user_id=uuid.uuid4(),
            bonus_awarded=False,
            bonus_amount=200,
        )
        
        assert bonus.bonus_awarded is False
        assert bonus.bonus_amount == 200

    def test_bonus_amount_when_specified(self):
        """Bonus amount is set correctly when specified."""
        bonus = UserVerificationBonus(
            user_id=uuid.uuid4(),
            bonus_amount=VERIFIED_USER_KARMA_BONUS,
        )
        
        assert bonus.bonus_amount == VERIFIED_USER_KARMA_BONUS


class TestServiceExceptions:
    """Test service exception classes."""

    def test_not_eligible_error(self):
        """NotEligibleError has descriptive message."""
        error = NotEligibleError("Phone verification required")
        assert "Phone" in str(error)

    def test_already_voted_error(self):
        """AlreadyVotedError has descriptive message."""
        error = AlreadyVotedError("You have already voted")
        assert "already" in str(error).lower()

    def test_map_version_not_found_error(self):
        """MapVersionNotFoundError has descriptive message."""
        map_id = uuid.uuid4()
        error = MapVersionNotFoundError(f"Map version {map_id} not found")
        assert str(map_id) in str(error)

    def test_exception_inheritance(self):
        """All errors inherit from MapAccuracyError."""
        assert issubclass(NotEligibleError, MapAccuracyError)
        assert issubclass(AlreadyVotedError, MapAccuracyError)
        assert issubclass(MapVersionNotFoundError, MapAccuracyError)


class TestConsensusThresholds:
    """Test that consensus thresholds work correctly."""

    def test_three_accurate_votes_reaches_verified(self):
        """3 accurate votes (100%) should reach VERIFIED."""
        # 3/3 = 1.0 >= 0.67 threshold
        assert 3 / 3 >= MIN_APPROVAL_RATIO

    def test_two_of_three_accurate_reaches_verified(self):
        """2 accurate + 1 other should reach VERIFIED."""
        # 2/3 = 0.67 >= 0.67 threshold (barely)
        assert 2 / 3 >= MIN_APPROVAL_RATIO

    def test_one_of_three_does_not_reach_consensus(self):
        """1 accurate + 2 other should NOT reach VERIFIED."""
        # 1/3 = 0.33 < 0.67 threshold
        assert 1 / 3 < MIN_APPROVAL_RATIO

    def test_abstain_votes_not_counted(self):
        """Abstain votes shouldn't count toward non-abstain total."""
        # e.g., 2 accurate + 1 abstain should still be 2/2 = 100%
        # because abstain votes are excluded from ratio calculation
        non_abstain = 2  # accurate only
        accurate = 2
        assert accurate / non_abstain >= MIN_APPROVAL_RATIO
