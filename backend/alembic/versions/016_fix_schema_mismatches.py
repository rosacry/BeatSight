"""Fix database schema to match SQLAlchemy models.

Revision ID: 016_fix_schema_mismatches
Revises: 015_fix_subscription_col
Create Date: 2025-12-08

This migration fixes multiple schema mismatches between the database 
and the SQLAlchemy models:

1. subscriptions: Add ai_quota_remaining column
2. subscriptions: Create subscriptionplan and subscriptionstatus enum types
3. subscriptions: Convert plan_code to use enum type
4. subscriptions: Convert status to use enum type
5. ai_jobs: Rename requester_id to requested_by_id
6. ai_jobs: Create aijobstate enum type
7. map_edit_proposals: Create editstatus enum type
8. map_edit_proposals: Fix column names (map_id -> map_version_id, diff_data -> diff_payload, etc.)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "016_fix_schema_mismatch"
down_revision = "015_fix_subscription_col"
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = :table_name AND column_name = :column_name
            )
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return result.scalar()


def enum_type_exists(type_name: str) -> bool:
    """Check if a PostgreSQL enum type exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = :type_name
            )
            """
        ),
        {"type_name": type_name},
    )
    return result.scalar()


def upgrade() -> None:
    """Apply schema fixes to match SQLAlchemy models."""
    
    # ============================================================
    # 1. SUBSCRIPTION ENUM TYPES
    # ============================================================
    
    # Create subscriptionplan enum if it doesn't exist
    if not enum_type_exists("subscriptionplan"):
        op.execute("""
            CREATE TYPE subscriptionplan AS ENUM (
                'free', 'basic_monthly', 'basic_yearly', 'pro_monthly', 'pro_yearly'
            )
        """)
    
    # Create subscriptionstatus enum if it doesn't exist
    if not enum_type_exists("subscriptionstatus"):
        op.execute("""
            CREATE TYPE subscriptionstatus AS ENUM (
                'active', 'past_due', 'cancelled'
            )
        """)
    
    # ============================================================
    # 2. SUBSCRIPTIONS TABLE FIXES
    # ============================================================
    
    # Add ai_quota_remaining column if it doesn't exist
    if not column_exists("subscriptions", "ai_quota_remaining"):
        op.add_column(
            "subscriptions",
            sa.Column("ai_quota_remaining", sa.Integer(), nullable=False, server_default="3"),
        )
    
    # Add last_synced_at column if it doesn't exist
    if not column_exists("subscriptions", "last_synced_at"):
        op.add_column(
            "subscriptions",
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        )
    
    # Convert plan_code from string to enum (if it's currently a string type)
    # First check if it's VARCHAR
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT data_type FROM information_schema.columns 
        WHERE table_name = 'subscriptions' AND column_name = 'plan_code'
    """))
    row = result.fetchone()
    if row and row[0] in ('character varying', 'varchar', 'text'):
        # Convert string column to enum
        op.execute("""
            ALTER TABLE subscriptions 
            ALTER COLUMN plan_code TYPE subscriptionplan 
            USING plan_code::subscriptionplan
        """)
    
    # Convert status from string to enum (if it's currently a string type)
    result = conn.execute(sa.text("""
        SELECT data_type FROM information_schema.columns 
        WHERE table_name = 'subscriptions' AND column_name = 'status'
    """))
    row = result.fetchone()
    if row and row[0] in ('character varying', 'varchar', 'text'):
        # Map old status values to new enum values
        op.execute("""
            UPDATE subscriptions SET status = 'active' 
            WHERE status NOT IN ('active', 'past_due', 'cancelled')
        """)
        op.execute("""
            ALTER TABLE subscriptions 
            ALTER COLUMN status TYPE subscriptionstatus 
            USING status::subscriptionstatus
        """)
    
    # ============================================================
    # 3. AI_JOBS TABLE FIXES  
    # ============================================================
    
    # Create aijobstate enum if it doesn't exist
    if not enum_type_exists("aijobstate"):
        op.execute("""
            CREATE TYPE aijobstate AS ENUM (
                'queued', 'processing', 'complete', 'failed', 'cancelled'
            )
        """)
    
    # Create aijobpriority enum if it doesn't exist
    if not enum_type_exists("aijobpriority"):
        op.execute("""
            CREATE TYPE aijobpriority AS ENUM ('standard', 'priority')
        """)
    
    # Rename requester_id to requested_by_id if needed
    if column_exists("ai_jobs", "requester_id") and not column_exists("ai_jobs", "requested_by_id"):
        op.alter_column("ai_jobs", "requester_id", new_column_name="requested_by_id")
    elif not column_exists("ai_jobs", "requested_by_id"):
        # Add the column if neither exists
        op.add_column(
            "ai_jobs",
            sa.Column(
                "requested_by_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
        )
    
    # Add state column if it doesn't exist (model uses 'state', not 'status')
    if not column_exists("ai_jobs", "state"):
        # If 'status' exists, we need to migrate data
        if column_exists("ai_jobs", "status"):
            # Add state column
            op.add_column(
                "ai_jobs",
                sa.Column("state", sa.String(20), nullable=True),
            )
            # Copy data from status to state
            op.execute("UPDATE ai_jobs SET state = status")
            # Convert to enum
            op.execute("""
                ALTER TABLE ai_jobs 
                ALTER COLUMN state TYPE aijobstate 
                USING state::aijobstate
            """)
            op.execute("ALTER TABLE ai_jobs ALTER COLUMN state SET NOT NULL")
            op.execute("ALTER TABLE ai_jobs ALTER COLUMN state SET DEFAULT 'queued'")
            # Drop old status column
            op.drop_column("ai_jobs", "status")
        else:
            # Just add state column with enum type
            op.execute("""
                ALTER TABLE ai_jobs 
                ADD COLUMN state aijobstate NOT NULL DEFAULT 'queued'
            """)
    
    # Convert priority to enum if it's currently integer
    result = conn.execute(sa.text("""
        SELECT data_type FROM information_schema.columns 
        WHERE table_name = 'ai_jobs' AND column_name = 'priority'
    """))
    row = result.fetchone()
    if row and row[0] in ('integer', 'int4'):
        # Add new priority_enum column
        op.execute("""
            ALTER TABLE ai_jobs 
            ADD COLUMN priority_new aijobpriority NOT NULL DEFAULT 'standard'
        """)
        # Map 0 -> standard, anything else -> priority
        op.execute("""
            UPDATE ai_jobs SET priority_new = 
            CASE WHEN priority > 0 THEN 'priority'::aijobpriority ELSE 'standard'::aijobpriority END
        """)
        # Drop old column and rename new
        op.drop_column("ai_jobs", "priority")
        op.alter_column("ai_jobs", "priority_new", new_column_name="priority")
    
    # Rename completed_at to finished_at if needed
    if column_exists("ai_jobs", "completed_at") and not column_exists("ai_jobs", "finished_at"):
        op.alter_column("ai_jobs", "completed_at", new_column_name="finished_at")
    
    # ============================================================
    # 4. MAP_EDIT_PROPOSALS TABLE FIXES
    # ============================================================
    
    # Create editstatus enum if it doesn't exist
    if not enum_type_exists("editstatus"):
        op.execute("""
            CREATE TYPE editstatus AS ENUM (
                'pending', 'approved', 'rejected', 'withdrawn'
            )
        """)
    
    # Create verificationdecision enum if it doesn't exist
    if not enum_type_exists("verificationdecision"):
        op.execute("""
            CREATE TYPE verificationdecision AS ENUM (
                'approve', 'reject', 'needs_changes'
            )
        """)
    
    # Rename map_id to map_version_id if needed (model references map_versions, not maps)
    if column_exists("map_edit_proposals", "map_id") and not column_exists("map_edit_proposals", "map_version_id"):
        op.alter_column("map_edit_proposals", "map_id", new_column_name="map_version_id")
    
    # Rename diff_data to diff_payload if needed
    if column_exists("map_edit_proposals", "diff_data") and not column_exists("map_edit_proposals", "diff_payload"):
        op.alter_column("map_edit_proposals", "diff_data", new_column_name="diff_payload")
    
    # Rename description to summary if needed
    if column_exists("map_edit_proposals", "description") and not column_exists("map_edit_proposals", "summary"):
        op.alter_column("map_edit_proposals", "description", new_column_name="summary")
    
    # Add summary column if it doesn't exist
    if not column_exists("map_edit_proposals", "summary"):
        op.add_column(
            "map_edit_proposals",
            sa.Column("summary", sa.String(255), nullable=True),
        )
    
    # Add diff_payload as JSON if it doesn't exist
    if not column_exists("map_edit_proposals", "diff_payload"):
        op.add_column(
            "map_edit_proposals",
            sa.Column("diff_payload", postgresql.JSON(), nullable=True),
        )
    
    # Convert status to editstatus enum
    result = conn.execute(sa.text("""
        SELECT data_type FROM information_schema.columns 
        WHERE table_name = 'map_edit_proposals' AND column_name = 'status'
    """))
    row = result.fetchone()
    if row and row[0] in ('character varying', 'varchar', 'text'):
        op.execute("""
            ALTER TABLE map_edit_proposals 
            ALTER COLUMN status TYPE editstatus 
            USING status::editstatus
        """)
    
    # ============================================================
    # 5. UPDATE INDEXES FOR RENAMED COLUMNS
    # ============================================================
    
    # Drop old index on requester_id if it exists
    try:
        op.drop_index("ix_ai_jobs_requester_id", table_name="ai_jobs")
    except Exception:
        pass  # Index might not exist
    
    # Create index on requested_by_id
    try:
        op.create_index("ix_ai_jobs_requested_by_id", "ai_jobs", ["requested_by_id"])
    except Exception:
        pass  # Index might already exist


def downgrade() -> None:
    """Reverse schema changes (best effort)."""
    # This is a complex migration, downgrade would need careful handling
    # For now, just document that manual intervention may be needed
    pass
