"""
Role-Based Access Control (RBAC) service.

Ticket E4-001: RBAC System
- Role model (user, verifier, admin)
- Permission checks on routes
- Role assignment API

This module provides:
- Permission enum defining all system permissions
- Role-permission mappings
- RBAC service for checking user permissions
- FastAPI dependencies for route protection
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import TYPE_CHECKING, Sequence

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.logging import get_logger
from app.models.role import Role, UserRole
from app.models.user import User

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


# =============================================================================
# Permission Definitions
# =============================================================================


class Permission(str, Enum):
    """
    System permissions that can be granted through roles.
    
    Naming convention: <resource>:<action>
    """
    
    # User management
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_LIST = "user:list"
    
    # Role management (admin only)
    ROLE_ASSIGN = "role:assign"
    ROLE_REVOKE = "role:revoke"
    ROLE_LIST = "role:list"
    
    # Song management
    SONG_CREATE = "song:create"
    SONG_READ = "song:read"
    SONG_UPDATE = "song:update"
    SONG_DELETE = "song:delete"
    SONG_LIST = "song:list"
    
    # AI job management
    JOB_CREATE = "job:create"
    JOB_READ = "job:read"
    JOB_CANCEL = "job:cancel"
    JOB_RETRY = "job:retry"
    JOB_LIST = "job:list"
    JOB_ADMIN = "job:admin"  # Admin-level job operations
    
    # Map verification (verifier role)
    MAP_VERIFY = "map:verify"
    MAP_REJECT = "map:reject"
    MAP_APPROVE = "map:approve"
    
    # Map editing
    MAP_EDIT_PROPOSE = "map:edit:propose"
    MAP_EDIT_REVIEW = "map:edit:review"
    
    # Admin operations
    ADMIN_DASHBOARD = "admin:dashboard"
    ADMIN_METRICS = "admin:metrics"
    ADMIN_AUDIT = "admin:audit"
    ADMIN_SYSTEM = "admin:system"
    
    # Subscription management
    SUBSCRIPTION_READ = "subscription:read"
    SUBSCRIPTION_MANAGE = "subscription:manage"


# =============================================================================
# Role Definitions
# =============================================================================


class RoleCode(str, Enum):
    """Standard role codes in the system."""
    
    USER = "user"
    VERIFIER = "verifier"
    ADMIN = "admin"


# Role-Permission mappings
# Each role inherits permissions from "lower" roles plus their own
ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    RoleCode.USER: {
        # Basic user permissions
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.SONG_CREATE,
        Permission.SONG_READ,
        Permission.SONG_LIST,
        Permission.JOB_CREATE,
        Permission.JOB_READ,
        Permission.JOB_CANCEL,
        Permission.JOB_LIST,
        Permission.MAP_EDIT_PROPOSE,
        Permission.SUBSCRIPTION_READ,
    },
    RoleCode.VERIFIER: {
        # Inherits all user permissions plus:
        Permission.MAP_VERIFY,
        Permission.MAP_REJECT,
        Permission.MAP_APPROVE,
        Permission.MAP_EDIT_REVIEW,
    },
    RoleCode.ADMIN: {
        # Inherits all verifier permissions plus:
        Permission.USER_DELETE,
        Permission.USER_LIST,
        Permission.ROLE_ASSIGN,
        Permission.ROLE_REVOKE,
        Permission.ROLE_LIST,
        Permission.SONG_UPDATE,
        Permission.SONG_DELETE,
        Permission.JOB_RETRY,
        Permission.JOB_ADMIN,
        Permission.ADMIN_DASHBOARD,
        Permission.ADMIN_METRICS,
        Permission.ADMIN_AUDIT,
        Permission.ADMIN_SYSTEM,
        Permission.SUBSCRIPTION_MANAGE,
    },
}

# Build complete permission sets with inheritance
ROLE_HIERARCHY = [RoleCode.USER, RoleCode.VERIFIER, RoleCode.ADMIN]


def _build_inherited_permissions() -> dict[str, set[Permission]]:
    """Build permission sets with role inheritance."""
    result: dict[str, set[Permission]] = {}
    accumulated: set[Permission] = set()
    
    for role in ROLE_HIERARCHY:
        accumulated = accumulated | ROLE_PERMISSIONS.get(role, set())
        result[role] = accumulated.copy()
    
    return result


EFFECTIVE_PERMISSIONS = _build_inherited_permissions()


# =============================================================================
# RBAC Service
# =============================================================================


class RBACService:
    """Service for role-based access control operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_user_roles(self, user_id: uuid.UUID) -> list[str]:
        """Get all role codes for a user."""
        result = await self.session.execute(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        return [row[0] for row in result.fetchall()]
    
    async def get_user_permissions(self, user_id: uuid.UUID) -> set[Permission]:
        """Get all effective permissions for a user."""
        roles = await self.get_user_roles(user_id)
        
        permissions: set[Permission] = set()
        for role in roles:
            role_perms = EFFECTIVE_PERMISSIONS.get(role, set())
            permissions |= role_perms
        
        return permissions
    
    async def user_has_permission(
        self,
        user_id: uuid.UUID,
        permission: Permission,
    ) -> bool:
        """Check if a user has a specific permission."""
        permissions = await self.get_user_permissions(user_id)
        return permission in permissions
    
    async def user_has_any_permission(
        self,
        user_id: uuid.UUID,
        permissions: Sequence[Permission],
    ) -> bool:
        """Check if a user has any of the specified permissions."""
        user_perms = await self.get_user_permissions(user_id)
        return bool(user_perms & set(permissions))
    
    async def user_has_all_permissions(
        self,
        user_id: uuid.UUID,
        permissions: Sequence[Permission],
    ) -> bool:
        """Check if a user has all of the specified permissions."""
        user_perms = await self.get_user_permissions(user_id)
        return set(permissions).issubset(user_perms)
    
    async def user_has_role(self, user_id: uuid.UUID, role_code: str) -> bool:
        """Check if a user has a specific role."""
        roles = await self.get_user_roles(user_id)
        return role_code in roles
    
    async def user_is_admin(self, user_id: uuid.UUID) -> bool:
        """Check if a user has admin role."""
        return await self.user_has_role(user_id, RoleCode.ADMIN)
    
    async def user_is_verifier(self, user_id: uuid.UUID) -> bool:
        """Check if a user has verifier role (or admin, which inherits it)."""
        roles = await self.get_user_roles(user_id)
        return RoleCode.VERIFIER in roles or RoleCode.ADMIN in roles
    
    # -------------------------------------------------------------------------
    # Role Management
    # -------------------------------------------------------------------------
    
    async def get_role_by_code(self, code: str) -> Role | None:
        """Get a role by its code."""
        result = await self.session.execute(
            select(Role).where(Role.code == code)
        )
        return result.scalar_one_or_none()
    
    async def get_all_roles(self) -> list[Role]:
        """Get all roles in the system."""
        result = await self.session.execute(select(Role).order_by(Role.id))
        return list(result.scalars().all())
    
    async def assign_role(
        self,
        user_id: uuid.UUID,
        role_code: str,
        assigned_by: uuid.UUID | None = None,
    ) -> UserRole:
        """
        Assign a role to a user.
        
        Raises:
            ValueError: If role doesn't exist or user already has it
        """
        role = await self.get_role_by_code(role_code)
        if role is None:
            raise ValueError(f"Role '{role_code}' does not exist")
        
        # Check if user already has this role
        existing = await self.session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError(f"User already has role '{role_code}'")
        
        user_role = UserRole(user_id=user_id, role_id=role.id)
        self.session.add(user_role)
        await self.session.flush()
        
        logger.info(
            "Role assigned",
            user_id=str(user_id),
            role=role_code,
            assigned_by=str(assigned_by) if assigned_by else None,
        )
        
        return user_role
    
    async def revoke_role(
        self,
        user_id: uuid.UUID,
        role_code: str,
        revoked_by: uuid.UUID | None = None,
    ) -> bool:
        """
        Revoke a role from a user.
        
        Returns True if role was revoked, False if user didn't have it.
        """
        role = await self.get_role_by_code(role_code)
        if role is None:
            raise ValueError(f"Role '{role_code}' does not exist")
        
        result = await self.session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
            )
        )
        user_role = result.scalar_one_or_none()
        
        if user_role is None:
            return False
        
        await self.session.delete(user_role)
        await self.session.flush()
        
        logger.info(
            "Role revoked",
            user_id=str(user_id),
            role=role_code,
            revoked_by=str(revoked_by) if revoked_by else None,
        )
        
        return True
    
    async def ensure_default_role(self, user_id: uuid.UUID) -> None:
        """Ensure user has at least the default 'user' role."""
        roles = await self.get_user_roles(user_id)
        if not roles:
            try:
                await self.assign_role(user_id, RoleCode.USER)
            except ValueError:
                pass  # Role might not exist yet (during migrations)


