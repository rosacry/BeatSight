"""Add session verification tables for osu-style sensitive action verification

Revision ID: 035_session_verification
Revises: 034_friends_subs
Create Date: 2024-12-13 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '035_session_verification'
down_revision = '034_friends_subs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create session_verifications table
    op.create_table(
        'session_verifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_token', sa.String(255), nullable=False),
        sa.Column('verification_code', sa.String(16), nullable=True),
        sa.Column('link_key', sa.String(128), nullable=True),
        sa.Column('is_verified', sa.Boolean(), default=False, nullable=False),
        sa.Column('code_issued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_attempts', sa.Integer(), default=0, nullable=False),
        sa.Column('request_country', sa.String(64), nullable=True),
        sa.Column('request_ip', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for session_verifications
    op.create_index('ix_session_verifications_user_id', 'session_verifications', ['user_id'])
    op.create_index('ix_session_verifications_session_token', 'session_verifications', ['session_token'])
    op.create_index('ix_session_verifications_link_key', 'session_verifications', ['link_key'])
    op.create_index('ix_session_verifications_verification_code', 'session_verifications', ['verification_code'])
    
    # Create sensitive_action_logs table for audit
    op.create_table(
        'sensitive_action_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action_type', sa.String(64), nullable=False),
        sa.Column('action_details', sa.Text(), nullable=True),
        sa.Column('verification_required', sa.Boolean(), default=False, nullable=False),
        sa.Column('verification_method', sa.String(32), nullable=True),
        sa.Column('ip_address', sa.String(64), nullable=True),
        sa.Column('country', sa.String(64), nullable=True),
        sa.Column('user_agent', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for sensitive_action_logs
    op.create_index('ix_sensitive_action_logs_user_id', 'sensitive_action_logs', ['user_id'])
    op.create_index('ix_sensitive_action_logs_action_type', 'sensitive_action_logs', ['action_type'])
    op.create_index('ix_sensitive_action_logs_created_at', 'sensitive_action_logs', ['created_at'])


def downgrade() -> None:
    # Drop indexes and tables
    op.drop_index('ix_sensitive_action_logs_created_at', table_name='sensitive_action_logs')
    op.drop_index('ix_sensitive_action_logs_action_type', table_name='sensitive_action_logs')
    op.drop_index('ix_sensitive_action_logs_user_id', table_name='sensitive_action_logs')
    op.drop_table('sensitive_action_logs')
    
    op.drop_index('ix_session_verifications_verification_code', table_name='session_verifications')
    op.drop_index('ix_session_verifications_link_key', table_name='session_verifications')
    op.drop_index('ix_session_verifications_session_token', table_name='session_verifications')
    op.drop_index('ix_session_verifications_user_id', table_name='session_verifications')
    op.drop_table('session_verifications')
