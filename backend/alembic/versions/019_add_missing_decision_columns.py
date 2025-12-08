"""Add missing columns to map_verification_decisions table.

Revision ID: 019_add_missing_decision_columns
Revises: 018_fix_remaining_schema
Create Date: 2025-12-08

This migration adds:
1. map_verification_decisions.notes column (VARCHAR(512))
2. map_verification_decisions.decided_at column (TIMESTAMP WITH TIME ZONE)
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "019_add_missing_decision_columns"
down_revision = "018_fix_remaining_schema"
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


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = :table_name
            )
            """
        ),
        {"table_name": table_name},
    )
    return result.scalar()


def upgrade() -> None:
    """Add missing columns to map_verification_decisions."""
    
    if not table_exists("map_verification_decisions"):
        print("Table map_verification_decisions does not exist, skipping")
        return
    
    # ============================================================
    # 1. Add 'notes' column
    # ============================================================
    if not column_exists("map_verification_decisions", "notes"):
        print("Adding 'notes' column to map_verification_decisions")
        op.add_column(
            "map_verification_decisions",
            sa.Column("notes", sa.String(512), nullable=True),
        )
    else:
        print("Column 'notes' already exists in map_verification_decisions")
    
    # ============================================================
    # 2. Add 'decided_at' column
    # ============================================================
    if not column_exists("map_verification_decisions", "decided_at"):
        print("Adding 'decided_at' column to map_verification_decisions")
        op.add_column(
            "map_verification_decisions",
            sa.Column(
                "decided_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
        )
        
        # Set decided_at to now() for any existing rows
        op.execute("""
            UPDATE map_verification_decisions 
            SET decided_at = now() 
            WHERE decided_at IS NULL
        """)
    else:
        print("Column 'decided_at' already exists in map_verification_decisions")


def downgrade() -> None:
    """Remove the added columns."""
    if table_exists("map_verification_decisions"):
        if column_exists("map_verification_decisions", "notes"):
            op.drop_column("map_verification_decisions", "notes")
        if column_exists("map_verification_decisions", "decided_at"):
            op.drop_column("map_verification_decisions", "decided_at")
