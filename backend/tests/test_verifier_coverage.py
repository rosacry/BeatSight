"""
Additional tests for verifier routes targeting uncovered code paths.
Uses direct function calls to bypass RBAC dependencies.
Focuses on lines 150-218, 242-275, 313-362, 385-457, 482-548.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.models.map_edit import (
    EditStatus,
    MapEditProposal,
    MapVerificationDecision,
    VerificationDecision,
)


def create_mock_user():
    """Create a mock user with verifier permissions."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.username = "test_verifier"
    user.email = "verifier@test.com"
    return user


def create_mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    return session


def create_mock_proposal(with_decision=False, status=EditStatus.PENDING):
    """Create a mock proposal with optional decision."""
    proposer = MagicMock()
    proposer.id = uuid4()
    proposer.username = "mapper_user"
    proposer.avatar_url = None

    proposal = MagicMock(spec=MapEditProposal)
    proposal.id = uuid4()
    proposal.map_version_id = uuid4()
    proposal.proposer = proposer
    proposal.proposer_id = proposer.id
    proposal.summary = "Updated timing"
    proposal.diff_payload = {"changes": []}
    proposal.status = status
    proposal.submitted_at = datetime.now(timezone.utc)
    proposal.updated_at = datetime.now(timezone.utc)
    proposal.decision = None

    if with_decision:
        verifier = MagicMock()
        verifier.id = uuid4()
        verifier.username = "verifier_user"

        decision = MagicMock(spec=MapVerificationDecision)
        decision.id = uuid4()
        decision.decision = VerificationDecision.APPROVE
        decision.notes = "Good work"
        decision.verifier_id = verifier.id
        decision.verifier = verifier
        decision.decided_at = datetime.now(timezone.utc)
        proposal.decision = decision
        proposal.status = EditStatus.APPROVED

    return proposal


class TestListProposalsDeepCoverage:
    """Deep coverage tests for list_proposals endpoint (lines 150-218)."""

    @pytest.mark.asyncio
    async def test_list_proposals_builds_response_correctly(self):
        """Test that proposal list builds ProposalRead correctly with all fields."""
        from app.api.routes.verifier import list_proposals

        mock_user = create_mock_user()
        mock_session = create_mock_session()
        mock_proposal = create_mock_proposal()

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock proposals query
        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_unique = MagicMock()
        mock_unique.all.return_value = [mock_proposal]
        mock_scalars.unique.return_value = mock_unique
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_session.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        # Call the function directly, bypassing RBAC
        result = await list_proposals(
            session=mock_session,
            current_user=mock_user,
            status_filter=None,
            page=1,
            page_size=20,
        )

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == mock_proposal.id

    @pytest.mark.asyncio
    async def test_list_proposals_with_decision_included(self):
        """Test that proposals with decisions include DecisionRead."""
        from app.api.routes.verifier import list_proposals

        mock_user = create_mock_user()
        mock_session = create_mock_session()
        mock_proposal = create_mock_proposal(with_decision=True)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_unique = MagicMock()
        mock_unique.all.return_value = [mock_proposal]
        mock_scalars.unique.return_value = mock_unique
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_session.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        result = await list_proposals(
            session=mock_session,
            current_user=mock_user,
            status_filter=EditStatus.APPROVED,
            page=1,
            page_size=20,
        )

        assert result.total == 1
        assert result.items[0].decision is not None
        assert result.items[0].decision.decision == VerificationDecision.APPROVE

    @pytest.mark.asyncio
    async def test_list_proposals_pagination(self):
        """Test pagination parameters are applied correctly."""
        from app.api.routes.verifier import list_proposals

        mock_user = create_mock_user()
        mock_session = create_mock_session()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 50

        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_unique = MagicMock()
        mock_unique.all.return_value = []
        mock_scalars.unique.return_value = mock_unique
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_session.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        result = await list_proposals(
            session=mock_session,
            current_user=mock_user,
            status_filter=None,
            page=3,
            page_size=10,
        )

        assert result.total == 50
        assert result.page == 3
        assert result.page_size == 10
        assert result.has_next is True


class TestGetProposalDeepCoverage:
    """Deep coverage tests for get_proposal endpoint (lines 242-275)."""

    @pytest.mark.asyncio
    async def test_get_proposal_with_verifier_username(self):
        """Test getting proposal includes verifier username in decision."""
        from app.api.routes.verifier import get_proposal

        mock_user = create_mock_user()
        mock_session = create_mock_session()
        mock_proposal = create_mock_proposal(with_decision=True)

        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_proposal(
            proposal_id=mock_proposal.id,
            session=mock_session,
            current_user=mock_user,
        )

        assert result.id == mock_proposal.id
        assert result.decision is not None
        assert result.decision.verifier_username == "verifier_user"

    @pytest.mark.asyncio
    async def test_get_proposal_without_decision(self):
        """Test getting proposal without a decision."""
        from app.api.routes.verifier import get_proposal

        mock_user = create_mock_user()
        mock_session = create_mock_session()
        mock_proposal = create_mock_proposal(with_decision=False)

        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_proposal(
            proposal_id=mock_proposal.id,
            session=mock_session,
            current_user=mock_user,
        )

        assert result.id == mock_proposal.id
        assert result.decision is None

    @pytest.mark.asyncio
    async def test_get_proposal_not_found(self):
        """Test 404 when proposal not found."""
        from app.api.routes.verifier import get_proposal

        mock_user = create_mock_user()
        mock_session = create_mock_session()

        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await get_proposal(
                proposal_id=uuid4(),
                session=mock_session,
                current_user=mock_user,
            )

        assert exc_info.value.status_code == 404


