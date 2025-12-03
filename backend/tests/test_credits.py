"""Tests for credit service operations.

Tests credit balance management, pack purchases, consumption,
and auto-topup functionality.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credits import (
    CreditBalance,
    CreditPackType,
    CreditPurchase,
    CreditTransaction,
    CreditTransactionType,
)
from app.services.credits import CreditService, CREDIT_PACKS, CreditPackConfig


class TestCreditPackConfig:
    """Test cases for credit pack configurations."""

    def test_starter_pack_config(self) -> None:
        """Test STARTER pack configuration."""
        pack = CREDIT_PACKS[CreditPackType.STARTER]

        assert pack.credits == 5
        assert pack.price_cents == 175
        assert pack.name == "Starter Pack"

    def test_value_pack_config(self) -> None:
        """Test VALUE pack configuration."""
        pack = CREDIT_PACKS[CreditPackType.VALUE]

        assert pack.credits == 15
        assert pack.price_cents == 450
        assert pack.name == "Value Pack"

    def test_power_pack_config(self) -> None:
        """Test POWER pack configuration."""
        pack = CREDIT_PACKS[CreditPackType.POWER]

        assert pack.credits == 40
        assert pack.price_cents == 1000
        assert pack.name == "Power Pack"

    def test_pack_savings_increase_with_size(self) -> None:
        """Test that larger packs have better per-credit pricing."""
        starter = CREDIT_PACKS[CreditPackType.STARTER]
        value = CREDIT_PACKS[CreditPackType.VALUE]
        power = CREDIT_PACKS[CreditPackType.POWER]

        starter_per = starter.price_cents / starter.credits
        value_per = value.price_cents / value.credits
        power_per = power.price_cents / power.credits

        assert starter_per > value_per > power_per

    def test_pack_config_properties(self) -> None:
        """Test CreditPackConfig computed properties."""
        pack = CREDIT_PACKS[CreditPackType.STARTER]
        
        # Test price_dollars
        assert pack.price_dollars == 1.75
        
        # Test per_credit_cents
        assert pack.per_credit_cents == 35.0
        
        # Test savings_percent (starter should be 0)
        assert pack.savings_percent == 0

    def test_value_pack_has_savings(self) -> None:
        """Test that Value pack shows savings."""
        pack = CREDIT_PACKS[CreditPackType.VALUE]
        
        # Value pack is $0.30/credit, base is $0.35
        # Savings = (1 - 30/35) * 100 = ~14%
        assert 10 < pack.savings_percent < 20

    def test_power_pack_has_more_savings(self) -> None:
        """Test that Power pack shows more savings than Value."""
        value = CREDIT_PACKS[CreditPackType.VALUE]
        power = CREDIT_PACKS[CreditPackType.POWER]
        
        assert power.savings_percent > value.savings_percent


class TestCreditService:
    """Test cases for CreditService."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def credit_service(self, mock_session: AsyncMock) -> CreditService:
        """Create a CreditService with mock session."""
        return CreditService(mock_session)

    @pytest.fixture
    def user_id(self) -> uuid.UUID:
        """Generate a test user ID."""
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_get_or_create_balance_existing(
        self, credit_service: CreditService, mock_session: AsyncMock, user_id: uuid.UUID
    ) -> None:
        """Test getting existing balance returns it."""
        # Create a balance object with explicit values
        existing_balance = MagicMock(spec=CreditBalance)
        existing_balance.user_id = user_id
        existing_balance.purchased_credits = 50
        existing_balance.bonus_credits = 10
        existing_balance.total_credits = 60
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_balance
        mock_session.execute.return_value = mock_result

        balance = await credit_service.get_or_create_balance(user_id)

        assert balance == existing_balance

    @pytest.mark.asyncio
    async def test_get_or_create_balance_new(
        self, credit_service: CreditService, mock_session: AsyncMock, user_id: uuid.UUID
    ) -> None:
        """Test creating balance when none exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        balance = await credit_service.get_or_create_balance(user_id)

        # Should have called session.add with a new balance
        mock_session.add.assert_called_once()
        added_balance = mock_session.add.call_args[0][0]
        assert isinstance(added_balance, CreditBalance)
        assert added_balance.user_id == user_id

    @pytest.mark.asyncio
    async def test_configure_auto_topup(
        self, credit_service: CreditService, mock_session: AsyncMock, user_id: uuid.UUID
    ) -> None:
        """Test configuring auto-topup settings."""
        existing_balance = MagicMock(spec=CreditBalance)
        existing_balance.auto_topup_enabled = False
        existing_balance.auto_topup_threshold = 0
        existing_balance.auto_topup_pack = None
        
        credit_service.get_or_create_balance = AsyncMock(return_value=existing_balance)

        balance = await credit_service.configure_auto_topup(
            user_id=user_id,
            enabled=True,
            threshold=5,
            pack_type=CreditPackType.VALUE,
        )

        assert balance.auto_topup_enabled is True
        assert balance.auto_topup_threshold == 5
        assert balance.auto_topup_pack == CreditPackType.VALUE

    @pytest.mark.asyncio
    async def test_disable_auto_topup(
        self, credit_service: CreditService, mock_session: AsyncMock, user_id: uuid.UUID
    ) -> None:
        """Test disabling auto-topup."""
        existing_balance = MagicMock(spec=CreditBalance)
        existing_balance.auto_topup_enabled = True
        existing_balance.auto_topup_threshold = 5
        existing_balance.auto_topup_pack = CreditPackType.POWER
        
        credit_service.get_or_create_balance = AsyncMock(return_value=existing_balance)

        balance = await credit_service.configure_auto_topup(
            user_id=user_id,
            enabled=False,
        )

        assert balance.auto_topup_enabled is False


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

    def test_all_packs_have_descriptions(self) -> None:
        """Test that all packs have non-empty descriptions."""
        for pack_type, config in CREDIT_PACKS.items():
            assert config.description, f"{pack_type} missing description"
            assert len(config.description) > 0


class TestCreditModels:
    """Test credit model structures and relationships."""

    def test_credit_pack_type_values(self) -> None:
        """Test CreditPackType enum has expected values."""
        assert CreditPackType.STARTER.value == "starter"
        assert CreditPackType.VALUE.value == "value"
        assert CreditPackType.POWER.value == "power"

    def test_credit_transaction_type_values(self) -> None:
        """Test CreditTransactionType enum has expected values."""
        assert CreditTransactionType.PURCHASE.value == "purchase"
        assert CreditTransactionType.CONSUMPTION.value == "consumption"
