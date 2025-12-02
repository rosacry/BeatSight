"""Tests for role management API routes.

These tests validate role listing, assignment, revocation, and permission checks.
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


class TestListRoles:
    """Tests for GET /roles endpoint."""

    @patch("app.api.routes.roles.RBACService")
    def test_list_roles_success(
        self,
        mock_rbac_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test listing all roles."""
        # Create mock roles
        mock_role1 = MagicMock()
        mock_role1.id = 1
        mock_role1.code = "user"
        mock_role1.description = "Basic user role"
        mock_role1.min_karma = 0
        mock_role1.requires_phone_verification = False
        mock_role1.created_at = datetime.now(timezone.utc)

        mock_role2 = MagicMock()
        mock_role2.id = 2
        mock_role2.code = "mapper"
        mock_role2.description = "Beatmap creator"
        mock_role2.min_karma = 100
        mock_role2.requires_phone_verification = False
        mock_role2.created_at = datetime.now(timezone.utc)

        mock_rbac_instance = MagicMock()
        mock_rbac_instance.get_all_roles = AsyncMock(return_value=[mock_role1, mock_role2])
        mock_rbac_class.return_value = mock_rbac_instance

        response = client_authenticated.get("/api/roles")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["code"] == "user"
        assert data[1]["code"] == "mapper"

    @patch("app.api.routes.roles.RBACService")
    def test_list_roles_empty(
        self,
        mock_rbac_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test listing roles when none exist."""
        mock_rbac_instance = MagicMock()
        mock_rbac_instance.get_all_roles = AsyncMock(return_value=[])
        mock_rbac_class.return_value = mock_rbac_instance

        response = client_authenticated.get("/api/roles")

        assert response.status_code == 200
        assert response.json() == []


class TestGetMyRoles:
    """Tests for GET /roles/my-roles endpoint."""

    @patch("app.api.routes.roles.RBACService")
    def test_get_my_roles_success(
        self,
        mock_rbac_class: MagicMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test getting current user's roles."""
        # Set up mock session result for the role query
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("user", datetime.now(timezone.utc)),
            ("mapper", datetime.now(timezone.utc)),
        ]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_rbac_instance = MagicMock()
        mock_rbac_instance.get_user_permissions = AsyncMock(
            return_value={Permission.SONG_READ, Permission.SONG_CREATE}
        )
        mock_rbac_class.return_value = mock_rbac_instance

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.get("/api/roles/my-roles")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert str(data["user_id"]) == str(mock_user.id)
        assert len(data["roles"]) == 2
        assert len(data["permissions"]) == 2


