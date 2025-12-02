"""Tests for intake analytics service.

Covers the intake funnel tracking and analytics calculations.
"""

import uuid
from unittest.mock import patch


from app.services.intake_analytics import (
    IntakeAnalytics,
    IntakeEvent,
    get_intake_analytics,
)


class TestIntakeEvent:
    """Tests for IntakeEvent enum."""

    def test_all_events_have_string_values(self):
        """Test that all events have string values."""
        for event in IntakeEvent:
            assert isinstance(event.value, str)

    def test_upload_events_exist(self):
        """Test upload phase events exist."""
        assert IntakeEvent.UPLOAD_STARTED
        assert IntakeEvent.UPLOAD_COMPLETED
        assert IntakeEvent.UPLOAD_FAILED

    def test_fingerprint_events_exist(self):
        """Test fingerprint phase events exist."""
        assert IntakeEvent.FINGERPRINT_STARTED
        assert IntakeEvent.FINGERPRINT_COMPLETED
        assert IntakeEvent.FINGERPRINT_FAILED
        assert IntakeEvent.FINGERPRINT_RETRIED

    def test_metadata_events_exist(self):
        """Test metadata phase events exist."""
        assert IntakeEvent.METADATA_LOOKUP_STARTED
        assert IntakeEvent.METADATA_FOUND
        assert IntakeEvent.METADATA_NOT_FOUND
        assert IntakeEvent.METADATA_MANUAL_ENTRY
        assert IntakeEvent.METADATA_SKIPPED

    def test_job_events_exist(self):
        """Test job phase events exist."""
        assert IntakeEvent.JOB_QUEUED
        assert IntakeEvent.JOB_STARTED
        assert IntakeEvent.JOB_COMPLETED
        assert IntakeEvent.JOB_FAILED

    def test_abort_events_exist(self):
        """Test abort/dropout events exist."""
        assert IntakeEvent.USER_ABANDONED
        assert IntakeEvent.SESSION_EXPIRED


class TestIntakeAnalyticsInit:
    """Tests for IntakeAnalytics initialization."""

    def test_creates_empty_session_data(self):
        """Test that session data dict is initialized empty."""
        analytics = IntakeAnalytics()
        assert analytics._session_data == {}


class TestTrack:
    """Tests for the base track method."""

    def test_track_logs_event(self):
        """Test that track logs the event."""
        analytics = IntakeAnalytics()

        with patch("app.services.intake_analytics.logger") as mock_logger:
            analytics.track(
                IntakeEvent.UPLOAD_STARTED,
                session_id="session-123",
            )

        mock_logger.info.assert_called_once()
        call_kwargs = mock_logger.info.call_args[1]
        assert call_kwargs["event"] == "upload_started"
        assert call_kwargs["session_id"] == "session-123"

    def test_track_with_user_id(self):
        """Test tracking with user_id."""
        analytics = IntakeAnalytics()
        user_id = uuid.uuid4()

        with patch("app.services.intake_analytics.logger") as mock_logger:
            analytics.track(
                IntakeEvent.UPLOAD_COMPLETED,
                user_id=user_id,
            )

        call_kwargs = mock_logger.info.call_args[1]
        assert call_kwargs["user_id"] == str(user_id)

    def test_track_with_song_id(self):
        """Test tracking with song_id."""
        analytics = IntakeAnalytics()
        song_id = uuid.uuid4()

        with patch("app.services.intake_analytics.logger"):
            analytics.track(
                IntakeEvent.FINGERPRINT_STARTED,
                song_id=song_id,
            )

    def test_track_with_job_id(self):
        """Test tracking with job_id."""
        analytics = IntakeAnalytics()
        job_id = uuid.uuid4()

        with patch("app.services.intake_analytics.logger"):
            analytics.track(
                IntakeEvent.JOB_QUEUED,
                job_id=job_id,
            )

    def test_track_with_metadata(self):
        """Test tracking with extra metadata."""
        analytics = IntakeAnalytics()

        with patch("app.services.intake_analytics.logger") as mock_logger:
            analytics.track(
                IntakeEvent.UPLOAD_STARTED,
                session_id="test",
                metadata={"filename": "song.mp3", "size": 1024},
            )

        call_kwargs = mock_logger.info.call_args[1]
        assert call_kwargs["filename"] == "song.mp3"
        assert call_kwargs["size"] == 1024

    def test_track_updates_session_data(self):
        """Test that tracking updates session data."""
        analytics = IntakeAnalytics()

        with patch("app.services.intake_analytics.logger"):
            analytics.track(IntakeEvent.UPLOAD_STARTED, session_id="session-abc")
            analytics.track(IntakeEvent.UPLOAD_COMPLETED, session_id="session-abc")

        assert "session-abc" in analytics._session_data
        events = analytics._session_data["session-abc"]["events"]
        assert "upload_started" in events
        assert "upload_completed" in events

    def test_track_without_session_id_no_session_data(self):
        """Test that tracking without session_id doesn't add session data."""
        analytics = IntakeAnalytics()

        with patch("app.services.intake_analytics.logger"):
            analytics.track(IntakeEvent.UPLOAD_STARTED)

        assert len(analytics._session_data) == 0


