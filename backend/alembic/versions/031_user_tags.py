"""Add user_tags table for custom profile badges

Revision ID: 031_user_tags
Revises: 030_user_number
Create Date: 2025-12-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '031_user_tags'
down_revision = '030_user_number'
branch_labels = None
depends_on = None


def upgrade():
    # Create user_tags table for custom profile tags (like osu!'s DEV, VIP, etc.)
    op.create_table(
        'user_tags',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(32), nullable=False),
        sa.Column('background_color', sa.String(16), nullable=False, server_default='#3b82f6'),
        sa.Column('text_color', sa.String(16), nullable=True),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for efficient user tag lookups
    op.create_index('ix_user_tags_user_id', 'user_tags', ['user_id'])


def downgrade():
    op.drop_index('ix_user_tags_user_id', table_name='user_tags')
    op.drop_table('user_tags')
