"""Initial schema - create all base tables.

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create roles table first (no FK dependencies)
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.String(255)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_roles_name", "roles", ["name"])

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("email_verified", sa.Boolean, default=False, nullable=False),
        sa.Column("phone_number", sa.String(32)),
        sa.Column("phone_verified", sa.Boolean, default=False, nullable=False),
        sa.Column("avatar_url", sa.String(512)),
        sa.Column("auth_provider_id", sa.String(128), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255)),
        sa.Column("karma_score", sa.Integer, default=0, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_karma_score", "users", ["karma_score"])

    # Create user_roles junction table
    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    # Create songs table
    op.create_table(
        "songs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("fingerprint_hash", sa.String(128), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("artist", sa.String(255), nullable=False),
        sa.Column("bpm", sa.Integer),
        sa.Column("status", sa.String(20), default="pending", nullable=False),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("fingerprint_hash", name="uq_song_fingerprint"),
    )
    op.create_index("ix_song_status", "songs", ["status"])
    op.create_index("ix_songs_created_by_id", "songs", ["created_by_id"])
    op.create_index("ix_songs_created_at", "songs", ["created_at"])

    # Create maps table
    op.create_table(
        "maps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "song_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("songs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("state", sa.String(20), default="unverified", nullable=False),
        sa.Column("instrument", sa.String(50), default="drums", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_maps_song_id", "maps", ["song_id"])
    op.create_index("ix_map_difficulty", "maps", ["difficulty"])

    # Create map_versions table
    op.create_table(
        "map_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "map_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("maps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("data_url", sa.String(512), nullable=False),
        sa.Column("is_current", sa.Boolean, default=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("map_id", "version", name="uq_map_version"),
    )
    op.create_index("ix_map_versions_map_id", "map_versions", ["map_id"])

    # Create map_assets table
    op.create_table(
        "map_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "map_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("maps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("asset_type", sa.String(50), nullable=False),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("size_bytes", sa.BigInteger),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_map_assets_map_id", "map_assets", ["map_id"])

    # Create ai_jobs table
    op.create_table(
        "ai_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "requester_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "song_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("songs.id"),
        ),
        sa.Column("status", sa.String(20), default="queued", nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("priority", sa.Integer, default=0, nullable=False),
        sa.Column("progress", sa.Float, default=0.0),
        sa.Column("result_url", sa.String(512)),
        sa.Column("error_message", sa.Text),
        # Note: worker_id, worker_heartbeat_at, retries, max_retries, last_retry_at
        # are added by subsequent migrations (001_worker_heartbeat, 002_job_retry)
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_ai_jobs_requester_id", "ai_jobs", ["requester_id"])
    op.create_index("ix_ai_jobs_song_id", "ai_jobs", ["song_id"])
    op.create_index("ix_ai_jobs_status", "ai_jobs", ["status"])

    # Create subscriptions table
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_subscription_id", sa.String(255), unique=True, nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=False),
        sa.Column("plan_id", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("cancel_at_period_end", sa.Boolean, default=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index(
        "ix_subscriptions_stripe_subscription_id",
        "subscriptions",
        ["stripe_subscription_id"],
    )

    # Create billing_transactions table
    op.create_table(
        "billing_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_invoice_id", sa.String(255), unique=True, nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), default="usd", nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_billing_transactions_subscription_id",
        "billing_transactions",
        ["subscription_id"],
    )

    # Create karma_ledger table
    op.create_table(
        "karma_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("delta", sa.Integer, nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True)),
        sa.Column("reference_type", sa.String(50)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_karma_ledger_user_id", "karma_ledger", ["user_id"])

    # Create map_edit_proposals table
    op.create_table(
        "map_edit_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "map_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("maps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "proposer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), default="pending", nullable=False),
        sa.Column("diff_data", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_map_edit_proposals_map_id", "map_edit_proposals", ["map_id"])
    op.create_index(
        "ix_map_edit_proposals_proposer_id", "map_edit_proposals", ["proposer_id"]
    )

    # Create map_verification_decisions table
    op.create_table(
        "map_verification_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "proposal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("map_edit_proposals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "verifier_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_map_verification_decisions_proposal_id",
        "map_verification_decisions",
        ["proposal_id"],
    )

    # Create achievements table
    op.create_table(
        "achievements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("icon_url", sa.String(512)),
        sa.Column("karma_reward", sa.Integer, default=0, nullable=False),
        sa.Column("threshold", sa.Integer),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_achievements_name", "achievements", ["name"])
    op.create_index("ix_achievements_category", "achievements", ["category"])

    # Create user_achievements table
    op.create_table(
        "user_achievements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "achievement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("achievements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "unlocked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )
    op.create_index("ix_user_achievements_user_id", "user_achievements", ["user_id"])

    # Create sync tables
    op.create_table(
        "sync_clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("device_name", sa.String(255), nullable=False),
        sa.Column("device_type", sa.String(50), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_sync_clients_user_id", "sync_clients", ["user_id"])

    op.create_table(
        "user_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("preferences_data", postgresql.JSONB, default={}),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Drop tables in reverse order of creation
    op.drop_table("user_preferences")
    op.drop_table("sync_clients")
    op.drop_table("user_achievements")
    op.drop_table("achievements")
    op.drop_table("map_verification_decisions")
    op.drop_table("map_edit_proposals")
    op.drop_table("karma_ledger")
    op.drop_table("billing_transactions")
    op.drop_table("subscriptions")
    op.drop_table("ai_jobs")
    op.drop_table("map_assets")
    op.drop_table("map_versions")
    op.drop_table("maps")
    op.drop_table("songs")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
