"""Add user friendships and subscriptions tables for social features.

Revision ID: 034_friends_subs
Revises: 033_user_banner
Create Date: 2025-12-12

Adds:
- user_friendships table for osu!-style friend system (with mutual friends)
- user_subscriptions table for bell notifications on beatmap uploads
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '034_friends_subs'
down_revision = '033_user_banner'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create user_friendships and user_subscriptions tables."""
    # User Friendships table (osu!-style with mutual friends)
    op.create_table(
        'user_friendships',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('friend_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Unique constraint to prevent duplicate friendships
    op.create_index(
        'ix_user_friendships_user_friend',
        'user_friendships',
        ['user_id', 'friend_id'],
        unique=True,
    )
    
    # Index for looking up who follows a user (for mutual friend detection)
    op.create_index(
        'ix_user_friendships_friend_user',
        'user_friendships',
        ['friend_id', 'user_id'],
    )

    # User Subscriptions table (bell notifications)
    op.create_table(
        'user_subscriptions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('subscriber_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('notify_on_map_upload', sa.Boolean(), default=True, nullable=False),
        sa.Column('notify_on_map_ranked', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Unique constraint to prevent duplicate subscriptions
    op.create_index(
        'ix_user_subscriptions_subscriber_target',
        'user_subscriptions',
        ['subscriber_id', 'target_user_id'],
        unique=True,
    )
    
    # Index for looking up subscribers (for sending notifications)
    op.create_index(
        'ix_user_subscriptions_target_notify',
        'user_subscriptions',
        ['target_user_id', 'notify_on_map_upload'],
    )


def downgrade() -> None:
    """Drop user_friendships and user_subscriptions tables."""
    op.drop_index('ix_user_subscriptions_target_notify', table_name='user_subscriptions')
    op.drop_index('ix_user_subscriptions_subscriber_target', table_name='user_subscriptions')
    op.drop_table('user_subscriptions')
    
    op.drop_index('ix_user_friendships_friend_user', table_name='user_friendships')
    op.drop_index('ix_user_friendships_user_friend', table_name='user_friendships')
    op.drop_table('user_friendships')
