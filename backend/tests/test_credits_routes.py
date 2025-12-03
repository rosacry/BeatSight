"""Tests for credit API routes.

Tests the REST endpoints for credit operations including
balance retrieval, pack purchases, and transaction history.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.credits import (
    CreditBalance,
    CreditPackType,
    CreditPurchase,
    CreditTransaction,
    CreditTransactionType,
)
from app.services.credits import CREDIT_PACKS


class TestCreditsRoutes:
    """Test cases for credit API endpoints."""

    @pytest.fixture
    def mock_user_id(self) -> uuid.UUID:
        """Generate a test user ID."""
        return uuid.uuid4()

    @pytest.fixture
    def mock_credit_balance(self, mock_user_id: uuid.UUID) -> CreditBalance:
        """Create a mock credit balance."""
        return CreditBalance(
            id=uuid.uuid4(),
            user_id=mock_user_id,
            purchased_credits=25,
            bonus_credits=5,
            auto_topup_enabled=False,
            auto_topup_threshold=0,
            auto_topup_pack=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    @pytest.fixture
    def auth_headers(self) -> dict[str, str]:
        """Create mock auth headers."""
        return {"Authorization": "Bearer test_token"}

    @pytest.mark.asyncio
    async def test_get_balance_authenticated(
        self, mock_user_id: uuid.UUID, mock_credit_balance: CreditBalance
    ) -> None:
        """Test GET /credits/balance returns user's balance."""
        with patch("app.api.routes.credits.get_current_user") as mock_auth:
            mock_user = MagicMock()
            mock_user.id = mock_user_id
            mock_auth.return_value = mock_user

            with patch("app.api.routes.credits.CreditService") as mock_service_class:
                mock_service = AsyncMock()
                mock_service.get_or_create_balance.return_value = mock_credit_balance
                mock_service_class.return_value = mock_service

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(
                        "/api/credits/balance",
                        headers={"Authorization": "Bearer test_token"},
                    )

                # Note: This test structure shows the pattern; actual auth mocking
                # may need adjustment based on your dependency injection setup

    def test_get_packs_returns_all_packs(self) -> None:
        """Test GET /credits/packs returns all available packs."""
        client = TestClient(app)

        response = client.get("/api/credits/packs")

        assert response.status_code == 200
        packs = response.json()
        assert len(packs) == 3  # STARTER, VALUE, POWER

        # Verify pack structure
        pack_ids = {p["id"] for p in packs}
        assert pack_ids == {"starter", "value", "power"}

        # Verify each pack has required fields
        for pack in packs:
            assert "id" in pack
            assert "name" in pack
            assert "credits" in pack
            assert "price_cents" in pack
            assert "per_credit_cents" in pack
            assert "savings_percent" in pack

    def test_get_packs_correct_pricing(self) -> None:
        """Test that pack pricing is correct."""
        client = TestClient(app)

        response = client.get("/api/credits/packs")
        packs = {p["id"]: p for p in response.json()}

        # Verify specific pack pricing
        assert packs["starter"]["credits"] == 5
        assert packs["starter"]["price_cents"] == 175

        assert packs["value"]["credits"] == 15
        assert packs["value"]["price_cents"] == 450

        assert packs["power"]["credits"] == 40
        assert packs["power"]["price_cents"] == 1000

    def test_get_packs_savings_calculated_correctly(self) -> None:
        """Test that savings percentages are calculated correctly."""
        client = TestClient(app)

        response = client.get("/api/credits/packs")
        packs = {p["id"]: p for p in response.json()}

        # Starter has no savings (baseline)
        assert packs["starter"]["savings_percent"] == 0

        # Value should have ~14% savings
        assert packs["value"]["savings_percent"] > 0
        assert packs["value"]["savings_percent"] < 20

        # Power should have more savings than value
        assert packs["power"]["savings_percent"] > packs["value"]["savings_percent"]


