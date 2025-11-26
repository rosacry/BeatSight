"""
Seed default roles in the database.

This script ensures the standard roles (user, verifier, admin) exist.
Run this after database migrations to set up the RBAC system.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.role import Role
from app.services.rbac import RoleCode


# Default roles to seed
DEFAULT_ROLES = [
    {
        "code": RoleCode.USER,
        "description": "Standard user with basic permissions",
        "min_karma": 0,
        "requires_phone_verification": False,
    },
    {
        "code": RoleCode.VERIFIER,
        "description": "Trusted user who can verify and approve beatmaps",
        "min_karma": 100,
        "requires_phone_verification": True,
    },
    {
        "code": RoleCode.ADMIN,
        "description": "Administrator with full system access",
        "min_karma": 0,
        "requires_phone_verification": True,
    },
]


async def seed_roles(session: AsyncSession) -> list[str]:
    """
    Seed default roles into the database.
    
    Returns list of created role codes.
    """
    created = []
    
    for role_data in DEFAULT_ROLES:
        # Check if role already exists
        result = await session.execute(
            select(Role).where(Role.code == role_data["code"])
        )
        existing = result.scalar_one_or_none()
        
        if existing is None:
            role = Role(**role_data)
            session.add(role)
            created.append(role_data["code"])
            print(f"Created role: {role_data['code']}")
        else:
            print(f"Role already exists: {role_data['code']}")
    
    await session.commit()
    return created


async def main() -> None:
    """Run the role seeding script."""
    print("Seeding default roles...")
    
    async with async_session_factory() as session:
        created = await seed_roles(session)
    
    if created:
        print(f"\nCreated {len(created)} role(s): {', '.join(created)}")
    else:
        print("\nNo new roles created (all already exist)")


if __name__ == "__main__":
    asyncio.run(main())