class TestTrackUploadMethods:
    """Tests for upload tracking methods."""

    def test_track_upload_started(self):
        """Test track_upload_started method."""
        analytics = IntakeAnalytics()

        with patch.object(analytics, "track") as mock_track:
            analytics.track_upload_started(
                session_id="s1",
                filename="test.mp3",
                file_size=10000,
                content_type="audio/mpeg",
                user_id=uuid.uuid4(),
            )

        mock_track.assert_called_once()
        call_kwargs = mock_track.call_args[1]
        assert call_kwargs["metadata"]["filename"] == "test.mp3"
        assert call_kwargs["metadata"]["file_size"] == 10000
        assert call_kwargs["metadata"]["content_type"] == "audio/mpeg"

    def test_track_upload_completed(self):
        """Test track_upload_completed method."""
        analytics = IntakeAnalytics()
        song_id = uuid.uuid4()

        with patch.object(analytics, "track") as mock_track:
            analytics.track_upload_completed(
                session_id="s1",
                song_id=song_id,
                duration_seconds=2.5,
            )

        mock_track.assert_called_once()
        call_kwargs = mock_track.call_args[1]
        assert call_kwargs["song_id"] == song_id
        assert call_kwargs["metadata"]["upload_duration_seconds"] == 2.5

    def test_track_upload_failed(self):
        """Test track_upload_failed method."""
        analytics = IntakeAnalytics()

        with patch.object(analytics, "track") as mock_track:
            analytics.track_upload_failed(
                session_id="s1",
                error="File too large",
            )

        mock_track.assert_called_once()
        call_kwargs = mock_track.call_args[1]
        assert call_kwargs["metadata"]["error"] == "File too large"


class TestTrackFingerprintMethods:
    """Tests for fingerprint tracking methods."""

    def test_track_fingerprint_started(self):
        """Test track_fingerprint_started method."""
        analytics = IntakeAnalytics()
        song_id = uuid.uuid4()

        with patch.object(analytics, "track") as mock_track:
            analytics.track_fingerprint_started(
                session_id="s1",
                song_id=song_id,
            )

        mock_track.assert_called_once()
        assert mock_track.call_args[0][0] == IntakeEvent.FINGERPRINT_STARTED

    def test_track_fingerprint_completed(self):
        """Test track_fingerprint_completed method."""
        analytics = IntakeAnalytics()
        song_id = uuid.uuid4()

        with patch.object(analytics, "track") as mock_track:
            analytics.track_fingerprint_completed(
                session_id="s1",
                song_id=song_id,
                duration_seconds=1.2,
            )

        call_kwargs = mock_track.call_args[1]
        assert call_kwargs["metadata"]["fingerprint_duration_seconds"] == 1.2

    def test_track_fingerprint_failed(self):
        """Test track_fingerprint_failed method."""
        analytics = IntakeAnalytics()
        song_id = uuid.uuid4()

        with patch.object(analytics, "track") as mock_track:
            analytics.track_fingerprint_failed(
                session_id="s1",
                song_id=song_id,
                error="Fingerprint extraction failed",
                retry_count=2,
            )

        call_kwargs = mock_track.call_args[1]
        assert call_kwargs["metadata"]["error"] == "Fingerprint extraction failed"
        assert call_kwargs["metadata"]["retry_count"] == 2

    def test_track_fingerprint_retried(self):
        """Test track_fingerprint_retried method."""
        analytics = IntakeAnalytics()
        song_id = uuid.uuid4()

        with patch.object(analytics, "track") as mock_track:
            analytics.track_fingerprint_retried(
                session_id="s1",
                song_id=song_id,
                retry_count=1,
            )

        call_kwargs = mock_track.call_args[1]
        assert call_kwargs["metadata"]["retry_count"] == 1