class TestCreateDecisionDeepCoverage:
    """Deep coverage tests for create_decision endpoint (lines 313-362)."""

    @pytest.mark.asyncio
    async def test_create_decision_approve_updates_status(self):
        """Test that approve decision sets status to APPROVED."""
        from app.api.routes.verifier import create_decision, DecisionCreate

        mock_user = create_mock_user()
        mock_session = create_mock_session()
        mock_proposal = create_mock_proposal()

        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock refresh to set id and decided_at
        async def mock_refresh(obj):
            obj.id = uuid4()
            obj.decided_at = datetime.now(timezone.utc)

        mock_session.refresh = mock_refresh

        request = DecisionCreate(
            decision=VerificationDecision.APPROVE,
            notes="Excellent work!",
        )

        result = await create_decision(
            proposal_id=mock_proposal.id,
            request=request,
            session=mock_session,
            current_user=mock_user,
            _approve=None,
        )

        assert result.decision == VerificationDecision.APPROVE
        assert mock_proposal.status == EditStatus.APPROVED

    @pytest.mark.asyncio
    async def test_create_decision_reject_updates_status(self):
        """Test that reject decision sets status to REJECTED."""
        from app.api.routes.verifier import create_decision, DecisionCreate

        mock_user = create_mock_user()
        mock_session = create_mock_session()
        mock_proposal = create_mock_proposal()

        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def mock_refresh(obj):
            obj.id = uuid4()
            obj.decided_at = datetime.now(timezone.utc)

        mock_session.refresh = mock_refresh

        request = DecisionCreate(
            decision=VerificationDecision.REJECT,
            notes="Does not meet standards",
        )

        result = await create_decision(
            proposal_id=mock_proposal.id,
            request=request,
            session=mock_session,
            current_user=mock_user,
            _approve=None,
        )

        assert result.decision == VerificationDecision.REJECT
        assert mock_proposal.status == EditStatus.REJECTED

    @pytest.mark.asyncio
    async def test_create_decision_needs_changes_keeps_pending(self):
        """Test that needs_changes decision keeps status as PENDING."""
        from app.api.routes.verifier import create_decision, DecisionCreate

        mock_user = create_mock_user()
        mock_session = create_mock_session()
        mock_proposal = create_mock_proposal()

        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def mock_refresh(obj):
            obj.id = uuid4()
            obj.decided_at = datetime.now(timezone.utc)

        mock_session.refresh = mock_refresh

        request = DecisionCreate(
            decision=VerificationDecision.NEEDS_CHANGES,
            notes="Fix measure 16",
        )

        result = await create_decision(
            proposal_id=mock_proposal.id,
            request=request,
            session=mock_session,
            current_user=mock_user,
            _approve=None,
        )

        assert result.decision == VerificationDecision.NEEDS_CHANGES
        assert mock_proposal.status == EditStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_decision_not_found_error(self):
        """Test error when proposal not found."""
        from app.api.routes.verifier import create_decision, DecisionCreate

        mock_user = create_mock_user()
        mock_session = create_mock_session()

        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        request = DecisionCreate(
            decision=VerificationDecision.APPROVE,
            notes="Good",
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_decision(
                proposal_id=uuid4(),
                request=request,
                session=mock_session,
                current_user=mock_user,
                _approve=None,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_decision_already_decided_error(self):
        """Test error when proposal already has decision."""
        from app.api.routes.verifier import create_decision, DecisionCreate

        mock_user = create_mock_user()
        mock_session = create_mock_session()
        mock_proposal = create_mock_proposal()
        mock_proposal.decision = MagicMock()  # Already has a decision
        mock_proposal.status = EditStatus.PENDING  # But status is still pending

        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_session.execute = AsyncMock(return_value=mock_result)

        request = DecisionCreate(
            decision=VerificationDecision.APPROVE,
            notes="Good",
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_decision(
                proposal_id=mock_proposal.id,
                request=request,
                session=mock_session,
                current_user=mock_user,
                _approve=None,
            )

        assert exc_info.value.status_code == 400
        assert "already has a decision" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_decision_not_pending_error(self):
        """Test error when proposal is not pending."""
        from app.api.routes.verifier import create_decision, DecisionCreate

        mock_user = create_mock_user()
        mock_session = create_mock_session()
        mock_proposal = create_mock_proposal()
        mock_proposal.status = EditStatus.APPROVED  # Not pending

        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_session.execute = AsyncMock(return_value=mock_result)

        request = DecisionCreate(
            decision=VerificationDecision.REJECT,
            notes="Too late",
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_decision(
                proposal_id=mock_proposal.id,
                request=request,
                session=mock_session,
                current_user=mock_user,
                _approve=None,
            )

        assert exc_info.value.status_code == 400
        assert "already" in str(exc_info.value.detail)


class TestVerifierStatsDeepCoverage:
    """Deep coverage tests for get_verifier_stats endpoint (lines 385-457)."""

    @pytest.mark.asyncio
    async def test_stats_returns_all_fields(self):
        """Test that stats endpoint returns all required fields."""
        from app.api.routes.verifier import get_verifier_stats

        mock_user = create_mock_user()
        mock_session = create_mock_session()

        # Create separate mock results for each query
        mock_results = [
            MagicMock(scalar=MagicMock(return_value=25)),  # pending_count
            MagicMock(scalar=MagicMock(return_value=12)),  # approved_today
            MagicMock(scalar=MagicMock(return_value=3)),  # rejected_today
            MagicMock(scalar=MagicMock(return_value=150)),  # total_reviewed_by_user
            MagicMock(scalar=MagicMock(return_value=2.5)),  # avg_review_time
        ]

        mock_session.execute = AsyncMock(side_effect=mock_results)

        result = await get_verifier_stats(
            session=mock_session,
            current_user=mock_user,
        )

        assert result.pending_count == 25
        assert result.approved_today == 12
        assert result.rejected_today == 3
        assert result.total_reviewed_by_user == 150
        assert result.avg_review_time_hours == 2.5

    @pytest.mark.asyncio
    async def test_stats_handles_null_avg_review_time(self):
        """Test that null avg_review_time is handled gracefully."""
        from app.api.routes.verifier import get_verifier_stats

        mock_user = create_mock_user()
        mock_session = create_mock_session()

        mock_results = [
            MagicMock(scalar=MagicMock(return_value=0)),
            MagicMock(scalar=MagicMock(return_value=0)),
            MagicMock(scalar=MagicMock(return_value=0)),
            MagicMock(scalar=MagicMock(return_value=0)),
            MagicMock(scalar=MagicMock(return_value=None)),  # No reviews yet
        ]

        mock_session.execute = AsyncMock(side_effect=mock_results)

        result = await get_verifier_stats(
            session=mock_session,
            current_user=mock_user,
        )

        assert result.avg_review_time_hours is None

    @pytest.mark.asyncio
    async def test_stats_handles_zero_counts(self):
        """Test stats with all zero values."""
        from app.api.routes.verifier import get_verifier_stats

        mock_user = create_mock_user()
        mock_session = create_mock_session()

        mock_results = [
            MagicMock(scalar=MagicMock(return_value=None)),  # None becomes 0
            MagicMock(scalar=MagicMock(return_value=None)),
            MagicMock(scalar=MagicMock(return_value=None)),
            MagicMock(scalar=MagicMock(return_value=None)),
            MagicMock(scalar=MagicMock(return_value=None)),
        ]

        mock_session.execute = AsyncMock(side_effect=mock_results)

        result = await get_verifier_stats(
            session=mock_session,
            current_user=mock_user,
        )

        assert result.pending_count == 0
        assert result.approved_today == 0


class TestMyDecisionsDeepCoverage:
    """Deep coverage tests for list_my_decisions endpoint (lines 482-548)."""

    @pytest.mark.asyncio
    async def test_my_decisions_returns_paginated_results(self):
        """Test my-decisions returns properly paginated results."""
        from app.api.routes.verifier import list_my_decisions

        mock_user = create_mock_user()
        mock_session = create_mock_session()
        mock_proposal = create_mock_proposal(with_decision=True)

        # Mock count
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock proposals
        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_unique = MagicMock()
        mock_unique.all.return_value = [mock_proposal]
        mock_scalars.unique.return_value = mock_unique
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_session.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        result = await list_my_decisions(
            session=mock_session,
            current_user=mock_user,
            page=1,
            page_size=20,
        )

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].decision is not None

    @pytest.mark.asyncio
    async def test_my_decisions_with_custom_pagination(self):
        """Test my-decisions with custom page and page_size."""
        from app.api.routes.verifier import list_my_decisions

        mock_user = create_mock_user()
        mock_session = create_mock_session()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 50

        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_unique = MagicMock()
        mock_unique.all.return_value = []
        mock_scalars.unique.return_value = mock_unique
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_session.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        result = await list_my_decisions(
            session=mock_session,
            current_user=mock_user,
            page=3,
            page_size=10,
        )

        assert result.total == 50
        assert result.page == 3
        assert result.has_next is True

    @pytest.mark.asyncio
    async def test_my_decisions_empty_list(self):
        """Test my-decisions with no decisions made."""
        from app.api.routes.verifier import list_my_decisions

        mock_user = create_mock_user()
        mock_session = create_mock_session()

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_unique = MagicMock()
        mock_unique.all.return_value = []
        mock_scalars.unique.return_value = mock_unique
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_session.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        result = await list_my_decisions(
            session=mock_session,
            current_user=mock_user,
            page=1,
            page_size=20,
        )

        assert result.total == 0
        assert len(result.items) == 0
        assert result.has_next is False
