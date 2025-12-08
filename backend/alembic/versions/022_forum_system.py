"""Add forum tables.

Revision ID: 022_forum_system
Revises: 021_phone_verification
Create Date: 2024-12-08

This migration adds the complete forum system including:
- Forum categories (top-level groupings)
- Forums (individual discussion boards)
- Topics (discussion threads)
- Posts (replies within topics)
- Voting system (upvote/downvote on topics and posts)
- Topic watching (notifications)
- Polls (attached to topics)
- Read tracking

It also adds new karma reason enum values for forum-related rewards.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "022_forum_system"
down_revision = "021_phone_verification"
branch_labels = None
depends_on = None


def enum_type_exists(type_name: str) -> bool:
    """Check if a PostgreSQL enum type exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = :type_name)"
        ).bindparams(type_name=type_name)
    )
    return result.scalar()


def enum_value_exists(type_name: str, value: str) -> bool:
    """Check if a value exists in a PostgreSQL enum type."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_enum 
                WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = :type_name)
                AND enumlabel = :value
            )
            """
        ).bindparams(type_name=type_name, value=value)
    )
    return result.scalar()


def upgrade() -> None:
    """Add forum tables and new karma reason enum values."""
    
    # 1. Add new KarmaReason enum values
    if enum_type_exists("karmareason"):
        new_karma_reasons = [
            "email_verified_bonus",
            "phone_verified_bonus", 
            "full_verification_bonus",
            "forum_post_upvoted",
            "forum_post_downvoted",
            "forum_topic_upvoted",
            "forum_topic_downvoted",
            "forum_helpful_answer",
            "forum_spam_penalty",
        ]
        for value in new_karma_reasons:
            if not enum_value_exists("karmareason", value):
                print(f"  Adding karmareason value: {value}")
                op.execute(f"ALTER TYPE karmareason ADD VALUE IF NOT EXISTS '{value}'")
            else:
                print(f"  karmareason value already exists: {value}")
    
    # 2. Create forum enums
    forumtopictype = postgresql.ENUM(
        "normal", "sticky", "announcement",
        name="forumtopictype",
        create_type=False,
    )
    forumtopicstatus = postgresql.ENUM(
        "open", "locked", "archived",
        name="forumtopicstatus",
        create_type=False,
    )
    forumpostvotetype = postgresql.ENUM(
        "-1", "1",  # Integer enum stored as string
        name="forumpostvotetype",
        create_type=False,
    )
    
    # Create enum types
    forumtopictype.create(op.get_bind(), checkfirst=True)
    forumtopicstatus.create(op.get_bind(), checkfirst=True)
    forumpostvotetype.create(op.get_bind(), checkfirst=True)
    
    # 3. Create forum_categories table
    op.create_table(
        "forum_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("display_order", sa.Integer, default=0),
        sa.Column("icon", sa.String(64), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("is_visible", sa.Boolean, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    
    # 4. Create forums table
    op.create_table(
        "forums",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forum_categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("display_order", sa.Integer, default=0),
        sa.Column("icon", sa.String(64), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("min_karma_to_post", sa.Integer, default=0),
        sa.Column("min_karma_to_create_topic", sa.Integer, default=0),
        sa.Column("requires_email_verified", sa.Boolean, default=False),
        sa.Column("requires_phone_verified", sa.Boolean, default=False),
        sa.Column("allow_polls", sa.Boolean, default=True),
        sa.Column("enable_voting", sa.Boolean, default=True),
        sa.Column("is_visible", sa.Boolean, default=True),
        sa.Column("is_locked", sa.Boolean, default=False),
        sa.Column("topic_count", sa.Integer, default=0),
        sa.Column("post_count", sa.Integer, default=0),
        sa.Column("last_post_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_post_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_poster_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_forum_category_order",
        "forums",
        ["category_id", "display_order"],
    )
    
    # 5. Create forum_topics table
    op.create_table(
        "forum_topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "forum_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forums.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_html", sa.Text, nullable=True),
        sa.Column(
            "topic_type",
            forumtopictype,
            default="normal",
        ),
        sa.Column(
            "status",
            forumtopicstatus,
            default="open",
        ),
        sa.Column("tags", sa.Text, nullable=True),
        sa.Column("view_count", sa.Integer, default=0),
        sa.Column("reply_count", sa.Integer, default=0),
        sa.Column("vote_score", sa.Integer, default=0),
        sa.Column("has_poll", sa.Boolean, default=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("last_post_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_poster_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_topic_forum_type_time",
        "forum_topics",
        ["forum_id", "topic_type", "last_post_at"],
    )
    op.create_index("ix_topic_author", "forum_topics", ["author_id"])
    op.create_index("ix_topic_created", "forum_topics", ["created_at"])
    
    # 6. Create forum_posts table
    op.create_table(
        "forum_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forum_topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reply_to_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forum_posts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_html", sa.Text, nullable=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("upvote_count", sa.Integer, default=0),
        sa.Column("downvote_count", sa.Integer, default=0),
        sa.Column("vote_score", sa.Integer, default=0),
        sa.Column("edit_count", sa.Integer, default=0),
        sa.Column("last_edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_edited_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("edit_reason", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_post_topic_created", "forum_posts", ["topic_id", "created_at"])
    op.create_index("ix_post_author", "forum_posts", ["author_id"])
    
    # 7. Create forum_post_votes table
    op.create_table(
        "forum_post_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forum_posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vote_type", forumpostvotetype, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint(
        "uq_post_vote_user_post",
        "forum_post_votes",
        ["user_id", "post_id"],
    )
    op.create_index("ix_post_vote_post", "forum_post_votes", ["post_id"])
    
    # 8. Create forum_topic_votes table
    op.create_table(
        "forum_topic_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forum_topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vote_type", forumpostvotetype, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint(
        "uq_topic_vote_user_topic",
        "forum_topic_votes",
        ["user_id", "topic_id"],
    )
    op.create_index("ix_topic_vote_topic", "forum_topic_votes", ["topic_id"])
    
    # 9. Create forum_topic_watches table
    op.create_table(
        "forum_topic_watches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forum_topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("notify_on_reply", sa.Boolean, default=True),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint(
        "uq_topic_watch_user_topic",
        "forum_topic_watches",
        ["user_id", "topic_id"],
    )
    
    # 10. Create forum_polls table
    op.create_table(
        "forum_polls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "topic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forum_topics.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("max_options", sa.Integer, default=1),
        sa.Column("allow_vote_change", sa.Boolean, default=True),
        sa.Column("hide_results_until_end", sa.Boolean, default=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_votes", sa.Integer, default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    
    # 11. Create forum_poll_options table
    op.create_table(
        "forum_poll_options",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "poll_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forum_polls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.String(255), nullable=False),
        sa.Column("display_order", sa.Integer, default=0),
        sa.Column("vote_count", sa.Integer, default=0),
    )
    op.create_index("ix_poll_option_poll", "forum_poll_options", ["poll_id"])
    
    # 12. Create forum_poll_votes table
    op.create_table(
        "forum_poll_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "option_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forum_poll_options.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint(
        "uq_poll_vote_user_option",
        "forum_poll_votes",
        ["user_id", "option_id"],
    )
    op.create_index("ix_poll_vote_option", "forum_poll_votes", ["option_id"])
    
    # 13. Create forum_read_trackers table
    op.create_table(
        "forum_read_trackers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "forum_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("forums.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "marked_read_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint(
        "uq_read_tracker_user_forum",
        "forum_read_trackers",
        ["user_id", "forum_id"],
    )
    
    # 14. Create default forum categories and forums
    conn = op.get_bind()
    
    # Insert default categories
    conn.execute(
        sa.text("""
            INSERT INTO forum_categories (id, name, description, display_order, icon, is_visible)
            VALUES 
                (gen_random_uuid(), 'BeatSight', 'BeatSight-specific discussions', 0, 'music', true),
                (gen_random_uuid(), 'Beatmaps', 'Discuss beatmap creation and modding', 1, 'map', true),
                (gen_random_uuid(), 'General', 'Off-topic and general discussions', 2, 'chat', true),
                (gen_random_uuid(), 'Help', 'Get help and support', 3, 'help', true)
        """)
    )
    
    # Get category IDs
    result = conn.execute(
        sa.text("SELECT id, name FROM forum_categories ORDER BY display_order")
    )
    categories = {row[1]: row[0] for row in result.fetchall()}
    
    # Insert default forums
    if categories:
        forums_data = [
            # BeatSight category
            (categories.get('BeatSight'), 'Development', 'development', 'Discuss BeatSight development, features, and roadmap', 0),
            (categories.get('BeatSight'), 'Feature Requests', 'feature-requests', 'Suggest new features for BeatSight', 1),
            (categories.get('BeatSight'), 'Announcements', 'announcements', 'Official announcements and updates', 2),
            # Beatmaps category
            (categories.get('Beatmaps'), 'Mapping Discussion', 'mapping-discussion', 'General mapping discussion and techniques', 0),
            (categories.get('Beatmaps'), 'AI Training Contributions', 'ai-contributions', 'Discuss AI training and model improvements', 1),
            (categories.get('Beatmaps'), 'Map Showcase', 'map-showcase', 'Share and showcase your beatmaps', 2),
            # General category
            (categories.get('General'), 'Off-Topic', 'off-topic', 'Random discussions', 0),
            (categories.get('General'), 'Introductions', 'introductions', 'Introduce yourself to the community', 1),
            (categories.get('General'), 'Music', 'music', 'Discuss music and drumming', 2),
            # Help category
            (categories.get('Help'), 'Technical Support', 'technical-support', 'Get help with technical issues', 0),
            (categories.get('Help'), 'Getting Started', 'getting-started', 'New to BeatSight? Start here', 1),
        ]
        
        for cat_id, name, slug, description, order in forums_data:
            if cat_id:
                conn.execute(
                    sa.text("""
                        INSERT INTO forums (id, category_id, name, slug, description, display_order)
                        VALUES (gen_random_uuid(), :cat_id, :name, :slug, :description, :display_order)
                    """).bindparams(
                        cat_id=cat_id,
                        name=name,
                        slug=slug,
                        description=description,
                        display_order=order,
                    )
                )


def downgrade() -> None:
    """Remove forum tables."""
    
    # Drop tables in reverse order of creation
    op.drop_table("forum_read_trackers")
    op.drop_table("forum_poll_votes")
    op.drop_table("forum_poll_options")
    op.drop_table("forum_polls")
    op.drop_table("forum_topic_watches")
    op.drop_table("forum_topic_votes")
    op.drop_table("forum_post_votes")
    op.drop_table("forum_posts")
    op.drop_table("forum_topics")
    op.drop_table("forums")
    op.drop_table("forum_categories")
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS forumpostvotetype")
    op.execute("DROP TYPE IF EXISTS forumtopicstatus")
    op.execute("DROP TYPE IF EXISTS forumtopictype")
    
    # Note: We don't remove the karma reason enum values as they may be referenced