# =============================================================================
# FastAPI Dependencies
# =============================================================================


def require_permission(permission: Permission):
    """
    Dependency factory that requires a specific permission.
    
    Usage:
        @router.get("/admin/users")
        async def list_users(
            user: User = Depends(require_permission(Permission.USER_LIST))
        ):
            ...
    """
    async def dependency(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        rbac = RBACService(session)
        has_permission = await rbac.user_has_permission(user.id, permission)
        
        if not has_permission:
            logger.warning(
                "Permission denied",
                user_id=str(user.id),
                permission=permission.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value}",
            )
        
        return user
    
    return dependency


def require_any_permission(*permissions: Permission):
    """
    Dependency factory that requires any of the specified permissions.
    
    Usage:
        @router.get("/maps/{id}/review")
        async def review_map(
            user: User = Depends(require_any_permission(
                Permission.MAP_VERIFY,
                Permission.ADMIN_DASHBOARD
            ))
        ):
            ...
    """
    async def dependency(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        rbac = RBACService(session)
        has_any = await rbac.user_has_any_permission(user.id, permissions)
        
        if not has_any:
            logger.warning(
                "Permission denied (any)",
                user_id=str(user.id),
                permissions=[p.value for p in permissions],
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        
        return user
    
    return dependency


def require_all_permissions(*permissions: Permission):
    """
    Dependency factory that requires all of the specified permissions.
    """
    async def dependency(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        rbac = RBACService(session)
        has_all = await rbac.user_has_all_permissions(user.id, permissions)
        
        if not has_all:
            logger.warning(
                "Permission denied (all)",
                user_id=str(user.id),
                permissions=[p.value for p in permissions],
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        
        return user
    
    return dependency


def require_role(role_code: str):
    """
    Dependency factory that requires a specific role.
    
    Usage:
        @router.post("/admin/action")
        async def admin_action(
            user: User = Depends(require_role("admin"))
        ):
            ...
    """
    async def dependency(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        rbac = RBACService(session)
        has_role = await rbac.user_has_role(user.id, role_code)
        
        if not has_role:
            logger.warning(
                "Role required",
                user_id=str(user.id),
                required_role=role_code,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role_code}",
            )
        
        return user
    
    return dependency


# Convenience dependencies for common cases
RequireAdmin = require_role(RoleCode.ADMIN)
RequireVerifier = require_any_permission(Permission.MAP_VERIFY, Permission.ADMIN_DASHBOARD)
RequireAdminDashboard = require_permission(Permission.ADMIN_DASHBOARD)
RequireJobAdmin = require_permission(Permission.JOB_ADMIN)
