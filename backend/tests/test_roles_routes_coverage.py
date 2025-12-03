"""Extended tests for roles API routes - Coverage expansion.

These tests add coverage for edge cases and less-tested code paths.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db_session
from app.main import app
from app.models.user import User
from app.services.rbac import Permission


@pytest.fixture
def mock_user() -> User:
    """Create a mock authenticated user."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.is_active = True
    return user


@pytest.fixture
def mock_admin_user() -> User:
    """Create a mock admin user."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "admin@example.com"
    user.display_name = "Admin User"
    user.is_active = True
    return user


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def client_authenticated(mock_user: User, mock_db_session: AsyncMock) -> TestClient:
    """Create a test client with basic authentication."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestListRolesEdgeCases:
    """Edge case tests for GET /roles endpoint."""

    @patch("app.api.routes.roles.RBACService")
    @patch("app.api.routes.roles.EFFECTIVE_PERMISSIONS", {"user": {Permission.SONG_READ}})
    def test_list_roles_with_permissions(
        self,
        mock_rbac_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test listing roles includes permissions."""
        mock_role = MagicMock()
        mock_role.id = 1
        mock_role.code = "user"
        mock_role.description = "Basic user role"
        mock_role.min_karma = 0
        mock_role.requires_phone_verification = False
        mock_role.created_at = datetime.now(timezone.utc)

        mock_rbac_instance = MagicMock()
        mock_rbac_instance.get_all_roles = AsyncMock(return_value=[mock_role])
        mock_rbac_class.return_value = mock_rbac_instance

        response = client_authenticated.get("/api/roles")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "permissions" in data[0]

    @patch("app.api.routes.roles.RBACService")
    def test_list_roles_with_multiple_permissions(
        self,
        mock_rbac_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test listing roles with multiple permission sets."""
        mock_role1 = MagicMock()
        mock_role1.id = 1
        mock_role1.code = "user"
        mock_role1.description = "Basic user"
        mock_role1.min_karma = 0
        mock_role1.requires_phone_verification = False
        mock_role1.created_at = datetime.now(timezone.utc)

        mock_role2 = MagicMock()
        mock_role2.id = 2
        mock_role2.code = "admin"
        mock_role2.description = "Administrator"
        mock_role2.min_karma = 1000
        mock_role2.requires_phone_verification = True
        mock_role2.created_at = datetime.now(timezone.utc)

        mock_rbac_instance = MagicMock()
        mock_rbac_instance.get_all_roles = AsyncMock(
            return_value=[mock_role1, mock_role2]
        )
        mock_rbac_class.return_value = mock_rbac_instance

        response = client_authenticated.get("/api/roles")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestGetMyRolesEdgeCases:
    """Edge case tests for GET /roles/my-roles endpoint."""

    @patch("app.api.routes.roles.RBACService")
    def test_get_my_roles_no_roles(
        self,
        mock_rbac_class: MagicMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test getting roles when user has none."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_rbac_instance = MagicMock()
        mock_rbac_instance.get_user_permissions = AsyncMock(return_value=set())
        mock_rbac_class.return_value = mock_rbac_instance

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.get("/api/roles/my-roles")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert len(data["roles"]) == 0
        assert len(data["permissions"]) == 0

    @patch("app.api.routes.roles.RBACService")
    def test_get_my_roles_multiple_permissions(
        self,
        mock_rbac_class: MagicMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test getting roles with multiple permissions."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("user", datetime.now(timezone.utc)),
            ("mapper", datetime.now(timezone.utc)),
            ("verifier", datetime.now(timezone.utc)),
        ]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_rbac_instance = MagicMock()
        mock_rbac_instance.get_user_permissions = AsyncMock(
            return_value={
                Permission.SONG_READ,
                Permission.SONG_CREATE,
                Permission.JOB_CREATE,
                Permission.MAP_VERIFY,
            }
        )
        mock_rbac_class.return_value = mock_rbac_instance

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.get("/api/roles/my-roles")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert len(data["roles"]) == 3
        assert len(data["permissions"]) == 4


class TestGetUserRolesEdgeCases:
    """Edge case tests for GET /roles/users/{user_id} endpoint."""

    @patch("app.api.routes.roles.RBACService")
    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_get_user_roles_success(
        self,
        mock_has_permission: AsyncMock,
        mock_route_rbac_class: MagicMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test successfully getting another user's roles."""
        mock_has_permission.return_value = True

        target_user_id = uuid.uuid4()

        # First query: check user exists
        mock_user_check = MagicMock()
        mock_user_check.scalar_one_or_none.return_value = MagicMock(spec=User)

        # Second query: get user roles
        mock_roles_result = MagicMock()
        mock_roles_result.fetchall.return_value = [
            ("user", datetime.now(timezone.utc)),
        ]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_user_check, mock_roles_result]
        )

        mock_route_rbac_instance = MagicMock()
        mock_route_rbac_instance.get_user_permissions = AsyncMock(
            return_value={Permission.SONG_READ}
        )
        mock_route_rbac_class.return_value = mock_route_rbac_instance

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.get(f"/api/roles/users/{target_user_id}")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert str(data["user_id"]) == str(target_user_id)


class TestAssignRoleEdgeCases:
    """Edge case tests for POST /roles/assign endpoint."""

    @patch("app.api.routes.roles.RBACService")
    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_assign_different_role_to_self(
        self,
        mock_has_permission: AsyncMock,
        mock_route_rbac_class: MagicMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test assigning non-admin role to self (should work)."""
        mock_has_permission.return_value = True

        # Mock user exists (self)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_route_rbac_instance = MagicMock()
        mock_route_rbac_instance.assign_role = AsyncMock()
        mock_route_rbac_class.return_value = mock_route_rbac_instance

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/roles/assign",
            json={
                "user_id": str(mock_user.id),  # Same as current user
                "role_code": "mapper",  # Not admin, should be allowed
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestRevokeRoleEdgeCases:
    """Edge case tests for POST /roles/revoke endpoint."""

    @patch("app.api.routes.roles.RBACService")
    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_revoke_role_error_from_service(
        self,
        mock_has_permission: AsyncMock,
        mock_route_rbac_class: MagicMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test revoke role when service raises ValueError."""
        mock_has_permission.return_value = True

        target_user = MagicMock(spec=User)
        target_user.id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = target_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_route_rbac_instance = MagicMock()
        mock_route_rbac_instance.revoke_role = AsyncMock(
            side_effect=ValueError("Invalid role code")
        )
        mock_route_rbac_class.return_value = mock_route_rbac_instance

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/roles/revoke",
            json={
                "user_id": str(target_user.id),
                "role_code": "invalid_role",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 400


class TestListPermissionsEdgeCases:
    """Edge case tests for GET /roles/permissions endpoint."""

    def test_list_permissions_returns_all(
        self,
        client_authenticated: TestClient,
    ) -> None:
        """Test that all permissions are returned."""
        response = client_authenticated.get("/api/roles/permissions")

        assert response.status_code == 200
        data = response.json()

        # Verify it's a list of strings
        assert isinstance(data, list)
        for perm in data:
            assert isinstance(perm, str)

        # Should have multiple permissions
        assert len(data) > 5


class TestCheckPermissionEdgeCases:
    """Edge case tests for GET /roles/check/{permission} endpoint."""

    @patch("app.api.routes.roles.RBACService")
    def test_check_permission_with_colon_in_name(
        self,
        mock_rbac_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test checking permission with colon-separated name."""
        mock_rbac_instance = MagicMock()
        mock_rbac_instance.user_has_permission = AsyncMock(return_value=True)
        mock_rbac_class.return_value = mock_rbac_instance

        response = client_authenticated.get("/api/roles/check/song:create")

        assert response.status_code == 200
        data = response.json()
        assert data["permission"] == "song:create"
        assert data["granted"] is True

    @patch("app.api.routes.roles.RBACService")
    def test_check_admin_permission(
        self,
        mock_rbac_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test checking admin-level permission."""
        mock_rbac_instance = MagicMock()
        mock_rbac_instance.user_has_permission = AsyncMock(return_value=False)
        mock_rbac_class.return_value = mock_rbac_instance

        response = client_authenticated.get("/api/roles/check/admin:system")

        assert response.status_code == 200
        data = response.json()
        assert data["permission"] == "admin:system"
        assert data["granted"] is False

    def test_check_permission_empty_string(
        self,
        client_authenticated: TestClient,
    ) -> None:
        """Test checking empty permission string."""
        response = client_authenticated.get("/api/roles/check/")

        # Should return 404 (no route matches) or 400
        assert response.status_code in [400, 404, 405]


class TestRoleAssignmentIntegration:
    """Integration-style tests for role assignment workflows."""

    @patch("app.api.routes.roles.RBACService")
    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_assign_and_verify_role(
        self,
        mock_has_permission: AsyncMock,
        mock_route_rbac_class: MagicMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test assigning role and then checking permissions."""
        mock_has_permission.return_value = True

        target_user = MagicMock(spec=User)
        target_user.id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = target_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_route_rbac_instance = MagicMock()
        mock_route_rbac_instance.assign_role = AsyncMock()
        mock_route_rbac_class.return_value = mock_route_rbac_instance

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)

        # Assign mapper role
        response = client.post(
            "/api/roles/assign",
            json={
                "user_id": str(target_user.id),
                "role_code": "mapper",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["role_code"] == "mapper"

        # Verify assign_role was called with correct params
        mock_route_rbac_instance.assign_role.assert_called_once()
        call_kwargs = mock_route_rbac_instance.assign_role.call_args.kwargs
        assert call_kwargs["user_id"] == target_user.id
        assert call_kwargs["role_code"] == "mapper"
        assert call_kwargs["assigned_by"] == mock_user.id
