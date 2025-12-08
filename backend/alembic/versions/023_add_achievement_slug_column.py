"""Add missing achievement columns (slug, icon, points, is_hidden, is_active)

Revision ID: 023_add_achievement_slug_column
Revises: 022_forum_system
Create Date: 2024-12-08

The Achievement model was updated with new columns but the database
schema wasn't migrated. This adds:
- slug: unique identifier for achievements
- icon: icon identifier (replaces icon_url)
- points: XP/points value (replaces karma_reward)
- is_hidden: whether achievement is hidden until earned
- is_active: whether achievement can be earned
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "023_add_achievement_slug_column"
down_revision = "022_forum_system"
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    from sqlalchemy import inspect
    from alembic import op

    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Add slug column if it doesn't exist
    if not column_exists("achievements", "slug"):
        # First add as nullable
        op.add_column(
            "achievements",
            sa.Column("slug", sa.String(64), nullable=True),
        )
        # Populate slug from name (lowercase, replace spaces with hyphens)
        op.execute(
            """
            UPDATE achievements 
            SET slug = LOWER(REPLACE(REPLACE(name, ' ', '-'), '''', ''))
            WHERE slug IS NULL
            """
        )
        # Make it not nullable and unique
        op.alter_column("achievements", "slug", nullable=False)
        op.create_unique_constraint("uq_achievements_slug", "achievements", ["slug"])
        op.create_index("ix_achievements_slug", "achievements", ["slug"])

    # Add icon column if it doesn't exist (replaces icon_url)
    if not column_exists("achievements", "icon"):
        op.add_column(
            "achievements",
            sa.Column("icon", sa.String(64), nullable=False, server_default="trophy"),
        )
        # Copy from icon_url if it exists, extract filename
        if column_exists("achievements", "icon_url"):
            op.execute(
                """
                UPDATE achievements 
                SET icon = COALESCE(
                    SUBSTRING(icon_url FROM '[^/]+$'),
                    'trophy'
                )
                WHERE icon_url IS NOT NULL
                """
            )

    # Add points column if it doesn't exist (replaces karma_reward)
    if not column_exists("achievements", "points"):
        op.add_column(
            "achievements",
            sa.Column("points", sa.String(8), nullable=False, server_default="10"),
        )
        # Copy from karma_reward if it exists
        if column_exists("achievements", "karma_reward"):
            op.execute(
                """
                UPDATE achievements 
                SET points = CAST(karma_reward AS VARCHAR)
                WHERE karma_reward IS NOT NULL
                """
            )

    # Add is_hidden column if it doesn't exist
    if not column_exists("achievements", "is_hidden"):
        op.add_column(
            "achievements",
            sa.Column("is_hidden", sa.Boolean, nullable=False, server_default="false"),
        )

    # Add is_active column if it doesn't exist
    if not column_exists("achievements", "is_active"):
        op.add_column(
            "achievements",
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        )

    # Remove server defaults after population
    op.alter_column("achievements", "icon", server_default=None)
    op.alter_column("achievements", "points", server_default=None)
    op.alter_column("achievements", "is_hidden", server_default=None)
    op.alter_column("achievements", "is_active", server_default=None)


def downgrade() -> None:
    # Drop new columns
    if column_exists("achievements", "slug"):
        op.drop_index("ix_achievements_slug", table_name="achievements")
        op.drop_constraint("uq_achievements_slug", "achievements", type_="unique")
        op.drop_column("achievements", "slug")

    if column_exists("achievements", "icon"):
        op.drop_column("achievements", "icon")

    if column_exists("achievements", "points"):
        op.drop_column("achievements", "points")

    if column_exists("achievements", "is_hidden"):
        op.drop_column("achievements", "is_hidden")

    if column_exists("achievements", "is_active"):
        op.drop_column("achievements", "is_active")
