"""Update roles schema to match RBAC system.

Revision ID: 010_rbac_schema_update
Revises: 009_webhook_idempotency
Create Date: 2025-12-07

This migration updates the roles and user_roles tables to match the
enhanced RBAC system requirements:
- roles.name -> roles.code
- Add roles.min_karma and roles.requires_phone_verification
- Update role id from UUID to Integer (with data migration)
- Update user_roles foreign keys accordingly
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "010_rbac_schema_update"
down_revision = "009_webhook_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Migrate roles schema to enhanced RBAC system."""
    conn = op.get_bind()

    # Step 1: Create new roles table with correct schema
    op.create_table(
        "roles_new",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(32), unique=True, nullable=False),
        sa.Column("description", sa.String(255)),
        sa.Column(
            "min_karma", sa.Integer, default=0, nullable=False, server_default="0"
        ),
        sa.Column(
            "requires_phone_verification",
            sa.Boolean,
            default=False,
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Step 2: Migrate existing role data (name -> code)
    # Map old UUID IDs to new integer IDs
    conn.execute(
        sa.text("""
        INSERT INTO roles_new (code, description, created_at)
        SELECT name, description, created_at FROM roles
    """)
    )

    # Step 3: Create new user_roles table with correct schema
    op.create_table(
        "user_roles_new",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id",
            sa.Integer,
            sa.ForeignKey("roles_new.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role_new"),
    )

    # Step 4: Migrate user_roles data with ID mapping
    # Join on role name/code to get the new integer ID
    conn.execute(
        sa.text("""
        INSERT INTO user_roles_new (user_id, role_id, assigned_at)
        SELECT ur.user_id, rn.id, COALESCE(ur.assigned_at, NOW())
        FROM user_roles ur
        JOIN roles r ON ur.role_id = r.id
        JOIN roles_new rn ON r.name = rn.code
    """)
    )

    # Step 5: Drop old tables and rename new ones
    op.drop_index("ix_user_roles_user_id", table_name="user_roles", if_exists=True)
    op.drop_index("ix_user_roles_role_id", table_name="user_roles", if_exists=True)
    op.drop_table("user_roles")

    op.drop_index("ix_roles_name", table_name="roles", if_exists=True)
    op.drop_table("roles")

    op.rename_table("roles_new", "roles")
    op.rename_table("user_roles_new", "user_roles")

    # Step 6: Recreate indexes
    op.create_index("ix_roles_code", "roles", ["code"])
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    # Step 7: Ensure standard roles exist
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


def downgrade() -> None:
    """Revert to original UUID-based roles schema."""
    conn = op.get_bind()

    # Create old-style tables
    op.create_table(
        "roles_old",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.String(255)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Migrate data back
    conn.execute(
        sa.text("""
        INSERT INTO roles_old (name, description, created_at)
        SELECT code, description, created_at FROM roles
    """)
    )

    op.create_table(
        "user_roles_old",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles_old.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    conn.execute(
        sa.text("""
        INSERT INTO user_roles_old (user_id, role_id, assigned_at)
        SELECT ur.user_id, ro.id, ur.assigned_at
        FROM user_roles ur
        JOIN roles r ON ur.role_id = r.id
        JOIN roles_old ro ON r.code = ro.name
    """)
    )

    # Swap tables
    op.drop_index("ix_user_roles_user_id", table_name="user_roles", if_exists=True)
    op.drop_index("ix_user_roles_role_id", table_name="user_roles", if_exists=True)
    op.drop_table("user_roles")

    op.drop_index("ix_roles_code", table_name="roles", if_exists=True)
    op.drop_table("roles")

    op.rename_table("roles_old", "roles")
    op.rename_table("user_roles_old", "user_roles")

    op.create_index("ix_roles_name", "roles", ["name"])
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])
