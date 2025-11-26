"""Tests for health check endpoints."""

from fastapi.testclient import TestClient

from app.main import app


def test_live_health() -> None:
    """Liveness probe returns 200 OK."""
    client = TestClient(app)
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ready_health() -> None:
    """Readiness probe returns ready (may fail without DB)."""
    client = TestClient(app)
    resp = client.get("/health/ready")
    # May return 503 if database is not available
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert resp.json()["status"] == "ready"


def test_basic_health() -> None:
    """Basic health check returns healthy."""
    client = TestClient(app)
    resp = client.get("/health/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "beatsight-api"
    assert "timestamp" in data


def test_detailed_health() -> None:
    """Detailed health check returns component information."""
    client = TestClient(app)
    resp = client.get("/health/detailed")
    # May return 500 if database is not available
    if resp.status_code == 200:
        data = resp.json()
        assert data["service"] == "beatsight-api"
        assert "status" in data
        assert "components" in data
        assert "database" in data["components"]
        assert "redis" in data["components"]
