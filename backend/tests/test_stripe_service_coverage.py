"""Additional coverage tests for StripeService.

These tests target specific code paths not covered by existing tests:
- Lines 75-85: Get existing customer ID from transactions
- Lines 198-228: _handle_checkout_completed
- Lines 305-341: _handle_invoice_paid
- Lines 349-374: _handle_invoice_failed
- Lines 464, 466: _get_plan_from_price
- Lines 481-483: get_stripe_service singleton
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.subscription import (
    BillingTransaction,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.models.user import User
from app.services.stripe_service import StripeService, get_stripe_service


class TestGetOrCreateCustomerExistingTransaction:
    """Test get_or_create_customer when customer ID exists in transactions."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with Stripe configured."""
        settings = MagicMock()
        settings.stripe_secret_key = "sk_test_123"
        settings.stripe_webhook_secret = "whsec_test123"
        settings.stripe_basic_monthly_price_id = "price_basic_monthly"
        settings.stripe_basic_yearly_price_id = "price_basic_yearly"
        settings.stripe_pro_monthly_price_id = "price_pro_monthly"
        settings.stripe_pro_yearly_price_id = "price_pro_yearly"
        settings.frontend_url = "http://localhost:5173"
        return settings

    @pytest.mark.asyncio
    async def test_returns_existing_customer_id_from_transaction(self, mock_settings):
        """Test that existing customer ID is returned from billing transaction."""
        user_id = uuid4()
        customer_id = "cus_existing123"

        with patch(
            "app.services.stripe_service.get_settings", return_value=mock_settings
        ):
            service = StripeService()

        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.email = "test@example.com"
        mock_user.display_name = "Test User"

        # Mock subscription exists
        mock_subscription = MagicMock(spec=Subscription)
        mock_sub_result = MagicMock()
        mock_sub_result.scalars.return_value.first.return_value = mock_subscription

        # Mock transaction with customer ID
        mock_transaction = MagicMock(spec=BillingTransaction)
        mock_transaction.provider_ref = f"{customer_id}:pi_test123"
        mock_tx_result = MagicMock()
        mock_tx_result.scalars.return_value.first.return_value = mock_transaction

        mock_db = AsyncMock()
        # First call returns subscription, second returns transaction
        mock_db.execute = AsyncMock(side_effect=[mock_sub_result, mock_tx_result])

        with patch("app.services.stripe_service.stripe"):
            result = await service.get_or_create_customer(mock_db, mock_user)

        assert result == customer_id

    @pytest.mark.asyncio
    async def test_creates_customer_when_no_transaction_exists(self, mock_settings):
        """Test customer creation when no existing transaction."""
        user_id = uuid4()

        with patch(
            "app.services.stripe_service.get_settings", return_value=mock_settings
        ):
            service = StripeService()

        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.email = "test@example.com"
        mock_user.display_name = "Test User"

        # Mock subscription exists but no transaction
        mock_subscription = MagicMock(spec=Subscription)
        mock_sub_result = MagicMock()
        mock_sub_result.scalars.return_value.first.return_value = mock_subscription

        mock_tx_result = MagicMock()
        mock_tx_result.scalars.return_value.first.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_sub_result, mock_tx_result])

        with patch("app.services.stripe_service.stripe") as mock_stripe:
            mock_stripe.Customer.create.return_value = MagicMock(id="cus_new123")
            result = await service.get_or_create_customer(mock_db, mock_user)

        assert result == "cus_new123"


