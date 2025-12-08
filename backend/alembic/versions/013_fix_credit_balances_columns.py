"""Fix credit_balances column names to match model.

Revision ID: 013_fix_credit_balances_columns
Revises: 012_add_missing_song_map_columns
Create Date: 2025-12-08

The migration 005 created columns with different names than the model expects:
- Model has: purchased_credits, bonus_credits
- Migration created: balance, lifetime_purchased, lifetime_consumed

This migration renames/adds the correct columns.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "013_fix_credit_balances_columns"
down_revision = "012_add_missing_song_map_columns"
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = :table_name AND column_name = :column_name
            )
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return result.scalar()


def upgrade() -> None:
    # =========================================================================
    # CREDIT_BALANCES TABLE - Fix column names
    # =========================================================================
    
    # Rename 'balance' to 'purchased_credits' (or add if doesn't exist)
    if column_exists("credit_balances", "balance") and not column_exists("credit_balances", "purchased_credits"):
        op.alter_column(
            "credit_balances",
            "balance",
            new_column_name="purchased_credits",
            existing_type=sa.Integer,
        )
    elif not column_exists("credit_balances", "purchased_credits"):
        op.add_column(
            "credit_balances",
            sa.Column("purchased_credits", sa.Integer, nullable=False, server_default="0"),
        )

    # Add bonus_credits column (new)
    if not column_exists("credit_balances", "bonus_credits"):
        op.add_column(
            "credit_balances",
            sa.Column("bonus_credits", sa.Integer, nullable=False, server_default="0"),
        )

    # Drop old columns that are no longer in the model
    if column_exists("credit_balances", "lifetime_purchased"):
        op.drop_column("credit_balances", "lifetime_purchased")
    
    if column_exists("credit_balances", "lifetime_consumed"):
        op.drop_column("credit_balances", "lifetime_consumed")


def downgrade() -> None:
    # Add back lifetime columns
    if not column_exists("credit_balances", "lifetime_purchased"):
        op.add_column(
            "credit_balances",
            sa.Column("lifetime_purchased", sa.Integer, nullable=False, server_default="0"),
        )
    
    if not column_exists("credit_balances", "lifetime_consumed"):
        op.add_column(
            "credit_balances",
            sa.Column("lifetime_consumed", sa.Integer, nullable=False, server_default="0"),
        )

    # Drop bonus_credits
    if column_exists("credit_balances", "bonus_credits"):
        op.drop_column("credit_balances", "bonus_credits")

    # Rename purchased_credits back to balance
    if column_exists("credit_balances", "purchased_credits"):
        op.alter_column(
            "credit_balances",
            "purchased_credits",
            new_column_name="balance",
            existing_type=sa.Integer,
        )
