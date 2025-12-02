"""Tests for map edit proposal endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user, get_db_session, get_rbac_service
from app.models.user import User
from app.models.map_edit import EditStatus


# Base URL for map edit proposals
BASE_URL = "/api/map-edit-proposals"


# Test fixtures
@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.username = "testuser"
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_verifier():
    """Create a mock user with verifier role."""
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
def mock_rbac():
    """Create a mock RBAC service."""
    rbac = MagicMock()
    rbac.user_is_verifier = AsyncMock(return_value=False)
    return rbac


@pytest.fixture
def client(mock_user, mock_db, mock_rbac):
    """Create a test client with mocked dependencies."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db_session] = lambda: mock_db
    app.dependency_overrides[get_rbac_service] = lambda: mock_rbac
    yield TestClient(app)
    app.dependency_overrides.clear()


# -------------------------------------------------------------------
# POST /api/map-edit-proposals - Create Proposal Tests
# -------------------------------------------------------------------


class TestCreateProposal:
    """Tests for creating a map edit proposal."""

    def test_create_proposal_map_not_found(self, mock_user, mock_db, mock_rbac):
        """Should return 404 when map version not found."""
        map_id = uuid4()

        # Mock MapVersion lookup - return None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.post(
            BASE_URL,
            json={
                "map_id": str(map_id),
                "proposed_changes": {
                    "edits": [],
                    "bsm_content": {},
                },
                "comment": "Test comment",
                "edit_type": "correction",
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    def test_create_proposal_invalid_map_id(self, mock_user, mock_db, mock_rbac):
        """Should return 422 when map_id is not a valid UUID."""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.post(
            BASE_URL,
            json={
                "map_id": "not-a-uuid",
                "proposed_changes": {
                    "edits": [],
                    "bsm_content": {},
                },
                "comment": "Test",
                "edit_type": "correction",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        app.dependency_overrides.clear()

    def test_create_proposal_missing_required_fields(
        self, mock_user, mock_db, mock_rbac
    ):
        """Should return 422 when required fields are missing."""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.post(
            BASE_URL,
            json={
                "map_id": str(uuid4()),
                # Missing proposed_changes
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        app.dependency_overrides.clear()

    def test_create_proposal_unauthenticated(self, mock_db, mock_rbac):
        """Should return 401 when user is not authenticated."""
        # Clear overrides to test unauthenticated access
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        # Don't override get_current_user to simulate unauthenticated
        async def raise_unauthorized():
            from fastapi import HTTPException

            raise HTTPException(status_code=401, detail="Not authenticated")

        app.dependency_overrides[get_current_user] = raise_unauthorized

        client = TestClient(app)

        response = client.post(
            BASE_URL,
            json={
                "map_id": str(uuid4()),
                "proposed_changes": {
                    "edits": [],
                    "bsm_content": {},
                },
                "comment": "Test",
                "edit_type": "correction",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        app.dependency_overrides.clear()


# -------------------------------------------------------------------
# GET /api/map-edit-proposals/mine - List My Proposals Tests
# -------------------------------------------------------------------


class TestListMyProposals:
    """Tests for listing current user's proposals."""

    def test_list_my_proposals_success(self, mock_user, mock_db, mock_rbac):
        """Should return paginated list of user's proposals."""
        proposal_id = uuid4()
        map_version_id = uuid4()

        mock_proposal = MagicMock()
        mock_proposal.id = proposal_id
        mock_proposal.map_version_id = map_version_id
        mock_proposal.proposer_id = mock_user.id
        mock_proposal.summary = "Fix timing"
        mock_proposal.status = EditStatus.PENDING
        mock_proposal.submitted_at = datetime.now(timezone.utc)

        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock proposals query result
        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_proposal]
        mock_proposals_result.scalars.return_value = mock_scalars

        # Return count first, then proposals
        mock_db.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.get(f"{BASE_URL}/mine")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(proposal_id)

        app.dependency_overrides.clear()

    def test_list_my_proposals_empty(self, mock_user, mock_db, mock_rbac):
        """Should return empty list when user has no proposals."""
        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0

        # Mock proposals query result (empty)
        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.get(f"{BASE_URL}/mine")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

        app.dependency_overrides.clear()

    def test_list_my_proposals_with_pagination(self, mock_user, mock_db, mock_rbac):
        """Should return paginated results."""
        # Mock count query result (50 total)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 50

        # Mock proposals query result for page 2
        mock_proposal = MagicMock()
        mock_proposal.id = uuid4()
        mock_proposal.map_version_id = uuid4()
        mock_proposal.summary = "Page 2 proposal"
        mock_proposal.status = EditStatus.PENDING
        mock_proposal.submitted_at = datetime.now(timezone.utc)

        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_proposal]
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.get(f"{BASE_URL}/mine?page=2&page_size=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 50
        assert data["page"] == 2
        assert data["page_size"] == 10

        app.dependency_overrides.clear()

    def test_list_my_proposals_with_status_filter(self, mock_user, mock_db, mock_rbac):
        """Should filter proposals by status."""
        mock_proposal = MagicMock()
        mock_proposal.id = uuid4()
        mock_proposal.map_version_id = uuid4()
        mock_proposal.summary = "Approved proposal"
        mock_proposal.status = EditStatus.APPROVED
        mock_proposal.submitted_at = datetime.now(timezone.utc)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        mock_proposals_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_proposal]
        mock_proposals_result.scalars.return_value = mock_scalars

        mock_db.execute = AsyncMock(
            side_effect=[mock_count_result, mock_proposals_result]
        )

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.get(f"{BASE_URL}/mine?status=approved")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "approved"

        app.dependency_overrides.clear()

    def test_list_my_proposals_invalid_page(self, mock_user, mock_db, mock_rbac):
        """Should return 422 for invalid page number."""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.get(f"{BASE_URL}/mine?page=0")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        app.dependency_overrides.clear()

    def test_list_my_proposals_invalid_page_size(self, mock_user, mock_db, mock_rbac):
        """Should return 422 for invalid page_size."""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.get(f"{BASE_URL}/mine?page_size=200")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        app.dependency_overrides.clear()


# -------------------------------------------------------------------
# GET /api/map-edit-proposals/{proposal_id} - Get Proposal Tests
# -------------------------------------------------------------------


class TestGetProposal:
    """Tests for getting a specific proposal."""

    def test_get_proposal_as_owner(self, mock_user, mock_db, mock_rbac):
        """Should return proposal when requested by owner."""
        proposal_id = uuid4()
        map_version_id = uuid4()

        mock_proposal = MagicMock()
        mock_proposal.id = proposal_id
        mock_proposal.map_version_id = map_version_id
        mock_proposal.proposer_id = mock_user.id  # Same as current user
        mock_proposal.summary = "Fix timing"
        mock_proposal.status = EditStatus.PENDING
        mock_proposal.submitted_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.get(f"{BASE_URL}/{proposal_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(proposal_id)
        assert data["summary"] == "Fix timing"

        app.dependency_overrides.clear()

    def test_get_proposal_as_verifier(self, mock_verifier, mock_db, mock_rbac):
        """Should allow verifier to view any proposal."""
        proposal_id = uuid4()
        other_user_id = uuid4()

        mock_proposal = MagicMock()
        mock_proposal.id = proposal_id
        mock_proposal.map_version_id = uuid4()
        mock_proposal.proposer_id = other_user_id  # Different user
        mock_proposal.summary = "Someone else's proposal"
        mock_proposal.status = EditStatus.PENDING
        mock_proposal.submitted_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Mock verifier status
        mock_rbac.user_is_verifier = AsyncMock(return_value=True)

        app.dependency_overrides[get_current_user] = lambda: mock_verifier
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.get(f"{BASE_URL}/{proposal_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(proposal_id)

        app.dependency_overrides.clear()

    def test_get_proposal_not_owner_not_verifier(self, mock_user, mock_db, mock_rbac):
        """Should return 403 when user is not owner and not verifier."""
        proposal_id = uuid4()
        other_user_id = uuid4()

        mock_proposal = MagicMock()
        mock_proposal.id = proposal_id
        mock_proposal.map_version_id = uuid4()
        mock_proposal.proposer_id = other_user_id  # Different user
        mock_proposal.summary = "Someone else's proposal"
        mock_proposal.status = EditStatus.PENDING
        mock_proposal.submitted_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Not a verifier
        mock_rbac.user_is_verifier = AsyncMock(return_value=False)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.get(f"{BASE_URL}/{proposal_id}")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "your own proposals" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    def test_get_proposal_not_found(self, mock_user, mock_db, mock_rbac):
        """Should return 404 when proposal doesn't exist."""
        proposal_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.get(f"{BASE_URL}/{proposal_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    def test_get_proposal_invalid_uuid(self, mock_user, mock_db, mock_rbac):
        """Should return 422 for invalid proposal ID."""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.get(f"{BASE_URL}/not-a-uuid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        app.dependency_overrides.clear()


# -------------------------------------------------------------------
# DELETE /api/map-edit-proposals/{proposal_id} - Withdraw Proposal Tests
# -------------------------------------------------------------------


class TestWithdrawProposal:
    """Tests for withdrawing a proposal."""

    def test_withdraw_proposal_success(self, mock_user, mock_db, mock_rbac):
        """Should successfully withdraw a pending proposal."""
        proposal_id = uuid4()

        mock_proposal = MagicMock()
        mock_proposal.id = proposal_id
        mock_proposal.proposer_id = mock_user.id
        mock_proposal.status = EditStatus.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.delete(f"{BASE_URL}/{proposal_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert mock_proposal.status == EditStatus.WITHDRAWN
        assert mock_db.commit.called

        app.dependency_overrides.clear()

    def test_withdraw_proposal_not_owner(self, mock_user, mock_db, mock_rbac):
        """Should return 403 when user is not the proposal owner."""
        proposal_id = uuid4()
        other_user_id = uuid4()

        mock_proposal = MagicMock()
        mock_proposal.id = proposal_id
        mock_proposal.proposer_id = other_user_id  # Different user
        mock_proposal.status = EditStatus.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.delete(f"{BASE_URL}/{proposal_id}")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "your own proposals" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    def test_withdraw_proposal_not_found(self, mock_user, mock_db, mock_rbac):
        """Should return 404 when proposal doesn't exist."""
        proposal_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.delete(f"{BASE_URL}/{proposal_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

        app.dependency_overrides.clear()

    def test_withdraw_proposal_already_approved(self, mock_user, mock_db, mock_rbac):
        """Should return 400 when trying to withdraw an approved proposal."""
        proposal_id = uuid4()

        mock_proposal = MagicMock()
        mock_proposal.id = proposal_id
        mock_proposal.proposer_id = mock_user.id
        mock_proposal.status = EditStatus.APPROVED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.delete(f"{BASE_URL}/{proposal_id}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot withdraw" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    def test_withdraw_proposal_already_rejected(self, mock_user, mock_db, mock_rbac):
        """Should return 400 when trying to withdraw a rejected proposal."""
        proposal_id = uuid4()

        mock_proposal = MagicMock()
        mock_proposal.id = proposal_id
        mock_proposal.proposer_id = mock_user.id
        mock_proposal.status = EditStatus.REJECTED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.delete(f"{BASE_URL}/{proposal_id}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot withdraw" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    def test_withdraw_proposal_already_withdrawn(self, mock_user, mock_db, mock_rbac):
        """Should return 400 when proposal is already withdrawn."""
        proposal_id = uuid4()

        mock_proposal = MagicMock()
        mock_proposal.id = proposal_id
        mock_proposal.proposer_id = mock_user.id
        mock_proposal.status = EditStatus.WITHDRAWN

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_proposal
        mock_db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.delete(f"{BASE_URL}/{proposal_id}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot withdraw" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    def test_withdraw_proposal_invalid_uuid(self, mock_user, mock_db, mock_rbac):
        """Should return 422 for invalid proposal ID."""
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_rbac_service] = lambda: mock_rbac

        client = TestClient(app)

        response = client.delete(f"{BASE_URL}/invalid-uuid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        app.dependency_overrides.clear()


# -------------------------------------------------------------------
# Edit Status Enum Tests
# -------------------------------------------------------------------


class TestEditStatusEnum:
    """Tests for EditStatus enum values."""

    def test_edit_status_values(self):
        """Should have all expected status values."""
        assert EditStatus.PENDING == "pending"
        assert EditStatus.APPROVED == "approved"
        assert EditStatus.REJECTED == "rejected"
        assert EditStatus.WITHDRAWN == "withdrawn"

    def test_edit_status_from_string(self):
        """Should be able to convert from string."""
        assert EditStatus("pending") == EditStatus.PENDING
        assert EditStatus("approved") == EditStatus.APPROVED
        assert EditStatus("rejected") == EditStatus.REJECTED
        assert EditStatus("withdrawn") == EditStatus.WITHDRAWN
