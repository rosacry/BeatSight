"""Add Two-Factor Authentication fields to users table.

Revision ID: 011_two_factor_auth
Revises: 010_rbac_schema_update
Create Date: 2025-01-20 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "011_two_factor_auth"
down_revision = "010_rbac_schema_update"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add 2FA fields to users table."""
    op.add_column(
        "users",
        sa.Column("totp_secret", sa.String(64), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("totp_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("totp_backup_codes", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove 2FA fields from users table."""
    op.drop_column("users", "totp_enabled_at")
    op.drop_column("users", "totp_backup_codes")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret")
