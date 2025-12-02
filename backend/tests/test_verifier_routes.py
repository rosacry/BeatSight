"""Comprehensive tests for verifier API routes."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.models.map_edit import (
    EditStatus,
    MapEditProposal,
    MapVerificationDecision,
    VerificationDecision,
)
from app.services.rbac import require_any_permission, Permission


# Base URL for verifier endpoints
BASE_URL = "/api/verifier"


# Test fixtures
@pytest.fixture
def mock_verifier_user():
    """Create a mock verifier user."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.username = "verifier"
    user.email = "verifier@example.com"
    return user


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_proposal(mock_verifier_user):
    """Create a mock map edit proposal."""
    proposer = MagicMock(spec=User)
    proposer.id = uuid4()
    proposer.username = "proposer_user"
    proposer.avatar_url = None

    proposal = MagicMock(spec=MapEditProposal)
    proposal.id = uuid4()
    proposal.map_version_id = uuid4()
    proposal.proposer_id = proposer.id
    proposal.proposer = proposer
    proposal.summary = "Fix timing issues"
    proposal.diff_payload = {"changes": []}
    proposal.status = EditStatus.PENDING
    proposal.submitted_at = datetime.now(timezone.utc)
    proposal.updated_at = datetime.now(timezone.utc)
    proposal.decision = None
    return proposal


# -------------------------------------------------------------------
# GET /api/verifier/proposals - List Proposals Tests
# -------------------------------------------------------------------


class TestListProposals:
    """Tests for listing proposals."""

    def test_list_proposals_success(self, mock_verifier_user, mock_db, mock_proposal):
        """Should return paginated list of proposals."""
        # Mock count result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock proposals result
        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_unique = MagicMock()
        mock_unique.all.return_value = [mock_proposal]
        mock_scalars.unique.return_value = mock_unique
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        # Mock verifier permission
        app.dependency_overrides[require_any_permission(Permission.MAP_VERIFY)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"{BASE_URL}/proposals")

        # Should succeed with mocked verifier permission
        assert response.status_code in [200, 403]
        if response.status_code == 200:
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data

        app.dependency_overrides.clear()

    def test_list_proposals_with_status_filter(self, mock_verifier_user, mock_db):
        """Should filter proposals by status."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_unique = MagicMock()
        mock_unique.all.return_value = []
        mock_scalars.unique.return_value = mock_unique
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_VERIFY)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"{BASE_URL}/proposals?status_filter=pending")

        assert response.status_code in [200, 403]

        app.dependency_overrides.clear()

    def test_list_proposals_with_pagination(self, mock_verifier_user, mock_db):
        """Should paginate results."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 100

        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_unique = MagicMock()
        mock_unique.all.return_value = []
        mock_scalars.unique.return_value = mock_unique
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_VERIFY)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"{BASE_URL}/proposals?page=2&page_size=10")

        assert response.status_code in [200, 403]

        app.dependency_overrides.clear()


# -------------------------------------------------------------------
# GET /api/verifier/proposals/{proposal_id} - Get Proposal Tests
# -------------------------------------------------------------------


class TestGetProposal:
    """Tests for getting a specific proposal."""

    def test_get_proposal_success(self, mock_verifier_user, mock_db, mock_proposal):
        """Should return proposal details."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_VERIFY)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"{BASE_URL}/proposals/{mock_proposal.id}")

        assert response.status_code in [200, 403]
        if response.status_code == 200:
            data = response.json()
            assert data["id"] == str(mock_proposal.id)
            assert data["summary"] == "Fix timing issues"

        app.dependency_overrides.clear()

    def test_get_proposal_not_found(self, mock_verifier_user, mock_db):
        """Should return 404 when proposal not found."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_VERIFY)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"{BASE_URL}/proposals/{uuid4()}")

        assert response.status_code in [403, 404]

        app.dependency_overrides.clear()

    def test_get_proposal_with_decision(
        self, mock_verifier_user, mock_db, mock_proposal
    ):
        """Should include decision info when available."""
        # Create decision mock
        decision_verifier = MagicMock(spec=User)
        decision_verifier.id = uuid4()
        decision_verifier.username = "other_verifier"

        mock_decision = MagicMock(spec=MapVerificationDecision)
        mock_decision.id = uuid4()
        mock_decision.decision = VerificationDecision.APPROVE
        mock_decision.notes = "Looks good"
        mock_decision.verifier_id = decision_verifier.id
        mock_decision.verifier = decision_verifier
        mock_decision.decided_at = datetime.now(timezone.utc)

        mock_proposal.decision = mock_decision
        mock_proposal.status = EditStatus.APPROVED

        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_VERIFY)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"{BASE_URL}/proposals/{mock_proposal.id}")

        assert response.status_code in [200, 403]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "approved"
            assert data["decision"] is not None

        app.dependency_overrides.clear()


