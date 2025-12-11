"""Add social features tables - messaging, blocking, reporting.

Revision ID: 029_social_features
Revises: 028_fix_schema_mismatches
Create Date: 2025-12-10

Adds:
- direct_messages table for user-to-user messaging
- user_blocks table for blocking users
- user_reports table for reporting users to admins

Includes appropriate indexes for efficient queries.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "029_social_features"
down_revision = "028_fix_schema_mismatches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create social features tables."""
    
    # Create ReportType enum
    report_type_enum = postgresql.ENUM(
        "spam",
        "harassment",
        "inappropriate_content",
        "cheating",
        "impersonation",
        "copyright",
        "other",
        name="reporttype",
    )
    report_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Create ReportStatus enum
    report_status_enum = postgresql.ENUM(
        "pending",
        "under_review",
        "resolved",
        "dismissed",
        name="reportstatus",
    )
    report_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create direct_messages table
    op.create_table(
        "direct_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "sender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "recipient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), default=False, nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_sender", sa.Boolean(), default=False, nullable=False),
        sa.Column("deleted_by_recipient", sa.Boolean(), default=False, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "reply_to_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("direct_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    
    # Create indexes for direct_messages
    op.create_index(
        "ix_direct_messages_sender_id",
        "direct_messages",
        ["sender_id"],
    )
    op.create_index(
        "ix_direct_messages_recipient_id",
        "direct_messages",
        ["recipient_id"],
    )
    op.create_index(
        "ix_direct_messages_created_at",
        "direct_messages",
        ["created_at"],
    )
    # Composite index for conversation queries
    op.create_index(
        "ix_direct_messages_conversation",
        "direct_messages",
        ["sender_id", "recipient_id", "created_at"],
    )
    
    # Create user_blocks table
    op.create_table(
        "user_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "blocker_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "blocked_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Unique constraint: can only block a user once
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_blocker_blocked"),
    )
    
    # Create indexes for user_blocks
    op.create_index(
        "ix_user_blocks_blocker_id",
        "user_blocks",
        ["blocker_id"],
    )
    op.create_index(
        "ix_user_blocks_blocked_id",
        "user_blocks",
        ["blocked_id"],
    )
    
    # Create user_reports table
    op.create_table(
        "user_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "reporter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reported_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_type",
            report_type_enum,
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            report_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    
    # Create indexes for user_reports
    op.create_index(
        "ix_user_reports_reporter_id",
        "user_reports",
        ["reporter_id"],
    )
    op.create_index(
        "ix_user_reports_reported_user_id",
        "user_reports",
        ["reported_user_id"],
    )
    op.create_index(
        "ix_user_reports_status",
        "user_reports",
        ["status"],
    )
    op.create_index(
        "ix_user_reports_created_at",
        "user_reports",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop social features tables."""
    
    # Drop user_reports
    op.drop_index("ix_user_reports_created_at", table_name="user_reports")
    op.drop_index("ix_user_reports_status", table_name="user_reports")
    op.drop_index("ix_user_reports_reported_user_id", table_name="user_reports")
    op.drop_index("ix_user_reports_reporter_id", table_name="user_reports")
    op.drop_table("user_reports")
    
    # Drop user_blocks
    op.drop_index("ix_user_blocks_blocked_id", table_name="user_blocks")
    op.drop_index("ix_user_blocks_blocker_id", table_name="user_blocks")
    op.drop_table("user_blocks")
    
    # Drop direct_messages
    op.drop_index("ix_direct_messages_conversation", table_name="direct_messages")
    op.drop_index("ix_direct_messages_created_at", table_name="direct_messages")
    op.drop_index("ix_direct_messages_recipient_id", table_name="direct_messages")
    op.drop_index("ix_direct_messages_sender_id", table_name="direct_messages")
    op.drop_table("direct_messages")
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS reportstatus")
    op.execute("DROP TYPE IF EXISTS reporttype")
