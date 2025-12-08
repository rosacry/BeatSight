"""Add staff role and grant admin to initial user.

Revision ID: 014_add_staff_role_and_admin_user
Revises: 013_fix_credit_balances_columns
Create Date: 2025-12-08

This migration:
1. Ensures the staff role exists
2. Ensures the admin role exists
3. Grants admin role to the initial admin user (10rosachri@gmail.com)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "014_add_staff_role_and_admin_user"
down_revision = "013_fix_credit_balances_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add staff role and grant admin to initial user."""
    conn = op.get_bind()

    # Step 1: Ensure staff role exists
    conn.execute(
        sa.text("""
        INSERT INTO roles (code, description, min_karma, requires_phone_verification)
        VALUES ('staff', 'Staff role with admin dashboard access', 0, false)
        ON CONFLICT (code) DO NOTHING
    """)
    )

    # Step 2: Ensure all standard roles exist
    conn.execute(
        sa.text("""
        INSERT INTO roles (code, description, min_karma, requires_phone_verification)
        VALUES 
            ('user', 'Standard user role', 0, false),
            ('verifier', 'Map verifier role', 100, false),
            ('admin', 'Administrator role', 0, false)
        ON CONFLICT (code) DO NOTHING
    """)
    )

    # Step 3: Grant admin role to the initial admin user
    # First get the user_id and role_id
    conn.execute(
        sa.text("""
        INSERT INTO user_roles (user_id, role_id)
        SELECT u.id, r.id
        FROM users u, roles r
        WHERE u.email = '10rosachri@gmail.com' AND r.code = 'admin'
        ON CONFLICT DO NOTHING
    """)
    )

    # Step 4: Also grant user role (base role)
    conn.execute(
        sa.text("""
        INSERT INTO user_roles (user_id, role_id)
        SELECT u.id, r.id
        FROM users u, roles r
        WHERE u.email = '10rosachri@gmail.com' AND r.code = 'user'
        ON CONFLICT DO NOTHING
    """)
    )


def downgrade() -> None:
    """Remove admin role from initial user (staff role remains)."""
    conn = op.get_bind()

    # Remove admin role from the initial user
    conn.execute(
        sa.text("""
        DELETE FROM user_roles
        WHERE user_id = (SELECT id FROM users WHERE email = '10rosachri@gmail.com')
        AND role_id = (SELECT id FROM roles WHERE code = 'admin')
    """)
    )