class TestHandleCheckoutCompleted:
    """Test _handle_checkout_completed method."""

    @pytest.fixture
    def service(self):
        """Create service with mocked settings."""
        settings = MagicMock()
        settings.stripe_secret_key = "sk_test_123"
        settings.stripe_webhook_secret = "whsec_test123"
        settings.stripe_basic_monthly_price_id = "price_basic_monthly"
        settings.stripe_basic_yearly_price_id = "price_basic_yearly"
        settings.stripe_pro_monthly_price_id = "price_pro_monthly"
        settings.stripe_pro_yearly_price_id = "price_pro_yearly"
        settings.frontend_url = "http://localhost:5173"

        with patch("app.services.stripe_service.get_settings", return_value=settings):
            return StripeService()

    @pytest.mark.asyncio
    async def test_missing_user_id_metadata(self, service):
        """Test checkout completed with missing user_id in metadata."""
        mock_db = AsyncMock()
        session_data = {
            "metadata": {},
            "subscription": "sub_123",
            "customer": "cus_123",
        }

        result = await service._handle_checkout_completed(mock_db, session_data)

        assert result == {"error": "missing_user_id"}

    @pytest.mark.asyncio
    async def test_successful_checkout_completed(self, service):
        """Test successful checkout completion."""
        mock_db = AsyncMock()
        user_id = str(uuid4())
        session_data = {
            "metadata": {"user_id": user_id, "plan": "pro_monthly"},
            "subscription": "sub_123",
            "customer": "cus_123",
        }

        result = await service._handle_checkout_completed(mock_db, session_data)

        assert result["user_id"] == user_id
        assert result["subscription_id"] == "sub_123"
        assert result["customer_id"] == "cus_123"
        assert result["plan"] == "pro_monthly"

    @pytest.mark.asyncio
    async def test_checkout_completed_default_plan(self, service):
        """Test checkout completion with default plan."""
        mock_db = AsyncMock()
        user_id = str(uuid4())
        session_data = {
            "metadata": {"user_id": user_id},  # No plan specified
            "subscription": "sub_123",
            "customer": "cus_123",
        }

        result = await service._handle_checkout_completed(mock_db, session_data)

        assert result["plan"] == "pro_monthly"  # Default


