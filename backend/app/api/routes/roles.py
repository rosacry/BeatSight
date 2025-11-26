"""
Role management API routes.

Ticket E4-001: RBAC System
- List all roles
- Get user's roles
- Assign role to user (admin only)
- Revoke role from user (admin only)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.logging import get_logger
from app.models.user import User
from app.services.rbac import (
    Permission,
    RBACService,
    RoleCode,
    require_permission,
    EFFECTIVE_PERMISSIONS,
)

router = APIRouter(prefix="/roles", tags=["roles"])
logger = get_logger(__name__)


# =============================================================================
# Response Models
# =============================================================================


class RoleInfo(BaseModel):
    """Information about a role."""

    id: int
    code: str
    description: str | None
    min_karma: int
    requires_phone_verification: bool
    created_at: datetime
    permissions: list[str]

    model_config = {"from_attributes": True}


class UserRoleInfo(BaseModel):
    """User's role assignment info."""

    role_code: str
    assigned_at: datetime


class UserRolesResponse(BaseModel):
    """Response with user's roles and permissions."""

    user_id: uuid.UUID
    roles: list[UserRoleInfo]
    permissions: list[str]


class RoleAssignRequest(BaseModel):
    """Request to assign a role to a user."""

    user_id: uuid.UUID
    role_code: str


class RoleRevokeRequest(BaseModel):
    """Request to revoke a role from a user."""

    user_id: uuid.UUID
    role_code: str


class RoleActionResponse(BaseModel):
    """Response for role assignment/revocation."""

    success: bool
    message: str
    user_id: uuid.UUID
    role_code: str


# =============================================================================
# Endpoints
# =============================================================================


@router.get("", response_model=list[RoleInfo])
async def list_roles(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[RoleInfo]:
    """
    List all available roles.

    Any authenticated user can see the list of roles.
    """
    rbac = RBACService(session)
    roles = await rbac.get_all_roles()

    result = []
    for role in roles:
        permissions = EFFECTIVE_PERMISSIONS.get(role.code, set())
        result.append(
            RoleInfo(
                id=role.id,
                code=role.code,
                description=role.description,
                min_karma=role.min_karma,
                requires_phone_verification=role.requires_phone_verification,
                created_at=role.created_at,
                permissions=[p.value for p in permissions],
            )
        )

    return result


@router.get("/my-roles", response_model=UserRolesResponse)
async def get_my_roles(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> UserRolesResponse:
    """
    Get the current user's roles and permissions.
    """
    rbac = RBACService(session)

    # Get roles with assignment times
    from sqlalchemy import select
    from app.models.role import Role, UserRole

    result = await session.execute(
        select(Role.code, UserRole.assigned_at)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == current_user.id)
    )

    roles = [
        UserRoleInfo(role_code=row[0], assigned_at=row[1]) for row in result.fetchall()
    ]

    permissions = await rbac.get_user_permissions(current_user.id)

    return UserRolesResponse(
        user_id=current_user.id,
        roles=roles,
        permissions=[p.value for p in permissions],
    )


@router.get("/users/{user_id}", response_model=UserRolesResponse)
async def get_user_roles(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_permission(Permission.ROLE_LIST)),
) -> UserRolesResponse:
    """
    Get a specific user's roles and permissions.

    Requires ROLE_LIST permission (admin only).
    """
    rbac = RBACService(session)

    # Verify user exists
    from sqlalchemy import select
    from app.models.role import Role, UserRole

    user_check = await session.execute(select(User).where(User.id == user_id))
    if user_check.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    result = await session.execute(
        select(Role.code, UserRole.assigned_at)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )

    roles = [
        UserRoleInfo(role_code=row[0], assigned_at=row[1]) for row in result.fetchall()
    ]

    permissions = await rbac.get_user_permissions(user_id)

    return UserRolesResponse(
        user_id=user_id,
        roles=roles,
        permissions=[p.value for p in permissions],
    )


@router.post("/assign", response_model=RoleActionResponse)
async def assign_role(
    request: RoleAssignRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_permission(Permission.ROLE_ASSIGN)),
) -> RoleActionResponse:
    """
    Assign a role to a user.

    Requires ROLE_ASSIGN permission (admin only).

    Admins cannot assign the admin role to themselves for safety.
    """
    # Safety check: can't self-assign admin
    if request.user_id == current_user.id and request.role_code == RoleCode.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign admin role to yourself",
        )

    # Verify target user exists
    from sqlalchemy import select

    user_check = await session.execute(select(User).where(User.id == request.user_id))
    if user_check.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    rbac = RBACService(session)

    try:
        await rbac.assign_role(
            user_id=request.user_id,
            role_code=request.role_code,
            assigned_by=current_user.id,
        )
        await session.commit()

        logger.info(
            "Role assigned via API",
            target_user_id=str(request.user_id),
            role=request.role_code,
            assigned_by=str(current_user.id),
        )

        return RoleActionResponse(
            success=True,
            message=f"Role '{request.role_code}' assigned successfully",
            user_id=request.user_id,
            role_code=request.role_code,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/revoke", response_model=RoleActionResponse)
async def revoke_role(
    request: RoleRevokeRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_permission(Permission.ROLE_REVOKE)),
) -> RoleActionResponse:
    """
    Revoke a role from a user.

    Requires ROLE_REVOKE permission (admin only).

    Admins cannot revoke their own admin role for safety.
    Cannot revoke the 'user' role as it's the default.
    """
    # Safety check: can't revoke own admin role
    if request.user_id == current_user.id and request.role_code == RoleCode.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke your own admin role",
        )

    # Safety check: can't revoke the base 'user' role
    if request.role_code == RoleCode.USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke the base 'user' role",
        )

    # Verify target user exists
    from sqlalchemy import select

    user_check = await session.execute(select(User).where(User.id == request.user_id))
    if user_check.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    rbac = RBACService(session)

    try:
        revoked = await rbac.revoke_role(
            user_id=request.user_id,
            role_code=request.role_code,
            revoked_by=current_user.id,
        )

        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User does not have role '{request.role_code}'",
            )

        await session.commit()

        logger.info(
            "Role revoked via API",
            target_user_id=str(request.user_id),
            role=request.role_code,
            revoked_by=str(current_user.id),
        )

        return RoleActionResponse(
            success=True,
            message=f"Role '{request.role_code}' revoked successfully",
            user_id=request.user_id,
            role_code=request.role_code,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/permissions", response_model=list[str])
async def list_permissions(
    current_user: User = Depends(get_current_user),
) -> list[str]:
    """
    List all available permissions in the system.

    Any authenticated user can see the list of permissions.
    """
    return [p.value for p in Permission]


@router.get("/check/{permission}")
async def check_permission(
    permission: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Check if the current user has a specific permission.

    Useful for frontend to determine UI state.
    """
    try:
        perm = Permission(permission)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown permission: {permission}",
        )

    rbac = RBACService(session)
    has_permission = await rbac.user_has_permission(current_user.id, perm)

    return {
        "permission": permission,
        "granted": has_permission,
    }
