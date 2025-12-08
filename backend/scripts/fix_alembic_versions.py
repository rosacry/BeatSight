#!/usr/bin/env python3
"""Fix renamed alembic migration versions in the database."""

import os
import sys


def main():
    """Update alembic_version table with renamed revision IDs."""
    # Check both DATABASE_DSN (used by alembic) and DATABASE_URL (Railway default)
    db_url = os.environ.get("DATABASE_DSN") or os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("No DATABASE_DSN or DATABASE_URL set, skipping alembic version fix")
        return 0

    # Fix postgres:// to postgresql:// for SQLAlchemy
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    elif db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Fix renamed migrations
            renames = [
                ("012_add_missing_song_map_columns", "012_add_song_map_cols"),
                ("013_fix_credit_balances_columns", "013_fix_credit_bal_cols"),
                ("014_add_staff_role_and_admin_user", "014_add_staff_role"),
            ]
            for old_name, new_name in renames:
                result = conn.execute(
                    text(
                        f"UPDATE alembic_version SET version_num='{new_name}' "
                        f"WHERE version_num='{old_name}'"
                    )
                )
                if result.rowcount > 0:
                    print(f"Updated alembic version: {old_name} -> {new_name}")
            conn.commit()
        print("Alembic version fix completed")
        return 0
    except Exception as e:
        print(f"Warning: Could not fix alembic versions: {e}")
        # Don't fail - the migration might still work
        return 0


if __name__ == "__main__":
    sys.exit(main())
