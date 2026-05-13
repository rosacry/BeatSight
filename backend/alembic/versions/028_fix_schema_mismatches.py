"""Fix schema mismatches causing 500 errors.

Revision ID: 028_fix_schema_mismatches
Revises: 027_anonymous_mode
Create Date: 2025-12-10

This migration fixes multiple schema mismatches:
1. user_achievements: rename unlocked_at → earned_at (model expects earned_at)
2. karma_ledger: rename reason → reason_code (model expects reason_code) 
3. karma_ledger: rename reference_type → related_entity_type
4. karma_ledger: rename reference_id → related_entity_id
5. karma_ledger: rename created_at → recorded_at
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "028_fix_schema_mismatches"
down_revision = "027_anonymous_mode"
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Fix schema mismatches."""
    
    # =========================================================================
    # 1. Fix user_achievements.unlocked_at → earned_at
    # =========================================================================
    if table_exists("user_achievements"):
        if column_exists("user_achievements", "unlocked_at"):
            if not column_exists("user_achievements", "earned_at"):
                print("Renaming user_achievements.unlocked_at to earned_at...")
                op.alter_column(
                    "user_achievements",
                    "unlocked_at",
                    new_column_name="earned_at",
                )
            else:
                print("Both columns exist - dropping unlocked_at")
                op.drop_column("user_achievements", "unlocked_at")
        elif not column_exists("user_achievements", "earned_at"):
            print("Neither column exists - creating earned_at...")
            op.add_column(
                "user_achievements",
                sa.Column(
                    "earned_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                    nullable=False,
                ),
            )
        else:
            print("user_achievements.earned_at already exists - no action needed")
    
    # =========================================================================
    # 2. Fix karma_ledger column names
    # =========================================================================
    if table_exists("karma_ledger"):
        # reason → reason_code
        if column_exists("karma_ledger", "reason"):
            if not column_exists("karma_ledger", "reason_code"):
                print("Renaming karma_ledger.reason to reason_code...")
                op.alter_column(
                    "karma_ledger",
                    "reason",
                    new_column_name="reason_code",
                )
        
        # reference_type → related_entity_type
        if column_exists("karma_ledger", "reference_type"):
            if not column_exists("karma_ledger", "related_entity_type"):
                print("Renaming karma_ledger.reference_type to related_entity_type...")
                op.alter_column(
                    "karma_ledger",
                    "reference_type",
                    new_column_name="related_entity_type",
                )
        
        # reference_id → related_entity_id
        if column_exists("karma_ledger", "reference_id"):
            if not column_exists("karma_ledger", "related_entity_id"):
                print("Renaming karma_ledger.reference_id to related_entity_id...")
                op.alter_column(
                    "karma_ledger",
                    "reference_id",
                    new_column_name="related_entity_id",
                )
        
        # created_at → recorded_at
        if column_exists("karma_ledger", "created_at"):
            if not column_exists("karma_ledger", "recorded_at"):
                print("Renaming karma_ledger.created_at to recorded_at...")
                op.alter_column(
                    "karma_ledger",
                    "created_at",
                    new_column_name="recorded_at",
                )


def downgrade() -> None:
    """Revert schema changes."""
    
    # user_achievements
    if table_exists("user_achievements"):
        if column_exists("user_achievements", "earned_at"):
            if not column_exists("user_achievements", "unlocked_at"):
                op.alter_column(
                    "user_achievements",
                    "earned_at",
                    new_column_name="unlocked_at",
                )
    
    # karma_ledger
    if table_exists("karma_ledger"):
        if column_exists("karma_ledger", "reason_code"):
            if not column_exists("karma_ledger", "reason"):
                op.alter_column(
                    "karma_ledger",
                    "reason_code",
                    new_column_name="reason",
                )
        
        if column_exists("karma_ledger", "related_entity_type"):
            if not column_exists("karma_ledger", "reference_type"):
                op.alter_column(
                    "karma_ledger",
                    "related_entity_type",
                    new_column_name="reference_type",
                )
        
        if column_exists("karma_ledger", "related_entity_id"):
            if not column_exists("karma_ledger", "reference_id"):
                op.alter_column(
                    "karma_ledger",
                    "related_entity_id",
                    new_column_name="reference_id",
                )
        
        if column_exists("karma_ledger", "recorded_at"):
            if not column_exists("karma_ledger", "created_at"):
                op.alter_column(
                    "karma_ledger",
                    "recorded_at",
                    new_column_name="created_at",
                )
