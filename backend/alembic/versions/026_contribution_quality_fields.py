"""Add contribution quality fields.

Revision ID: 026_contribution_quality_fields
Revises: 025_user_settings_model_version
Create Date: 2025-01-18 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "026_contribution_quality_fields"
down_revision = "025_user_settings_model_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add training_weight, has_conflicts, and consensus_count columns."""
    # Add training_weight column with default value
    op.add_column(
        "training_contributions",
        sa.Column("training_weight", sa.Float(), nullable=False, server_default="1.0"),
    )
    
    # Add has_conflicts column with default value
    op.add_column(
        "training_contributions",
        sa.Column("has_conflicts", sa.Boolean(), nullable=False, server_default="false"),
    )
    
    # Add consensus_count column with default value
    op.add_column(
        "training_contributions",
        sa.Column("consensus_count", sa.Integer(), nullable=False, server_default="1"),
    )
    
    # Remove server defaults after column creation (cleaner model)
    op.alter_column("training_contributions", "training_weight", server_default=None)
    op.alter_column("training_contributions", "has_conflicts", server_default=None)
    op.alter_column("training_contributions", "consensus_count", server_default=None)


def downgrade() -> None:
    """Remove training quality columns."""
    op.drop_column("training_contributions", "consensus_count")
    op.drop_column("training_contributions", "has_conflicts")
    op.drop_column("training_contributions", "training_weight")
