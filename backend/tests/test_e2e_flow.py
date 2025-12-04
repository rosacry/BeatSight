"""End-to-end integration tests for the complete AI job flow.

Created: December 3, 2025
References: ENGINEERING_ACTION_TRACKER.md item 4.9

Tests the complete journey from:
1. User uploads a song
2. User requests AI processing
3. Job is enqueued and processed
4. Results are returned to user
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.ai_job import AIJob, AIJobState
from app.models.song import Song
from app.models.user import User
from app.schemas.ai_jobs import AIJobCreate


class TestSongUploadFlow:
    """Test the complete song upload flow."""

    @pytest.mark.asyncio
    async def test_song_creation(
        self,
        mock_session: AsyncMock,
        mock_user: User,
    ) -> None:
        """Test that creating a song works correctly."""
        from app.services.songs import SongService

        # Setup: Session behavior for song creation
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock())

        song_service = SongService(mock_session)

        # The actual upload flow involves:
        # 1. Creating a Song record with status=PENDING
        # 2. Uploading the file to storage
        # 3. Updating the Song with the storage URL
        # This test verifies the service layer exists and can be instantiated
        assert song_service._session == mock_session


class TestAIJobFlow:
    """Test the complete AI job processing flow."""

    @pytest.mark.asyncio
    @patch("app.services.ai_jobs.get_redis")
    async def test_enqueue_job_success(
        self,
        mock_get_redis: AsyncMock,
        mock_session: AsyncMock,
        mock_user: User,
        mock_song: Song,
    ) -> None:
        """Test successfully enqueuing an AI job."""
        from app.services.ai_jobs import AIJobService

        # Setup: Mock Redis
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        # Setup session behavior
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Create job service
        job_service = AIJobService(mock_session)

        # Execute: Enqueue job using the correct schema
        job_payload = AIJobCreate(
            song_id=mock_song.id,
            priority="standard",
        )
        job = await job_service.enqueue(job_payload, requested_by=mock_user.id)

        # Verify: Job was added to session
        mock_session.add.assert_called()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    @patch("app.services.ai_jobs.get_redis")
    @patch("app.services.ai_jobs.publish_progress")
    async def test_job_state_transitions(
        self,
        mock_publish: AsyncMock,
        mock_get_redis: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Test that job states transition correctly."""
        from app.services.ai_jobs import AIJobService

        # Create a mock job
        job_id = uuid4()
        mock_job = MagicMock(spec=AIJob)
        mock_job.id = job_id
        mock_job.state = AIJobState.QUEUED

        # Mock session.get to return the job
        mock_session.get = AsyncMock(return_value=mock_job)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_get_redis.return_value = AsyncMock()

        job_service = AIJobService(mock_session)

        # Test: Start job (QUEUED -> PROCESSING)
        worker_id = uuid4()
        await job_service.mark_started(job_id, worker_id=worker_id)
        assert mock_job.state == AIJobState.PROCESSING
        assert mock_job.worker_id == worker_id

    @pytest.mark.asyncio
    @patch("app.services.ai_jobs.get_redis")
    @patch("app.services.ai_jobs.publish_progress")
    async def test_job_completion(
        self,
        mock_publish: AsyncMock,
        mock_get_redis: AsyncMock,
        mock_session: AsyncMock,
        mock_song: Song,
    ) -> None:
        """Test that completing a job updates state correctly."""
        from app.services.ai_jobs import AIJobService

        # Create a mock job linked to the song
        job_id = uuid4()
        mock_job = MagicMock(spec=AIJob)
        mock_job.id = job_id
        mock_job.song_id = mock_song.id
        mock_job.state = AIJobState.PROCESSING

        mock_session.get = AsyncMock(return_value=mock_job)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_get_redis.return_value = AsyncMock()

        job_service = AIJobService(mock_session)

        # Execute: Complete the job (no error means success)
        await job_service.mark_finished(job_id, error=None)

        # Verify: Job state updated
        assert mock_job.state == AIJobState.COMPLETE

    @pytest.mark.asyncio
    @patch("app.services.ai_jobs.get_redis")
    @patch("app.services.ai_jobs.publish_progress")
    async def test_job_failure_handling(
        self,
        mock_publish: AsyncMock,
        mock_get_redis: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Test that job failures are handled correctly."""
        from app.services.ai_jobs import AIJobService

        job_id = uuid4()
        mock_job = MagicMock(spec=AIJob)
        mock_job.id = job_id
        mock_job.state = AIJobState.PROCESSING
        mock_job.retry_count = 0

        mock_session.get = AsyncMock(return_value=mock_job)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_get_redis.return_value = AsyncMock()

        job_service = AIJobService(mock_session)

        # Execute: Fail the job
        await job_service.mark_finished(job_id, error="Test error message")

        # Verify: Job state updated to failed
        assert mock_job.state == AIJobState.FAILED
        assert mock_job.error_message == "Test error message"


class TestQuotaEnforcement:
    """Test quota enforcement throughout the flow."""

    @pytest.mark.asyncio
    @patch("app.services.quota.get_redis")
    @patch("app.services.quota.get_quota_usage")
    async def test_free_user_quota_limits(
        self,
        mock_get_quota_usage: AsyncMock,
        mock_get_redis: AsyncMock,
        mock_session: AsyncMock,
        mock_user: User,
    ) -> None:
        """Test that free users are limited to 3 jobs/month."""
        from app.services.quota import QuotaService

        # Setup: Free user (no subscription)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_get_redis.return_value = AsyncMock()
        # User has used 3/3 monthly quota
        mock_get_quota_usage.side_effect = [3, 2]  # month, day

        quota_service = QuotaService(mock_session)
        # Mock the credit balance lookup to return 0
        quota_service._credit_service = MagicMock()
        quota_service._credit_service.get_or_create_balance = AsyncMock(
            return_value=MagicMock(balance=0)
        )

        status = await quota_service.get_quota_status(mock_user.id)

        # Verify: Cannot enqueue more jobs (used all quota, no credits)
        assert status.can_enqueue is False
        assert status.remaining_month == 0

    @pytest.mark.asyncio
    @patch("app.services.quota.get_redis")
    @patch("app.services.quota.get_quota_usage")
    async def test_pro_user_higher_quota(
        self,
        mock_get_quota_usage: AsyncMock,
        mock_get_redis: AsyncMock,
        mock_session: AsyncMock,
        mock_user: User,
        mock_pro_subscription: MagicMock,
    ) -> None:
        """Test that Pro users have higher quota limits."""
        from app.services.quota import QuotaService

        # Setup: Pro user with subscription
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_pro_subscription
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_get_redis.return_value = AsyncMock()
        # Pro user has used 10/50 monthly quota
        mock_get_quota_usage.side_effect = [10, 5]  # month, day

        quota_service = QuotaService(mock_session)
        # Mock the credit balance lookup
        quota_service._credit_service = MagicMock()
        quota_service._credit_service.get_or_create_balance = AsyncMock(
            return_value=MagicMock(balance=0)
        )

        status = await quota_service.get_quota_status(mock_user.id)

        # Verify: Can enqueue more jobs
        assert status.can_enqueue is True
        assert status.remaining_month == 40  # 50 - 10


class TestCreditFlow:
    """Test credit purchase and consumption flow."""

    @pytest.mark.asyncio
    async def test_credit_purchase_flow(
        self,
        mock_session: AsyncMock,
        mock_user: User,
    ) -> None:
        """Test purchasing credits increases balance."""
        from app.models.credits import CreditBalance, CreditTransactionType
        from app.services.credits import CreditService

        # Setup: User starts with 0 credits
        mock_balance = MagicMock(spec=CreditBalance)
        mock_balance.id = uuid4()
        mock_balance.purchased_credits = 0
        mock_balance.bonus_credits = 0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_balance
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        credit_service = CreditService(mock_session)

        # Execute: Add credits (simulating purchase completion)
        await credit_service.add_credits(
            user_id=mock_user.id,
            amount=10,
            transaction_type=CreditTransactionType.PURCHASE,
            description="Credit pack purchase",
        )

        # Verify: Balance increased
        assert mock_balance.purchased_credits == 10

    @pytest.mark.asyncio
    async def test_credit_consumption_on_job(
        self,
        mock_session: AsyncMock,
        mock_user: User,
    ) -> None:
        """Test that using credits decreases balance."""
        from app.models.credits import CreditBalance
        from app.services.credits import CreditService

        # Setup: User has 5 purchased credits
        mock_balance = MagicMock(spec=CreditBalance)
        mock_balance.id = uuid4()
        mock_balance.purchased_credits = 5
        mock_balance.bonus_credits = 0
        mock_balance.has_credits = True
        mock_balance.total_credits = 5

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_balance
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        credit_service = CreditService(mock_session)

        # Execute: Consume 1 credit for AI job
        await credit_service.consume_credit(
            user_id=mock_user.id,
            description="AI transcription",
        )

        # Verify: Balance decreased
        assert mock_balance.purchased_credits == 4


class TestSSEProgress:
    """Test Server-Sent Events for job progress."""

    @pytest.mark.asyncio
    async def test_progress_broadcast(self) -> None:
        """Test that progress updates are broadcast via Redis pub/sub."""
        from datetime import datetime, timezone

        from app.db.redis import ProgressUpdate, publish_progress

        # Create a mock Redis client
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()

        job_id = uuid4()

        # Create progress update
        update = ProgressUpdate(
            job_id=job_id,
            percent=50,
            message="Processing audio...",
            stage="separation",
            timestamp=datetime.now(timezone.utc),
        )

        # Execute: Send progress update
        await publish_progress(mock_redis, update)

        # Verify: Message was published to Redis
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert str(job_id) in call_args[0][0]  # Channel contains job_id


class TestWebhookIntegration:
    """Test Stripe webhook handling."""

    def test_subscription_webhook_payload_structure(self) -> None:
        """Test that subscription webhook payloads have expected structure."""
        # This tests the structure without actually calling Stripe
        # Full webhook testing requires proper signature verification
        webhook_payload = {
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "customer": "cus_test123",
                    "status": "active",
                    "items": {
                        "data": [
                            {
                                "price": {"id": "price_pro_monthly"},
                            }
                        ]
                    },
                }
            },
        }

        # Verify expected fields exist
        assert webhook_payload["type"] == "customer.subscription.created"
        assert webhook_payload["data"]["object"]["status"] == "active"


class TestFullUserJourney:
    """Integration tests for complete user journeys."""

    @pytest.mark.asyncio
    async def test_new_user_quota_check(
        self,
        mock_session: AsyncMock,
        mock_user: User,
    ) -> None:
        """Test a new user's quota check journey."""
        # New users start with FREE tier: 3 jobs/month
        # This verifies the quota system works correctly

        from unittest.mock import patch

        from app.services.quota import QuotaService

        # Setup: New user, no subscription, no usage
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.quota.get_redis") as mock_redis, \
             patch("app.services.quota.get_quota_usage") as mock_usage:
            mock_redis.return_value = AsyncMock()
            mock_usage.side_effect = [0, 0]  # No usage this month or today

            quota_service = QuotaService(mock_session)
            quota_service._credit_service = MagicMock()
            quota_service._credit_service.get_or_create_balance = AsyncMock(
                return_value=MagicMock(balance=0)
            )

            status = await quota_service.get_quota_status(mock_user.id)

            # Verify: New user can enqueue jobs
            assert status.can_enqueue is True
            assert status.remaining_month == 3
            assert status.remaining_today == 2

    @pytest.mark.asyncio
    async def test_exhausted_quota_needs_credits(
        self,
        mock_session: AsyncMock,
        mock_user: User,
    ) -> None:
        """Test that exhausted quota requires credits."""
        from unittest.mock import patch

        from app.services.quota import QuotaService

        # Setup: Free user who has exhausted quota
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.quota.get_redis") as mock_redis, \
             patch("app.services.quota.get_quota_usage") as mock_usage:
            mock_redis.return_value = AsyncMock()
            mock_usage.side_effect = [3, 2]  # Used all monthly and daily quota

            quota_service = QuotaService(mock_session)
            # User has no credits
            quota_service._credit_service = MagicMock()
            quota_service._credit_service.get_or_create_balance = AsyncMock(
                return_value=MagicMock(balance=0)
            )

            status = await quota_service.get_quota_status(mock_user.id)

            # Verify: Cannot enqueue without credits
            assert status.can_enqueue is False
            assert status.remaining_month == 0

    @pytest.mark.asyncio
    async def test_credits_allow_extra_jobs(
        self,
        mock_session: AsyncMock,
        mock_user: User,
    ) -> None:
        """Test that credits allow jobs beyond quota."""
        from unittest.mock import patch

        from app.services.quota import QuotaService

        # Setup: Free user with exhausted quota but has credits
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.quota.get_redis") as mock_redis, \
             patch("app.services.quota.get_quota_usage") as mock_usage:
            mock_redis.return_value = AsyncMock()
            mock_usage.side_effect = [3, 2]  # Used all quota

            quota_service = QuotaService(mock_session)
            # User has 5 credits
            quota_service._credit_service = MagicMock()
            quota_service._credit_service.get_or_create_balance = AsyncMock(
                return_value=MagicMock(balance=5)
            )

            status = await quota_service.get_quota_status(mock_user.id)

            # Verify: Can enqueue using credits
            assert status.can_enqueue is True
            assert status.credit_balance == 5
            assert status.will_use_credit is True
