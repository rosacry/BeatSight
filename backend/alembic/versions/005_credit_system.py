"""add credit system tables

Revision ID: 005_credit_system
Revises: 004_map_votes
Create Date: 2025-01-20

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005_credit_system"
down_revision: Union[str, None] = "004_map_votes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create CreditPackType enum
    credit_pack_type_enum = postgresql.ENUM(
        "starter",
        "value",
        "power",
        name="creditpacktype",
        create_type=True,
    )
    credit_pack_type_enum.create(op.get_bind(), checkfirst=True)

    # Create CreditTransactionType enum
    credit_transaction_type_enum = postgresql.ENUM(
        "purchase",
        "consumption",
        "refund",
        "bonus",
        "subscription_grant",
        "expiry",
        name="credittransactiontype",
        create_type=True,
    )
    credit_transaction_type_enum.create(op.get_bind(), checkfirst=True)

    # Create credit_balances table
    op.create_table(
        "credit_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("balance", sa.Integer(), nullable=False, default=0),
        sa.Column("lifetime_purchased", sa.Integer(), nullable=False, default=0),
        sa.Column("lifetime_consumed", sa.Integer(), nullable=False, default=0),
        sa.Column("auto_topup_enabled", sa.Boolean(), nullable=False, default=False),
        sa.Column("auto_topup_threshold", sa.Integer(), nullable=True),
        sa.Column("auto_topup_pack", credit_pack_type_enum, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Create credit_purchases table
    op.create_table(
        "credit_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pack_type", credit_pack_type_enum, nullable=False),
        sa.Column("credits_amount", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(255), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, default="pending"),
        sa.Column("is_auto_topup", sa.Boolean(), nullable=False, default=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Create credit_transactions table (audit log)
    op.create_table(
        "credit_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("transaction_type", credit_transaction_type_enum, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_before", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "related_purchase_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("credit_purchases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "related_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create indexes for efficient queries
    op.create_index(
        "ix_credit_balance_user",
        "credit_balances",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "ix_credit_purchase_user",
        "credit_purchases",
        ["user_id"],
    )
    op.create_index(
        "ix_credit_purchase_stripe_session",
        "credit_purchases",
        ["stripe_checkout_session_id"],
    )
    op.create_index(
        "ix_credit_transaction_user",
        "credit_transactions",
        ["user_id"],
    )
    op.create_index(
        "ix_credit_transaction_created",
        "credit_transactions",
        ["created_at"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_credit_transaction_created", table_name="credit_transactions")
    op.drop_index("ix_credit_transaction_user", table_name="credit_transactions")
    op.drop_index("ix_credit_purchase_stripe_session", table_name="credit_purchases")
    op.drop_index("ix_credit_purchase_user", table_name="credit_purchases")
    op.drop_index("ix_credit_balance_user", table_name="credit_balances")

    # Drop tables
    op.drop_table("credit_transactions")
    op.drop_table("credit_purchases")
    op.drop_table("credit_balances")

    # Drop enums
    credit_transaction_type_enum = postgresql.ENUM(
        "purchase",
        "consumption",
        "refund",
        "bonus",
        "subscription_grant",
        "expiry",
        name="credittransactiontype",
    )
    credit_transaction_type_enum.drop(op.get_bind(), checkfirst=True)

    credit_pack_type_enum = postgresql.ENUM(
        "starter",
        "value",
        "power",
        name="creditpacktype",
    )
    credit_pack_type_enum.drop(op.get_bind(), checkfirst=True)
