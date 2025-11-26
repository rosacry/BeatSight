"""Tests for Stripe billing endpoints and service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.subscription import (
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.models.user import User
from app.services.stripe_service import StripeService


# -------------------------------------------------------------------------
# Service Tests
# -------------------------------------------------------------------------


class TestStripeService:
    """Tests for StripeService."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with Stripe configured."""
        settings = MagicMock()
        settings.stripe_secret_key = "sk_test_123"
        settings.stripe_webhook_secret = "whsec_test123"
        settings.stripe_pro_monthly_price_id = "price_monthly"
        settings.stripe_pro_yearly_price_id = "price_yearly"
        settings.frontend_url = "http://localhost:5173"
        return settings

    @pytest.fixture
    def mock_settings_unconfigured(self):
        """Mock settings without Stripe configured."""
        settings = MagicMock()
        settings.stripe_secret_key = None
        settings.stripe_webhook_secret = None
        settings.stripe_pro_monthly_price_id = None
        settings.stripe_pro_yearly_price_id = None
        settings.frontend_url = None
        return settings

    @pytest.fixture
    def mock_stripe(self):
        """Mock Stripe API calls."""
        with patch("app.services.stripe_service.stripe") as mock:
            mock.Customer.create.return_value = MagicMock(id="cus_test123")
            mock.checkout.Session.create.return_value = MagicMock(
                id="cs_test123",
                url="https://checkout.stripe.com/test",
            )
            mock.billing_portal.Session.create.return_value = MagicMock(
                url="https://billing.stripe.com/portal/test",
            )
            mock.Subscription.retrieve.return_value = MagicMock(
                metadata={"user_id": str(uuid4())},
            )
            yield mock

    @pytest.fixture
    def stripe_service(self, mock_settings, mock_stripe):
        """Create a configured Stripe service."""
        with patch("app.services.stripe_service.get_settings", return_value=mock_settings):
            service = StripeService()
            return service

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock()
        # Mock scalars().first() to return None (no existing subscription)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        session.execute.return_value = mock_result
        return session

    @pytest.fixture
    def mock_user(self) -> User:
        """Create a mock user."""
        user = MagicMock(spec=User)
        user.id = uuid4()
        user.display_name = "Test User"
        user.email = "test@example.com"
        return user

    def test_is_configured_true(self, stripe_service):
        """Test is_configured returns True when keys are set."""
        assert stripe_service.is_configured() is True

    def test_is_configured_false(self, mock_settings_unconfigured):
        """Test is_configured returns False when keys missing."""
        with patch("app.services.stripe_service.get_settings", return_value=mock_settings_unconfigured):
            service = StripeService()
            assert service.is_configured() is False

    @pytest.mark.asyncio
    async def test_get_or_create_customer_new(
        self, stripe_service, mock_session, mock_user, mock_stripe
    ):
        """Test creating a new Stripe customer."""
        customer_id = await stripe_service.get_or_create_customer(mock_session, mock_user)
        
        assert customer_id == "cus_test123"
        mock_stripe.Customer.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_checkout_session(
        self, stripe_service, mock_session, mock_user, mock_stripe
    ):
        """Test creating a checkout session."""
        result = await stripe_service.create_checkout_session(
            db=mock_session,
            user=mock_user,
            plan=SubscriptionPlan.PRO_MONTHLY,
        )
        
        assert result["session_id"] == "cs_test123"
        assert "checkout.stripe.com" in result["checkout_url"]
        mock_stripe.checkout.Session.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_portal_session(
        self, stripe_service, mock_session, mock_user, mock_stripe
    ):
        """Test creating a portal session."""
        result = await stripe_service.create_portal_session(
            db=mock_session,
            user=mock_user,
        )
        
        assert "billing.stripe.com" in result["portal_url"]
        mock_stripe.billing_portal.Session.create.assert_called_once()

    def test_get_price_id(self, stripe_service):
        """Test plan to price ID mapping."""
        assert stripe_service._get_price_id(SubscriptionPlan.PRO_MONTHLY) == "price_monthly"
        assert stripe_service._get_price_id(SubscriptionPlan.PRO_YEARLY) == "price_yearly"
        assert stripe_service._get_price_id(SubscriptionPlan.FREE) is None

    def test_get_plan_from_price(self, stripe_service):
        """Test price ID to plan mapping."""
        assert stripe_service._get_plan_from_price("price_monthly") == SubscriptionPlan.PRO_MONTHLY
        assert stripe_service._get_plan_from_price("price_yearly") == SubscriptionPlan.PRO_YEARLY
        assert stripe_service._get_plan_from_price("unknown") == SubscriptionPlan.FREE

    @pytest.mark.asyncio
    async def test_create_checkout_not_configured(self, mock_settings_unconfigured, mock_session, mock_user):
        """Test checkout raises when Stripe not configured."""
        with patch("app.services.stripe_service.get_settings", return_value=mock_settings_unconfigured):
            service = StripeService()
            
            with pytest.raises(ValueError, match="not configured"):
                await service.create_checkout_session(
                    db=mock_session,
                    user=mock_user,
                    plan=SubscriptionPlan.PRO_MONTHLY,
                )


