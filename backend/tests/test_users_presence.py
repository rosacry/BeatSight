"""Tests for lightweight user presence logic in users routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.api.routes.users import _is_recently_active


def test_is_recently_active_true_with_recent_aware_timestamp() -> None:
    now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)
    last_active = now - timedelta(minutes=2)
    assert _is_recently_active(last_active, now=now)


def test_is_recently_active_false_for_stale_timestamp() -> None:
    now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)
    last_active = now - timedelta(minutes=8)
    assert not _is_recently_active(last_active, now=now)


def test_is_recently_active_false_for_future_timestamp() -> None:
    now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)
    last_active = now + timedelta(minutes=1)
    assert not _is_recently_active(last_active, now=now)


def test_is_recently_active_treats_naive_timestamp_as_utc() -> None:
    now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)
    last_active_naive = datetime(2026, 2, 18, 11, 58, 0)
    assert _is_recently_active(last_active_naive, now=now)


def test_is_recently_active_false_for_missing_timestamp() -> None:
    assert not _is_recently_active(None)
