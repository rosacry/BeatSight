"""Forum models for community discussions.

This module implements a comprehensive forum system inspired by osu!'s forums,
with additional karma-based voting mechanics for BeatSight.

Forum Structure:
- ForumCategory: Top-level groupings (e.g., "osu! specific", "Beatmaps", "Other")
- Forum: Individual forums within categories (e.g., "Development", "Help")
- ForumTopic: Discussion threads within forums
- ForumPost: Individual posts/replies within topics
- ForumPostVote: Upvote/downvote system for posts
- ForumTopicWatch: Track topics users are watching
- ForumPoll: Optional polls attached to topics
- ForumPollOption: Poll choices
- ForumPollVote: User votes on polls

Karma Integration:
- Post upvotes/downvotes affect author's karma
- Quality contributions are rewarded
- Spam/bad content is penalized
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .user import User


class ForumTopicType(str, enum.Enum):
    """Type of forum topic for display/sorting."""
    NORMAL = "normal"
    STICKY = "sticky"          # Pinned to top
    ANNOUNCEMENT = "announcement"  # Important announcements


class ForumTopicStatus(str, enum.Enum):
    """Status of a forum topic."""
    OPEN = "open"
    LOCKED = "locked"          # No new replies
    ARCHIVED = "archived"      # Historical, no activity


class ForumPostVoteType(int, enum.Enum):
    """Vote direction for forum posts."""
    DOWNVOTE = -1
    UPVOTE = 1


class ForumCategory(Base):
    """Top-level forum grouping.
    
    Categories organize forums into logical groups like:
    - "BeatSight" (site-specific discussions)
    - "Beatmaps" (mapping discussion, modding queues)
    - "General" (off-topic, introductions)
    - "Language Specific" (localized discussions)
    """
    
    __tablename__ = "forum_categories"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    icon: Mapped[str | None] = mapped_column(String(64))  # Icon name/class
    color: Mapped[str | None] = mapped_column(String(7))  # Hex color code
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    forums: Mapped[list["Forum"]] = relationship(
        "Forum", back_populates="category", cascade="all, delete-orphan"
    )


class Forum(Base):
    """Individual forum within a category.
    
    Forums contain topics and have specific rules/permissions.
    Examples: "Development", "Gameplay & Rankings", "Help"
    
    Each forum can have:
    - Custom permission requirements (min karma, verified only, etc.)
    - Topic creation restrictions
    - Unique visual styling
    """
    
    __tablename__ = "forums"
    
    __table_args__ = (
        Index("ix_forum_category_order", "category_id", "display_order"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forum_categories.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    icon: Mapped[str | None] = mapped_column(String(64))
    color: Mapped[str | None] = mapped_column(String(7))
    
    # Permissions
    min_karma_to_post: Mapped[int] = mapped_column(Integer, default=0)
    min_karma_to_create_topic: Mapped[int] = mapped_column(Integer, default=0)
    requires_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Settings
    allow_polls: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_voting: Mapped[bool] = mapped_column(Boolean, default=True)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Counters (denormalized for performance)
    topic_count: Mapped[int] = mapped_column(Integer, default=0)
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Last activity tracking
    last_post_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    last_post_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_poster_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    category: Mapped["ForumCategory"] = relationship(
        "ForumCategory", back_populates="forums"
    )
    topics: Mapped[list["ForumTopic"]] = relationship(
        "ForumTopic", back_populates="forum", cascade="all, delete-orphan"
    )


class ForumTopic(Base):
    """A discussion thread within a forum.
    
    Topics contain the original post and all replies.
    Can be pinned, locked, or have polls attached.
    """
    
    __tablename__ = "forum_topics"
    
    __table_args__ = (
        Index("ix_topic_forum_type_time", "forum_id", "topic_type", "last_post_at"),
        Index("ix_topic_author", "author_id"),
        Index("ix_topic_created", "created_at"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    forum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forums.id", ondelete="CASCADE"),
        nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True  # Allow null if user is deleted
    )
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Content of the first post (stored here for efficiency)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str | None] = mapped_column(Text)  # Pre-rendered HTML
    
    # Type and status
    topic_type: Mapped[ForumTopicType] = mapped_column(
        SAEnum(ForumTopicType), default=ForumTopicType.NORMAL
    )
    status: Mapped[ForumTopicStatus] = mapped_column(
        SAEnum(ForumTopicStatus), default=ForumTopicStatus.OPEN
    )
    
    # Tags for categorization
    tags: Mapped[str | None] = mapped_column(Text)  # JSON array of tags
    
    # Counters
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    vote_score: Mapped[int] = mapped_column(Integer, default=0)  # Aggregate votes
    
    # Poll reference (if topic has poll)
    has_poll: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_post_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_poster_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    
    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    
    # Relationships
    forum: Mapped["Forum"] = relationship("Forum", back_populates="topics")
    author: Mapped[Optional["User"]] = relationship("User", foreign_keys=[author_id])
    posts: Mapped[list["ForumPost"]] = relationship(
        "ForumPost", back_populates="topic", cascade="all, delete-orphan"
    )
    votes: Mapped[list["ForumTopicVote"]] = relationship(
        "ForumTopicVote", back_populates="topic", cascade="all, delete-orphan"
    )
    watchers: Mapped[list["ForumTopicWatch"]] = relationship(
        "ForumTopicWatch", back_populates="topic", cascade="all, delete-orphan"
    )
    poll: Mapped[Optional["ForumPoll"]] = relationship(
        "ForumPoll", back_populates="topic", uselist=False, cascade="all, delete-orphan"
    )


class ForumPost(Base):
    """A reply post within a topic.
    
    Posts can be voted on (upvote/downvote) which affects the author's karma.
    The first post of a topic is not stored here - it's in ForumTopic.content.
    """
    
    __tablename__ = "forum_posts"
    
    __table_args__ = (
        Index("ix_post_topic_created", "topic_id", "created_at"),
        Index("ix_post_author", "author_id"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forum_topics.id", ondelete="CASCADE"),
        nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Reply to another post (for threading)
    reply_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forum_posts.id", ondelete="SET NULL")
    )
    
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str | None] = mapped_column(Text)
    
    # Post position in topic (1-indexed, sequential)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Voting
    upvote_count: Mapped[int] = mapped_column(Integer, default=0)
    downvote_count: Mapped[int] = mapped_column(Integer, default=0)
    vote_score: Mapped[int] = mapped_column(Integer, default=0)
    
    # Edit tracking
    edit_count: Mapped[int] = mapped_column(Integer, default=0)
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_edited_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    edit_reason: Mapped[str | None] = mapped_column(String(255))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    
    # Relationships
    topic: Mapped["ForumTopic"] = relationship("ForumTopic", back_populates="posts")
    author: Mapped[Optional["User"]] = relationship("User", foreign_keys=[author_id])
    votes: Mapped[list["ForumPostVote"]] = relationship(
        "ForumPostVote", back_populates="post", cascade="all, delete-orphan"
    )
    reply_to: Mapped[Optional["ForumPost"]] = relationship(
        "ForumPost", remote_side=[id], foreign_keys=[reply_to_id]
    )


class ForumPostVote(Base):
    """Vote on a forum post (affects author karma)."""
    
    __tablename__ = "forum_post_votes"
    
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_post_vote_user_post"),
        Index("ix_post_vote_post", "post_id"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forum_posts.id", ondelete="CASCADE"),
        nullable=False
    )
    vote_type: Mapped[ForumPostVoteType] = mapped_column(
        SAEnum(ForumPostVoteType), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    post: Mapped["ForumPost"] = relationship("ForumPost", back_populates="votes")


class ForumTopicVote(Base):
    """Vote on the original topic post (affects author karma)."""
    
    __tablename__ = "forum_topic_votes"
    
    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", name="uq_topic_vote_user_topic"),
        Index("ix_topic_vote_topic", "topic_id"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forum_topics.id", ondelete="CASCADE"),
        nullable=False
    )
    vote_type: Mapped[ForumPostVoteType] = mapped_column(
        SAEnum(ForumPostVoteType), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    topic: Mapped["ForumTopic"] = relationship("ForumTopic", back_populates="votes")


class ForumTopicWatch(Base):
    """Track topics a user is watching for notifications."""
    
    __tablename__ = "forum_topic_watches"
    
    __table_args__ = (
        UniqueConstraint("user_id", "topic_id", name="uq_topic_watch_user_topic"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forum_topics.id", ondelete="CASCADE"),
        nullable=False
    )
    notify_on_reply: Mapped[bool] = mapped_column(Boolean, default=True)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    topic: Mapped["ForumTopic"] = relationship("ForumTopic", back_populates="watchers")


class ForumPoll(Base):
    """Poll attached to a topic."""
    
    __tablename__ = "forum_polls"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forum_topics.id", ondelete="CASCADE"),
        unique=True, nullable=False
    )
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    max_options: Mapped[int] = mapped_column(Integer, default=1)  # Max selections
    
    # Settings
    allow_vote_change: Mapped[bool] = mapped_column(Boolean, default=True)
    hide_results_until_end: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Duration
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # Total votes
    total_votes: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    topic: Mapped["ForumTopic"] = relationship("ForumTopic", back_populates="poll")
    options: Mapped[list["ForumPollOption"]] = relationship(
        "ForumPollOption", back_populates="poll", cascade="all, delete-orphan"
    )


class ForumPollOption(Base):
    """An option in a poll."""
    
    __tablename__ = "forum_poll_options"
    
    __table_args__ = (
        Index("ix_poll_option_poll", "poll_id"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    poll_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forum_polls.id", ondelete="CASCADE"),
        nullable=False
    )
    
    text: Mapped[str] = mapped_column(String(255), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    vote_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    poll: Mapped["ForumPoll"] = relationship("ForumPoll", back_populates="options")
    votes: Mapped[list["ForumPollVote"]] = relationship(
        "ForumPollVote", back_populates="option", cascade="all, delete-orphan"
    )


class ForumPollVote(Base):
    """A user's vote on a poll option."""
    
    __tablename__ = "forum_poll_votes"
    
    __table_args__ = (
        UniqueConstraint("user_id", "option_id", name="uq_poll_vote_user_option"),
        Index("ix_poll_vote_option", "option_id"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    option_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forum_poll_options.id", ondelete="CASCADE"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    option: Mapped["ForumPollOption"] = relationship(
        "ForumPollOption", back_populates="votes"
    )


class ForumReadTracker(Base):
    """Track which forums a user has read (for 'mark as read' functionality)."""
    
    __tablename__ = "forum_read_trackers"
    
    __table_args__ = (
        UniqueConstraint("user_id", "forum_id", name="uq_read_tracker_user_forum"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    forum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("forums.id", ondelete="CASCADE"),
        nullable=False
    )
    marked_read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
