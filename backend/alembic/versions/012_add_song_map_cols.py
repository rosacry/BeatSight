"""Add missing columns to songs, maps, and map_versions tables.

Revision ID: 012_add_song_map_cols
Revises: 011_two_factor_auth
Create Date: 2025-12-08

This migration adds columns that were in the SQLAlchemy models but missing from
the database schema:
- songs.canonical_map_id (FK to maps.id)
- maps.difficulty_label (rename from difficulty)
- maps.is_canonical
- maps.current_version_id (FK to map_versions.id)
- map_versions.version_number (rename from version)
- map_versions.source_type
- map_versions.generation_job_id
- map_versions.storage_uri (rename from data_url)
- map_versions.stem_uri
- map_versions.diff_summary
- map_versions.created_by
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "012_add_song_map_cols"
down_revision = "011_two_factor_auth"
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = :table_name AND column_name = :column_name
            )
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return result.scalar()


def constraint_exists(constraint_name: str) -> bool:
    """Check if a constraint exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = :constraint_name
            )
            """
        ),
        {"constraint_name": constraint_name},
    )
    return result.scalar()


def upgrade() -> None:
    # =========================================================================
    # SONGS TABLE
    # =========================================================================
    
    # Add canonical_map_id to songs table
    if not column_exists("songs", "canonical_map_id"):
        op.add_column(
            "songs",
            sa.Column(
                "canonical_map_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        # Add FK constraint separately to handle circular reference
        op.create_foreign_key(
            "fk_songs_canonical_map_id",
            "songs",
            "maps",
            ["canonical_map_id"],
            ["id"],
        )

    # =========================================================================
    # MAPS TABLE
    # =========================================================================
    
    # Rename difficulty to difficulty_label in maps table if needed
    if column_exists("maps", "difficulty") and not column_exists("maps", "difficulty_label"):
        op.alter_column(
            "maps",
            "difficulty",
            new_column_name="difficulty_label",
            existing_type=sa.String(20),
            type_=sa.String(64),
        )
        # Drop old index if exists
        try:
            op.drop_index("ix_map_difficulty", table_name="maps")
        except Exception:
            pass  # Index might not exist
    elif not column_exists("maps", "difficulty_label"):
        # Column doesn't exist at all, create it
        op.add_column(
            "maps",
            sa.Column("difficulty_label", sa.String(64), nullable=False, server_default="medium"),
        )

    # Add is_canonical to maps table
    if not column_exists("maps", "is_canonical"):
        op.add_column(
            "maps",
            sa.Column("is_canonical", sa.Boolean, nullable=False, server_default="false"),
        )

    # Add current_version_id to maps table
    if not column_exists("maps", "current_version_id"):
        op.add_column(
            "maps",
            sa.Column(
                "current_version_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.create_foreign_key(
            "fk_maps_current_version_id",
            "maps",
            "map_versions",
            ["current_version_id"],
            ["id"],
        )

    # =========================================================================
    # MAP_VERSIONS TABLE
    # =========================================================================
    
    # Rename version to version_number
    if column_exists("map_versions", "version") and not column_exists("map_versions", "version_number"):
        # Drop the old unique constraint first
        if constraint_exists("uq_map_version"):
            op.drop_constraint("uq_map_version", "map_versions", type_="unique")
        
        op.alter_column(
            "map_versions",
            "version",
            new_column_name="version_number",
            existing_type=sa.Integer,
        )
        
        # Recreate constraint with new column name
        op.create_unique_constraint(
            "uq_map_version_number",
            "map_versions",
            ["map_id", "version_number"],
        )
    elif not column_exists("map_versions", "version_number"):
        op.add_column(
            "map_versions",
            sa.Column("version_number", sa.Integer, nullable=False, server_default="1"),
        )

    # Rename data_url to storage_uri
    if column_exists("map_versions", "data_url") and not column_exists("map_versions", "storage_uri"):
        op.alter_column(
            "map_versions",
            "data_url",
            new_column_name="storage_uri",
            existing_type=sa.String(512),
        )
    elif not column_exists("map_versions", "storage_uri"):
        op.add_column(
            "map_versions",
            sa.Column("storage_uri", sa.String(512), nullable=False, server_default=""),
        )

    # Add source_type column
    if not column_exists("map_versions", "source_type"):
        op.add_column(
            "map_versions",
            sa.Column("source_type", sa.String(20), nullable=False, server_default="ai"),
        )

    # Add generation_job_id column
    if not column_exists("map_versions", "generation_job_id"):
        op.add_column(
            "map_versions",
            sa.Column(
                "generation_job_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.create_foreign_key(
            "fk_map_versions_generation_job_id",
            "map_versions",
            "ai_jobs",
            ["generation_job_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Add stem_uri column
    if not column_exists("map_versions", "stem_uri"):
        op.add_column(
            "map_versions",
            sa.Column("stem_uri", sa.String(512), nullable=True),
        )

    # Add diff_summary column
    if not column_exists("map_versions", "diff_summary"):
        op.add_column(
            "map_versions",
            sa.Column("diff_summary", sa.JSON, nullable=True),
        )

    # Add created_by column
    if not column_exists("map_versions", "created_by"):
        op.add_column(
            "map_versions",
            sa.Column(
                "created_by",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.create_foreign_key(
            "fk_map_versions_created_by",
            "map_versions",
            "users",
            ["created_by"],
            ["id"],
        )
        # Add index for created_by
        op.create_index("ix_map_versions_created_by", "map_versions", ["created_by"])

    # Drop old is_current column if it exists (not in model)
    if column_exists("map_versions", "is_current"):
        op.drop_column("map_versions", "is_current")

    # =========================================================================
    # MAP_ASSETS TABLE
    # =========================================================================
    
    # The model uses map_version_id but migration has map_id
    # Need to add map_version_id and migrate data if needed
    if column_exists("map_assets", "map_id") and not column_exists("map_assets", "map_version_id"):
        # Add the new column
        op.add_column(
            "map_assets",
            sa.Column(
                "map_version_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,  # Temporarily nullable for migration
            ),
        )
        # Drop old FK and index
        try:
            op.drop_constraint("map_assets_map_id_fkey", "map_assets", type_="foreignkey")
        except Exception:
            pass
        try:
            op.drop_index("ix_map_assets_map_id", table_name="map_assets")
        except Exception:
            pass
        # Drop old column
        op.drop_column("map_assets", "map_id")
        # Make new column required after dropping old one
        op.alter_column("map_assets", "map_version_id", nullable=False)
        # Add FK
        op.create_foreign_key(
            "fk_map_assets_map_version_id",
            "map_assets",
            "map_versions",
            ["map_version_id"],
            ["id"],
            ondelete="CASCADE",
        )
    elif not column_exists("map_assets", "map_version_id"):
        op.add_column(
            "map_assets",
            sa.Column(
                "map_version_id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
            ),
        )
        op.create_foreign_key(
            "fk_map_assets_map_version_id",
            "map_assets",
            "map_versions",
            ["map_version_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # Rename url to storage_uri in map_assets
    if column_exists("map_assets", "url") and not column_exists("map_assets", "storage_uri"):
        op.alter_column(
            "map_assets",
            "url",
            new_column_name="storage_uri",
            existing_type=sa.String(512),
        )
    elif not column_exists("map_assets", "storage_uri"):
        op.add_column(
            "map_assets",
            sa.Column("storage_uri", sa.String(512), nullable=False, server_default=""),
        )

    # Drop size_bytes if it exists (not in model)
    if column_exists("map_assets", "size_bytes"):
        op.drop_column("map_assets", "size_bytes")


def downgrade() -> None:
    # Re-add is_current to map_versions
    if not column_exists("map_versions", "is_current"):
        op.add_column(
            "map_versions",
            sa.Column("is_current", sa.Boolean, nullable=False, server_default="true"),
        )

    # Remove created_by index and FK
    if column_exists("map_versions", "created_by"):
        op.drop_index("ix_map_versions_created_by", table_name="map_versions")
        op.drop_constraint("fk_map_versions_created_by", "map_versions", type_="foreignkey")
        op.drop_column("map_versions", "created_by")

    # Remove diff_summary
    if column_exists("map_versions", "diff_summary"):
        op.drop_column("map_versions", "diff_summary")

    # Remove stem_uri
    if column_exists("map_versions", "stem_uri"):
        op.drop_column("map_versions", "stem_uri")

    # Remove generation_job_id
    if column_exists("map_versions", "generation_job_id"):
        op.drop_constraint("fk_map_versions_generation_job_id", "map_versions", type_="foreignkey")
        op.drop_column("map_versions", "generation_job_id")

    # Remove source_type
    if column_exists("map_versions", "source_type"):
        op.drop_column("map_versions", "source_type")

    # Rename storage_uri back to data_url
    if column_exists("map_versions", "storage_uri"):
        op.alter_column(
            "map_versions",
            "storage_uri",
            new_column_name="data_url",
            existing_type=sa.String(512),
        )

    # Rename version_number back to version
    if column_exists("map_versions", "version_number"):
        if constraint_exists("uq_map_version_number"):
            op.drop_constraint("uq_map_version_number", "map_versions", type_="unique")
        
        op.alter_column(
            "map_versions",
            "version_number",
            new_column_name="version",
            existing_type=sa.Integer,
        )
        
        op.create_unique_constraint(
            "uq_map_version",
            "map_versions",
            ["map_id", "version"],
        )

    # Remove current_version_id from maps
    if column_exists("maps", "current_version_id"):
        op.drop_constraint("fk_maps_current_version_id", "maps", type_="foreignkey")
        op.drop_column("maps", "current_version_id")

    # Remove is_canonical from maps
    if column_exists("maps", "is_canonical"):
        op.drop_column("maps", "is_canonical")

    # Rename difficulty_label back to difficulty
    if column_exists("maps", "difficulty_label"):
        op.alter_column(
            "maps",
            "difficulty_label",
            new_column_name="difficulty",
            existing_type=sa.String(64),
            type_=sa.String(20),
        )
        op.create_index("ix_map_difficulty", "maps", ["difficulty"])

    # Remove canonical_map_id from songs
    if column_exists("songs", "canonical_map_id"):
        op.drop_constraint("fk_songs_canonical_map_id", "songs", type_="foreignkey")
        op.drop_column("songs", "canonical_map_id")
