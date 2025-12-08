"""Add user moderation system.

Revision ID: 024_user_moderation
Revises: 023_add_achievement_slug_column
Create Date: 2025-12-08

Adds fields and tables for user account moderation, including:
- Restriction levels (none, silenced, restricted, banned)
- Moderation history tracking
- User warnings counter
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "024_user_moderation"
down_revision = "023_add_achievement_slug_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add moderation fields to users table and create account history table."""
    
    # Create moderation_action enum type
    moderation_action_enum = postgresql.ENUM(
        "note",
        "silence",
        "restriction",
        "ban",
        "unsilence",
        "unrestrict",
        "unban",
        name="moderationaction",
        create_type=True,
    )
    moderation_action_enum.create(op.get_bind(), checkfirst=True)
    
    # Add moderation columns to users table
    op.add_column(
        "users",
        sa.Column(
            "restriction_level",
            sa.String(20),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column(
        "users",
        sa.Column("restriction_reason", sa.String(512), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "restriction_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "restricted_by_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "restricted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "user_warnings",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    
    # Create user_account_history table
    op.create_table(
        "user_account_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "action",
            postgresql.ENUM(
                "note",
                "silence",
                "restriction",
                "ban",
                "unsilence",
                "unrestrict",
                "unban",
                name="moderationaction",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("duration_hours", sa.Integer, nullable=True),
        sa.Column("reason", sa.String(512), nullable=True),
        sa.Column("admin_notes", sa.Text, nullable=True),
        sa.Column("supporting_url", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    
    # Create index for looking up recent moderation actions
    op.create_index(
        "ix_user_account_history_created_at",
        "user_account_history",
        ["created_at"],
    )


def downgrade() -> None:
    """Remove moderation fields and tables."""
    
    # Drop user_account_history table
    op.drop_index("ix_user_account_history_created_at", table_name="user_account_history")
    op.drop_table("user_account_history")
    
    # Remove columns from users table
    op.drop_column("users", "user_warnings")
    op.drop_column("users", "restricted_at")
    op.drop_column("users", "restricted_by_id")
    op.drop_column("users", "restriction_expires_at")
    op.drop_column("users", "restriction_reason")
    op.drop_column("users", "restriction_level")
    
    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS moderationaction")
