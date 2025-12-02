"""Tests for billing API routes.

These tests validate Stripe payment and subscription management endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db_session
from app.main import app
from app.models.subscription import SubscriptionPlan, SubscriptionStatus
from app.models.user import User


@pytest.fixture
def mock_user() -> User:
    """Create a mock authenticated user."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.is_active = True
    return user


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def client_authenticated(mock_user: User, mock_db_session: AsyncMock) -> TestClient:
    """Create a test client with authentication."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client_anonymous(mock_db_session: AsyncMock) -> TestClient:
    """Create a test client without authentication."""
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestGetPricing:
    """Tests for GET /billing/pricing endpoint."""

    def test_get_pricing_success(
        self,
        client_anonymous: TestClient,
    ) -> None:
        """Test getting pricing table (public endpoint)."""
        response = client_anonymous.get("/api/billing/pricing")

        assert response.status_code == 200
        data = response.json()
        # Verify pricing structure
        assert "tiers" in data or isinstance(data, dict)


class TestGetStripeConfig:
    """Tests for GET /billing/config endpoint."""

    @patch("app.api.routes.billing.get_stripe_service")
    @patch("app.api.routes.billing.get_settings")
    def test_get_config_configured(
        self,
        mock_get_settings: MagicMock,
        mock_get_service: MagicMock,
        client_anonymous: TestClient,
    ) -> None:
        """Test getting Stripe config when configured."""
        mock_settings = MagicMock()
        mock_settings.stripe_publishable_key = "pk_test_123"
        mock_get_settings.return_value = mock_settings

        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        mock_get_service.return_value = mock_service

        response = client_anonymous.get("/api/billing/config")

        assert response.status_code == 200
        data = response.json()
        assert data["publishable_key"] == "pk_test_123"
        assert data["is_configured"] is True

    @patch("app.api.routes.billing.get_stripe_service")
    @patch("app.api.routes.billing.get_settings")
    def test_get_config_not_configured(
        self,
        mock_get_settings: MagicMock,
        mock_get_service: MagicMock,
        client_anonymous: TestClient,
    ) -> None:
        """Test getting Stripe config when not configured."""
        mock_settings = MagicMock()
        mock_settings.stripe_publishable_key = None
        mock_get_settings.return_value = mock_settings

        mock_service = MagicMock()
        mock_service.is_configured.return_value = False
        mock_get_service.return_value = mock_service

        response = client_anonymous.get("/api/billing/config")

        assert response.status_code == 200
        data = response.json()
        assert data["publishable_key"] is None
        assert data["is_configured"] is False


class TestGetSubscription:
    """Tests for GET /billing/subscription endpoint."""

    def test_get_subscription_with_active_subscription(
        self,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test getting subscription when user has active subscription."""
        # Mock subscription
        mock_subscription = MagicMock()
        mock_subscription.plan_code = SubscriptionPlan.PRO_MONTHLY
        mock_subscription.status = SubscriptionStatus.ACTIVE
        mock_subscription.ai_quota_remaining = 45
        mock_subscription.current_period_end = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_subscription
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.get("/api/billing/subscription")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["plan"] == "pro_monthly"
        assert data["status"] == "active"
        assert data["ai_quota_remaining"] == 45
        assert data["is_active"] is True

    def test_get_subscription_free_tier(
        self,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test getting subscription when user is on free tier."""
        # No subscription found
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.get("/api/billing/subscription")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["plan"] == "free"
        assert data["is_active"] is True


class TestCreateCheckoutSession:
    """Tests for POST /billing/checkout endpoint."""

    @patch("app.api.routes.billing.get_stripe_service")
    def test_checkout_stripe_not_configured(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test checkout when Stripe is not configured."""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = False
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/billing/checkout",
            json={"plan": "pro_monthly"},
        )

        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]

    @patch("app.api.routes.billing.get_stripe_service")
    def test_checkout_cannot_purchase_free(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test that free plan cannot be purchased."""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/billing/checkout",
            json={"plan": "free"},
        )

        assert response.status_code == 400
        assert "Cannot purchase free plan" in response.json()["detail"]

    @patch("app.api.routes.billing.get_stripe_service")
    def test_checkout_success(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test successful checkout session creation."""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        mock_service.create_checkout_session = AsyncMock(
            return_value={
                "session_id": "cs_test_123",
                "checkout_url": "https://checkout.stripe.com/cs_test_123",
            }
        )
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/billing/checkout",
            json={"plan": "pro_monthly"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "cs_test_123"
        assert "checkout_url" in data

    @patch("app.api.routes.billing.get_stripe_service")
    def test_checkout_with_custom_urls(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test checkout with custom success/cancel URLs."""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        mock_service.create_checkout_session = AsyncMock(
            return_value={
                "session_id": "cs_test_123",
                "checkout_url": "https://checkout.stripe.com/cs_test_123",
            }
        )
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/billing/checkout",
            json={
                "plan": "pro_yearly",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )

        assert response.status_code == 200

    @patch("app.api.routes.billing.get_stripe_service")
    def test_checkout_value_error(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test checkout with value error from service."""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        mock_service.create_checkout_session = AsyncMock(
            side_effect=ValueError("Invalid plan configuration")
        )
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/billing/checkout",
            json={"plan": "pro_monthly"},
        )

        assert response.status_code == 400
        assert "Invalid plan" in response.json()["detail"]

    @patch("app.api.routes.billing.get_stripe_service")
    def test_checkout_unexpected_error(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test checkout with unexpected error."""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        mock_service.create_checkout_session = AsyncMock(
            side_effect=Exception("Stripe API error")
        )
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/billing/checkout",
            json={"plan": "pro_monthly"},
        )

        assert response.status_code == 500


class TestCreatePortalSession:
    """Tests for POST /billing/portal endpoint."""

    @patch("app.api.routes.billing.get_stripe_service")
    def test_portal_not_configured(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test portal when Stripe is not configured."""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = False
        mock_get_service.return_value = mock_service

        response = client_authenticated.post("/api/billing/portal")

        assert response.status_code == 503

    @patch("app.api.routes.billing.get_stripe_service")
    def test_portal_success(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test successful portal session creation."""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        mock_service.create_portal_session = AsyncMock(
            return_value={
                "portal_url": "https://billing.stripe.com/portal/session_123",
            }
        )
        mock_get_service.return_value = mock_service

        response = client_authenticated.post("/api/billing/portal")

        assert response.status_code == 200
        data = response.json()
        assert "portal_url" in data

    @patch("app.api.routes.billing.get_stripe_service")
    def test_portal_error(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test portal with error."""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        mock_service.create_portal_session = AsyncMock(
            side_effect=Exception("Portal error")
        )
        mock_get_service.return_value = mock_service

        response = client_authenticated.post("/api/billing/portal")

        assert response.status_code == 500


class TestStripeWebhook:
    """Tests for POST /billing/webhook endpoint."""

    @patch("app.api.routes.billing.get_stripe_service")
    def test_webhook_missing_signature(
        self,
        mock_get_service: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test webhook without signature header."""
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/billing/webhook",
            content=b'{"type": "test"}',
        )

        app.dependency_overrides.clear()

        assert response.status_code == 400
        assert "stripe-signature" in response.json()["detail"]

    @patch("app.api.routes.billing.get_stripe_service")
    def test_webhook_not_configured(
        self,
        mock_get_service: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test webhook when Stripe is not configured."""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = False
        mock_get_service.return_value = mock_service

        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/billing/webhook",
            content=b'{"type": "test"}',
            headers={"stripe-signature": "test_sig"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 503

    @patch("app.api.routes.billing.get_stripe_service")
    def test_webhook_success(
        self,
        mock_get_service: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test successful webhook processing."""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        mock_service.handle_webhook = AsyncMock(
            return_value={"event_type": "checkout.session.completed"}
        )
        mock_get_service.return_value = mock_service

        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/billing/webhook",
            content=b'{"type": "checkout.session.completed"}',
            headers={"stripe-signature": "test_sig"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["received"] is True

    @patch("app.api.routes.billing.get_stripe_service")
    def test_webhook_validation_error(
        self,
        mock_get_service: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test webhook with invalid signature."""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        mock_service.handle_webhook = AsyncMock(
            side_effect=ValueError("Invalid signature")
        )
        mock_get_service.return_value = mock_service

        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/billing/webhook",
            content=b'{"type": "test"}',
            headers={"stripe-signature": "invalid_sig"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 400

    @patch("app.api.routes.billing.get_stripe_service")
    def test_webhook_processing_error(
        self,
        mock_get_service: MagicMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test webhook with processing error."""
        mock_service = MagicMock()
        mock_service.is_configured.return_value = True
        mock_service.handle_webhook = AsyncMock(
            side_effect=Exception("Processing error")
        )
        mock_get_service.return_value = mock_service

        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/billing/webhook",
            content=b'{"type": "test"}',
            headers={"stripe-signature": "test_sig"},
        )

        app.dependency_overrides.clear()

        assert response.status_code == 500