# -------------------------------------------------------------------------
# Webhook Handler Tests
# -------------------------------------------------------------------------


class TestWebhookHandlers:
    """Tests for Stripe webhook event handlers."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings."""
        settings = MagicMock()
        settings.stripe_secret_key = "sk_test_123"
        settings.stripe_webhook_secret = "whsec_test123"
        settings.stripe_pro_monthly_price_id = "price_monthly"
        settings.stripe_pro_yearly_price_id = "price_yearly"
        settings.frontend_url = "http://localhost:5173"
        return settings

    @pytest.fixture
    def mock_stripe(self):
        """Mock Stripe API."""
        with patch("app.services.stripe_service.stripe") as mock:
            yield mock

    @pytest.fixture
    def stripe_service(self, mock_settings, mock_stripe):
        """Create Stripe service."""
        with patch("app.services.stripe_service.get_settings", return_value=mock_settings):
            return StripeService()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.add = MagicMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_handle_checkout_completed(self, stripe_service, mock_session):
        """Test handling checkout completion."""
        user_id = str(uuid4())
        session_data = {
            "metadata": {
                "user_id": user_id,
                "plan": "pro_monthly",
            },
            "subscription": "sub_123",
            "customer": "cus_123",
        }
        
        result = await stripe_service._handle_checkout_completed(mock_session, session_data)
        
        assert result["user_id"] == user_id
        assert result["subscription_id"] == "sub_123"
        assert result["plan"] == "pro_monthly"

    @pytest.mark.asyncio
    async def test_handle_checkout_missing_user_id(self, stripe_service, mock_session):
        """Test checkout with missing user_id."""
        session_data = {
            "metadata": {},
            "subscription": "sub_123",
        }
        
        result = await stripe_service._handle_checkout_completed(mock_session, session_data)
        
        assert result.get("error") == "missing_user_id"

    @pytest.mark.asyncio
    async def test_handle_subscription_deleted(self, stripe_service, mock_session):
        """Test subscription cancellation."""
        user_id = str(uuid4())
        
        # Mock finding existing subscription
        mock_subscription = MagicMock()
        mock_subscription.status = SubscriptionStatus.ACTIVE
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_subscription
        mock_session.execute.return_value = mock_result
        
        subscription_data = {
            "metadata": {"user_id": user_id},
        }
        
        result = await stripe_service._handle_subscription_deleted(mock_session, subscription_data)
        
        assert result["status"] == "cancelled"
        assert mock_subscription.status == SubscriptionStatus.CANCELLED
        assert mock_subscription.plan_code == SubscriptionPlan.FREE

    @pytest.mark.asyncio
    async def test_sync_subscription_new(self, stripe_service, mock_session):
        """Test syncing a new subscription."""
        user_id = str(uuid4())
        
        # Mock no existing subscription
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result
        
        subscription_data = {
            "metadata": {"user_id": user_id},
            "status": "active",
            "items": {"data": [{"price": {"id": "price_monthly"}}]},
            "current_period_start": int(datetime.now(timezone.utc).timestamp()),
            "current_period_end": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
        }
        
        result = await stripe_service._sync_subscription(mock_session, subscription_data)
        
        assert result["plan"] == "pro_monthly"
        assert result["status"] == "active"
        mock_session.add.assert_called_once()  # New subscription added

    @pytest.mark.asyncio
    async def test_sync_subscription_existing(self, stripe_service, mock_session):
        """Test updating existing subscription."""
        user_id = str(uuid4())
        
        # Mock existing subscription
        existing_sub = MagicMock()
        existing_sub.plan_code = SubscriptionPlan.FREE
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = existing_sub
        mock_session.execute.return_value = mock_result
        
        subscription_data = {
            "metadata": {"user_id": user_id},
            "status": "active",
            "items": {"data": [{"price": {"id": "price_yearly"}}]},
            "current_period_start": int(datetime.now(timezone.utc).timestamp()),
            "current_period_end": int((datetime.now(timezone.utc) + timedelta(days=365)).timestamp()),
        }
        
        result = await stripe_service._sync_subscription(mock_session, subscription_data)
        
        assert result["plan"] == "pro_yearly"
        assert existing_sub.plan_code == SubscriptionPlan.PRO_YEARLY
