"""Add processed_webhook_events table for idempotency

This migration adds a table to track processed webhook events,
preventing duplicate processing from provider retries.

Revision ID: 009_webhook_idempotency
Revises: 008_add_performance_indexes
Create Date: 2025-01-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "009_webhook_idempotency"
down_revision = "008_add_performance_indexes"
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Create processed_webhook_events table."""
    if table_exists("processed_webhook_events"):
        return

    op.create_table(
        "processed_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "event_id",
            sa.String(128),
            nullable=False,
            unique=True,
            index=True,
            comment="Provider's event ID (e.g., Stripe evt_xxx)",
        ),
        sa.Column(
            "event_type",
            sa.String(128),
            nullable=False,
            comment="Event type (e.g., checkout.session.completed)",
        ),
        sa.Column(
            "provider",
            sa.String(32),
            nullable=False,
            comment="Provider name (stripe, modal, etc.)",
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            sa.String(512),
            nullable=True,
            comment="Optional processing metadata",
        ),
    )


def downgrade() -> None:
    """Drop processed_webhook_events table."""
    op.drop_table("processed_webhook_events")
