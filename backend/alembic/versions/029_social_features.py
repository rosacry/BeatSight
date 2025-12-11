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
    
    conn = op.get_bind()
    
    # Check if enums exist and create them if not
    # ReportType enum
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'reporttype'"
    ))
    if not result.fetchone():
        op.execute("""
            CREATE TYPE reporttype AS ENUM (
                'spam', 'harassment', 'inappropriate_content', 
                'cheating', 'impersonation', 'copyright', 'other'
            )
        """)
    
    # ReportStatus enum
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'reportstatus'"
    ))
    if not result.fetchone():
        op.execute("""
            CREATE TYPE reportstatus AS ENUM (
                'pending', 'under_review', 'resolved', 'dismissed'
            )
        """)
    
    # Check if direct_messages table exists
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'direct_messages'"
    ))
    if not result.fetchone():
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
            sa.Column("is_read", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by_sender", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("deleted_by_recipient", sa.Boolean(), server_default="false", nullable=False),
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
        op.create_index(
            "ix_direct_messages_conversation",
            "direct_messages",
            ["sender_id", "recipient_id", "created_at"],
        )
    
    # Check if user_blocks table exists
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'user_blocks'"
    ))
    if not result.fetchone():
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
    
    # Check if user_reports table exists
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'user_reports'"
    ))
    if not result.fetchone():
        # Create user_reports table using raw SQL for enum columns to avoid recreation
        op.execute("""
            CREATE TABLE user_reports (
                id UUID PRIMARY KEY,
                reporter_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                reported_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                report_type reporttype NOT NULL,
                description TEXT NOT NULL,
                status reportstatus NOT NULL DEFAULT 'pending',
                admin_notes TEXT,
                reviewed_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
                reviewed_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
            )
        """)
        
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
    op.execute("DROP INDEX IF EXISTS ix_user_reports_created_at")
    op.execute("DROP INDEX IF EXISTS ix_user_reports_status")
    op.execute("DROP INDEX IF EXISTS ix_user_reports_reported_user_id")
    op.execute("DROP INDEX IF EXISTS ix_user_reports_reporter_id")
    op.execute("DROP TABLE IF EXISTS user_reports")
    
    # Drop user_blocks
    op.execute("DROP INDEX IF EXISTS ix_user_blocks_blocked_id")
    op.execute("DROP INDEX IF EXISTS ix_user_blocks_blocker_id")
    op.execute("DROP TABLE IF EXISTS user_blocks")
    
    # Drop direct_messages
    op.execute("DROP INDEX IF EXISTS ix_direct_messages_conversation")
    op.execute("DROP INDEX IF EXISTS ix_direct_messages_created_at")
    op.execute("DROP INDEX IF EXISTS ix_direct_messages_recipient_id")
    op.execute("DROP INDEX IF EXISTS ix_direct_messages_sender_id")
    op.execute("DROP TABLE IF EXISTS direct_messages")
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS reportstatus")
    op.execute("DROP TYPE IF EXISTS reporttype")
