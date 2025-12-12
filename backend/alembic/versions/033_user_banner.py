"""Add user banner_url column

Revision ID: 033_user_banner
Revises: 032_karma_score_achieved_at
Create Date: 2025-12-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '033_user_banner'
down_revision = '032_karma_score_achieved_at'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add banner_url column to users table."""
    op.add_column(
        'users',
        sa.Column('banner_url', sa.String(512), nullable=True)
    )


def downgrade() -> None:
    """Remove banner_url column from users table."""
    op.drop_column('users', 'banner_url')
