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
            
            # Check current version(s)
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            rows = result.fetchall()
            if rows:
                current_versions = [r[0] for r in rows]
                print(f"Current alembic version(s): {current_versions}")
                
                # If there are multiple rows (heads), keep only the latest one
                if len(current_versions) > 1:
                    print("Multiple versions detected, cleaning up...")
                    # Delete all rows first, then insert the latest
                    await conn.execute(text("DELETE FROM alembic_version"))
                    # Determine which is the latest version
                    # Priority order for our migrations
                    priority = [
                        "018_fix_remaining_schema",
                        "017_fix_enum_case", 
                        "016_fix_schema_mismatches",
                        "015_fix_subscription_col",
                        "014_add_staff_role",
                        "013_fix_credit_bal_cols",
                        "012_add_song_map_cols",
                    ]
                    latest = None
                    for p in priority:
                        if p in current_versions:
                            latest = p
                            break
                    if not latest:
                        # Fallback: pick highest numbered one
                        def get_num(v):
                            try:
                                return int(v.split('_')[0])
                            except:
                                return 0
                        latest = max(current_versions, key=get_num)
                    
                    await conn.execute(
                        text(f"INSERT INTO alembic_version (version_num) VALUES ('{latest}')")
                    )
                    print(f"Reset to single version: {latest}")
            
            await conn.commit()
        await engine.dispose()
        print("Alembic version fix completed")
        return 0
    except Exception as e:
        print(f"Warning: Could not fix alembic versions: {e}")
        # Don't fail - the migration might still work
        return 0
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
