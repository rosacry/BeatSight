"""Add user_number field for human-friendly user IDs like osu!

Revision ID: 030_user_number
Revises: 029_social_features
Create Date: 2025-12-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '030_user_number'
down_revision = '029_social_features'
branch_labels = None
depends_on = None


def upgrade():
    # Create sequence for user numbers starting at 1 (like osu! - represents x-th account created)
    op.execute('CREATE SEQUENCE IF NOT EXISTS user_number_seq START WITH 1')
    
    # Add user_number column
    op.add_column('users', sa.Column('user_number', sa.Integer(), nullable=True))
    
    # Populate existing users with sequential numbers based on created_at order
    op.execute("""
        UPDATE users 
        SET user_number = nextval('user_number_seq')
        WHERE user_number IS NULL
    """)
    
    # Make the column non-nullable after population
    op.alter_column('users', 'user_number', nullable=False)
    
    # Create unique index
    op.create_index('ix_users_user_number', 'users', ['user_number'], unique=True)
    
    # Set default for new users to use the sequence
    op.execute("ALTER TABLE users ALTER COLUMN user_number SET DEFAULT nextval('user_number_seq')")


def downgrade():
    op.drop_index('ix_users_user_number', table_name='users')
    op.drop_column('users', 'user_number')
    op.execute('DROP SEQUENCE IF EXISTS user_number_seq')
