"""Add anonymous mode settings for users.

Revision ID: 027_anonymous_mode
Revises: 026_contribution_quality_fields
Create Date: 2025-12-09

Adds:
- hide_from_leaderboards column to user_settings table
- hide_from_public_queues column to user_settings table

This allows users to opt-out of appearing on public leaderboards
and public job queue displays while still using the platform.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "027_anonymous_mode"
down_revision = "026_contribution_quality_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add anonymous mode columns to user_settings."""
    
    # Check if user_settings table exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [c["name"] for c in inspector.get_columns("user_settings")]
    
    if "hide_from_leaderboards" not in existing_columns:
        op.add_column(
            "user_settings",
            sa.Column(
                "hide_from_leaderboards",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
                comment="Hide user from public leaderboards (karma, verifiers, contributors)",
            ),
        )
    
    if "hide_from_public_queues" not in existing_columns:
        op.add_column(
            "user_settings",
            sa.Column(
                "hide_from_public_queues",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
                comment="Hide user's jobs from public queue view",
            ),
        )


def downgrade() -> None:
    """Remove anonymous mode columns from user_settings."""
    
    op.drop_column("user_settings", "hide_from_public_queues")
    op.drop_column("user_settings", "hide_from_leaderboards")
