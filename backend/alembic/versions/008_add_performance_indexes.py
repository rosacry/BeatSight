"""Add performance indexes for common query patterns

This migration adds indexes to optimize common database queries:
- User subscription lookups
- AI job listings by user and song
- Song listings by creator
- Map version history lookups
- Edit proposal verification queue

Revision ID: 008_add_performance_indexes
Revises: 007_contribution_batch_impact
Create Date: 2025-01-25
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "008_add_performance_indexes"
down_revision = "007_contribution_batch_impact"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add performance indexes for common query patterns."""

    # Subscription indexes - HIGH IMPACT
    # User subscription lookups (every authenticated request checks subscription)
    op.create_index(
        "ix_subscriptions_user_id",
        "subscriptions",
        ["user_id"],
        unique=False,
    )
    # Filter by status (active subscriptions, batch updates for expired)
    op.create_index(
        "ix_subscriptions_status",
        "subscriptions",
        ["status"],
        unique=False,
    )

    # AI Job indexes - HIGH IMPACT
    # User's job listing ("My Jobs" page)
    op.create_index(
        "ix_ai_jobs_requested_by_id",
        "ai_jobs",
        ["requested_by_id"],
        unique=False,
    )
    # Finding all jobs for a specific song
    op.create_index(
        "ix_ai_jobs_song_id",
        "ai_jobs",
        ["song_id"],
        unique=False,
    )

    # Song indexes - MEDIUM-HIGH IMPACT
    # User's uploaded songs ("My Songs" page)
    op.create_index(
        "ix_songs_created_by_id",
        "songs",
        ["created_by_id"],
        unique=False,
    )
    # Sorting by creation date (newest first pagination)
    op.create_index(
        "ix_songs_created_at",
        "songs",
        ["created_at"],
        unique=False,
    )

    # Map version indexes - MEDIUM IMPACT
    # Loading all versions of a map (version history)
    op.create_index(
        "ix_map_versions_map_id",
        "map_versions",
        ["map_id"],
        unique=False,
    )
    # Finding versions created by a user (contribution stats)
    op.create_index(
        "ix_map_versions_created_by",
        "map_versions",
        ["created_by"],
        unique=False,
    )

    # Billing transaction indexes - MEDIUM-HIGH IMPACT
    # Billing history for a user
    op.create_index(
        "ix_billing_transactions_user_id",
        "billing_transactions",
        ["user_id"],
        unique=False,
    )
    # Looking up transactions by payment provider reference
    op.create_index(
        "ix_billing_transactions_provider_ref",
        "billing_transactions",
        ["provider_ref"],
        unique=False,
    )

    # Map edit proposal indexes - MEDIUM IMPACT
    # Verification queue (pending edits)
    op.create_index(
        "ix_map_edit_proposals_status",
        "map_edit_proposals",
        ["status"],
        unique=False,
    )
    # User's edit history
    op.create_index(
        "ix_map_edit_proposals_proposer_id",
        "map_edit_proposals",
        ["proposer_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove performance indexes."""
    # Map edit proposal indexes
    op.drop_index("ix_map_edit_proposals_proposer_id", table_name="map_edit_proposals")
    op.drop_index("ix_map_edit_proposals_status", table_name="map_edit_proposals")

    # Billing transaction indexes
    op.drop_index(
        "ix_billing_transactions_provider_ref", table_name="billing_transactions"
    )
    op.drop_index("ix_billing_transactions_user_id", table_name="billing_transactions")

    # Map version indexes
    op.drop_index("ix_map_versions_created_by", table_name="map_versions")
    op.drop_index("ix_map_versions_map_id", table_name="map_versions")

    # Song indexes
    op.drop_index("ix_songs_created_at", table_name="songs")
    op.drop_index("ix_songs_created_by_id", table_name="songs")

    # AI Job indexes
    op.drop_index("ix_ai_jobs_song_id", table_name="ai_jobs")
    op.drop_index("ix_ai_jobs_requested_by_id", table_name="ai_jobs")

    # Subscription indexes
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
