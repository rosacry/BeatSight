"""Add contribution batch impact table

Revision ID: 007_contribution_batch_impact
Revises: 006_training_contributions
Create Date: 2025-12-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "007_contribution_batch_impact"
down_revision = "006_training_contributions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create contribution_batch_impacts table for tracking training impact."""
    op.create_table(
        "contribution_batch_impacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "batch_id",
            sa.String(50),
            nullable=False,
            unique=True,
            index=True,
            comment="Unique identifier for the training batch (from manifest)",
        ),
        sa.Column(
            "model_checkpoint",
            sa.String(255),
            nullable=False,
            comment="Model checkpoint path or identifier after training",
        ),
        sa.Column(
            "baseline_accuracy",
            sa.Float(),
            nullable=False,
            comment="Model accuracy before training on this batch",
        ),
        sa.Column(
            "post_training_accuracy",
            sa.Float(),
            nullable=False,
            comment="Model accuracy after training on this batch",
        ),
        sa.Column(
            "baseline_f1_macro",
            sa.Float(),
            nullable=True,
            comment="Macro F1 score before training",
        ),
        sa.Column(
            "post_training_f1_macro",
            sa.Float(),
            nullable=True,
            comment="Macro F1 score after training",
        ),
        sa.Column(
            "baseline_f1_per_class",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Per-class F1 scores before training (JSON dict)",
        ),
        sa.Column(
            "post_training_f1_per_class",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Per-class F1 scores after training (JSON dict)",
        ),
        sa.Column(
            "per_class_improvement",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Per-class accuracy improvement (JSON dict)",
        ),
        sa.Column(
            "contribution_count",
            sa.Integer(),
            nullable=False,
            default=0,
            comment="Number of contributions in this batch",
        ),
        sa.Column(
            "top_contributors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Top contributors by impact (JSON array of dicts)",
        ),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When the impact evaluation was recorded",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_contribution_batch_impacts"),
    )
    
    # Create index for looking up recent impacts
    op.create_index(
        "ix_contribution_batch_impacts_evaluated_at",
        "contribution_batch_impacts",
        ["evaluated_at"],
        postgresql_using="btree",
    )


def downgrade() -> None:
    """Drop contribution_batch_impacts table."""
    op.drop_index(
        "ix_contribution_batch_impacts_evaluated_at",
        table_name="contribution_batch_impacts",
    )
    op.drop_table("contribution_batch_impacts")
