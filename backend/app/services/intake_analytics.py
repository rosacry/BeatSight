"""
Intake funnel analytics service.

Tracks the user journey from audio upload through beatmap generation:
1. Upload started
2. Upload completed
3. Fingerprint started
4. Fingerprint succeeded/failed
5. Metadata lookup succeeded/failed/skipped
6. AI job queued
7. AI job completed

This data helps identify drop-off points and improve the user experience.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)


class IntakeEvent(str, Enum):
    """Events in the intake funnel."""

    # Upload phase
    UPLOAD_STARTED = "upload_started"
    UPLOAD_COMPLETED = "upload_completed"
    UPLOAD_FAILED = "upload_failed"

    # Fingerprint phase
    FINGERPRINT_STARTED = "fingerprint_started"
    FINGERPRINT_COMPLETED = "fingerprint_completed"
    FINGERPRINT_FAILED = "fingerprint_failed"
    FINGERPRINT_RETRIED = "fingerprint_retried"

    # Metadata phase
    METADATA_LOOKUP_STARTED = "metadata_lookup_started"
    METADATA_FOUND = "metadata_found"
    METADATA_NOT_FOUND = "metadata_not_found"
    METADATA_MANUAL_ENTRY = "metadata_manual_entry"
    METADATA_SKIPPED = "metadata_skipped"

    # Job phase
    JOB_QUEUED = "job_queued"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"

    # Abort/dropout
    USER_ABANDONED = "user_abandoned"
    SESSION_EXPIRED = "session_expired"


class IntakeAnalytics:
    """
    Analytics service for tracking intake funnel events.

    In production, this would write to:
    - A time-series database (InfluxDB, TimescaleDB)
    - An analytics service (Mixpanel, Amplitude, PostHog)
    - Or a simple log aggregator (CloudWatch, Datadog)

    For MVP, we use structured logging that can be parsed later.
    """

    def __init__(self):
        self._session_data: dict[str, dict[str, Any]] = {}

    def track(
        self,
        event: IntakeEvent,
        session_id: str | None = None,
        user_id: uuid.UUID | None = None,
        song_id: uuid.UUID | None = None,
        job_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Track an intake funnel event.

        Args:
            event: The event type.
            session_id: Browser session ID for anonymous tracking.
            user_id: User ID if authenticated.
            song_id: Song ID if available.
            job_id: AI job ID if available.
            metadata: Additional event metadata.
        """
        event_data = {
            "event": event.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "user_id": str(user_id) if user_id else None,
            "song_id": str(song_id) if song_id else None,
            "job_id": str(job_id) if job_id else None,
            **(metadata or {}),
        }

        # Log for aggregation
        logger.info(
            "intake_funnel_event",
            **event_data,
        )

        # Update session data for funnel analysis
        if session_id:
            if session_id not in self._session_data:
                self._session_data[session_id] = {
                    "events": [],
                    "started_at": datetime.now(timezone.utc),
                }
            self._session_data[session_id]["events"].append(event.value)

    def track_upload_started(
        self,
        session_id: str,
        filename: str,
        file_size: int,
        content_type: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Track upload start."""
        self.track(
            IntakeEvent.UPLOAD_STARTED,
            session_id=session_id,
            user_id=user_id,
            metadata={
                "filename": filename,
                "file_size": file_size,
                "content_type": content_type,
            },
        )

    def track_upload_completed(
        self,
        session_id: str,
        song_id: uuid.UUID,
        duration_seconds: float,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Track successful upload."""
        self.track(
            IntakeEvent.UPLOAD_COMPLETED,
            session_id=session_id,
            user_id=user_id,
            song_id=song_id,
            metadata={
                "upload_duration_seconds": duration_seconds,
            },
        )

    def track_upload_failed(
        self,
        session_id: str,
        error: str,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Track upload failure."""
        self.track(
            IntakeEvent.UPLOAD_FAILED,
            session_id=session_id,
            user_id=user_id,
            metadata={"error": error},
        )

    def track_fingerprint_started(
        self,
        session_id: str,
        song_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Track fingerprint start."""
        self.track(
            IntakeEvent.FINGERPRINT_STARTED,
            session_id=session_id,
            user_id=user_id,
            song_id=song_id,
        )

    def track_fingerprint_completed(
        self,
        session_id: str,
        song_id: uuid.UUID,
        duration_seconds: float,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Track successful fingerprint."""
        self.track(
            IntakeEvent.FINGERPRINT_COMPLETED,
            session_id=session_id,
            user_id=user_id,
            song_id=song_id,
            metadata={"fingerprint_duration_seconds": duration_seconds},
        )

    def track_fingerprint_failed(
        self,
        session_id: str,
        song_id: uuid.UUID | None = None,
        error: str | None = None,
        retry_count: int = 0,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Track fingerprint failure."""
        self.track(
            IntakeEvent.FINGERPRINT_FAILED,
            session_id=session_id,
            user_id=user_id,
            song_id=song_id,
            metadata={
                "error": error,
                "retry_count": retry_count,
            },
        )

    def track_fingerprint_retried(
        self,
        session_id: str,
        song_id: uuid.UUID,
        retry_count: int,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Track fingerprint retry."""
        self.track(
            IntakeEvent.FINGERPRINT_RETRIED,
            session_id=session_id,
            user_id=user_id,
            song_id=song_id,
            metadata={"retry_count": retry_count},
        )

    def track_metadata_found(
        self,
        session_id: str,
        song_id: uuid.UUID,
        source: str,
        confidence: float,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Track successful metadata lookup."""
        self.track(
            IntakeEvent.METADATA_FOUND,
            session_id=session_id,
            user_id=user_id,
            song_id=song_id,
            metadata={
                "source": source,
                "confidence": confidence,
            },
        )

    def track_metadata_not_found(
        self,
        session_id: str,
        song_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Track metadata lookup with no results."""
        self.track(
            IntakeEvent.METADATA_NOT_FOUND,
            session_id=session_id,
            user_id=user_id,
            song_id=song_id,
        )

    def track_metadata_manual(
        self,
        session_id: str,
        song_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Track manual metadata entry."""
        self.track(
            IntakeEvent.METADATA_MANUAL_ENTRY,
            session_id=session_id,
            user_id=user_id,
            song_id=song_id,
        )

    def track_job_queued(
        self,
        session_id: str,
        job_id: uuid.UUID,
        song_id: uuid.UUID,
        priority: str,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Track AI job queued."""
        self.track(
            IntakeEvent.JOB_QUEUED,
            session_id=session_id,
            user_id=user_id,
            song_id=song_id,
            job_id=job_id,
            metadata={"priority": priority},
        )

    def track_job_completed(
        self,
        job_id: uuid.UUID,
        song_id: uuid.UUID,
        duration_seconds: float,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Track AI job completion."""
        self.track(
            IntakeEvent.JOB_COMPLETED,
            user_id=user_id,
            song_id=song_id,
            job_id=job_id,
            metadata={"processing_duration_seconds": duration_seconds},
        )

    def track_job_failed(
        self,
        job_id: uuid.UUID,
        song_id: uuid.UUID,
        error: str,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Track AI job failure."""
        self.track(
            IntakeEvent.JOB_FAILED,
            user_id=user_id,
            song_id=song_id,
            job_id=job_id,
            metadata={"error": error},
        )

    def get_session_funnel(self, session_id: str) -> list[str]:
        """Get the event sequence for a session."""
        if session_id in self._session_data:
            return self._session_data[session_id]["events"]
        return []

    def calculate_conversion_rate(
        self,
        from_event: IntakeEvent,
        to_event: IntakeEvent,
    ) -> float:
        """
        Calculate conversion rate between two funnel steps.

        Note: This is a simplified in-memory calculation.
        In production, use a proper analytics database query.
        """
        from_count = 0
        to_count = 0

        for session_data in self._session_data.values():
            events = session_data["events"]
            if from_event.value in events:
                from_count += 1
                if to_event.value in events:
                    to_count += 1

        if from_count == 0:
            return 0.0
        return to_count / from_count


# Singleton instance
_analytics: IntakeAnalytics | None = None


def get_intake_analytics() -> IntakeAnalytics:
    """Get the shared analytics instance."""
    global _analytics
    if _analytics is None:
        _analytics = IntakeAnalytics()
    return _analytics