class TestTrackMetadataMethods:
    """Tests for metadata tracking methods."""

    def test_track_metadata_found(self):
        """Test track_metadata_found method."""
        analytics = IntakeAnalytics()
        song_id = uuid.uuid4()

        with patch.object(analytics, "track") as mock_track:
            analytics.track_metadata_found(
                session_id="s1",
                song_id=song_id,
                source="acoustid",
                confidence=0.95,
            )

        call_kwargs = mock_track.call_args[1]
        assert call_kwargs["metadata"]["source"] == "acoustid"
        assert call_kwargs["metadata"]["confidence"] == 0.95

    def test_track_metadata_not_found(self):
        """Test track_metadata_not_found method."""
        analytics = IntakeAnalytics()

        with patch.object(analytics, "track") as mock_track:
            analytics.track_metadata_not_found(
                session_id="s1",
            )

        mock_track.assert_called_once()
        assert mock_track.call_args[0][0] == IntakeEvent.METADATA_NOT_FOUND

    def test_track_metadata_manual(self):
        """Test track_metadata_manual method."""
        analytics = IntakeAnalytics()
        song_id = uuid.uuid4()

        with patch.object(analytics, "track") as mock_track:
            analytics.track_metadata_manual(
                session_id="s1",
                song_id=song_id,
            )

        mock_track.assert_called_once()
        assert mock_track.call_args[0][0] == IntakeEvent.METADATA_MANUAL_ENTRY


class TestTrackJobMethods:
    """Tests for job tracking methods."""

    def test_track_job_queued(self):
        """Test track_job_queued method."""
        analytics = IntakeAnalytics()
        job_id = uuid.uuid4()
        song_id = uuid.uuid4()

        with patch.object(analytics, "track") as mock_track:
            analytics.track_job_queued(
                session_id="s1",
                job_id=job_id,
                song_id=song_id,
                priority="high",
            )

        call_kwargs = mock_track.call_args[1]
        assert call_kwargs["job_id"] == job_id
        assert call_kwargs["metadata"]["priority"] == "high"

    def test_track_job_completed(self):
        """Test track_job_completed method."""
        analytics = IntakeAnalytics()
        job_id = uuid.uuid4()
        song_id = uuid.uuid4()

        with patch.object(analytics, "track") as mock_track:
            analytics.track_job_completed(
                job_id=job_id,
                song_id=song_id,
                duration_seconds=45.5,
            )

        call_kwargs = mock_track.call_args[1]
        assert call_kwargs["metadata"]["processing_duration_seconds"] == 45.5

    def test_track_job_failed(self):
        """Test track_job_failed method."""
        analytics = IntakeAnalytics()
        job_id = uuid.uuid4()
        song_id = uuid.uuid4()

        with patch.object(analytics, "track") as mock_track:
            analytics.track_job_failed(
                job_id=job_id,
                song_id=song_id,
                error="GPU out of memory",
            )

        call_kwargs = mock_track.call_args[1]
        assert call_kwargs["metadata"]["error"] == "GPU out of memory"


