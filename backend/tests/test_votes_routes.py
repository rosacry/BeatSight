"""Tests for map voting API routes.

These tests validate vote creation, removal, and vote count retrieval.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_current_user,
    get_current_user_optional,
    get_db_session,
    require_community,
)
from app.main import app
from app.models.map_vote import VoteType
from app.models.user import User


@pytest.fixture
def mock_user() -> User:
    """Create a mock authenticated user."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.is_active = True
    return user


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def client_authenticated(mock_user: User, mock_db_session: AsyncMock) -> TestClient:
    """Create a test client with authentication."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_current_user_optional] = lambda: mock_user
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[require_community] = lambda: None  # Enable community features
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client_anonymous(mock_db_session: AsyncMock) -> TestClient:
    """Create a test client without authentication."""
    app.dependency_overrides[get_current_user_optional] = lambda: None
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[require_community] = lambda: None  # Enable community features
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestGetMapVotes:
    """Tests for GET /maps/{map_id}/votes endpoint."""

    @patch("app.api.routes.votes.VoteService")
    def test_get_votes_success(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test getting vote counts for a map."""
        map_id = uuid.uuid4()

        mock_service = MagicMock()
        mock_service.get_vote_counts = AsyncMock(
            return_value={"upvotes": 10, "downvotes": 3, "score": 7}
        )
        mock_service.get_vote = AsyncMock(return_value=None)
        mock_service_class.return_value = mock_service

        response = client_authenticated.get(f"/api/maps/{map_id}/votes")

        assert response.status_code == 200
        data = response.json()
        assert data["map_id"] == str(map_id)
        assert data["upvotes"] == 10
        assert data["downvotes"] == 3
        assert data["score"] == 7
        assert data["user_vote"] is None

    @patch("app.api.routes.votes.VoteService")
    def test_get_votes_with_user_upvote(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test getting votes when user has upvoted."""
        map_id = uuid.uuid4()

        mock_vote = MagicMock()
        mock_vote.vote_type = VoteType.UPVOTE

        mock_service = MagicMock()
        mock_service.get_vote_counts = AsyncMock(
            return_value={"upvotes": 10, "downvotes": 3, "score": 7}
        )
        mock_service.get_vote = AsyncMock(return_value=mock_vote)
        mock_service_class.return_value = mock_service

        response = client_authenticated.get(f"/api/maps/{map_id}/votes")

        assert response.status_code == 200
        data = response.json()
        assert data["user_vote"] == "upvote"

    @patch("app.api.routes.votes.VoteService")
    def test_get_votes_with_user_downvote(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test getting votes when user has downvoted."""
        map_id = uuid.uuid4()

        mock_vote = MagicMock()
        mock_vote.vote_type = VoteType.DOWNVOTE

        mock_service = MagicMock()
        mock_service.get_vote_counts = AsyncMock(
            return_value={"upvotes": 10, "downvotes": 3, "score": 7}
        )
        mock_service.get_vote = AsyncMock(return_value=mock_vote)
        mock_service_class.return_value = mock_service

        response = client_authenticated.get(f"/api/maps/{map_id}/votes")

        assert response.status_code == 200
        data = response.json()
        assert data["user_vote"] == "downvote"

    @patch("app.api.routes.votes.VoteService")
    def test_get_votes_map_not_found(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test getting votes for non-existent map."""
        from app.services.votes import MapNotFoundError

        map_id = uuid.uuid4()

        mock_service = MagicMock()
        mock_service.get_vote_counts = AsyncMock(side_effect=MapNotFoundError())
        mock_service_class.return_value = mock_service

        response = client_authenticated.get(f"/api/maps/{map_id}/votes")

        assert response.status_code == 404
        assert "Map not found" in response.json()["detail"]


class TestVoteOnMap:
    """Tests for POST /maps/{map_id}/vote endpoint."""

    @patch("app.api.routes.votes.VoteService")
    def test_upvote_success(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test successful upvote."""
        map_id = uuid.uuid4()

        mock_service = MagicMock()
        mock_service.cast_vote = AsyncMock(
            return_value={"upvotes": 11, "downvotes": 3, "score": 8}
        )
        mock_service_class.return_value = mock_service

        response = client_authenticated.post(
            f"/api/maps/{map_id}/vote",
            json={"action": "upvote"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["upvotes"] == 11
        assert data["score"] == 8
        assert data["user_vote"] == "upvote"

    @patch("app.api.routes.votes.VoteService")
    def test_downvote_success(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test successful downvote."""
        map_id = uuid.uuid4()

        mock_service = MagicMock()
        mock_service.cast_vote = AsyncMock(
            return_value={"upvotes": 10, "downvotes": 4, "score": 6}
        )
        mock_service_class.return_value = mock_service

        response = client_authenticated.post(
            f"/api/maps/{map_id}/vote",
            json={"action": "downvote"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["downvotes"] == 4
        assert data["user_vote"] == "downvote"

    @patch("app.api.routes.votes.VoteService")
    def test_vote_map_not_found(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test voting on non-existent map."""
        from app.services.votes import MapNotFoundError

        map_id = uuid.uuid4()

        mock_service = MagicMock()
        mock_service.cast_vote = AsyncMock(side_effect=MapNotFoundError())
        mock_service_class.return_value = mock_service

        response = client_authenticated.post(
            f"/api/maps/{map_id}/vote",
            json={"action": "upvote"},
        )

        assert response.status_code == 404
        assert "Map not found" in response.json()["detail"]

    @patch("app.api.routes.votes.VoteService")
    def test_vote_self_vote_error(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test voting on own map."""
        from app.services.votes import SelfVoteError

        map_id = uuid.uuid4()

        mock_service = MagicMock()
        mock_service.cast_vote = AsyncMock(side_effect=SelfVoteError())
        mock_service_class.return_value = mock_service

        response = client_authenticated.post(
            f"/api/maps/{map_id}/vote",
            json={"action": "upvote"},
        )

        assert response.status_code == 400
        assert "Cannot vote on your own maps" in response.json()["detail"]

    def test_vote_invalid_action(
        self,
        client_authenticated: TestClient,
    ) -> None:
        """Test voting with invalid action."""
        map_id = uuid.uuid4()

        response = client_authenticated.post(
            f"/api/maps/{map_id}/vote",
            json={"action": "invalid"},
        )

        assert response.status_code == 422  # Validation error


class TestRemoveVote:
    """Tests for DELETE /maps/{map_id}/vote endpoint."""

    @patch("app.api.routes.votes.VoteService")
    def test_remove_vote_success(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test successful vote removal."""
        map_id = uuid.uuid4()

        mock_service = MagicMock()
        mock_service.remove_vote = AsyncMock(
            return_value={"upvotes": 9, "downvotes": 3, "score": 6}
        )
        mock_service_class.return_value = mock_service

        response = client_authenticated.delete(f"/api/maps/{map_id}/vote")

        assert response.status_code == 200
        data = response.json()
        assert data["upvotes"] == 9
        assert data["user_vote"] is None

    @patch("app.api.routes.votes.VoteService")
    def test_remove_vote_map_not_found(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test removing vote from non-existent map."""
        from app.services.votes import MapNotFoundError

        map_id = uuid.uuid4()

        mock_service = MagicMock()
        mock_service.remove_vote = AsyncMock(side_effect=MapNotFoundError())
        mock_service_class.return_value = mock_service

        response = client_authenticated.delete(f"/api/maps/{map_id}/vote")

        assert response.status_code == 404
        assert "Map not found" in response.json()["detail"]


class TestBulkVotes:
    """Tests for POST /maps/votes/bulk endpoint."""

    @patch("app.api.routes.votes.VoteService")
    def test_bulk_votes_success(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test getting votes for multiple maps."""
        map_id_1 = uuid.uuid4()
        map_id_2 = uuid.uuid4()

        mock_service = MagicMock()
        mock_service.get_user_votes = AsyncMock(
            return_value={map_id_1: VoteType.UPVOTE}
        )
        mock_service.get_vote_counts = AsyncMock(
            side_effect=[
                {"upvotes": 10, "downvotes": 2, "score": 8},
                {"upvotes": 5, "downvotes": 1, "score": 4},
            ]
        )
        mock_service_class.return_value = mock_service

        response = client_authenticated.post(
            "/api/maps/votes/bulk",
            json={"map_ids": [str(map_id_1), str(map_id_2)]},
        )

        assert response.status_code == 200
        data = response.json()
        assert str(map_id_1) in data["votes"]
        assert str(map_id_2) in data["votes"]
        assert data["votes"][str(map_id_1)]["upvotes"] == 10
        assert data["votes"][str(map_id_1)]["user_vote"] == "upvote"
        assert data["votes"][str(map_id_2)]["user_vote"] is None

    @patch("app.api.routes.votes.VoteService")
    def test_bulk_votes_empty_list(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test bulk votes with empty list."""
        mock_service = MagicMock()
        mock_service.get_user_votes = AsyncMock(return_value={})
        mock_service_class.return_value = mock_service

        response = client_authenticated.post(
            "/api/maps/votes/bulk",
            json={"map_ids": []},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["votes"] == {}

    @patch("app.api.routes.votes.VoteService")
    def test_bulk_votes_skip_not_found(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test bulk votes skips maps that don't exist."""
        from app.services.votes import MapNotFoundError

        map_id_1 = uuid.uuid4()
        map_id_2 = uuid.uuid4()

        mock_service = MagicMock()
        mock_service.get_user_votes = AsyncMock(return_value={})
        # First map exists, second doesn't
        mock_service.get_vote_counts = AsyncMock(
            side_effect=[
                {"upvotes": 10, "downvotes": 2, "score": 8},
                MapNotFoundError(),
            ]
        )
        mock_service_class.return_value = mock_service

        response = client_authenticated.post(
            "/api/maps/votes/bulk",
            json={"map_ids": [str(map_id_1), str(map_id_2)]},
        )

        assert response.status_code == 200
        data = response.json()
        # Only first map should be in response
        assert str(map_id_1) in data["votes"]
        assert str(map_id_2) not in data["votes"]

    @patch("app.api.routes.votes.VoteService")
    def test_bulk_votes_no_user_votes(
        self,
        mock_service_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test bulk votes when user has no votes on any maps."""
        map_id = uuid.uuid4()

        mock_service = MagicMock()
        mock_service.get_user_votes = AsyncMock(return_value={})
        mock_service.get_vote_counts = AsyncMock(
            return_value={"upvotes": 10, "downvotes": 2, "score": 8}
        )
        mock_service_class.return_value = mock_service

        response = client_authenticated.post(
            "/api/maps/votes/bulk",
            json={"map_ids": [str(map_id)]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["votes"][str(map_id)]["user_vote"] is None