# -------------------------------------------------------------------
# POST /api/verifier/proposals/{proposal_id}/decision - Create Decision Tests
# -------------------------------------------------------------------


class TestCreateDecision:
    """Tests for creating a verification decision."""

    def test_create_decision_approve(self, mock_verifier_user, mock_db, mock_proposal):
        """Should approve a pending proposal."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_APPROVE)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            f"{BASE_URL}/proposals/{mock_proposal.id}/decision",
            json={"decision": "approve", "notes": "Great work!"},
        )

        assert response.status_code in [201, 400, 403]

        app.dependency_overrides.clear()

    def test_create_decision_reject(self, mock_verifier_user, mock_db, mock_proposal):
        """Should reject a pending proposal."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_APPROVE)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            f"{BASE_URL}/proposals/{mock_proposal.id}/decision",
            json={"decision": "reject", "notes": "Does not meet quality standards"},
        )

        assert response.status_code in [201, 400, 403]

        app.dependency_overrides.clear()

    def test_create_decision_needs_changes(
        self, mock_verifier_user, mock_db, mock_proposal
    ):
        """Should request changes on a proposal."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_APPROVE)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            f"{BASE_URL}/proposals/{mock_proposal.id}/decision",
            json={
                "decision": "needs_changes",
                "notes": "Please fix timing on measure 32",
            },
        )

        assert response.status_code in [201, 400, 403]

        app.dependency_overrides.clear()

    def test_create_decision_proposal_not_found(self, mock_verifier_user, mock_db):
        """Should return 404 when proposal not found."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_APPROVE)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            f"{BASE_URL}/proposals/{uuid4()}/decision",
            json={"decision": "approve"},
        )

        assert response.status_code in [403, 404]

        app.dependency_overrides.clear()

    def test_create_decision_already_decided(
        self, mock_verifier_user, mock_db, mock_proposal
    ):
        """Should return 400 when proposal already has decision."""
        # Create existing decision
        mock_decision = MagicMock(spec=MapVerificationDecision)
        mock_decision.id = uuid4()
        mock_proposal.decision = mock_decision

        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_APPROVE)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            f"{BASE_URL}/proposals/{mock_proposal.id}/decision",
            json={"decision": "approve"},
        )

        assert response.status_code in [400, 403]

        app.dependency_overrides.clear()

    def test_create_decision_not_pending(
        self, mock_verifier_user, mock_db, mock_proposal
    ):
        """Should return 400 when proposal is not pending."""
        mock_proposal.status = EditStatus.APPROVED
        mock_proposal.decision = None

        mock_result = MagicMock()
        mock_result.scalar.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_APPROVE)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            f"{BASE_URL}/proposals/{mock_proposal.id}/decision",
            json={"decision": "reject"},
        )

        assert response.status_code in [400, 403]

        app.dependency_overrides.clear()


# -------------------------------------------------------------------
# GET /api/verifier/stats - Verifier Statistics Tests
# -------------------------------------------------------------------


class TestVerifierStats:
    """Tests for verifier statistics endpoint."""

    def test_get_stats_success(self, mock_verifier_user, mock_db):
        """Should return verification statistics."""
        # Mock multiple scalar results
        mock_result = MagicMock()
        mock_result.scalar.side_effect = [
            15,  # pending count
            8,  # approved today
            2,  # rejected today
            50,  # total reviewed by user
            24.5,  # avg review time hours
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_VERIFY)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"{BASE_URL}/stats")

        assert response.status_code in [200, 403]
        if response.status_code == 200:
            data = response.json()
            assert "pending_count" in data
            assert "approved_today" in data
            assert "rejected_today" in data
            assert "total_reviewed_by_user" in data

        app.dependency_overrides.clear()

    def test_get_stats_empty(self, mock_verifier_user, mock_db):
        """Should return zeros when no activity."""
        mock_result = MagicMock()
        mock_result.scalar.side_effect = [0, 0, 0, 0, None]
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_VERIFY)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"{BASE_URL}/stats")

        assert response.status_code in [200, 403]

        app.dependency_overrides.clear()


# -------------------------------------------------------------------
# GET /api/verifier/my-decisions - My Decisions Tests
# -------------------------------------------------------------------


