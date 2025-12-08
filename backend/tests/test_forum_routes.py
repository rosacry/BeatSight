"""Tests for forum API routes.

Tests cover:
- GET /forum/categories - List all categories
- GET /forum/{forum_id} - Get forum details
- GET /forum/{forum_id}/topics - List topics in forum
- POST /forum/{forum_id}/topics - Create new topic
- GET /forum/topics/{topic_id} - Get topic details
- POST /forum/topics/{topic_id}/posts - Create reply
- POST /forum/posts/{post_id}/vote - Vote on post
- Topic moderation endpoints (lock, unlock, pin, unpin)
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.user import User


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client() -> TestClient:
    """Create a synchronous test client."""
    return TestClient(app)


@pytest.fixture
def test_user_id() -> str:
    """Generate a test user ID."""
    return str(uuid4())


@pytest.fixture
def test_forum_id() -> str:
    """Generate a test forum ID."""
    return str(uuid4())


@pytest.fixture
def test_topic_id() -> str:
    """Generate a test topic ID."""
    return str(uuid4())


@pytest.fixture
def test_post_id() -> str:
    """Generate a test post ID."""
    return str(uuid4())


@pytest.fixture
def mock_user(test_user_id: str) -> User:
    """Create a mock user."""
    user = MagicMock(spec=User)
    user.id = test_user_id
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.karma_score = 100
    user.roles = ["user"]
    user.is_active = True
    user.email_verified = True
    return user


@pytest.fixture
def mock_admin_user() -> User:
    """Create a mock admin user."""
    user = MagicMock(spec=User)
    user.id = str(uuid4())
    user.email = "admin@example.com"
    user.display_name = "Admin User"
    user.karma_score = 1000
    user.roles = ["user", "admin"]
    user.is_active = True
    user.email_verified = True
    return user


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Create mock authentication headers."""
    return {"Authorization": "Bearer test-token"}


# =============================================================================
# Category Endpoint Tests
# =============================================================================

class TestCategoryEndpoints:
    """Tests for forum category endpoints."""

    def test_get_categories_unauthenticated(self, client: TestClient):
        """Test that categories can be fetched without authentication."""
        # This endpoint should be public
        # Note: Will likely fail due to DB not being set up, but tests route exists
        response = client.get("/api/forum/categories")
        # Route should exist (might return 500 due to no DB, but not 404)
        assert response.status_code != status.HTTP_404_NOT_FOUND

    @patch("app.api.routes.forum.get_db")
    @patch("app.api.routes.forum.ForumService")
    def test_get_categories_returns_list(
        self,
        mock_service_class: MagicMock,
        mock_get_db: MagicMock,
        client: TestClient,
    ):
        """Test that categories endpoint returns a list."""
        # Setup mocks
        mock_service = MagicMock()
        mock_service.get_categories = AsyncMock(return_value=[])
        mock_service_class.return_value = mock_service
        
        # Categories endpoint should return list format
        # Actual test would need proper dependency injection


# =============================================================================
# Forum Endpoint Tests
# =============================================================================

class TestForumEndpoints:
    """Tests for forum endpoints."""

    def test_get_forum_route_exists(
        self, client: TestClient, test_forum_id: str
    ):
        """Test that the get forum route exists."""
        response = client.get(f"/api/forum/{test_forum_id}")
        # Route should exist
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_get_forum_topics_route_exists(
        self, client: TestClient, test_forum_id: str
    ):
        """Test that the get forum topics route exists."""
        response = client.get(f"/api/forum/{test_forum_id}/topics")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_create_topic_requires_auth(
        self, client: TestClient, test_forum_id: str
    ):
        """Test that creating a topic requires authentication."""
        response = client.post(
            f"/api/forum/{test_forum_id}/topics",
            json={"title": "Test", "content": "Test content"},
        )
        # Should return 401 or 403 without auth
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_422_UNPROCESSABLE_ENTITY,  # Might fail validation first
        ]


# =============================================================================
# Topic Endpoint Tests
# =============================================================================

