"""Fix remaining schema issues: submitted_at and decision column types.

Revision ID: 018_fix_remaining_schema
Revises: 017_fix_enum_case
Create Date: 2025-12-08

This migration fixes:
1. map_edit_proposals.submitted_at column doesn't exist (need to add it)
2. map_verification_decisions.decision is VARCHAR, needs to be enum type
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "018_fix_remaining_schema"
down_revision = "017_fix_enum_case"
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
    """Fix remaining schema issues."""
    conn = op.get_bind()
    
    # ============================================================
    # 1. FIX map_edit_proposals.submitted_at
    # ============================================================
    
    if table_exists("map_edit_proposals"):
        # Add submitted_at column if it doesn't exist
        if not column_exists("map_edit_proposals", "submitted_at"):
            print("Adding submitted_at column to map_edit_proposals")
            
            # Check if created_at exists - we can copy from it
            if column_exists("map_edit_proposals", "created_at"):
                # Add column without default first
                op.add_column(
                    "map_edit_proposals",
                    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
                )
                # Copy data from created_at
                op.execute("UPDATE map_edit_proposals SET submitted_at = created_at")
                # Set default for future rows
                op.execute("""
                    ALTER TABLE map_edit_proposals 
                    ALTER COLUMN submitted_at SET DEFAULT now()
                """)
            else:
                # Just add the column with server default
                op.add_column(
                    "map_edit_proposals",
                    sa.Column(
                        "submitted_at", 
                        sa.DateTime(timezone=True), 
                        server_default=sa.func.now(),
                        nullable=True
                    ),
                )
    
    # ============================================================
    # 2. FIX map_verification_decisions.decision column type
    # ============================================================
    
    if table_exists("map_verification_decisions"):
        # Check if decision column exists and what type it is
        result = conn.execute(sa.text("""
            SELECT data_type FROM information_schema.columns 
            WHERE table_name = 'map_verification_decisions' AND column_name = 'decision'
        """))
        row = result.fetchone()
        
        if row:
            current_type = row[0]
            print(f"map_verification_decisions.decision current type: {current_type}")
            
            if current_type in ('character varying', 'varchar', 'text'):
                # Create verificationdecision enum if it doesn't exist
                if not enum_type_exists("verificationdecision"):
                    print("Creating verificationdecision enum")
                    op.execute("""
                        CREATE TYPE verificationdecision AS ENUM (
                            'APPROVE', 'REJECT', 'NEEDS_CHANGES'
                        )
                    """)
                
                # Convert existing values to uppercase
                print("Converting decision values to uppercase")
                op.execute("""
                    UPDATE map_verification_decisions 
                    SET decision = UPPER(decision)
                    WHERE decision IS NOT NULL
                """)
                
                # Convert the column to enum type
                print("Converting decision column to verificationdecision enum")
                op.execute("""
                    ALTER TABLE map_verification_decisions 
                    ALTER COLUMN decision TYPE verificationdecision 
                    USING decision::verificationdecision
                """)
    
    # ============================================================
    # 3. Ensure editstatus enum exists and is applied
    # ============================================================
    
    if table_exists("map_edit_proposals"):
        result = conn.execute(sa.text("""
            SELECT data_type FROM information_schema.columns 
            WHERE table_name = 'map_edit_proposals' AND column_name = 'status'
        """))
        row = result.fetchone()
        
        if row:
            current_type = row[0]
            print(f"map_edit_proposals.status current type: {current_type}")
            
            if current_type in ('character varying', 'varchar', 'text'):
                # Create editstatus enum if it doesn't exist
                if not enum_type_exists("editstatus"):
                    print("Creating editstatus enum")
                    op.execute("""
                        CREATE TYPE editstatus AS ENUM (
                            'PENDING', 'APPROVED', 'REJECTED', 'WITHDRAWN'
                        )
                    """)
                
                # Convert existing values to uppercase
                print("Converting status values to uppercase")
                op.execute("""
                    UPDATE map_edit_proposals 
                    SET status = UPPER(status)
                    WHERE status IS NOT NULL
                """)
                
                # Set default for NULL values
                op.execute("""
                    UPDATE map_edit_proposals 
                    SET status = 'PENDING'
                    WHERE status IS NULL
                """)
                
                # Convert the column to enum type
                print("Converting status column to editstatus enum")
                op.execute("""
                    ALTER TABLE map_edit_proposals 
                    ALTER COLUMN status TYPE editstatus 
                    USING status::editstatus
                """)


def downgrade() -> None:
    """Reverse changes (best effort)."""
    pass