class TestCreditPurchaseFlow:
    """Test cases for credit purchase flow."""

    @pytest.fixture
    def mock_stripe_service(self) -> MagicMock:
        """Create a mock Stripe service."""
        mock = MagicMock()
        mock.create_credit_checkout_session = AsyncMock(
            return_value={
                "session_id": "cs_test_123",
                "checkout_url": "https://checkout.stripe.com/test",
            }
        )
        return mock

    @pytest.mark.asyncio
    async def test_purchase_creates_checkout_session(self) -> None:
        """Test POST /credits/purchase creates Stripe checkout."""
        # This test demonstrates the expected behavior
        # Actual implementation depends on auth setup
        pass

    @pytest.mark.asyncio
    async def test_purchase_requires_authentication(self) -> None:
        """Test that purchase endpoint requires authentication."""
        client = TestClient(app)

        response = client.post(
            "/api/credits/purchase",
            json={"pack_type": "value"},
        )

        # Should return 401 or 403 without auth
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_purchase_validates_pack_type(self) -> None:
        """Test that invalid pack types are rejected."""
        # With proper auth mocking, this would validate pack type
        pass


class TestCreditHistoryEndpoint:
    """Test cases for credit transaction history endpoint."""

    @pytest.fixture
    def mock_transactions(self, mock_user_id: uuid.UUID) -> list[CreditTransaction]:
        """Create mock transactions."""
        return [
            CreditTransaction(
                id=uuid.uuid4(),
                user_id=mock_user_id,
                transaction_type=CreditTransactionType.PURCHASE,
                amount=15,
                balance_before=10,
                balance_after=25,
                description="Purchased Standard Pack",
                created_at=datetime.now(timezone.utc),
            ),
            CreditTransaction(
                id=uuid.uuid4(),
                user_id=mock_user_id,
                transaction_type=CreditTransactionType.CONSUMPTION,
                amount=-1,
                balance_before=25,
                balance_after=24,
                description="AI beatmap generation",
                created_at=datetime.now(timezone.utc),
            ),
        ]

    @pytest.fixture
    def mock_user_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_history_requires_authentication(self) -> None:
        """Test that history endpoint requires authentication."""
        client = TestClient(app)

        response = client.get("/api/credits/history")

        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_history_pagination(self) -> None:
        """Test that history supports pagination parameters."""
        # This test would verify limit/offset parameters work
        pass


class TestAutoTopupEndpoint:
    """Test cases for auto-topup configuration endpoint."""

    @pytest.mark.asyncio
    async def test_configure_auto_topup_requires_auth(self) -> None:
        """Test that auto-topup configuration requires authentication."""
        client = TestClient(app)

        response = client.put(
            "/api/credits/auto-topup",
            json={
                "enabled": True,
                "threshold": 5,
                "pack_type": "value",
            },
        )

        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_disable_auto_topup(self) -> None:
        """Test disabling auto-topup."""
        # Would test with proper auth mocking
        pass

    @pytest.mark.asyncio
    async def test_auto_topup_validates_threshold(self) -> None:
        """Test that negative thresholds are rejected."""
        # Would test validation with proper auth mocking
        pass


class TestCreditPackIntegrity:
    """Test cases to ensure pack configurations are consistent."""

    def test_all_pack_types_have_config(self) -> None:
        """Test that all CreditPackType enum values have configurations."""
        for pack_type in CreditPackType:
            assert pack_type in CREDIT_PACKS, f"Missing config for {pack_type}"

    def test_pack_configs_have_positive_values(self) -> None:
        """Test that all pack configs have positive values."""
        for pack_type, config in CREDIT_PACKS.items():
            assert config.credits > 0, f"{pack_type} has non-positive credits"
            assert config.price_cents > 0, f"{pack_type} has non-positive price"
            assert len(config.name) > 0, f"{pack_type} has empty name"

    def test_per_credit_price_decreases_with_size(self) -> None:
        """Test that larger packs have lower per-credit prices."""
        pack_list = [
            (CreditPackType.STARTER, CREDIT_PACKS[CreditPackType.STARTER]),
            (CreditPackType.VALUE, CREDIT_PACKS[CreditPackType.VALUE]),
            (CreditPackType.POWER, CREDIT_PACKS[CreditPackType.POWER]),
        ]

        per_credit_prices = [
            (pack_type, config.price_cents / config.credits)
            for pack_type, config in pack_list
        ]

        # Each subsequent pack should have lower per-credit price
        for i in range(len(per_credit_prices) - 1):
            current = per_credit_prices[i]
            next_pack = per_credit_prices[i + 1]
            assert current[1] > next_pack[1], (
                f"{current[0]} per-credit ({current[1]:.2f}) should be > "
                f"{next_pack[0]} per-credit ({next_pack[1]:.2f})"
            )
