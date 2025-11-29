"""add map_votes table

Revision ID: 004_map_votes
Revises: 003_push_subscriptions
Create Date: 2025-01-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_map_votes"
down_revision: Union[str, None] = "003_push_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create VoteType enum
    vote_type_enum = postgresql.ENUM(
        "DOWNVOTE", "UPVOTE", name="votetype", create_type=True
    )
    vote_type_enum.create(op.get_bind(), checkfirst=True)

    # Create map_votes table
    op.create_table(
        "map_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "map_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("maps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vote_type",
            vote_type_enum,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Create unique index for user+map (one vote per user per map)
    op.create_index(
        "ix_map_vote_user_map",
        "map_votes",
        ["user_id", "map_id"],
        unique=True,
    )

    # Create index for efficient vote counting per map
    op.create_index(
        "ix_map_vote_map",
        "map_votes",
        ["map_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_map_vote_map", table_name="map_votes")
    op.drop_index("ix_map_vote_user_map", table_name="map_votes")
    op.drop_table("map_votes")

    # Drop the enum type
    vote_type_enum = postgresql.ENUM("DOWNVOTE", "UPVOTE", name="votetype")
    vote_type_enum.drop(op.get_bind(), checkfirst=True)
