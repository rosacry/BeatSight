"""Tests for forum API routes.

Tests cover:
- Route existence validation
- Authentication requirements
- Request validation
"""

from __future__ import annotations

import pytest
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client() -> TestClient:
    """Create a synchronous test client."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def test_forum_slug() -> str:
    """Generate a test forum slug."""
    return "general-discussion"


@pytest.fixture
def test_topic_id() -> str:
    """Generate a test topic ID."""
    return str(uuid4())


@pytest.fixture
def test_post_id() -> str:
    """Generate a test post ID."""
    return str(uuid4())


@pytest.fixture
def test_poll_id() -> str:
    """Generate a test poll ID."""
    return str(uuid4())


# =============================================================================
# Category Endpoint Tests
# =============================================================================

class TestCategoryEndpoints:
    """Tests for forum category endpoints."""

    def test_get_categories_route_exists(self, client: TestClient):
        """Test that categories route exists."""
        response = client.get("/api/forum/categories")
        # Route should exist (might return 500 due to no DB, but not 404)
        assert response.status_code != status.HTTP_404_NOT_FOUND


# =============================================================================
# Forum Endpoint Tests
# =============================================================================

class TestForumEndpoints:
    """Tests for forum endpoints."""

    def test_get_forum_route_exists(
        self, client: TestClient, test_forum_slug: str
    ):
        """Test that the get forum route exists."""
        response = client.get(f"/api/forum/forums/{test_forum_slug}")
        # Route should exist
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_get_forum_topics_route_exists(
        self, client: TestClient, test_forum_slug: str
    ):
        """Test that the get forum topics route exists."""
        response = client.get(f"/api/forum/forums/{test_forum_slug}/topics")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_create_topic_requires_auth(
        self, client: TestClient, test_forum_slug: str
    ):
        """Test that creating a topic requires authentication."""
        response = client.post(
            f"/api/forum/forums/{test_forum_slug}/topics",
            json={"title": "Test", "content": "Test content"},
        )
        # Should return 401 or 403 without auth
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


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
        # Route exists (might return 500 for DB, but not 404 for route)
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
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_watch_topic_requires_auth(
        self, client: TestClient, test_topic_id: str
    ):
        """Test that watching a topic requires authentication."""
        response = client.post(f"/api/forum/topics/{test_topic_id}/watch")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_unwatch_topic_requires_auth(
        self, client: TestClient, test_topic_id: str
    ):
        """Test that unwatching a topic requires authentication."""
        response = client.delete(f"/api/forum/topics/{test_topic_id}/watch")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


# =============================================================================
# Post Endpoint Tests
# =============================================================================

class TestPostEndpoints:
    """Tests for post endpoints."""

    def test_edit_post_requires_auth(
        self, client: TestClient, test_post_id: str
    ):
        """Test that editing a post requires authentication."""
        response = client.patch(
            f"/api/forum/posts/{test_post_id}",
            json={"content": "Updated content"},
        )
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_delete_post_requires_auth(
        self, client: TestClient, test_post_id: str
    ):
        """Test that deleting a post requires authentication."""
        response = client.delete(f"/api/forum/posts/{test_post_id}")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


# =============================================================================
# Voting Endpoint Tests
# =============================================================================

class TestVotingEndpoints:
    """Tests for voting endpoints."""

    def test_vote_on_topic_requires_auth(
        self, client: TestClient, test_topic_id: str
    ):
        """Test that voting on a topic requires authentication."""
        response = client.post(
            f"/api/forum/topics/{test_topic_id}/vote",
            json={"vote_type": 1},
        )
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_vote_on_post_requires_auth(
        self, client: TestClient, test_post_id: str
    ):
        """Test that voting on a post requires authentication."""
        response = client.post(
            f"/api/forum/posts/{test_post_id}/vote",
            json={"vote_type": 1},
        )
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


# =============================================================================
# Poll Endpoint Tests
# =============================================================================

class TestPollEndpoints:
    """Tests for poll endpoints."""

    def test_get_poll_route_exists(
        self, client: TestClient, test_poll_id: str
    ):
        """Test that the get poll route exists."""
        response = client.get(f"/api/forum/polls/{test_poll_id}")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_vote_on_poll_requires_auth(
        self, client: TestClient, test_poll_id: str
    ):
        """Test that voting on a poll requires authentication."""
        response = client.post(
            f"/api/forum/polls/{test_poll_id}/vote",
            json={"option_ids": ["option-1"]},
        )
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


# =============================================================================
# Watch/Stats Endpoint Tests
# =============================================================================

class TestWatchedEndpoints:
    """Tests for watched topics endpoint."""

    def test_get_watched_requires_auth(self, client: TestClient):
        """Test that getting watched topics requires authentication."""
        response = client.get("/api/forum/watched")
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


# =============================================================================
# Search Endpoint Tests
# =============================================================================

class TestSearchEndpoint:
    """Tests for forum search endpoint."""

    def test_search_route_exists(self, client: TestClient):
        """Test that the search route exists."""
        response = client.get("/api/forum/search?query=test")
        assert response.status_code != status.HTTP_404_NOT_FOUND

    def test_search_requires_query(self, client: TestClient):
        """Test that search requires a query parameter."""
        response = client.get("/api/forum/search")
        # Should return 422 for missing required query param
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# Stats Endpoint Tests
# =============================================================================

class TestStatsEndpoint:
    """Tests for forum stats endpoint."""

    def test_get_stats_route_exists(self, client: TestClient):
        """Test that the stats route exists."""
        response = client.get("/api/forum/stats")
        assert response.status_code != status.HTTP_404_NOT_FOUND
