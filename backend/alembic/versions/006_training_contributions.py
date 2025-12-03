"""Add training contributions tables

Revision ID: 006_training_contributions
Revises: 005_credit_system
Create Date: 2025-12-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "006_training_contributions"
down_revision = "005_credit_system"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create contribution_consents table
    op.create_table(
        "contribution_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consent_given", sa.Boolean(), nullable=False, default=False),
        sa.Column(
            "allow_anonymous_export",
            sa.Boolean(),
            nullable=False,
            default=True,
            comment="If true, contributions exported without user attribution",
        ),
        sa.Column(
            "allow_public_credit",
            sa.Boolean(),
            nullable=False,
            default=False,
            comment="If true, user can be credited in release notes/acknowledgments",
        ),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_contribution_consent_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_contribution_consent_user"),
    )
    op.create_index(
        "ix_contribution_consents_user_id",
        "contribution_consents",
        ["user_id"],
        unique=False,
    )

    # Create correction_type enum
    correction_type = postgresql.ENUM(
        "component_change",
        "timing_adjustment",
        "note_addition",
        "note_removal",
        "velocity_change",
        name="correctiontype",
        create_type=True,
    )
    correction_type.create(op.get_bind(), checkfirst=True)

    # Create contribution_status enum
    contribution_status = postgresql.ENUM(
        "pending",
        "approved",
        "rejected",
        "exported",
        name="contributionstatus",
        create_type=True,
    )
    contribution_status.create(op.get_bind(), checkfirst=True)

    # Create training_contributions table
    op.create_table(
        "training_contributions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("map_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("onset_time_ms", sa.Integer(), nullable=False),
        sa.Column(
            "correction_type",
            postgresql.ENUM(
                "component_change",
                "timing_adjustment",
                "note_addition",
                "note_removal",
                "velocity_change",
                name="correctiontype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("original_component", sa.String(length=50), nullable=False),
        sa.Column("original_confidence", sa.Float(), nullable=True),
        sa.Column("corrected_component", sa.String(length=50), nullable=False),
        sa.Column("corrected_time_ms", sa.Integer(), nullable=True),
        sa.Column("corrected_velocity", sa.Float(), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "approved",
                "rejected",
                "exported",
                name="contributionstatus",
                create_type=False,
            ),
            nullable=False,
            default="pending",
        ),
        sa.Column("verifier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verifier_notes", sa.String(length=512), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exported_to_training", sa.Boolean(), nullable=False, default=False),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("export_batch_id", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_training_contribution_user",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["map_version_id"],
            ["map_versions.id"],
            name="fk_training_contribution_map_version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["verifier_id"],
            ["users.id"],
            name="fk_training_contribution_verifier",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "map_version_id",
            "onset_time_ms",
            "user_id",
            name="uq_contribution_per_onset",
        ),
    )

    # Create indexes
    op.create_index(
        "ix_training_contributions_user_id",
        "training_contributions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_training_contributions_map_version_id",
        "training_contributions",
        ["map_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_training_contributions_status",
        "training_contributions",
        ["status"],
        unique=False,
    )
    
    # Partial index for pending review queue
    op.create_index(
        "idx_contributions_pending_review",
        "training_contributions",
        ["status"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )
    
    # Partial index for export queue
    op.create_index(
        "idx_contributions_export_ready",
        "training_contributions",
        ["exported_to_training", "status"],
        unique=False,
        postgresql_where=sa.text(
            "exported_to_training = false AND status = 'approved'"
        ),
    )


def downgrade() -> None:
    # Drop training_contributions table and indexes
    op.drop_index("idx_contributions_export_ready", table_name="training_contributions")
    op.drop_index("idx_contributions_pending_review", table_name="training_contributions")
    op.drop_index("ix_training_contributions_status", table_name="training_contributions")
    op.drop_index("ix_training_contributions_map_version_id", table_name="training_contributions")
    op.drop_index("ix_training_contributions_user_id", table_name="training_contributions")
    op.drop_table("training_contributions")

    # Drop contribution_consents table
    op.drop_index("ix_contribution_consents_user_id", table_name="contribution_consents")
    op.drop_table("contribution_consents")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS contributionstatus")
    op.execute("DROP TYPE IF EXISTS correctiontype")
