"""add push_subscriptions table

Revision ID: 003_push_subscriptions
Revises: 002_job_retry
Create Date: 2024-11-26

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "003_push_subscriptions"
down_revision: Union[str, None] = "002_job_retry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if table_exists("push_subscriptions"):
        return  # Already exists, skip

    op.create_table(
        "push_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("endpoint", sa.Text(), nullable=False, unique=True),
        sa.Column("p256dh_key", sa.String(255), nullable=False),
        sa.Column("auth_key", sa.String(255), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_name", sa.String(100), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_push_subscription_user_id", "push_subscriptions", ["user_id"])
    op.create_unique_constraint(
        "uq_push_subscription_user_endpoint",
        "push_subscriptions",
        ["user_id", "endpoint"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_push_subscription_user_endpoint", "push_subscriptions", type_="unique"
    )
    op.drop_index("ix_push_subscription_user_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
