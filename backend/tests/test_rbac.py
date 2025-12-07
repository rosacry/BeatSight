"""
Tests for the RBAC (Role-Based Access Control) system.

Ticket E4-001: RBAC System
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.role import Role, UserRole
from app.services.rbac import (
    Permission,
    RBACService,
    RoleCode,
    EFFECTIVE_PERMISSIONS,
    ROLE_PERMISSIONS,
    ROLE_HIERARCHY,
)


# =============================================================================
# Permission Definition Tests
# =============================================================================


class TestPermissionDefinitions:
    """Tests for permission enum and role mappings."""

    def test_all_permissions_are_strings(self):
        """All permission values should be strings."""
        for perm in Permission:
            assert isinstance(perm.value, str)
            assert ":" in perm.value  # format: resource:action

    def test_permission_count(self):
        """Verify we have a reasonable number of permissions."""
        assert len(Permission) >= 20  # We defined many permissions

    def test_role_permissions_are_valid(self):
        """All permissions in role mappings should be valid Permission enums."""
        for role, perms in ROLE_PERMISSIONS.items():
            for perm in perms:
                assert isinstance(perm, Permission), (
                    f"Invalid permission {perm} in role {role}"
                )

    def test_role_hierarchy_order(self):
        """Role hierarchy should be in ascending privilege order."""
        assert ROLE_HIERARCHY == [
            RoleCode.USER,
            RoleCode.VERIFIER,
            RoleCode.STAFF,
            RoleCode.ADMIN,
        ]

    def test_role_hierarchy_inheritance(self):
        """Higher roles should have all permissions of lower roles."""
        user_perms = EFFECTIVE_PERMISSIONS.get(RoleCode.USER, set())
        verifier_perms = EFFECTIVE_PERMISSIONS.get(RoleCode.VERIFIER, set())
        staff_perms = EFFECTIVE_PERMISSIONS.get(RoleCode.STAFF, set())
        admin_perms = EFFECTIVE_PERMISSIONS.get(RoleCode.ADMIN, set())

        # User should have some permissions
        assert len(user_perms) > 0

        # Verifier should have all user permissions
        assert user_perms.issubset(verifier_perms)

        # Staff should have all verifier permissions
        assert verifier_perms.issubset(staff_perms)

        # Admin should have all staff permissions
        assert staff_perms.issubset(admin_perms)

    def test_admin_has_all_admin_permissions(self):
        """Admin role should have all admin-specific permissions."""
        admin_perms = EFFECTIVE_PERMISSIONS.get(RoleCode.ADMIN, set())

        assert Permission.ADMIN_DASHBOARD in admin_perms
        assert Permission.ADMIN_METRICS in admin_perms
        assert Permission.ADMIN_AUDIT in admin_perms
        assert Permission.ROLE_ASSIGN in admin_perms
        assert Permission.ROLE_REVOKE in admin_perms

    def test_verifier_has_verification_permissions(self):
        """Verifier role should have map verification permissions."""
        verifier_perms = EFFECTIVE_PERMISSIONS.get(RoleCode.VERIFIER, set())

        assert Permission.MAP_VERIFY in verifier_perms
        assert Permission.MAP_REJECT in verifier_perms
        assert Permission.MAP_APPROVE in verifier_perms

    def test_user_has_basic_permissions(self):
        """User role should have basic permissions."""
        user_perms = EFFECTIVE_PERMISSIONS.get(RoleCode.USER, set())

        assert Permission.SONG_CREATE in user_perms
        assert Permission.SONG_READ in user_perms
        assert Permission.JOB_CREATE in user_perms
        assert Permission.JOB_READ in user_perms

    def test_user_does_not_have_admin_permissions(self):
        """User role should NOT have admin permissions."""
        user_perms = EFFECTIVE_PERMISSIONS.get(RoleCode.USER, set())

        assert Permission.ADMIN_DASHBOARD not in user_perms
        assert Permission.ROLE_ASSIGN not in user_perms
        assert Permission.ROLE_REVOKE not in user_perms

    def test_verifier_does_not_have_admin_permissions(self):
        """Verifier role should NOT have admin permissions."""
        verifier_perms = EFFECTIVE_PERMISSIONS.get(RoleCode.VERIFIER, set())

        assert Permission.ADMIN_DASHBOARD not in verifier_perms
        assert Permission.ROLE_ASSIGN not in verifier_perms


class TestRoleCode:
    """Tests for RoleCode enum."""

    def test_role_codes_are_strings(self):
        """Role codes should be strings."""
        assert RoleCode.USER == "user"
        assert RoleCode.VERIFIER == "verifier"
        assert RoleCode.ADMIN == "admin"

    def test_all_role_codes_have_permissions(self):
        """All role codes should have permission mappings."""
        for role in RoleCode:
            assert role in EFFECTIVE_PERMISSIONS


# =============================================================================
# RBAC Service Unit Tests
# =============================================================================


class TestRBACServiceUnit:
    """Unit tests for RBACService with mocked dependencies."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def rbac_service(self, mock_session):
        """Create an RBACService with mocked session."""
        return RBACService(mock_session)

    @pytest.mark.asyncio
    async def test_get_user_roles_returns_role_codes(self, rbac_service, mock_session):
        """get_user_roles should return list of role codes."""
        user_id = uuid.uuid4()

        # Mock the query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("user",), ("verifier",)]
        mock_session.execute.return_value = mock_result

        roles = await rbac_service.get_user_roles(user_id)

        assert roles == ["user", "verifier"]

    @pytest.mark.asyncio
    async def test_get_user_roles_empty(self, rbac_service, mock_session):
        """get_user_roles returns empty list when user has no roles."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        roles = await rbac_service.get_user_roles(user_id)

        assert roles == []

    @pytest.mark.asyncio
    async def test_get_user_permissions_combines_roles(
        self, rbac_service, mock_session
    ):
        """get_user_permissions should combine permissions from all roles."""
        user_id = uuid.uuid4()

        # Mock user having both user and verifier roles
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("user",), ("verifier",)]
        mock_session.execute.return_value = mock_result

        permissions = await rbac_service.get_user_permissions(user_id)

        # Should have user permissions
        assert Permission.SONG_CREATE in permissions
        # Should have verifier permissions
        assert Permission.MAP_VERIFY in permissions

    @pytest.mark.asyncio
    async def test_user_has_permission_true(self, rbac_service, mock_session):
        """user_has_permission returns True when user has the permission."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("admin",)]
        mock_session.execute.return_value = mock_result

        has_perm = await rbac_service.user_has_permission(
            user_id, Permission.ADMIN_DASHBOARD
        )

        assert has_perm is True

    @pytest.mark.asyncio
    async def test_user_has_permission_false(self, rbac_service, mock_session):
        """user_has_permission returns False when user lacks the permission."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("user",)]
        mock_session.execute.return_value = mock_result

        has_perm = await rbac_service.user_has_permission(
            user_id, Permission.ADMIN_DASHBOARD
        )

        assert has_perm is False

    @pytest.mark.asyncio
    async def test_user_has_any_permission_true(self, rbac_service, mock_session):
        """user_has_any_permission returns True when user has at least one."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("user",)]
        mock_session.execute.return_value = mock_result

        has_any = await rbac_service.user_has_any_permission(
            user_id,
            [Permission.SONG_CREATE, Permission.ADMIN_DASHBOARD],
        )

        assert has_any is True

    @pytest.mark.asyncio
    async def test_user_has_any_permission_false(self, rbac_service, mock_session):
        """user_has_any_permission returns False when user has none."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("user",)]
        mock_session.execute.return_value = mock_result

        has_any = await rbac_service.user_has_any_permission(
            user_id,
            [Permission.ADMIN_DASHBOARD, Permission.ROLE_ASSIGN],
        )

        assert has_any is False

    @pytest.mark.asyncio
    async def test_user_has_all_permissions_true(self, rbac_service, mock_session):
        """user_has_all_permissions returns True when user has all."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("user",)]
        mock_session.execute.return_value = mock_result

        has_all = await rbac_service.user_has_all_permissions(
            user_id,
            [Permission.SONG_CREATE, Permission.SONG_READ],
        )

        assert has_all is True

    @pytest.mark.asyncio
    async def test_user_has_all_permissions_false(self, rbac_service, mock_session):
        """user_has_all_permissions returns False when user lacks one."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("user",)]
        mock_session.execute.return_value = mock_result

        has_all = await rbac_service.user_has_all_permissions(
            user_id,
            [Permission.SONG_CREATE, Permission.ADMIN_DASHBOARD],
        )

        assert has_all is False

    @pytest.mark.asyncio
    async def test_user_has_role_true(self, rbac_service, mock_session):
        """user_has_role returns True when user has the role."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("admin",)]
        mock_session.execute.return_value = mock_result

        has_role = await rbac_service.user_has_role(user_id, RoleCode.ADMIN)

        assert has_role is True

    @pytest.mark.asyncio
    async def test_user_has_role_false(self, rbac_service, mock_session):
        """user_has_role returns False when user lacks the role."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("user",)]
        mock_session.execute.return_value = mock_result

        has_role = await rbac_service.user_has_role(user_id, RoleCode.ADMIN)

        assert has_role is False

    @pytest.mark.asyncio
    async def test_user_is_admin(self, rbac_service, mock_session):
        """user_is_admin returns True for admin users."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("admin",)]
        mock_session.execute.return_value = mock_result

        is_admin = await rbac_service.user_is_admin(user_id)

        assert is_admin is True

    @pytest.mark.asyncio
    async def test_user_is_verifier_direct(self, rbac_service, mock_session):
        """user_is_verifier returns True for verifiers."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("verifier",)]
        mock_session.execute.return_value = mock_result

        is_verifier = await rbac_service.user_is_verifier(user_id)

        assert is_verifier is True

    @pytest.mark.asyncio
    async def test_user_is_verifier_as_admin(self, rbac_service, mock_session):
        """user_is_verifier returns True for admins (inherited)."""
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("admin",)]
        mock_session.execute.return_value = mock_result

        is_verifier = await rbac_service.user_is_verifier(user_id)

        assert is_verifier is True


# =============================================================================
# Role Management Tests
# =============================================================================


class TestRoleManagement:
    """Tests for role assignment and revocation."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.delete = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def rbac_service(self, mock_session):
        """Create an RBACService with mocked session."""
        return RBACService(mock_session)

    @pytest.mark.asyncio
    async def test_assign_role_success(self, rbac_service, mock_session):
        """assign_role creates a UserRole record."""
        user_id = uuid.uuid4()

        # Mock role lookup
        mock_role = MagicMock(spec=Role)
        mock_role.id = 1
        mock_role.code = RoleCode.USER

        mock_role_result = MagicMock()
        mock_role_result.scalar_one_or_none.return_value = mock_role

        # Mock existing role check (no existing role)
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [mock_role_result, mock_existing_result]

        user_role = await rbac_service.assign_role(user_id, RoleCode.USER)

        assert user_role is not None
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_assign_role_nonexistent(self, rbac_service, mock_session):
        """assign_role raises error for nonexistent role."""
        user_id = uuid.uuid4()

        # Mock role not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="does not exist"):
            await rbac_service.assign_role(user_id, "nonexistent")

    @pytest.mark.asyncio
    async def test_assign_role_duplicate(self, rbac_service, mock_session):
        """assign_role raises error if user already has role."""
        user_id = uuid.uuid4()

        # Mock role exists
        mock_role = MagicMock(spec=Role)
        mock_role.id = 1

        mock_role_result = MagicMock()
        mock_role_result.scalar_one_or_none.return_value = mock_role

        # Mock existing user_role found
        mock_existing = MagicMock(spec=UserRole)
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = mock_existing

        mock_session.execute.side_effect = [mock_role_result, mock_existing_result]

        with pytest.raises(ValueError, match="already has role"):
            await rbac_service.assign_role(user_id, RoleCode.USER)

    @pytest.mark.asyncio
    async def test_revoke_role_success(self, rbac_service, mock_session):
        """revoke_role removes the UserRole record."""
        user_id = uuid.uuid4()

        # Mock role exists
        mock_role = MagicMock(spec=Role)
        mock_role.id = 1

        mock_role_result = MagicMock()
        mock_role_result.scalar_one_or_none.return_value = mock_role

        # Mock existing user_role found
        mock_user_role = MagicMock(spec=UserRole)
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = mock_user_role

        mock_session.execute.side_effect = [mock_role_result, mock_existing_result]

        revoked = await rbac_service.revoke_role(user_id, RoleCode.USER)

        assert revoked is True
        mock_session.delete.assert_called_once_with(mock_user_role)
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_role_not_assigned(self, rbac_service, mock_session):
        """revoke_role returns False if user doesn't have role."""
        user_id = uuid.uuid4()

        # Mock role exists
        mock_role = MagicMock(spec=Role)
        mock_role.id = 1

        mock_role_result = MagicMock()
        mock_role_result.scalar_one_or_none.return_value = mock_role

        # Mock no existing user_role
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [mock_role_result, mock_existing_result]

        revoked = await rbac_service.revoke_role(user_id, RoleCode.USER)

        assert revoked is False

    @pytest.mark.asyncio
    async def test_revoke_role_nonexistent(self, rbac_service, mock_session):
        """revoke_role raises error for nonexistent role."""
        user_id = uuid.uuid4()

        # Mock role not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError, match="does not exist"):
            await rbac_service.revoke_role(user_id, "nonexistent")

    @pytest.mark.asyncio
    async def test_get_all_roles(self, rbac_service, mock_session):
        """get_all_roles returns all roles."""
        mock_roles = [
            MagicMock(code=RoleCode.USER),
            MagicMock(code=RoleCode.VERIFIER),
            MagicMock(code=RoleCode.ADMIN),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_roles
        mock_session.execute.return_value = mock_result

        roles = await rbac_service.get_all_roles()

        assert len(roles) == 3

    @pytest.mark.asyncio
    async def test_get_role_by_code(self, rbac_service, mock_session):
        """get_role_by_code returns the role."""
        mock_role = MagicMock(spec=Role)
        mock_role.code = RoleCode.ADMIN

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_role
        mock_session.execute.return_value = mock_result

        role = await rbac_service.get_role_by_code(RoleCode.ADMIN)

        assert role is not None
        assert role.code == RoleCode.ADMIN


# =============================================================================
# Permission String Tests
# =============================================================================


class TestPermissionStrings:
    """Tests for permission string formats."""

    def test_user_permissions_format(self):
        """User-related permissions follow naming convention."""
        assert Permission.USER_READ.value == "user:read"
        assert Permission.USER_UPDATE.value == "user:update"
        assert Permission.USER_DELETE.value == "user:delete"
        assert Permission.USER_LIST.value == "user:list"

    def test_role_permissions_format(self):
        """Role-related permissions follow naming convention."""
        assert Permission.ROLE_ASSIGN.value == "role:assign"
        assert Permission.ROLE_REVOKE.value == "role:revoke"
        assert Permission.ROLE_LIST.value == "role:list"

    def test_song_permissions_format(self):
        """Song-related permissions follow naming convention."""
        assert Permission.SONG_CREATE.value == "song:create"
        assert Permission.SONG_READ.value == "song:read"
        assert Permission.SONG_UPDATE.value == "song:update"
        assert Permission.SONG_DELETE.value == "song:delete"

    def test_job_permissions_format(self):
        """Job-related permissions follow naming convention."""
        assert Permission.JOB_CREATE.value == "job:create"
        assert Permission.JOB_READ.value == "job:read"
        assert Permission.JOB_CANCEL.value == "job:cancel"
        assert Permission.JOB_ADMIN.value == "job:admin"

    def test_admin_permissions_format(self):
        """Admin-related permissions follow naming convention."""
        assert Permission.ADMIN_DASHBOARD.value == "admin:dashboard"
        assert Permission.ADMIN_METRICS.value == "admin:metrics"
        assert Permission.ADMIN_AUDIT.value == "admin:audit"
        assert Permission.ADMIN_SYSTEM.value == "admin:system"