class TestGetSessionFunnel:
    """Tests for get_session_funnel method."""

    def test_returns_events_for_existing_session(self):
        """Test returning events for an existing session."""
        analytics = IntakeAnalytics()

        with patch("app.services.intake_analytics.logger"):
            analytics.track(IntakeEvent.UPLOAD_STARTED, session_id="s1")
            analytics.track(IntakeEvent.UPLOAD_COMPLETED, session_id="s1")
            analytics.track(IntakeEvent.FINGERPRINT_STARTED, session_id="s1")

        funnel = analytics.get_session_funnel("s1")

        assert funnel == ["upload_started", "upload_completed", "fingerprint_started"]

    def test_returns_empty_for_unknown_session(self):
        """Test returning empty list for unknown session."""
        analytics = IntakeAnalytics()

        funnel = analytics.get_session_funnel("nonexistent")

        assert funnel == []


class TestCalculateConversionRate:
    """Tests for calculate_conversion_rate method."""

    def test_conversion_rate_calculation(self):
        """Test basic conversion rate calculation."""
        analytics = IntakeAnalytics()

        with patch("app.services.intake_analytics.logger"):
            # 3 sessions start upload
            analytics.track(IntakeEvent.UPLOAD_STARTED, session_id="s1")
            analytics.track(IntakeEvent.UPLOAD_STARTED, session_id="s2")
            analytics.track(IntakeEvent.UPLOAD_STARTED, session_id="s3")

            # 2 complete upload
            analytics.track(IntakeEvent.UPLOAD_COMPLETED, session_id="s1")
            analytics.track(IntakeEvent.UPLOAD_COMPLETED, session_id="s2")

        rate = analytics.calculate_conversion_rate(
            IntakeEvent.UPLOAD_STARTED,
            IntakeEvent.UPLOAD_COMPLETED,
        )

        # 2 out of 3 = 0.666...
        assert abs(rate - 2 / 3) < 0.001

    def test_conversion_rate_zero_from_count(self):
        """Test that zero from_count returns 0.0."""
        analytics = IntakeAnalytics()

        rate = analytics.calculate_conversion_rate(
            IntakeEvent.UPLOAD_STARTED,
            IntakeEvent.UPLOAD_COMPLETED,
        )

        assert rate == 0.0

    def test_conversion_rate_perfect(self):
        """Test 100% conversion rate."""
        analytics = IntakeAnalytics()

        with patch("app.services.intake_analytics.logger"):
            analytics.track(IntakeEvent.JOB_QUEUED, session_id="s1")
            analytics.track(IntakeEvent.JOB_COMPLETED, session_id="s1")
            analytics.track(IntakeEvent.JOB_QUEUED, session_id="s2")
            analytics.track(IntakeEvent.JOB_COMPLETED, session_id="s2")

        rate = analytics.calculate_conversion_rate(
            IntakeEvent.JOB_QUEUED,
            IntakeEvent.JOB_COMPLETED,
        )

        assert rate == 1.0

    def test_conversion_rate_zero_to_count(self):
        """Test 0% conversion rate."""
        analytics = IntakeAnalytics()

        with patch("app.services.intake_analytics.logger"):
            analytics.track(IntakeEvent.UPLOAD_STARTED, session_id="s1")
            analytics.track(IntakeEvent.UPLOAD_STARTED, session_id="s2")
            # None complete

        rate = analytics.calculate_conversion_rate(
            IntakeEvent.UPLOAD_STARTED,
            IntakeEvent.UPLOAD_COMPLETED,
        )

        assert rate == 0.0


class TestGetIntakeAnalytics:
    """Tests for get_intake_analytics singleton."""

    def test_returns_same_instance(self):
        """Test that get_intake_analytics returns the same instance."""
        # Reset singleton for test
        import app.services.intake_analytics as module

        module._analytics = None

        instance1 = get_intake_analytics()
        instance2 = get_intake_analytics()

        assert instance1 is instance2

    def test_creates_instance_if_none(self):
        """Test that it creates an instance if none exists."""
        import app.services.intake_analytics as module

        module._analytics = None

        instance = get_intake_analytics()

        assert isinstance(instance, IntakeAnalytics)