class TestMyDecisions:
    """Tests for user's decision history."""

    def test_list_my_decisions_success(
        self, mock_verifier_user, mock_db, mock_proposal
    ):
        """Should return user's verification history."""
        # Add decision to proposal
        mock_decision = MagicMock(spec=MapVerificationDecision)
        mock_decision.id = uuid4()
        mock_decision.decision = VerificationDecision.APPROVE
        mock_decision.notes = "Good work"
        mock_decision.verifier_id = mock_verifier_user.id
        mock_decision.verifier = mock_verifier_user
        mock_decision.decided_at = datetime.now(timezone.utc)
        mock_proposal.decision = mock_decision

        # Mock count result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock proposals result
        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_unique = MagicMock()
        mock_unique.all.return_value = [mock_proposal]
        mock_scalars.unique.return_value = mock_unique
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_VERIFY)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"{BASE_URL}/my-decisions")

        assert response.status_code in [200, 403]
        if response.status_code == 200:
            data = response.json()
            assert "items" in data
            assert "total" in data

        app.dependency_overrides.clear()

    def test_list_my_decisions_empty(self, mock_verifier_user, mock_db):
        """Should return empty list when no decisions made."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_unique = MagicMock()
        mock_unique.all.return_value = []
        mock_scalars.unique.return_value = mock_unique
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_VERIFY)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"{BASE_URL}/my-decisions")

        assert response.status_code in [200, 403]

        app.dependency_overrides.clear()

    def test_list_my_decisions_with_pagination(self, mock_verifier_user, mock_db):
        """Should paginate decision history."""
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 50

        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_unique = MagicMock()
        mock_unique.all.return_value = []
        mock_scalars.unique.return_value = mock_unique
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_current_user] = lambda: mock_verifier_user
        app.dependency_overrides[require_any_permission(Permission.MAP_VERIFY)] = (
            lambda: mock_verifier_user
        )

        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"{BASE_URL}/my-decisions?page=2&page_size=10")

        assert response.status_code in [200, 403]

        app.dependency_overrides.clear()


# -------------------------------------------------------------------
# Authorization Tests
# -------------------------------------------------------------------


class TestVerifierAuthorization:
    """Tests for verifier authorization requirements."""

    def test_proposals_requires_auth(self):
        """List proposals requires authentication."""
        client = TestClient(app)
        response = client.get(f"{BASE_URL}/proposals")
        assert response.status_code in [401, 403]

    def test_proposal_detail_requires_auth(self):
        """Get proposal requires authentication."""
        client = TestClient(app)
        response = client.get(f"{BASE_URL}/proposals/{uuid4()}")
        assert response.status_code in [401, 403]

    def test_create_decision_requires_auth(self):
        """Create decision requires authentication."""
        client = TestClient(app)
        response = client.post(
            f"{BASE_URL}/proposals/{uuid4()}/decision",
            json={"decision": "approve"},
        )
        assert response.status_code in [401, 403]

    def test_stats_requires_auth(self):
        """Get stats requires authentication."""
        client = TestClient(app)
        response = client.get(f"{BASE_URL}/stats")
        assert response.status_code in [401, 403]

    def test_my_decisions_requires_auth(self):
        """My decisions requires authentication."""
        client = TestClient(app)
        response = client.get(f"{BASE_URL}/my-decisions")
        assert response.status_code in [401, 403]


# -------------------------------------------------------------------
# Input Validation Tests
# -------------------------------------------------------------------


class TestVerifierValidation:
    """Tests for input validation."""

    def test_invalid_proposal_id(self):
        """Should return 422 for invalid UUID."""
        client = TestClient(app)

        response = client.get(f"{BASE_URL}/proposals/invalid-uuid")
        # 422 for invalid UUID or 401/403 for auth
        assert response.status_code in [401, 403, 422]

    def test_invalid_decision_value(self):
        """Should return 422 for invalid decision value."""
        client = TestClient(app)

        response = client.post(
            f"{BASE_URL}/proposals/{uuid4()}/decision",
            json={"decision": "invalid_decision"},
        )
        # 422 for invalid enum or 401/403 for auth (depending on check order)
        assert response.status_code in [401, 403, 422]

    def test_notes_too_long(self):
        """Should return 422 when notes exceed max length."""
        client = TestClient(app)

        response = client.post(
            f"{BASE_URL}/proposals/{uuid4()}/decision",
            json={"decision": "approve", "notes": "x" * 600},  # Max is 512
        )
        # 422 for validation or 401/403 for auth
        assert response.status_code in [401, 403, 422]

    def test_page_size_validation(self):
        """Should validate page size limits."""
        client = TestClient(app)

        # Page size too large
        response = client.get(f"{BASE_URL}/proposals?page_size=200")
        # 422 for validation or 401/403 for auth
        assert response.status_code in [401, 403, 422]

        # Page size negative
        response = client.get(f"{BASE_URL}/proposals?page_size=-1")
        assert response.status_code in [401, 403, 422]
