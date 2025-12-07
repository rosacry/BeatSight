"""Add retry tracking fields to ai_jobs table.

Revision ID: 002_job_retry
Revises: 001_worker_heartbeat
Create Date: 2025-11-25

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "002_job_retry"
down_revision: Union[str, None] = "001_worker_heartbeat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Add retry tracking columns to ai_jobs table."""
    if not column_exists("ai_jobs", "retry_count"):
        op.add_column(
            "ai_jobs",
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        )
    if not column_exists("ai_jobs", "max_retries"):
        op.add_column(
            "ai_jobs",
            sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        )
    if not column_exists("ai_jobs", "next_retry_at"):
        op.add_column(
            "ai_jobs",
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not column_exists("ai_jobs", "last_error"):
        op.add_column(
            "ai_jobs", sa.Column("last_error", sa.String(1024), nullable=True)
        )


def downgrade() -> None:
    """Remove retry tracking columns from ai_jobs table."""
    op.drop_column("ai_jobs", "last_error")
    op.drop_column("ai_jobs", "next_retry_at")
    op.drop_column("ai_jobs", "max_retries")
    op.drop_column("ai_jobs", "retry_count")
