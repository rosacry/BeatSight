"""add ai job worker heartbeat fields

Revision ID: 001_worker_heartbeat
Revises: 001_initial_schema
Create Date: 2024-11-25 13:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "001_worker_heartbeat"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(index_name: str) -> bool:
    """Check if an index exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = [idx["name"] for idx in inspector.get_indexes("ai_jobs")]
    return index_name in indexes


def upgrade() -> None:
    """Add worker heartbeat tracking columns to ai_jobs table."""
    if not column_exists("ai_jobs", "worker_id"):
        op.add_column(
            "ai_jobs",
            sa.Column(
                "worker_id",
                sa.UUID(),
                nullable=True,
                comment="UUID of the worker currently processing this job",
            ),
        )
    if not column_exists("ai_jobs", "last_heartbeat"):
        op.add_column(
            "ai_jobs",
            sa.Column(
                "last_heartbeat",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="Last heartbeat timestamp from the worker",
            ),
        )
    if not column_exists("ai_jobs", "progress_percent"):
        op.add_column(
            "ai_jobs",
            sa.Column(
                "progress_percent",
                sa.Integer(),
                nullable=True,
                comment="Job progress percentage (0-100)",
            ),
        )
    if not column_exists("ai_jobs", "progress_message"):
        op.add_column(
            "ai_jobs",
            sa.Column(
                "progress_message",
                sa.String(length=500),
                nullable=True,
                comment="Human-readable progress message",
            ),
        )

    # Add index on worker_id for efficient stale job queries
    if not index_exists("ix_ai_jobs_worker_id"):
        op.create_index(
            "ix_ai_jobs_worker_id",
            "ai_jobs",
            ["worker_id"],
            unique=False,
        )

    # Add index on last_heartbeat for finding stale jobs
    if not index_exists("ix_ai_jobs_last_heartbeat"):
        op.create_index(
            "ix_ai_jobs_last_heartbeat",
            "ai_jobs",
            ["last_heartbeat"],
            unique=False,
        )


def downgrade() -> None:
    """Remove worker heartbeat tracking columns from ai_jobs table."""
    op.drop_index("ix_ai_jobs_last_heartbeat", table_name="ai_jobs")
    op.drop_index("ix_ai_jobs_worker_id", table_name="ai_jobs")
    op.drop_column("ai_jobs", "progress_message")
    op.drop_column("ai_jobs", "progress_percent")
    op.drop_column("ai_jobs", "last_heartbeat")
    op.drop_column("ai_jobs", "worker_id")
