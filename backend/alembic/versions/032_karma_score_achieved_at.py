"""Add karma_score_achieved_at for leaderboard tie-breaking.

Revision ID: 032_karma_score_achieved_at
Revises: 031_user_tags
Create Date: 2025-12-11

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "032_karma_score_achieved_at"
down_revision = "031_user_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add karma_score_achieved_at column to users table
    # This tracks when the user first reached their current karma score,
    # used for tie-breaking on leaderboards (earlier = higher rank)
    op.add_column(
        "users",
        sa.Column(
            "karma_score_achieved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when current karma_score was first achieved (for leaderboard tie-breaking)",
        ),
    )
    
    # Backfill existing users: set karma_score_achieved_at based on their most recent
    # karma ledger entry that resulted in their current score, or use created_at as fallback
    # This uses a subquery to find when each user last gained karma
    op.execute("""
        UPDATE users u
        SET karma_score_achieved_at = COALESCE(
            (
                SELECT MAX(kl.recorded_at)
                FROM karma_ledger kl
                WHERE kl.user_id = u.id AND kl.delta > 0
            ),
            u.created_at
        )
        WHERE u.karma_score > 0
    """)


def downgrade() -> None:
    op.drop_column("users", "karma_score_achieved_at")
