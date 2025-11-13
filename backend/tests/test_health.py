"""Smoke tests for health endpoints."""

from fastapi.testclient import TestClient

from app.main import app


def test_live_health() -> None:
    client = TestClient(app)
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ready_health() -> None:
    client = TestClient(app)
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"
