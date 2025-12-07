#!/usr/bin/env python3
"""
Create an admin user account.

Usage:
    python -m scripts.create_admin <email> <password> <display_name>

Example:
    python -m scripts.create_admin admin@beatsight.io MySecurePassword123! "Admin User"
"""

import asyncio
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.user import User
from app.models.role import Role, UserRole
from app.services.auth import AuthService
from app.services.rbac import RoleCode


async def create_admin(
    email: str,
    password: str,
    display_name: str,
    session: AsyncSession,
) -> User:
    """Create an admin user with all required roles."""

    # Create auth service for password hashing
    auth_service = AuthService(session)

    # Check if user already exists
    result = await session.execute(select(User).where(User.email == email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        print(f"User with email {email} already exists!")
        print(f"User ID: {existing_user.id}")

        # Check if they have admin role
        role_result = await session.execute(
            select(Role)
            .join(UserRole)
            .where(UserRole.user_id == existing_user.id)
            .where(Role.code == RoleCode.ADMIN)
        )
        has_admin = role_result.scalar_one_or_none()

        if not has_admin:
            print("Adding admin role to existing user...")
            await assign_admin_role(existing_user, session)
            await session.commit()
            print("✅ Admin role assigned!")
        else:
            print("✅ User already has admin role!")

        return existing_user

    # Create new user
    user = User(
        email=email,
        display_name=display_name,
        hashed_password=auth_service.hash_password(password),
        auth_provider_id=f"local:{uuid.uuid4()}",
        email_verified=True,  # Admin accounts are pre-verified
    )
    session.add(user)
    await session.flush()  # Get the user ID

    print(f"Created user: {email}")
    print(f"User ID: {user.id}")

    # Assign admin role
    await assign_admin_role(user, session)

    await session.commit()
    print("✅ Admin user created successfully!")

    return user


async def assign_admin_role(user: User, session: AsyncSession) -> None:
    """Assign admin role to a user."""

    # Get admin role
    result = await session.execute(select(Role).where(Role.code == RoleCode.ADMIN))
    admin_role = result.scalar_one_or_none()

    if not admin_role:
        print("⚠️  Admin role doesn't exist! Running role seeder...")
        from app.db.seed_roles import seed_roles

        await seed_roles(session)

        result = await session.execute(select(Role).where(Role.code == RoleCode.ADMIN))
        admin_role = result.scalar_one_or_none()

    if admin_role:
        # Check if assignment already exists
        existing = await session.execute(
            select(UserRole)
            .where(UserRole.user_id == user.id)
            .where(UserRole.role_id == admin_role.id)
        )
        if not existing.scalar_one_or_none():
            user_role = UserRole(user_id=user.id, role_id=admin_role.id)
            session.add(user_role)
            print(f"Assigned role: {RoleCode.ADMIN}")

    # Also assign basic user role
    result = await session.execute(select(Role).where(Role.code == RoleCode.USER))
    user_role_obj = result.scalar_one_or_none()

    if user_role_obj:
        existing = await session.execute(
            select(UserRole)
            .where(UserRole.user_id == user.id)
            .where(UserRole.role_id == user_role_obj.id)
        )
        if not existing.scalar_one_or_none():
            assignment = UserRole(user_id=user.id, role_id=user_role_obj.id)
            session.add(assignment)
            print(f"Assigned role: {RoleCode.USER}")


async def main() -> None:
    """Main entry point."""
    if len(sys.argv) != 4:
        print(__doc__)
        print("\n❌ Error: Please provide email, password, and display_name")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    display_name = sys.argv[3]

    # Validate password length
    if len(password) < 8:
        print("❌ Error: Password must be at least 8 characters")
        sys.exit(1)

    print("\n🔧 Creating admin account:")
    print(f"   Email: {email}")
    print(f"   Display Name: {display_name}")
    print()

    async with async_session_factory() as session:
        await create_admin(email, password, display_name, session)

    print("\n🎉 Done! You can now log in at https://beatsight.io/login")


if __name__ == "__main__":
    asyncio.run(main())
