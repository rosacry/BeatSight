"""Fix enum values from lowercase to UPPERCASE.

Revision ID: 017_fix_enum_case
Revises: 016_fix_schema_mismatches
Create Date: 2025-12-08

SQLAlchemy's SAEnum sends Python enum NAMES (uppercase like QUEUED, ACTIVE)
to PostgreSQL, but the database enums were created with lowercase values.
This migration recreates the enum types with UPPERCASE values.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "017_fix_enum_case"
down_revision = "016_fix_schema_mismatches"
branch_labels = None
depends_on = None


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


def get_enum_values(type_name: str) -> list[str]:
    """Get the current values of a PostgreSQL enum type."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT enumlabel FROM pg_enum 
            JOIN pg_type ON pg_enum.enumtypid = pg_type.oid 
            WHERE pg_type.typname = :type_name
            ORDER BY enumsortorder
            """
        ),
        {"type_name": type_name},
    )
    return [row[0] for row in result.fetchall()]


def recreate_enum_with_uppercase(
    type_name: str,
    table_name: str,
    column_name: str,
    uppercase_values: list[str],
    default_value: str | None = None,
) -> None:
    """Recreate an enum type with uppercase values, migrating existing data."""
    conn = op.get_bind()
    
    # Check if enum exists
    if not enum_type_exists(type_name):
        # Create new enum with uppercase values
        values_str = ", ".join(f"'{v}'" for v in uppercase_values)
        op.execute(sa.text(f"CREATE TYPE {type_name} AS ENUM ({values_str})"))
        return
    
    # Get current enum values
    current_values = get_enum_values(type_name)
    
    # Check if already uppercase (first value is uppercase)
    if current_values and current_values[0].isupper():
        print(f"Enum {type_name} already has uppercase values, skipping")
        return
    
    # Check if column exists in table
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
    column_exists = result.scalar()
    
    if not column_exists:
        # Just drop and recreate the enum
        op.execute(sa.text(f"DROP TYPE IF EXISTS {type_name} CASCADE"))
        values_str = ", ".join(f"'{v}'" for v in uppercase_values)
        op.execute(sa.text(f"CREATE TYPE {type_name} AS ENUM ({values_str})"))
        return
    
    # Need to migrate the column:
    # 1. Change column to TEXT
    # 2. Drop old enum
    # 3. Create new enum with uppercase
    # 4. Convert column values to uppercase
    # 5. Change column back to enum
    
    print(f"Recreating enum {type_name} with uppercase values for {table_name}.{column_name}")
    
    # Get current column default if any
    result = conn.execute(
        sa.text(
            """
            SELECT column_default FROM information_schema.columns
            WHERE table_name = :table_name AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    row = result.fetchone()
    has_default = row and row[0] is not None
    
    # 1. Remove default and change column to TEXT
    if has_default:
        op.execute(sa.text(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP DEFAULT"))
    
    op.execute(sa.text(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE TEXT"))
    
    # 2. Update values to uppercase
    op.execute(sa.text(f"UPDATE {table_name} SET {column_name} = UPPER({column_name})"))
    
    # 3. Drop old enum
    op.execute(sa.text(f"DROP TYPE {type_name}"))
    
    # 4. Create new enum with uppercase values
    values_str = ", ".join(f"'{v}'" for v in uppercase_values)
    op.execute(sa.text(f"CREATE TYPE {type_name} AS ENUM ({values_str})"))
    
    # 5. Convert column back to enum
    op.execute(sa.text(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE {type_name} USING {column_name}::{type_name}"))
    
    # 6. Restore default if needed
    if default_value:
        op.execute(sa.text(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET DEFAULT '{default_value}'"))


def upgrade() -> None:
    """Recreate all enum types with UPPERCASE values."""
    
    # ============================================================
    # SUBSCRIPTION ENUMS
    # ============================================================
    
    recreate_enum_with_uppercase(
        type_name="subscriptionplan",
        table_name="subscriptions",
        column_name="plan_code",
        uppercase_values=["FREE", "BASIC_MONTHLY", "BASIC_YEARLY", "PRO_MONTHLY", "PRO_YEARLY"],
        default_value="FREE",
    )
    
    recreate_enum_with_uppercase(
        type_name="subscriptionstatus",
        table_name="subscriptions",
        column_name="status",
        uppercase_values=["ACTIVE", "PAST_DUE", "CANCELLED"],
        default_value="ACTIVE",
    )
    
    # ============================================================
    # AI JOB ENUMS
    # ============================================================
    
    recreate_enum_with_uppercase(
        type_name="aijobstate",
        table_name="ai_jobs",
        column_name="state",
        uppercase_values=["QUEUED", "PROCESSING", "COMPLETE", "FAILED", "CANCELLED"],
        default_value="QUEUED",
    )
    
    recreate_enum_with_uppercase(
        type_name="aijobpriority",
        table_name="ai_jobs",
        column_name="priority",
        uppercase_values=["STANDARD", "PRIORITY"],
        default_value="STANDARD",
    )
    
    # ============================================================
    # MAP EDIT ENUMS
    # ============================================================
    
    recreate_enum_with_uppercase(
        type_name="editstatus",
        table_name="map_edit_proposals",
        column_name="status",
        uppercase_values=["PENDING", "APPROVED", "REJECTED", "WITHDRAWN"],
        default_value="PENDING",
    )
    
    recreate_enum_with_uppercase(
        type_name="verificationdecision",
        table_name="edit_verifications",  # This table may not exist yet
        column_name="decision",
        uppercase_values=["APPROVE", "REJECT", "NEEDS_CHANGES"],
        default_value=None,
    )


def downgrade() -> None:
    """This migration cannot be easily reversed."""
    pass
