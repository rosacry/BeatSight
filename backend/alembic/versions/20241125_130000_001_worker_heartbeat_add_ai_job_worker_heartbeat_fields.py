"""add ai job worker heartbeat fields

Revision ID: 001_worker_heartbeat
Revises: 
Create Date: 2024-11-25 13:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_worker_heartbeat"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add worker heartbeat tracking columns to ai_jobs table."""
    op.add_column(
        "ai_jobs",
        sa.Column(
            "worker_id",
            sa.UUID(),
            nullable=True,
            comment="UUID of the worker currently processing this job",
        ),
    )
    op.add_column(
        "ai_jobs",
        sa.Column(
            "last_heartbeat",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last heartbeat timestamp from the worker",
        ),
    )
    op.add_column(
        "ai_jobs",
        sa.Column(
            "progress_percent",
            sa.Integer(),
            nullable=True,
            comment="Job progress percentage (0-100)",
        ),
    )
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
    op.create_index(
        "ix_ai_jobs_worker_id",
        "ai_jobs",
        ["worker_id"],
        unique=False,
    )

    # Add index on last_heartbeat for finding stale jobs
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
