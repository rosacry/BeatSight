"""Fix subscriptions.plan_id to plan_code column name.

Revision ID: 015_fix_subscription_col
Revises: 014_add_staff_role
Create Date: 2025-12-08

The database has 'plan_id' but the model expects 'plan_code'.
This migration renames the column to match the model.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "015_fix_subscription_col"
down_revision = "014_add_staff_role"
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
    """Rename plan_id to plan_code in subscriptions table."""
    # Only rename if plan_id exists and plan_code doesn't
    if column_exists("subscriptions", "plan_id") and not column_exists("subscriptions", "plan_code"):
        op.alter_column(
            "subscriptions",
            "plan_id",
            new_column_name="plan_code",
        )
    elif not column_exists("subscriptions", "plan_code"):
        # If neither exists, add plan_code with default
        op.add_column(
            "subscriptions",
            sa.Column(
                "plan_code",
                sa.Enum("free", "basic_monthly", "basic_yearly", "pro_monthly", "pro_yearly", name="subscriptionplan"),
                nullable=False,
                server_default="free",
            ),
        )


def downgrade() -> None:
    """Rename plan_code back to plan_id."""
    if column_exists("subscriptions", "plan_code") and not column_exists("subscriptions", "plan_id"):
        op.alter_column(
            "subscriptions",
            "plan_code",
            new_column_name="plan_id",
        )