class TestHandleInvoicePaid:
    """Test _handle_invoice_paid method."""

    @pytest.fixture
    def service(self):
        """Create service with mocked settings."""
        settings = MagicMock()
        settings.stripe_secret_key = "sk_test_123"
        settings.stripe_webhook_secret = "whsec_test123"
        settings.stripe_basic_monthly_price_id = "price_basic_monthly"
        settings.stripe_basic_yearly_price_id = "price_basic_yearly"
        settings.stripe_pro_monthly_price_id = "price_pro_monthly"
        settings.stripe_pro_yearly_price_id = "price_pro_yearly"
        settings.frontend_url = "http://localhost:5173"

        with patch("app.services.stripe_service.get_settings", return_value=settings):
            return StripeService()

    @pytest.mark.asyncio
    async def test_invoice_paid_success(self, service):
        """Test successful invoice payment recording."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        user_id = str(uuid4())
        invoice_data = {
            "subscription": "sub_123",
            "customer": "cus_123",
            "id": "inv_123",
            "amount_paid": 1999,
            "currency": "usd",
        }

        with patch("app.services.stripe_service.stripe") as mock_stripe:
            mock_sub = MagicMock()
            mock_sub.metadata.get.return_value = user_id
            mock_stripe.Subscription.retrieve.return_value = mock_sub

            result = await service._handle_invoice_paid(mock_db, invoice_data)

        assert result["user_id"] == user_id
        assert result["amount"] == 1999
        assert result["currency"] == "USD"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoice_paid_no_subscription_id(self, service):
        """Test invoice without subscription ID."""
        mock_db = AsyncMock()
        invoice_data = {
            "customer": "cus_123",
            "amount_paid": 1999,
        }

        result = await service._handle_invoice_paid(mock_db, invoice_data)

        assert result == {"subscription_id": None}

    @pytest.mark.asyncio
    async def test_invoice_paid_no_user_id(self, service):
        """Test invoice where subscription has no user_id metadata."""
        mock_db = AsyncMock()
        invoice_data = {
            "subscription": "sub_123",
            "customer": "cus_123",
            "amount_paid": 1999,
        }

        with patch("app.services.stripe_service.stripe") as mock_stripe:
            mock_sub = MagicMock()
            mock_sub.metadata.get.return_value = None  # No user_id
            mock_stripe.Subscription.retrieve.return_value = mock_sub

            result = await service._handle_invoice_paid(mock_db, invoice_data)

        assert result == {"subscription_id": "sub_123"}

    @pytest.mark.asyncio
    async def test_invoice_paid_stripe_error(self, service):
        """Test invoice payment when Stripe API fails."""
        mock_db = AsyncMock()
        invoice_data = {
            "subscription": "sub_123",
            "customer": "cus_123",
            "amount_paid": 1999,
        }

        with patch("app.services.stripe_service.stripe") as mock_stripe:
            mock_stripe.Subscription.retrieve.side_effect = Exception("API error")

            result = await service._handle_invoice_paid(mock_db, invoice_data)

        assert result == {"subscription_id": "sub_123"}


class TestHandleInvoiceFailed:
    """Test _handle_invoice_failed method."""

    @pytest.fixture
    def service(self):
        """Create service with mocked settings."""
        settings = MagicMock()
        settings.stripe_secret_key = "sk_test_123"
        settings.stripe_webhook_secret = "whsec_test123"
        settings.stripe_basic_monthly_price_id = "price_basic_monthly"
        settings.stripe_basic_yearly_price_id = "price_basic_yearly"
        settings.stripe_pro_monthly_price_id = "price_pro_monthly"
        settings.stripe_pro_yearly_price_id = "price_pro_yearly"
        settings.frontend_url = "http://localhost:5173"

        with patch("app.services.stripe_service.get_settings", return_value=settings):
            return StripeService()

    @pytest.mark.asyncio
    async def test_invoice_failed_updates_subscription(self, service):
        """Test failed invoice updates subscription to past due."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        user_id = str(uuid4())
        invoice_data = {
            "subscription": "sub_123",
        }

        # Mock subscription lookup
        mock_subscription = MagicMock(spec=Subscription)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_subscription
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.stripe_service.stripe") as mock_stripe:
            mock_sub = MagicMock()
            mock_sub.metadata.get.return_value = user_id
            mock_stripe.Subscription.retrieve.return_value = mock_sub

            result = await service._handle_invoice_failed(mock_db, invoice_data)

        assert result["user_id"] == user_id
        assert result["status"] == "past_due"
        assert mock_subscription.status == SubscriptionStatus.PAST_DUE

    @pytest.mark.asyncio
    async def test_invoice_failed_no_subscription(self, service):
        """Test failed invoice when subscription not found in DB."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        user_id = str(uuid4())
        invoice_data = {
            "subscription": "sub_123",
        }

        # Mock no subscription found
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("app.services.stripe_service.stripe") as mock_stripe:
            mock_sub = MagicMock()
            mock_sub.metadata.get.return_value = user_id
            mock_stripe.Subscription.retrieve.return_value = mock_sub

            result = await service._handle_invoice_failed(mock_db, invoice_data)

        # Should not crash, returns subscription_id
        assert result == {"subscription_id": "sub_123"}

    @pytest.mark.asyncio
    async def test_invoice_failed_no_subscription_id(self, service):
        """Test failed invoice without subscription ID."""
        mock_db = AsyncMock()
        invoice_data = {}

        result = await service._handle_invoice_failed(mock_db, invoice_data)

        assert result == {"subscription_id": None}

    @pytest.mark.asyncio
    async def test_invoice_failed_stripe_error(self, service):
        """Test failed invoice when Stripe API fails."""
        mock_db = AsyncMock()
        invoice_data = {
            "subscription": "sub_123",
        }

        with patch("app.services.stripe_service.stripe") as mock_stripe:
            mock_stripe.Subscription.retrieve.side_effect = Exception("API error")

            result = await service._handle_invoice_failed(mock_db, invoice_data)

        assert result == {"subscription_id": "sub_123"}

    @pytest.mark.asyncio
    async def test_invoice_failed_no_user_id_in_metadata(self, service):
        """Test failed invoice where subscription has no user_id."""
        mock_db = AsyncMock()
        invoice_data = {
            "subscription": "sub_123",
        }

        with patch("app.services.stripe_service.stripe") as mock_stripe:
            mock_sub = MagicMock()
            mock_sub.metadata.get.return_value = None
            mock_stripe.Subscription.retrieve.return_value = mock_sub

            result = await service._handle_invoice_failed(mock_db, invoice_data)

        assert result == {"subscription_id": "sub_123"}


class TestGetPlanFromPrice:
    """Test _get_plan_from_price method."""

    @pytest.fixture
    def service(self):
        """Create service with mocked settings."""
        settings = MagicMock()
        settings.stripe_secret_key = "sk_test_123"
        settings.stripe_webhook_secret = "whsec_test123"
        settings.stripe_basic_monthly_price_id = "price_basic_monthly"
        settings.stripe_basic_yearly_price_id = "price_basic_yearly"
        settings.stripe_pro_monthly_price_id = "price_pro_monthly"
        settings.stripe_pro_yearly_price_id = "price_pro_yearly"
        settings.frontend_url = "http://localhost:5173"

        with patch("app.services.stripe_service.get_settings", return_value=settings):
            return StripeService()

    def test_basic_monthly_price(self, service):
        """Test mapping basic monthly price ID."""
        result = service._get_plan_from_price("price_basic_monthly")
        assert result == SubscriptionPlan.BASIC_MONTHLY

    def test_basic_yearly_price(self, service):
        """Test mapping basic yearly price ID."""
        result = service._get_plan_from_price("price_basic_yearly")
        assert result == SubscriptionPlan.BASIC_YEARLY

    def test_pro_monthly_price(self, service):
        """Test mapping pro monthly price ID."""
        result = service._get_plan_from_price("price_pro_monthly")
        assert result == SubscriptionPlan.PRO_MONTHLY

    def test_pro_yearly_price(self, service):
        """Test mapping pro yearly price ID."""
        result = service._get_plan_from_price("price_pro_yearly")
        assert result == SubscriptionPlan.PRO_YEARLY

    def test_unknown_price_returns_free(self, service):
        """Test unknown price ID returns FREE plan."""
        result = service._get_plan_from_price("price_unknown")
        assert result == SubscriptionPlan.FREE

    def test_none_price_returns_free(self, service):
        """Test None price ID returns FREE plan."""
        result = service._get_plan_from_price(None)
        assert result == SubscriptionPlan.FREE


class TestGetStripeServiceSingleton:
    """Test get_stripe_service singleton function."""

    def test_get_stripe_service_creates_instance(self):
        """Test singleton creation."""
        import app.services.stripe_service as stripe_module

        # Reset the singleton
        stripe_module._stripe_service = None

        settings = MagicMock()
        settings.stripe_secret_key = "sk_test_123"
        settings.stripe_webhook_secret = "whsec_test123"
        settings.stripe_basic_monthly_price_id = None
        settings.stripe_basic_yearly_price_id = None
        settings.stripe_pro_monthly_price_id = None
        settings.stripe_pro_yearly_price_id = None
        settings.frontend_url = None

        with patch("app.services.stripe_service.get_settings", return_value=settings):
            service1 = get_stripe_service()
            service2 = get_stripe_service()

        assert service1 is service2

        # Clean up
        stripe_module._stripe_service = None

    def test_get_stripe_service_returns_same_instance(self):
        """Test singleton returns same instance."""
        import app.services.stripe_service as stripe_module

        # Reset
        stripe_module._stripe_service = None

        settings = MagicMock()
        settings.stripe_secret_key = "sk_test_123"
        settings.stripe_webhook_secret = "whsec_test123"
        settings.stripe_basic_monthly_price_id = None
        settings.stripe_basic_yearly_price_id = None
        settings.stripe_pro_monthly_price_id = None
        settings.stripe_pro_yearly_price_id = None
        settings.frontend_url = None

        with patch("app.services.stripe_service.get_settings", return_value=settings):
            service = get_stripe_service()
            assert stripe_module._stripe_service is service

        # Clean up
        stripe_module._stripe_service = None


class TestSyncSubscription:
    """Test _sync_subscription method."""

    @pytest.fixture
    def service(self):
        """Create service with mocked settings."""
        settings = MagicMock()
        settings.stripe_secret_key = "sk_test_123"
        settings.stripe_webhook_secret = "whsec_test123"
        settings.stripe_basic_monthly_price_id = "price_basic_monthly"
        settings.stripe_basic_yearly_price_id = "price_basic_yearly"
        settings.stripe_pro_monthly_price_id = "price_pro_monthly"
        settings.stripe_pro_yearly_price_id = "price_pro_yearly"
        settings.frontend_url = "http://localhost:5173"

        with patch("app.services.stripe_service.get_settings", return_value=settings):
            return StripeService()

    @pytest.mark.asyncio
    async def test_sync_creates_new_subscription(self, service):
        """Test syncing creates new subscription if none exists."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        user_id = str(uuid4())

        # No existing subscription
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        subscription_data = {
            "metadata": {"user_id": user_id},
            "status": "active",
            "items": {"data": [{"price": {"id": "price_pro_monthly"}}]},
            "current_period_start": 1704067200,  # 2024-01-01
            "current_period_end": 1706745600,  # 2024-02-01
        }

        result = await service._sync_subscription(mock_db, subscription_data)

        assert result["user_id"] == user_id
        assert result["plan"] == "pro_monthly"
        assert result["status"] == "active"
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_updates_existing_subscription(self, service):
        """Test syncing updates existing subscription."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        user_id = str(uuid4())

        # Existing subscription
        mock_subscription = MagicMock(spec=Subscription)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_subscription
        mock_db.execute = AsyncMock(return_value=mock_result)

        subscription_data = {
            "metadata": {"user_id": user_id},
            "status": "active",
            "items": {"data": [{"price": {"id": "price_pro_yearly"}}]},
            "current_period_start": 1704067200,
            "current_period_end": 1735689600,
        }

        result = await service._sync_subscription(mock_db, subscription_data)

        assert mock_subscription.plan_code == SubscriptionPlan.PRO_YEARLY
        assert mock_subscription.status == SubscriptionStatus.ACTIVE
        assert result["plan"] == "pro_yearly"

    @pytest.mark.asyncio
    async def test_sync_missing_user_id(self, service):
        """Test syncing with missing user_id returns error."""
        mock_db = AsyncMock()

        subscription_data = {
            "metadata": {},
            "status": "active",
        }

        result = await service._sync_subscription(mock_db, subscription_data)

        assert result == {"error": "missing_user_id"}

    @pytest.mark.asyncio
    async def test_sync_past_due_status(self, service):
        """Test syncing maps past_due status correctly."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        user_id = str(uuid4())

        mock_subscription = MagicMock(spec=Subscription)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_subscription
        mock_db.execute = AsyncMock(return_value=mock_result)

        subscription_data = {
            "metadata": {"user_id": user_id},
            "status": "past_due",
            "items": {"data": []},
            "current_period_start": 1704067200,
            "current_period_end": 1706745600,
        }

        result = await service._sync_subscription(mock_db, subscription_data)

        assert mock_subscription.status == SubscriptionStatus.PAST_DUE
        assert result["status"] == "past_due"

    @pytest.mark.asyncio
    async def test_sync_canceled_status(self, service):
        """Test syncing maps canceled status correctly."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        user_id = str(uuid4())

        mock_subscription = MagicMock(spec=Subscription)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_subscription
        mock_db.execute = AsyncMock(return_value=mock_result)

        subscription_data = {
            "metadata": {"user_id": user_id},
            "status": "canceled",
            "items": {"data": []},
            "current_period_start": 1704067200,
            "current_period_end": 1706745600,
        }

        _result = await service._sync_subscription(mock_db, subscription_data)

        assert mock_subscription.status == SubscriptionStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_sync_unpaid_status(self, service):
        """Test syncing maps unpaid status to past_due."""
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()

        user_id = str(uuid4())

        mock_subscription = MagicMock(spec=Subscription)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_subscription
        mock_db.execute = AsyncMock(return_value=mock_result)

        subscription_data = {
            "metadata": {"user_id": user_id},
            "status": "unpaid",
            "items": {"data": []},
            "current_period_start": 1704067200,
            "current_period_end": 1706745600,
        }

        _result = await service._sync_subscription(mock_db, subscription_data)

        assert mock_subscription.status == SubscriptionStatus.PAST_DUE


class TestSubscriptionCreatedEmailIntegration:
    """Test that subscription created sends confirmation email."""

    @pytest.fixture
    def service(self):
        """Create service with mocked settings."""
        settings = MagicMock()
        settings.stripe_secret_key = "sk_test_123"
        settings.stripe_webhook_secret = "whsec_test123"
        settings.stripe_basic_monthly_price_id = "price_basic_monthly"
        settings.stripe_basic_yearly_price_id = "price_basic_yearly"
        settings.stripe_pro_monthly_price_id = "price_pro_monthly"
        settings.stripe_pro_yearly_price_id = "price_pro_yearly"
        settings.frontend_url = "http://localhost:5173"

        with patch("app.services.stripe_service.get_settings", return_value=settings):
            return StripeService()

    @pytest.mark.asyncio
    async def test_subscription_created_sends_email(self, service):
        """Test that creating a subscription sends confirmation email."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        user_id = str(uuid4())

        # Mock subscription lookup
        mock_subscription = MagicMock(spec=Subscription)
        mock_sub_result = MagicMock()
        mock_sub_result.scalars.return_value.first.return_value = mock_subscription

        # Mock user lookup
        mock_user = MagicMock()
        mock_user.email = "subscriber@test.com"
        mock_user.display_name = "Test Subscriber"
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute = AsyncMock(side_effect=[mock_sub_result, mock_user_result])

        subscription_data = {
            "metadata": {"user_id": user_id},
            "status": "active",
            "items": {"data": [{"price": {"id": "price_pro_monthly"}}]},
            "current_period_start": 1704067200,
            "current_period_end": 1706745600,
        }

        with patch("app.services.stripe_service.get_email_service") as mock_get_email:
            mock_email_service = MagicMock()
            mock_email_service.send_subscription_confirmation = AsyncMock(
                return_value=True
            )
            mock_get_email.return_value = mock_email_service

            _result = await service._handle_subscription_created(
                mock_db, subscription_data
            )

        # Email should have been sent
        mock_email_service.send_subscription_confirmation.assert_called_once()
        call_args = mock_email_service.send_subscription_confirmation.call_args
        assert call_args[0][0] == "subscriber@test.com"
        assert call_args[0][1] == "Test Subscriber"

    @pytest.mark.asyncio
    async def test_subscription_created_email_failure_doesnt_break(self, service):
        """Test that email failure doesn't break subscription creation."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        user_id = str(uuid4())

        mock_subscription = MagicMock(spec=Subscription)
        mock_sub_result = MagicMock()
        mock_sub_result.scalars.return_value.first.return_value = mock_subscription

        mock_user = MagicMock()
        mock_user.email = "subscriber@test.com"
        mock_user.display_name = "Test Subscriber"
        mock_user_result = MagicMock()
        mock_user_result.scalar_one_or_none.return_value = mock_user

        mock_db.execute = AsyncMock(side_effect=[mock_sub_result, mock_user_result])

        subscription_data = {
            "metadata": {"user_id": user_id},
            "status": "active",
            "items": {"data": [{"price": {"id": "price_pro_monthly"}}]},
            "current_period_start": 1704067200,
            "current_period_end": 1706745600,
        }

        with patch("app.services.stripe_service.get_email_service") as mock_get_email:
            mock_email_service = MagicMock()
            mock_email_service.send_subscription_confirmation = AsyncMock(
                side_effect=Exception("Email service down")
            )
            mock_get_email.return_value = mock_email_service

            # Should not raise even though email fails
            result = await service._handle_subscription_created(
                mock_db, subscription_data
            )

        # Should still return success result
        assert result["user_id"] == user_id
        assert "error" not in result