class TestGetUserRoles:
    """Tests for GET /roles/users/{user_id} endpoint."""

    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_get_user_roles_without_permission(
        self,
        mock_has_permission: AsyncMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test getting user roles without proper permission."""
        # Mock RBAC to deny permission
        mock_has_permission.return_value = False

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        target_user_id = uuid.uuid4()
        response = client.get(f"/api/roles/users/{target_user_id}")

        app.dependency_overrides.clear()

        assert response.status_code == 403


class TestAssignRole:
    """Tests for POST /roles/assign endpoint."""

    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_assign_role_without_permission(
        self,
        mock_has_permission: AsyncMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test role assignment without proper permission."""
        mock_has_permission.return_value = False

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/roles/assign",
            json={
                "user_id": str(uuid.uuid4()),
                "role_code": "mapper",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 403

    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_assign_admin_to_self_fails(
        self,
        mock_has_permission: AsyncMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that admins cannot assign admin role to themselves."""
        mock_has_permission.return_value = True

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/roles/assign",
            json={
                "user_id": str(mock_user.id),  # Same as current user
                "role_code": "admin",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 400
        assert "Cannot assign admin role to yourself" in response.json()["detail"]

    @patch("app.api.routes.roles.RBACService")
    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_assign_role_user_not_found(
        self,
        mock_has_permission: AsyncMock,
        mock_route_rbac_class: MagicMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test assigning role to non-existent user."""
        # Mock permission check passes
        mock_has_permission.return_value = True

        # Mock user not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/roles/assign",
            json={
                "user_id": str(uuid.uuid4()),
                "role_code": "mapper",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    @patch("app.api.routes.roles.RBACService")
    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_assign_role_success(
        self,
        mock_has_permission: AsyncMock,
        mock_route_rbac_class: MagicMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test successful role assignment."""
        # Mock permission check passes
        mock_has_permission.return_value = True

        # Mock user exists
        target_user = MagicMock(spec=User)
        target_user.id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = target_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Mock route RBAC service
        mock_route_rbac_instance = MagicMock()
        mock_route_rbac_instance.assign_role = AsyncMock()
        mock_route_rbac_class.return_value = mock_route_rbac_instance

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
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

    @patch("app.api.routes.roles.RBACService")
    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_assign_role_invalid_role(
        self,
        mock_has_permission: AsyncMock,
        mock_route_rbac_class: MagicMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test assigning an invalid role."""
        # Mock permission check passes
        mock_has_permission.return_value = True

        # Mock user exists
        target_user = MagicMock(spec=User)
        target_user.id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = target_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Mock route RBAC to raise ValueError for invalid role
        mock_route_rbac_instance = MagicMock()
        mock_route_rbac_instance.assign_role = AsyncMock(side_effect=ValueError("Invalid role"))
        mock_route_rbac_class.return_value = mock_route_rbac_instance

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/roles/assign",
            json={
                "user_id": str(target_user.id),
                "role_code": "invalid_role",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 400


class TestRevokeRole:
    """Tests for POST /roles/revoke endpoint."""

    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_revoke_role_without_permission(
        self,
        mock_has_permission: AsyncMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test role revocation without proper permission."""
        mock_has_permission.return_value = False

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/roles/revoke",
            json={
                "user_id": str(uuid.uuid4()),
                "role_code": "mapper",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 403

    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_revoke_own_admin_fails(
        self,
        mock_has_permission: AsyncMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that admins cannot revoke their own admin role."""
        mock_has_permission.return_value = True

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/roles/revoke",
            json={
                "user_id": str(mock_user.id),
                "role_code": "admin",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 400
        assert "Cannot revoke your own admin role" in response.json()["detail"]

    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_revoke_user_role_fails(
        self,
        mock_has_permission: AsyncMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test that base 'user' role cannot be revoked."""
        mock_has_permission.return_value = True

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/roles/revoke",
            json={
                "user_id": str(uuid.uuid4()),
                "role_code": "user",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 400
        assert "Cannot revoke the base 'user' role" in response.json()["detail"]

    @patch("app.api.routes.roles.RBACService")
    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_revoke_role_user_not_found(
        self,
        mock_has_permission: AsyncMock,
        mock_route_rbac_class: MagicMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test revoking role from non-existent user."""
        mock_has_permission.return_value = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/roles/revoke",
            json={
                "user_id": str(uuid.uuid4()),
                "role_code": "mapper",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    @patch("app.api.routes.roles.RBACService")
    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_revoke_role_success(
        self,
        mock_has_permission: AsyncMock,
        mock_route_rbac_class: MagicMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test successful role revocation."""
        mock_has_permission.return_value = True

        # Mock user exists
        target_user = MagicMock(spec=User)
        target_user.id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = target_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_route_rbac_instance = MagicMock()
        mock_route_rbac_instance.revoke_role = AsyncMock(return_value=True)
        mock_route_rbac_class.return_value = mock_route_rbac_instance

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/roles/revoke",
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

    @patch("app.api.routes.roles.RBACService")
    @patch("app.services.rbac.RBACService.user_has_permission")
    def test_revoke_role_user_doesnt_have_role(
        self,
        mock_has_permission: AsyncMock,
        mock_route_rbac_class: MagicMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test revoking role user doesn't have."""
        mock_has_permission.return_value = True

        # Mock user exists
        target_user = MagicMock(spec=User)
        target_user.id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = target_user
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mock_route_rbac_instance = MagicMock()
        mock_route_rbac_instance.revoke_role = AsyncMock(return_value=False)  # User didn't have role
        mock_route_rbac_class.return_value = mock_route_rbac_instance

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/roles/revoke",
            json={
                "user_id": str(target_user.id),
                "role_code": "mapper",
            },
        )

        app.dependency_overrides.clear()

        assert response.status_code == 400
        assert "does not have role" in response.json()["detail"]


class TestListPermissions:
    """Tests for GET /roles/permissions endpoint."""

    def test_list_permissions_success(
        self,
        client_authenticated: TestClient,
    ) -> None:
        """Test listing all permissions."""
        response = client_authenticated.get("/api/roles/permissions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Check some expected permissions exist
        assert "user:read" in data
        assert "role:assign" in data


class TestCheckPermission:
    """Tests for GET /roles/check/{permission} endpoint."""

    @patch("app.api.routes.roles.RBACService")
    def test_check_permission_granted(
        self,
        mock_rbac_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test checking a permission the user has."""
        mock_rbac_instance = MagicMock()
        mock_rbac_instance.user_has_permission = AsyncMock(return_value=True)
        mock_rbac_class.return_value = mock_rbac_instance

        response = client_authenticated.get("/api/roles/check/user:read")

        assert response.status_code == 200
        data = response.json()
        assert data["permission"] == "user:read"
        assert data["granted"] is True

    @patch("app.api.routes.roles.RBACService")
    def test_check_permission_denied(
        self,
        mock_rbac_class: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test checking a permission the user doesn't have."""
        mock_rbac_instance = MagicMock()
        mock_rbac_instance.user_has_permission = AsyncMock(return_value=False)
        mock_rbac_class.return_value = mock_rbac_instance

        response = client_authenticated.get("/api/roles/check/admin:system")

        assert response.status_code == 200
        data = response.json()
        assert data["permission"] == "admin:system"
        assert data["granted"] is False

    def test_check_permission_invalid(
        self,
        client_authenticated: TestClient,
    ) -> None:
        """Test checking an invalid permission."""
        response = client_authenticated.get("/api/roles/check/invalid:permission")

        assert response.status_code == 400
        assert "Unknown permission" in response.json()["detail"]
