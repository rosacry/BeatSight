"""Add phone verification tables.

Revision ID: 021_phone_verification
Revises: 020_map_accuracy_verification
Create Date: 2024-12-08

This migration adds tables for phone verification:
- phone_verification_codes: Stores pending verification codes with expiry
- phone_verification_attempts: Tracks verification attempts for rate limiting

These support the multi-verifier beatmap accuracy voting system, which requires
users to have both email AND phone verified before they can vote.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic
revision = "021_phone_verification"
down_revision = "020_map_accuracy_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create phone verification tables."""
    
    # Phone verification codes table
    op.create_table(
        "phone_verification_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "phone_number",
            sa.String(32),
            nullable=False,
            comment="Phone number in E.164 format",
        ),
        sa.Column(
            "code_hash",
            sa.String(128),
            nullable=False,
            comment="Hashed verification code",
        ),
        sa.Column(
            "attempts",
            sa.Integer,
            default=0,
            nullable=False,
            comment="Number of verification attempts",
        ),
        sa.Column(
            "is_used",
            sa.Boolean,
            default=False,
            nullable=False,
            comment="Whether code has been successfully used",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the code expires",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    
    # Indexes for phone_verification_codes
    op.create_index(
        "ix_phone_verification_codes_user_id",
        "phone_verification_codes",
        ["user_id"],
    )
    op.create_index(
        "ix_phone_verification_codes_expires_at",
        "phone_verification_codes",
        ["expires_at"],
    )
    
    # Phone verification attempts table
    op.create_table(
        "phone_verification_attempts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "phone_number",
            sa.String(32),
            nullable=False,
            comment="Phone number attempted",
        ),
        sa.Column(
            "ip_address",
            sa.String(45),
            nullable=True,
            comment="IP address of the request",
        ),
        sa.Column(
            "success",
            sa.Boolean,
            default=False,
            nullable=False,
            comment="Whether verification succeeded",
        ),
        sa.Column(
            "failure_reason",
            sa.String(128),
            nullable=True,
            comment="Reason for failure if applicable",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    
    # Indexes for phone_verification_attempts (rate limiting)
    op.create_index(
        "ix_phone_verification_attempts_user_created",
        "phone_verification_attempts",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_phone_verification_attempts_phone_created",
        "phone_verification_attempts",
        ["phone_number", "created_at"],
    )


def downgrade() -> None:
    """Remove phone verification tables."""
    op.drop_index("ix_phone_verification_attempts_phone_created")
    op.drop_index("ix_phone_verification_attempts_user_created")
    op.drop_table("phone_verification_attempts")
    
    op.drop_index("ix_phone_verification_codes_expires_at")
    op.drop_index("ix_phone_verification_codes_user_id")
    op.drop_table("phone_verification_codes")
