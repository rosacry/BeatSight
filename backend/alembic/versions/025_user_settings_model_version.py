"""Add user settings and AI model version tracking.

Revision ID: 025_user_settings_model_version
Revises: 024_user_moderation
Create Date: 2025-01-15

Adds:
- user_settings table for privacy and re-evaluation preferences
- model_version column to ai_jobs table for version tracking
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "025_user_settings_model_version"
down_revision = "024_user_moderation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add user_settings table and model_version to ai_jobs."""
    
    # Create upload_visibility enum type
    upload_visibility_enum = postgresql.ENUM(
        "public",
        "anonymous", 
        "private",
        name="uploadvisibility",
        create_type=True,
    )
    upload_visibility_enum.create(op.get_bind(), checkfirst=True)
    
    # Create re_evaluation_policy enum type
    re_evaluation_policy_enum = postgresql.ENUM(
        "auto_free",
        "opt_in",
        "opt_out",
        name="reevaluationpolicy",
        create_type=True,
    )
    re_evaluation_policy_enum.create(op.get_bind(), checkfirst=True)
    
    # Create user_settings table
    op.create_table(
        "user_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        # Privacy settings
        sa.Column(
            "default_upload_visibility",
            upload_visibility_enum,
            nullable=False,
            server_default="public",
        ),
        sa.Column(
            "show_activity_on_profile",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "show_statistics_on_profile",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        # AI re-evaluation settings
        sa.Column(
            "re_evaluation_policy",
            re_evaluation_policy_enum,
            nullable=False,
            server_default="auto_free",
        ),
        sa.Column(
            "last_acknowledged_model_version",
            sa.String(64),
            nullable=True,
        ),
        # Notification settings
        sa.Column(
            "notify_job_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "notify_map_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "notify_re_evaluation_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "notify_weekly_summary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        # Timestamps
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    
    # Create index on user_id for fast lookups
    op.create_index(
        "ix_user_settings_user_id",
        "user_settings",
        ["user_id"],
    )
    
    # Add model_version column to ai_jobs table
    op.add_column(
        "ai_jobs",
        sa.Column(
            "model_version",
            sa.String(64),
            nullable=True,
            comment="AI model version that processed this job (e.g., 'v5.2.1')",
        ),
    )
    
    # Create index for finding jobs by model version (for re-evaluation queries)
    op.create_index(
        "ix_ai_jobs_model_version",
        "ai_jobs",
        ["model_version"],
    )


def downgrade() -> None:
    """Remove user_settings table and model_version from ai_jobs."""
    
    # Remove index from ai_jobs
    op.drop_index("ix_ai_jobs_model_version", table_name="ai_jobs")
    
    # Remove model_version column from ai_jobs
    op.drop_column("ai_jobs", "model_version")
    
    # Drop user_settings table
    op.drop_index("ix_user_settings_user_id", table_name="user_settings")
    op.drop_table("user_settings")
    
    # Drop enum types
    re_evaluation_policy_enum = postgresql.ENUM(
        "auto_free",
        "opt_in",
        "opt_out",
        name="reevaluationpolicy",
    )
    re_evaluation_policy_enum.drop(op.get_bind(), checkfirst=True)
    
    upload_visibility_enum = postgresql.ENUM(
        "public",
        "anonymous",
        "private",
        name="uploadvisibility",
    )
    upload_visibility_enum.drop(op.get_bind(), checkfirst=True)
