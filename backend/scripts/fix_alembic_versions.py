#!/usr/bin/env python3
"""Fix renamed alembic migration versions in the database."""

import asyncio
import os
import sys


async def fix_versions():
    """Update alembic_version table with renamed revision IDs."""
    # Check both DATABASE_DSN (used by alembic) and DATABASE_URL (Railway default)
    db_url = os.environ.get("DATABASE_DSN") or os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("No DATABASE_DSN or DATABASE_URL set, skipping alembic version fix")
        return 0

    # Convert to asyncpg format
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(db_url)
        async with engine.connect() as conn:
            # Fix renamed migrations
            renames = [
                ("012_add_missing_song_map_columns", "012_add_song_map_cols"),
                ("013_fix_credit_balances_columns", "013_fix_credit_bal_cols"),
                ("014_add_staff_role_and_admin_user", "014_add_staff_role"),
            ]
            for old_name, new_name in renames:
                result = await conn.execute(
                    text(
                        f"UPDATE alembic_version SET version_num='{new_name}' "
                        f"WHERE version_num='{old_name}'"
                    )
                )
                if result.rowcount > 0:
                    print(f"Updated alembic version: {old_name} -> {new_name}")
            await conn.commit()
        await engine.dispose()
        print("Alembic version fix completed")
        return 0
    except Exception as e:
        print(f"Warning: Could not fix alembic versions: {e}")
        # Don't fail - the migration might still work
        return 0


def main():
    """Entry point."""
    return asyncio.run(fix_versions())


if __name__ == "__main__":
    sys.exit(main())
