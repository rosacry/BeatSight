"""Add map accuracy verification tables and user verification bonus.

Revision ID: 020_map_accuracy_verification
Revises: 019_add_missing_decision_columns
Create Date: 2025-12-08

This migration adds:
1. map_accuracy_votes - Individual verifier votes on beatmap accuracy
2. map_accuracy_consensus - Aggregated consensus status for each map version
3. user_verification_bonuses - Tracks one-time karma bonus for verified users
4. New karma reason enum values for verification-related rewards

The multi-verifier consensus system requires REQUIRED_VERIFIERS_FOR_ACCURACY (3)
verifiers to vote before consensus can be reached. Users with both email AND
phone verified receive a 200 karma bonus to help them participate.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = "020_map_accuracy_verification"
down_revision = "019_add_missing_decision_columns"
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def enum_type_exists(enum_name: str) -> bool:
    """Check if an enum type exists."""
    bind = op.get_bind()
    result = bind.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = :name)"
        ).bindparams(name=enum_name)
    )
    return result.scalar()


def enum_value_exists(enum_name: str, value: str) -> bool:
    """Check if an enum value exists."""
    bind = op.get_bind()
    result = bind.execute(
        text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = :enum_name AND e.enumlabel = :value
            )
        """).bindparams(enum_name=enum_name, value=value)
    )
    return result.scalar()


def index_exists(index_name: str, table_name: str) -> bool:
    """Check if an index exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
        return index_name in indexes
    except Exception:
        return False


def upgrade() -> None:
    """Add map accuracy verification tables and karma reason enum values."""
    
    # ==========================================================================
    # 1. Add new KarmaReason enum values
    # ==========================================================================
    print("Adding new KarmaReason enum values...")
    
    new_karma_reasons = [
        "verified_user_bonus",
        "accuracy_vote_cast", 
        "accuracy_consensus_contributor",
    ]
    
    for value in new_karma_reasons:
        if not enum_value_exists("karmareason", value):
            print(f"  Adding karmareason value: {value}")
            op.execute(f"ALTER TYPE karmareason ADD VALUE IF NOT EXISTS '{value}'")
        else:
            print(f"  karmareason value already exists: {value}")

    # ==========================================================================
    # 2. Create AccuracyVoteType enum
    # ==========================================================================
    if not enum_type_exists("accuracyvotetype"):
        print("Creating accuracyvotetype enum...")
        op.execute("""
            CREATE TYPE accuracyvotetype AS ENUM (
                'accurate',
                'inaccurate', 
                'needs_work',
                'abstain'
            )
        """)
    else:
        print("accuracyvotetype enum already exists")

    # ==========================================================================
    # 3. Create MapAccuracyStatus enum
    # ==========================================================================
    if not enum_type_exists("mapaccuracystatus"):
        print("Creating mapaccuracystatus enum...")
        op.execute("""
            CREATE TYPE mapaccuracystatus AS ENUM (
                'pending',
                'verified',
                'disputed',
                'rejected',
                'needs_revision'
            )
        """)
    else:
        print("mapaccuracystatus enum already exists")

    # ==========================================================================
    # 4. Create map_accuracy_votes table
    # ==========================================================================
    if not table_exists("map_accuracy_votes"):
        print("Creating map_accuracy_votes table...")
        op.create_table(
            "map_accuracy_votes",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "map_version_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("map_versions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "verifier_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "vote",
                postgresql.ENUM(
                    "accurate", "inaccurate", "needs_work", "abstain",
                    name="accuracyvotetype",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("confidence_level", sa.Integer, default=3, nullable=False),
            sa.Column("notes", sa.Text),
            sa.Column("timestamp_markers", sa.Text),  # JSON for issue timestamps
            sa.Column(
                "voted_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "map_version_id", "verifier_id", name="uq_accuracy_vote"
            ),
        )
        
        # Create indexes
        if not index_exists("ix_accuracy_votes_map_version", "map_accuracy_votes"):
            op.create_index(
                "ix_accuracy_votes_map_version",
                "map_accuracy_votes",
                ["map_version_id"],
            )
        if not index_exists("ix_accuracy_votes_verifier", "map_accuracy_votes"):
            op.create_index(
                "ix_accuracy_votes_verifier",
                "map_accuracy_votes",
                ["verifier_id"],
            )
    else:
        print("map_accuracy_votes table already exists")

    # ==========================================================================
    # 5. Create map_accuracy_consensus table
    # ==========================================================================
    if not table_exists("map_accuracy_consensus"):
        print("Creating map_accuracy_consensus table...")
        op.create_table(
            "map_accuracy_consensus",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "map_version_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("map_versions.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "status",
                postgresql.ENUM(
                    "pending", "verified", "disputed", "rejected", "needs_revision",
                    name="mapaccuracystatus",
                    create_type=False,
                ),
                default="pending",
                nullable=False,
            ),
            sa.Column("total_votes", sa.Integer, default=0, nullable=False),
            sa.Column("accurate_votes", sa.Integer, default=0, nullable=False),
            sa.Column("inaccurate_votes", sa.Integer, default=0, nullable=False),
            sa.Column("needs_work_votes", sa.Integer, default=0, nullable=False),
            sa.Column("abstain_votes", sa.Integer, default=0, nullable=False),
            sa.Column("average_confidence", sa.Float, nullable=True),
            sa.Column("consensus_reached_at", sa.DateTime(timezone=True), nullable=True),
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
        
        # Create indexes
        if not index_exists("ix_accuracy_consensus_status", "map_accuracy_consensus"):
            op.create_index(
                "ix_accuracy_consensus_status",
                "map_accuracy_consensus",
                ["status"],
            )
        if not index_exists("ix_accuracy_consensus_map_version", "map_accuracy_consensus"):
            op.create_index(
                "ix_accuracy_consensus_map_version",
                "map_accuracy_consensus",
                ["map_version_id"],
            )
    else:
        print("map_accuracy_consensus table already exists")

    # ==========================================================================
    # 6. Create user_verification_bonuses table
    # ==========================================================================
    if not table_exists("user_verification_bonuses"):
        print("Creating user_verification_bonuses table...")
        op.create_table(
            "user_verification_bonuses",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,  # Only one bonus record per user
            ),
            sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("bonus_awarded", sa.Boolean, default=False, nullable=False),
            sa.Column("bonus_amount", sa.Integer, default=200, nullable=False),
            sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
    else:
        print("user_verification_bonuses table already exists")

    print("Migration 020_map_accuracy_verification complete!")


def downgrade() -> None:
    """Remove map accuracy verification tables and enum values."""
    
    # Drop tables in reverse order (respecting FK dependencies)
    if table_exists("user_verification_bonuses"):
        print("Dropping user_verification_bonuses table...")
        op.drop_table("user_verification_bonuses")
    
    if table_exists("map_accuracy_consensus"):
        print("Dropping map_accuracy_consensus table...")
        op.drop_table("map_accuracy_consensus")
    
    if table_exists("map_accuracy_votes"):
        print("Dropping map_accuracy_votes table...")
        op.drop_table("map_accuracy_votes")
    
    # Drop enum types
    if enum_type_exists("mapaccuracystatus"):
        print("Dropping mapaccuracystatus enum...")
        op.execute("DROP TYPE IF EXISTS mapaccuracystatus")
    
    if enum_type_exists("accuracyvotetype"):
        print("Dropping accuracyvotetype enum...")
        op.execute("DROP TYPE IF EXISTS accuracyvotetype")
    
    # Note: Cannot easily remove enum values in PostgreSQL
    # The new karma reason values will remain in the enum
    
    print("Downgrade 020_map_accuracy_verification complete!")
