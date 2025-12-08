#!/usr/bin/env python3
"""
Script to delete test user accounts from the database.

Usage:
    python scripts/delete_test_users.py

This will delete users with the following display names:
- Test User
- CorsTest
- FinalTest

The script will:
1. Show matching users before deletion
2. Ask for confirmation
3. Delete users and all related data (cascading)
"""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.user import User


# Test user display names to delete
TEST_USER_NAMES = [
    "Test User",
    "CorsTest", 
    "FinalTest",
]


async def find_test_users(session: AsyncSession) -> list[User]:
    """Find all test users by display name."""
    result = await session.execute(
        select(User).where(User.display_name.in_(TEST_USER_NAMES))
    )
    return list(result.scalars().all())


async def delete_test_users(session: AsyncSession, users: list[User]) -> int:
    """Delete the specified users."""
    deleted_count = 0
    for user in users:
        await session.delete(user)
        deleted_count += 1
    await session.commit()
    return deleted_count


async def main() -> None:
    """Main entry point."""
    settings = get_settings()
    
    # Create async engine
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    
    # Create session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        # Find test users
        print("\n🔍 Searching for test users...")
        users = await find_test_users(session)
        
        if not users:
            print("✅ No test users found. Database is clean!")
            return
        
        # Display found users
        print(f"\n📋 Found {len(users)} test user(s):\n")
        for user in users:
            print(f"  • {user.display_name}")
            print(f"    Email: {user.email}")
            print(f"    ID: {user.id}")
            print(f"    Created: {user.created_at}")
            print()
        
        # Confirm deletion
        print("⚠️  This will permanently delete these users and all associated data.")
        confirm = input("Type 'DELETE' to confirm: ").strip()
        
        if confirm != "DELETE":
            print("\n❌ Deletion cancelled.")
            return
        
        # Delete users
        print("\n🗑️  Deleting test users...")
        deleted = await delete_test_users(session, users)
        print(f"✅ Successfully deleted {deleted} test user(s).")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