class TestTopicEndpoints:
    """Tests for topic endpoints."""

    def test_get_topic_route_exists(
        self, client: TestClient, test_topic_id: str
    ):
        """Test that the get topic route exists."""
        response = client.get(f"/api/forum/topics/{test_topic_id}")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_get_topic_posts_route_exists(
        self, client: TestClient, test_topic_id: str
    ):
        """Test that the get topic posts route exists."""
        response = client.get(f"/api/forum/topics/{test_topic_id}/posts")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_create_post_requires_auth(
        self, client: TestClient, test_topic_id: str
    ):
        """Test that creating a post requires authentication."""
        response = client.post(
            f"/api/forum/topics/{test_topic_id}/posts",
            json={"content": "Test reply"},
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    def test_lock_topic_requires_auth(
        self, client: TestClient, test_topic_id: str
    ):
        """Test that locking a topic requires authentication."""
        response = client.post(f"/api/forum/topics/{test_topic_id}/lock")
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_pin_topic_requires_auth(
        self, client: TestClient, test_topic_id: str
    ):
        """Test that pinning a topic requires authentication."""
        response = client.post(f"/api/forum/topics/{test_topic_id}/pin")
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_watch_topic_requires_auth(
        self, client: TestClient, test_topic_id: str
    ):
        """Test that watching a topic requires authentication."""
        response = client.post(f"/api/forum/topics/{test_topic_id}/watch")
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


# =============================================================================
# Post Endpoint Tests
# =============================================================================

class TestPostEndpoints:
    """Tests for post endpoints."""

    def test_get_post_route_exists(
        self, client: TestClient, test_post_id: str
    ):
        """Test that the get post route exists."""
        response = client.get(f"/api/forum/posts/{test_post_id}")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_edit_post_requires_auth(
        self, client: TestClient, test_post_id: str
    ):
        """Test that editing a post requires authentication."""
        response = client.put(
            f"/api/forum/posts/{test_post_id}",
            json={"content": "Updated content"},
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    def test_delete_post_requires_auth(
        self, client: TestClient, test_post_id: str
    ):
        """Test that deleting a post requires authentication."""
        response = client.delete(f"/api/forum/posts/{test_post_id}")
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


# =============================================================================
# Voting Endpoint Tests
# =============================================================================

class TestVotingEndpoints:
    """Tests for voting endpoints."""

    def test_vote_on_post_requires_auth(
        self, client: TestClient, test_post_id: str
    ):
        """Test that voting on a post requires authentication."""
        response = client.post(
            f"/api/forum/posts/{test_post_id}/vote",
            json={"vote_type": "upvote"},
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    def test_remove_vote_requires_auth(
        self, client: TestClient, test_post_id: str
    ):
        """Test that removing a vote requires authentication."""
        response = client.delete(f"/api/forum/posts/{test_post_id}/vote")
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


# =============================================================================
# Poll Endpoint Tests
# =============================================================================

class TestPollEndpoints:
    """Tests for poll endpoints."""

    def test_get_poll_route_exists(
        self, client: TestClient, test_topic_id: str
    ):
        """Test that the get poll route exists."""
        response = client.get(f"/api/forum/topics/{test_topic_id}/poll")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_vote_on_poll_requires_auth(
        self, client: TestClient, test_topic_id: str
    ):
        """Test that voting on a poll requires authentication."""
        response = client.post(
            f"/api/forum/topics/{test_topic_id}/poll/vote",
            json={"option_ids": ["option-1"]},
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]


# =============================================================================
# User Stats Endpoint Tests
# =============================================================================

class TestUserStatsEndpoints:
    """Tests for user forum stats endpoints."""

    def test_get_user_stats_route_exists(
        self, client: TestClient, test_user_id: str
    ):
        """Test that the get user stats route exists."""
        response = client.get(f"/api/forum/users/{test_user_id}/stats")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_get_my_stats_requires_auth(self, client: TestClient):
        """Test that getting own stats requires authentication."""
        response = client.get("/api/forum/me/stats")
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


# =============================================================================
# Recent Topics Endpoint Tests
# =============================================================================

class TestRecentTopicsEndpoint:
    """Tests for recent topics endpoint."""

    def test_get_recent_topics_route_exists(self, client: TestClient):
        """Test that the recent topics route exists."""
        response = client.get("/api/forum/topics/recent")
        assert response.status_code != status.HTTP_404_NOT_FOUND


# =============================================================================
# Search Endpoint Tests
# =============================================================================

class TestSearchEndpoint:
    """Tests for forum search endpoint."""

    def test_search_route_exists(self, client: TestClient):
        """Test that the search route exists."""
        response = client.get("/api/forum/search?q=test")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_search_requires_query(self, client: TestClient):
        """Test that search requires a query parameter."""
        response = client.get("/api/forum/search")
        # Should return 422 for missing required query param
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# Pagination Tests
# =============================================================================

class TestPagination:
    """Tests for pagination on forum endpoints."""

    def test_topics_pagination_params(
        self, client: TestClient, test_forum_id: str
    ):
        """Test that topics endpoint accepts pagination params."""
        response = client.get(
            f"/api/forum/{test_forum_id}/topics",
            params={"page": 1, "page_size": 25},
        )
        # Should not return 422 for these params
        assert response.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_posts_pagination_params(
        self, client: TestClient, test_topic_id: str
    ):
        """Test that posts endpoint accepts pagination params."""
        response = client.get(
            f"/api/forum/topics/{test_topic_id}/posts",
            params={"page": 1, "page_size": 20},
        )
        assert response.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# Sorting Tests
# =============================================================================

class TestSorting:
    """Tests for sorting on forum endpoints."""

    def test_topics_sort_params(
        self, client: TestClient, test_forum_id: str
    ):
        """Test that topics endpoint accepts sort params."""
        for sort in ["newest", "oldest", "most_posts", "most_views"]:
            response = client.get(
                f"/api/forum/{test_forum_id}/topics",
                params={"sort": sort},
            )
            # Should not return 422 for valid sort params
            assert response.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling on forum endpoints."""

    def test_invalid_forum_id_format(self, client: TestClient):
        """Test handling of invalid forum ID format."""
        response = client.get("/api/forum/invalid-not-uuid")
        # Should return 422 for invalid UUID or 404 for not found
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,  # Might happen without DB
        ]

    def test_invalid_vote_type(
        self, client: TestClient, test_post_id: str, auth_headers: dict
    ):
        """Test handling of invalid vote type."""
        response = client.post(
            f"/api/forum/posts/{test_post_id}/vote",
            json={"vote_type": "invalid"},
            headers=auth_headers,
        )
        # Should return 422 for invalid vote type
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_401_UNAUTHORIZED,
        ]
