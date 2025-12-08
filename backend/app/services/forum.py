"""Forum service for community discussions.

This service handles all forum-related operations including:
- Category and forum management
- Topic creation, editing, locking
- Post creation, editing, deletion
- Voting on posts/topics with karma integration
- Poll management
- Topic watching/notifications
- Read tracking
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Optional
from unicodedata import normalize

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.forum import (
    Forum,
    ForumCategory,
    ForumPoll,
    ForumPollOption,
    ForumPollVote,
    ForumPost,
    ForumPostVote,
    ForumPostVoteType,
    ForumTopic,
    ForumTopicStatus,
    ForumTopicType,
    ForumTopicVote,
    ForumTopicWatch,
)
from app.models.karma import KarmaReason
from app.models.user import User
from app.services.karma import KarmaService


# =============================================================================
# Exceptions
# =============================================================================


class ForumError(Exception):
    """Base exception for forum operations."""
    pass


class ForumNotFoundError(ForumError):
    """Forum does not exist."""
    pass


class TopicNotFoundError(ForumError):
    """Topic does not exist."""
    pass


class PostNotFoundError(ForumError):
    """Post does not exist."""
    pass


class PollNotFoundError(ForumError):
    """Poll does not exist."""
    pass


class InsufficientPermissionError(ForumError):
    """User lacks permission for this action."""
    pass


class TopicLockedError(ForumError):
    """Topic is locked and cannot be modified."""
    pass


class ForumLockedError(ForumError):
    """Forum is locked and no new topics/posts allowed."""
    pass


class AlreadyVotedError(ForumError):
    """User has already voted on this item."""
    pass


class SelfVoteError(ForumError):
    """Cannot vote on own content."""
    pass


class PollEndedError(ForumError):
    """Poll has ended and no new votes allowed."""
    pass


class PollVoteChangeError(ForumError):
    """Poll does not allow changing votes."""
    pass


# =============================================================================
# Utilities
# =============================================================================


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    # Normalize unicode
    text = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    # Convert to lowercase and replace spaces with hyphens
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:100] or "untitled"


# =============================================================================
# Service Class
# =============================================================================


class ForumService:
    """Service for managing forum operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._karma_service: Optional[KarmaService] = None
    
    @property
    def karma_service(self) -> KarmaService:
        """Lazy-load karma service."""
        if self._karma_service is None:
            self._karma_service = KarmaService(self.session)
        return self._karma_service
    
    # =========================================================================
    # Permission Checks
    # =========================================================================
    
    async def check_forum_permission(
        self,
        user: User,
        forum: Forum,
        action: str = "post",
    ) -> tuple[bool, str]:
        """
        Check if user can perform an action in a forum.
        
        Args:
            user: The user attempting the action.
            forum: The forum to check permissions for.
            action: "post" or "create_topic"
        
        Returns:
            Tuple of (allowed, reason_if_not_allowed)
        """
        if forum.is_locked:
            return False, "This forum is locked"
        
        # Check karma requirements
        if action == "create_topic":
            if user.karma_score < forum.min_karma_to_create_topic:
                return False, f"Minimum {forum.min_karma_to_create_topic} karma required to create topics"
        else:
            if user.karma_score < forum.min_karma_to_post:
                return False, f"Minimum {forum.min_karma_to_post} karma required to post"
        
        # Check verification requirements
        if forum.requires_email_verified and not user.email_verified:
            return False, "Email verification required to participate"
        
        if forum.requires_phone_verified and not user.phone_verified:
            return False, "Phone verification required to participate"
        
        return True, ""
    
    # =========================================================================
    # Category Operations
    # =========================================================================
    
    async def get_all_categories(
        self,
        include_hidden: bool = False,
    ) -> list[ForumCategory]:
        """Get all forum categories with their forums."""
        query = (
            select(ForumCategory)
            .options(selectinload(ForumCategory.forums))
            .order_by(ForumCategory.display_order)
        )
        
        if not include_hidden:
            query = query.where(ForumCategory.is_visible.is_(True))
        
        result = await self.session.execute(query)
        categories = list(result.scalars().all())
        
        # Filter out hidden forums from each category
        if not include_hidden:
            for cat in categories:
                cat.forums = [f for f in cat.forums if f.is_visible]
                cat.forums.sort(key=lambda f: f.display_order)
        
        return categories
    
    async def create_category(
        self,
        name: str,
        description: Optional[str] = None,
        display_order: int = 0,
        icon: Optional[str] = None,
        color: Optional[str] = None,
    ) -> ForumCategory:
        """Create a new forum category (admin only)."""
        category = ForumCategory(
            name=name,
            description=description,
            display_order=display_order,
            icon=icon,
            color=color,
        )
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category
    
    # =========================================================================
    # Forum Operations
    # =========================================================================
    
    async def get_forum(self, forum_id: uuid.UUID) -> Forum:
        """Get a forum by ID."""
        result = await self.session.execute(
            select(Forum)
            .options(selectinload(Forum.category))
            .where(Forum.id == forum_id)
        )
        forum = result.scalar_one_or_none()
        if forum is None:
            raise ForumNotFoundError(f"Forum {forum_id} not found")
        return forum
    
    async def get_forum_by_slug(self, slug: str) -> Forum:
        """Get a forum by its slug."""
        result = await self.session.execute(
            select(Forum)
            .options(selectinload(Forum.category))
            .where(Forum.slug == slug)
        )
        forum = result.scalar_one_or_none()
        if forum is None:
            raise ForumNotFoundError(f"Forum '{slug}' not found")
        return forum
    
    async def create_forum(
        self,
        category_id: uuid.UUID,
        name: str,
        description: Optional[str] = None,
        display_order: int = 0,
        min_karma_to_post: int = 0,
        min_karma_to_create_topic: int = 0,
        requires_email_verified: bool = False,
        requires_phone_verified: bool = False,
        allow_polls: bool = True,
        enable_voting: bool = True,
    ) -> Forum:
        """Create a new forum (admin only)."""
        slug = slugify(name)
        
        # Ensure unique slug
        existing = await self.session.execute(
            select(func.count()).select_from(Forum).where(Forum.slug == slug)
        )
        if existing.scalar() > 0:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        
        forum = Forum(
            category_id=category_id,
            name=name,
            slug=slug,
            description=description,
            display_order=display_order,
            min_karma_to_post=min_karma_to_post,
            min_karma_to_create_topic=min_karma_to_create_topic,
            requires_email_verified=requires_email_verified,
            requires_phone_verified=requires_phone_verified,
            allow_polls=allow_polls,
            enable_voting=enable_voting,
        )
        self.session.add(forum)
        await self.session.commit()
        await self.session.refresh(forum)
        return forum
    
    async def get_forum_topics(
        self,
        forum_id: uuid.UUID,
        limit: int = 25,
        offset: int = 0,
        include_sticky: bool = True,
    ) -> tuple[list[ForumTopic], int]:
        """
        Get topics in a forum, sorted by type then last activity.
        
        Returns:
            Tuple of (topics, total_count)
        """
        base_query = (
            select(ForumTopic)
            .where(
                ForumTopic.forum_id == forum_id,
                ForumTopic.deleted_at.is_(None),
            )
        )
        
        # Count total
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar()
        
        # Get topics: stickies first, then by last activity
        query = (
            base_query
            .options(selectinload(ForumTopic.author))
            .order_by(
                ForumTopic.topic_type.desc(),  # Announcements > Sticky > Normal
                ForumTopic.last_post_at.desc().nulls_last(),
                ForumTopic.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        
        result = await self.session.execute(query)
        topics = list(result.scalars().all())
        
        return topics, total
    
    # =========================================================================
    # Topic Operations
    # =========================================================================
    
    async def get_topic(
        self,
        topic_id: uuid.UUID,
        increment_views: bool = False,
    ) -> ForumTopic:
        """Get a topic by ID."""
        result = await self.session.execute(
            select(ForumTopic)
            .options(
                selectinload(ForumTopic.author),
                selectinload(ForumTopic.forum).selectinload(Forum.category),
                selectinload(ForumTopic.poll).selectinload(ForumPoll.options),
            )
            .where(ForumTopic.id == topic_id, ForumTopic.deleted_at.is_(None))
        )
        topic = result.scalar_one_or_none()
        if topic is None:
            raise TopicNotFoundError(f"Topic {topic_id} not found")
        
        if increment_views:
            topic.view_count += 1
            await self.session.commit()
        
        return topic
    
    async def create_topic(
        self,
        forum_id: uuid.UUID,
        author: User,
        title: str,
        content: str,
        topic_type: ForumTopicType = ForumTopicType.NORMAL,
        tags: Optional[list[str]] = None,
        poll_data: Optional[dict] = None,
    ) -> ForumTopic:
        """
        Create a new topic.
        
        Args:
            forum_id: Forum to create topic in.
            author: User creating the topic.
            title: Topic title.
            content: Topic content (first post).
            topic_type: Type of topic (normal, sticky, announcement).
            tags: Optional list of tags.
            poll_data: Optional poll configuration.
        """
        # Get forum and check permissions
        forum = await self.get_forum(forum_id)
        allowed, reason = await self.check_forum_permission(author, forum, "create_topic")
        if not allowed:
            raise InsufficientPermissionError(reason)
        
        now = datetime.now(timezone.utc)
        slug = slugify(title)
        
        # Make slug unique by appending short UUID if needed
        slug = f"{slug}-{uuid.uuid4().hex[:8]}"
        
        topic = ForumTopic(
            forum_id=forum_id,
            author_id=author.id,
            title=title,
            slug=slug,
            content=content,
            topic_type=topic_type,
            tags=",".join(tags) if tags else None,
            last_post_at=now,
            last_poster_id=author.id,
            has_poll=poll_data is not None,
        )
        self.session.add(topic)
        await self.session.flush()  # Get topic ID
        
        # Create poll if specified
        if poll_data and forum.allow_polls:
            await self._create_poll(topic.id, poll_data)
        
        # Update forum counters
        forum.topic_count += 1
        forum.post_count += 1
        forum.last_post_at = now
        forum.last_poster_id = author.id
        
        # Auto-watch the topic
        watch = ForumTopicWatch(
            user_id=author.id,
            topic_id=topic.id,
            last_read_at=now,
        )
        self.session.add(watch)
        
        await self.session.commit()
        await self.session.refresh(topic)
        
        return topic
    
    async def update_topic(
        self,
        topic_id: uuid.UUID,
        user: User,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> ForumTopic:
        """Update a topic (author or moderator only)."""
        topic = await self.get_topic(topic_id)
        
        # Check permission (author or admin)
        is_author = topic.author_id == user.id
        is_admin = user.karma_score >= 10000  # Admin threshold
        
        if not is_author and not is_admin:
            raise InsufficientPermissionError("Only the author or moderators can edit this topic")
        
        if title:
            topic.title = title
        if content:
            topic.content = content
        if tags is not None:
            topic.tags = ",".join(tags)
        
        topic.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(topic)
        
        return topic
    
    async def lock_topic(
        self,
        topic_id: uuid.UUID,
        moderator: User,
        lock: bool = True,
    ) -> ForumTopic:
        """Lock or unlock a topic (moderator only)."""
        topic = await self.get_topic(topic_id)
        
        # Require moderator karma
        if moderator.karma_score < 500:  # Verifier threshold
            raise InsufficientPermissionError("Moderator privileges required")
        
        topic.status = ForumTopicStatus.LOCKED if lock else ForumTopicStatus.OPEN
        await self.session.commit()
        
        return topic
    
    async def pin_topic(
        self,
        topic_id: uuid.UUID,
        moderator: User,
        pin_type: ForumTopicType,
    ) -> ForumTopic:
        """Pin or unpin a topic (moderator only)."""
        topic = await self.get_topic(topic_id)
        
        if moderator.karma_score < 500:
            raise InsufficientPermissionError("Moderator privileges required")
        
        topic.topic_type = pin_type
        await self.session.commit()
        
        return topic
    
    async def delete_topic(
        self,
        topic_id: uuid.UUID,
        user: User,
    ) -> None:
        """Soft delete a topic."""
        topic = await self.get_topic(topic_id)
        
        is_author = topic.author_id == user.id
        is_admin = user.karma_score >= 10000
        
        if not is_author and not is_admin:
            raise InsufficientPermissionError("Only the author or moderators can delete this topic")
        
        now = datetime.now(timezone.utc)
        topic.deleted_at = now
        topic.deleted_by_id = user.id
        
        # Update forum counters
        forum = await self.get_forum(topic.forum_id)
        forum.topic_count = max(0, forum.topic_count - 1)
        forum.post_count = max(0, forum.post_count - topic.reply_count - 1)
        
        await self.session.commit()
    
    # =========================================================================
    # Post Operations
    # =========================================================================
    
    async def get_topic_posts(
        self,
        topic_id: uuid.UUID,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[ForumPost], int]:
        """Get posts in a topic, ordered by position."""
        base_query = (
            select(ForumPost)
            .where(
                ForumPost.topic_id == topic_id,
                ForumPost.deleted_at.is_(None),
            )
        )
        
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar()
        
        query = (
            base_query
            .options(selectinload(ForumPost.author))
            .order_by(ForumPost.position)
            .limit(limit)
            .offset(offset)
        )
        
        result = await self.session.execute(query)
        posts = list(result.scalars().all())
        
        return posts, total
    
    async def create_post(
        self,
        topic_id: uuid.UUID,
        author: User,
        content: str,
        reply_to_id: Optional[uuid.UUID] = None,
    ) -> ForumPost:
        """
        Create a new post/reply in a topic.
        """
        topic = await self.get_topic(topic_id)
        
        if topic.status == ForumTopicStatus.LOCKED:
            raise TopicLockedError("This topic is locked")
        
        forum = await self.get_forum(topic.forum_id)
        allowed, reason = await self.check_forum_permission(author, forum, "post")
        if not allowed:
            raise InsufficientPermissionError(reason)
        
        # Get next position
        result = await self.session.execute(
            select(func.max(ForumPost.position))
            .where(ForumPost.topic_id == topic_id)
        )
        max_pos = result.scalar() or 0
        
        now = datetime.now(timezone.utc)
        
        post = ForumPost(
            topic_id=topic_id,
            author_id=author.id,
            content=content,
            position=max_pos + 1,
            reply_to_id=reply_to_id,
        )
        self.session.add(post)
        
        # Update topic
        topic.reply_count += 1
        topic.last_post_at = now
        topic.last_poster_id = author.id
        
        # Update forum
        forum.post_count += 1
        forum.last_post_at = now
        forum.last_poster_id = author.id
        
        await self.session.commit()
        await self.session.refresh(post)
        
        return post
    
    async def update_post(
        self,
        post_id: uuid.UUID,
        user: User,
        content: str,
        edit_reason: Optional[str] = None,
    ) -> ForumPost:
        """Update a post (author or moderator only)."""
        result = await self.session.execute(
            select(ForumPost)
            .options(selectinload(ForumPost.topic))
            .where(ForumPost.id == post_id, ForumPost.deleted_at.is_(None))
        )
        post = result.scalar_one_or_none()
        if post is None:
            raise PostNotFoundError(f"Post {post_id} not found")
        
        is_author = post.author_id == user.id
        is_admin = user.karma_score >= 10000
        
        if not is_author and not is_admin:
            raise InsufficientPermissionError("Only the author or moderators can edit this post")
        
        post.content = content
        post.edit_count += 1
        post.last_edited_at = datetime.now(timezone.utc)
        post.last_edited_by_id = user.id
        post.edit_reason = edit_reason
        
        await self.session.commit()
        await self.session.refresh(post)
        
        return post
    
    async def delete_post(
        self,
        post_id: uuid.UUID,
        user: User,
    ) -> None:
        """Soft delete a post."""
        result = await self.session.execute(
            select(ForumPost)
            .options(selectinload(ForumPost.topic))
            .where(ForumPost.id == post_id, ForumPost.deleted_at.is_(None))
        )
        post = result.scalar_one_or_none()
        if post is None:
            raise PostNotFoundError(f"Post {post_id} not found")
        
        is_author = post.author_id == user.id
        is_admin = user.karma_score >= 10000
        
        if not is_author and not is_admin:
            raise InsufficientPermissionError("Only the author or moderators can delete this post")
        
        post.deleted_at = datetime.now(timezone.utc)
        post.deleted_by_id = user.id
        
        # Update topic reply count
        topic = post.topic
        topic.reply_count = max(0, topic.reply_count - 1)
        
        # Update forum post count
        forum = await self.get_forum(topic.forum_id)
        forum.post_count = max(0, forum.post_count - 1)
        
        await self.session.commit()
    
    # =========================================================================
    # Voting Operations (with karma integration)
    # =========================================================================
    
    async def vote_on_topic(
        self,
        topic_id: uuid.UUID,
        user: User,
        vote_type: ForumPostVoteType,
    ) -> dict:
        """
        Vote on a topic's original post.
        
        Returns:
            Dict with upvotes, downvotes, score, user_vote
        """
        topic = await self.get_topic(topic_id)
        
        # Can't vote on own content
        if topic.author_id == user.id:
            raise SelfVoteError("Cannot vote on your own topic")
        
        # Check if forum allows voting
        forum = await self.get_forum(topic.forum_id)
        if not forum.enable_voting:
            raise InsufficientPermissionError("Voting is disabled in this forum")
        
        # Check for existing vote
        result = await self.session.execute(
            select(ForumTopicVote).where(
                ForumTopicVote.user_id == user.id,
                ForumTopicVote.topic_id == topic_id,
            )
        )
        existing_vote = result.scalar_one_or_none()
        
        old_vote_value = 0
        
        if existing_vote:
            if existing_vote.vote_type == vote_type:
                # Same vote = remove it
                await self._reverse_topic_vote_karma(topic, existing_vote.vote_type)
                await self.session.delete(existing_vote)
                
                # Update topic counters
                if vote_type == ForumPostVoteType.UPVOTE:
                    topic.vote_score -= 1
                else:
                    topic.vote_score += 1
                
                await self.session.commit()
                
                return await self._get_topic_vote_counts(topic_id, user.id)
            else:
                # Different vote = change it
                old_vote_value = existing_vote.vote_type.value
                await self._reverse_topic_vote_karma(topic, existing_vote.vote_type)
                existing_vote.vote_type = vote_type
                existing_vote.created_at = datetime.now(timezone.utc)
        else:
            # New vote
            vote = ForumTopicVote(
                user_id=user.id,
                topic_id=topic_id,
                vote_type=vote_type,
            )
            self.session.add(vote)
        
        # Update topic score
        topic.vote_score += vote_type.value - old_vote_value
        
        # Award/deduct karma
        await self._apply_topic_vote_karma(topic, vote_type)
        
        await self.session.commit()
        
        return await self._get_topic_vote_counts(topic_id, user.id)
    
    async def vote_on_post(
        self,
        post_id: uuid.UUID,
        user: User,
        vote_type: ForumPostVoteType,
    ) -> dict:
        """Vote on a reply post."""
        result = await self.session.execute(
            select(ForumPost)
            .options(selectinload(ForumPost.topic).selectinload(ForumTopic.forum))
            .where(ForumPost.id == post_id, ForumPost.deleted_at.is_(None))
        )
        post = result.scalar_one_or_none()
        if post is None:
            raise PostNotFoundError(f"Post {post_id} not found")
        
        if post.author_id == user.id:
            raise SelfVoteError("Cannot vote on your own post")
        
        if not post.topic.forum.enable_voting:
            raise InsufficientPermissionError("Voting is disabled in this forum")
        
        # Check for existing vote
        result = await self.session.execute(
            select(ForumPostVote).where(
                ForumPostVote.user_id == user.id,
                ForumPostVote.post_id == post_id,
            )
        )
        existing_vote = result.scalar_one_or_none()
        
        if existing_vote:
            if existing_vote.vote_type == vote_type:
                # Same vote = remove it
                await self._reverse_post_vote_karma(post, existing_vote.vote_type)
                await self.session.delete(existing_vote)
                
                if vote_type == ForumPostVoteType.UPVOTE:
                    post.upvote_count -= 1
                else:
                    post.downvote_count -= 1
                post.vote_score = post.upvote_count - post.downvote_count
                
                await self.session.commit()
                
                return {
                    "upvotes": post.upvote_count,
                    "downvotes": post.downvote_count,
                    "score": post.vote_score,
                    "user_vote": None,
                }
            else:
                # Different vote = change it
                await self._reverse_post_vote_karma(post, existing_vote.vote_type)
                
                # Update counters
                if existing_vote.vote_type == ForumPostVoteType.UPVOTE:
                    post.upvote_count -= 1
                else:
                    post.downvote_count -= 1
                
                existing_vote.vote_type = vote_type
                existing_vote.created_at = datetime.now(timezone.utc)
        else:
            # New vote
            vote = ForumPostVote(
                user_id=user.id,
                post_id=post_id,
                vote_type=vote_type,
            )
            self.session.add(vote)
        
        # Update counters
        if vote_type == ForumPostVoteType.UPVOTE:
            post.upvote_count += 1
        else:
            post.downvote_count += 1
        post.vote_score = post.upvote_count - post.downvote_count
        
        # Award/deduct karma
        await self._apply_post_vote_karma(post, vote_type)
        
        await self.session.commit()
        
        user_vote = "upvote" if vote_type == ForumPostVoteType.UPVOTE else "downvote"
        return {
            "upvotes": post.upvote_count,
            "downvotes": post.downvote_count,
            "score": post.vote_score,
            "user_vote": user_vote,
        }
    
    async def _apply_topic_vote_karma(
        self,
        topic: ForumTopic,
        vote_type: ForumPostVoteType,
    ) -> None:
        """Apply karma to topic author based on vote."""
        if topic.author_id is None:
            return
        
        reason = (
            KarmaReason.FORUM_TOPIC_UPVOTED
            if vote_type == ForumPostVoteType.UPVOTE
            else KarmaReason.FORUM_TOPIC_DOWNVOTED
        )
        
        await self.karma_service.award_karma(
            user_id=topic.author_id,
            reason=reason,
            related_entity_type="forum_topic",
            related_entity_id=topic.id,
        )
    
    async def _reverse_topic_vote_karma(
        self,
        topic: ForumTopic,
        vote_type: ForumPostVoteType,
    ) -> None:
        """Reverse karma when a vote is removed."""
        if topic.author_id is None:
            return
        
        # Reverse the karma (opposite of what was given)
        reason = (
            KarmaReason.FORUM_TOPIC_UPVOTED
            if vote_type == ForumPostVoteType.UPVOTE
            else KarmaReason.FORUM_TOPIC_DOWNVOTED
        )
        
        # Get the original delta and reverse it
        from app.services.karma import KARMA_REWARDS
        original_delta = KARMA_REWARDS.get(reason, 0)
        
        await self.karma_service.award_karma(
            user_id=topic.author_id,
            reason=reason,
            delta=-original_delta,  # Reverse it
            related_entity_type="forum_topic_vote_reversal",
            related_entity_id=topic.id,
        )
    
    async def _apply_post_vote_karma(
        self,
        post: ForumPost,
        vote_type: ForumPostVoteType,
    ) -> None:
        """Apply karma to post author based on vote."""
        if post.author_id is None:
            return
        
        reason = (
            KarmaReason.FORUM_POST_UPVOTED
            if vote_type == ForumPostVoteType.UPVOTE
            else KarmaReason.FORUM_POST_DOWNVOTED
        )
        
        await self.karma_service.award_karma(
            user_id=post.author_id,
            reason=reason,
            related_entity_type="forum_post",
            related_entity_id=post.id,
        )
    
    async def _reverse_post_vote_karma(
        self,
        post: ForumPost,
        vote_type: ForumPostVoteType,
    ) -> None:
        """Reverse karma when a vote is removed."""
        if post.author_id is None:
            return
        
        reason = (
            KarmaReason.FORUM_POST_UPVOTED
            if vote_type == ForumPostVoteType.UPVOTE
            else KarmaReason.FORUM_POST_DOWNVOTED
        )
        
        from app.services.karma import KARMA_REWARDS
        original_delta = KARMA_REWARDS.get(reason, 0)
        
        await self.karma_service.award_karma(
            user_id=post.author_id,
            reason=reason,
            delta=-original_delta,
            related_entity_type="forum_post_vote_reversal",
            related_entity_id=post.id,
        )
    
    async def _get_topic_vote_counts(
        self,
        topic_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> dict:
        """Get vote counts for a topic."""
        # Get upvote count
        up_result = await self.session.execute(
            select(func.count())
            .select_from(ForumTopicVote)
            .where(
                ForumTopicVote.topic_id == topic_id,
                ForumTopicVote.vote_type == ForumPostVoteType.UPVOTE,
            )
        )
        upvotes = up_result.scalar()
        
        # Get downvote count
        down_result = await self.session.execute(
            select(func.count())
            .select_from(ForumTopicVote)
            .where(
                ForumTopicVote.topic_id == topic_id,
                ForumTopicVote.vote_type == ForumPostVoteType.DOWNVOTE,
            )
        )
        downvotes = down_result.scalar()
        
        user_vote = None
        if user_id:
            vote_result = await self.session.execute(
                select(ForumTopicVote.vote_type).where(
                    ForumTopicVote.topic_id == topic_id,
                    ForumTopicVote.user_id == user_id,
                )
            )
            vote = vote_result.scalar_one_or_none()
            if vote:
                user_vote = "upvote" if vote == ForumPostVoteType.UPVOTE else "downvote"
        
        return {
            "upvotes": upvotes,
            "downvotes": downvotes,
            "score": upvotes - downvotes,
            "user_vote": user_vote,
        }
    
    # =========================================================================
    # Poll Operations
    # =========================================================================
    
    async def _create_poll(
        self,
        topic_id: uuid.UUID,
        poll_data: dict,
    ) -> ForumPoll:
        """Create a poll for a topic."""
        poll = ForumPoll(
            topic_id=topic_id,
            title=poll_data["title"],
            max_options=poll_data.get("max_options", 1),
            allow_vote_change=poll_data.get("allow_vote_change", True),
            hide_results_until_end=poll_data.get("hide_results", False),
            ends_at=poll_data.get("ends_at"),
        )
        self.session.add(poll)
        await self.session.flush()
        
        # Create options
        for i, option_text in enumerate(poll_data.get("options", [])):
            option = ForumPollOption(
                poll_id=poll.id,
                text=option_text,
                display_order=i,
            )
            self.session.add(option)
        
        return poll
    
    async def vote_on_poll(
        self,
        poll_id: uuid.UUID,
        user: User,
        option_ids: list[uuid.UUID],
    ) -> ForumPoll:
        """Vote on a poll."""
        result = await self.session.execute(
            select(ForumPoll)
            .options(selectinload(ForumPoll.options))
            .where(ForumPoll.id == poll_id)
        )
        poll = result.scalar_one_or_none()
        if poll is None:
            raise PollNotFoundError(f"Poll {poll_id} not found")
        
        # Check if poll has ended
        if poll.ends_at and poll.ends_at < datetime.now(timezone.utc):
            raise PollEndedError("This poll has ended")
        
        # Check max options
        if len(option_ids) > poll.max_options:
            raise ForumError(f"Maximum {poll.max_options} options allowed")
        
        # Check for existing votes
        existing_result = await self.session.execute(
            select(ForumPollVote)
            .join(ForumPollOption)
            .where(
                ForumPollVote.user_id == user.id,
                ForumPollOption.poll_id == poll_id,
            )
        )
        existing_votes = list(existing_result.scalars().all())
        
        if existing_votes and not poll.allow_vote_change:
            raise PollVoteChangeError("This poll does not allow changing votes")
        
        # Remove existing votes
        for vote in existing_votes:
            # Decrement option count
            for opt in poll.options:
                if opt.id == vote.option_id:
                    opt.vote_count = max(0, opt.vote_count - 1)
            await self.session.delete(vote)
        
        # Add new votes
        for option_id in option_ids:
            vote = ForumPollVote(
                user_id=user.id,
                option_id=option_id,
            )
            self.session.add(vote)
            
            # Increment option count
            for opt in poll.options:
                if opt.id == option_id:
                    opt.vote_count += 1
        
        # Update total votes (unique voters)
        total_result = await self.session.execute(
            select(func.count(func.distinct(ForumPollVote.user_id)))
            .select_from(ForumPollVote)
            .join(ForumPollOption)
            .where(ForumPollOption.poll_id == poll_id)
        )
        poll.total_votes = total_result.scalar() or 0
        
        await self.session.commit()
        await self.session.refresh(poll)
        
        return poll
    
    async def get_poll_results(
        self,
        poll_id: uuid.UUID,
        user: Optional[User] = None,
    ) -> dict:
        """Get poll results."""
        result = await self.session.execute(
            select(ForumPoll)
            .options(selectinload(ForumPoll.options))
            .where(ForumPoll.id == poll_id)
        )
        poll = result.scalar_one_or_none()
        if poll is None:
            raise PollNotFoundError(f"Poll {poll_id} not found")
        
        # Check if results are hidden
        now = datetime.now(timezone.utc)
        results_hidden = (
            poll.hide_results_until_end
            and poll.ends_at
            and poll.ends_at > now
        )
        
        user_votes = []
        if user:
            votes_result = await self.session.execute(
                select(ForumPollVote.option_id)
                .join(ForumPollOption)
                .where(
                    ForumPollVote.user_id == user.id,
                    ForumPollOption.poll_id == poll_id,
                )
            )
            user_votes = [str(v) for v in votes_result.scalars().all()]
        
        options_data = []
        for opt in sorted(poll.options, key=lambda o: o.display_order):
            options_data.append({
                "id": str(opt.id),
                "text": opt.text,
                "vote_count": 0 if results_hidden else opt.vote_count,
                "percentage": (
                    0 if results_hidden or poll.total_votes == 0
                    else round(opt.vote_count / poll.total_votes * 100, 1)
                ),
            })
        
        return {
            "id": str(poll.id),
            "title": poll.title,
            "max_options": poll.max_options,
            "allow_vote_change": poll.allow_vote_change,
            "total_votes": 0 if results_hidden else poll.total_votes,
            "results_hidden": results_hidden,
            "ends_at": poll.ends_at.isoformat() if poll.ends_at else None,
            "has_ended": poll.ends_at and poll.ends_at < now,
            "options": options_data,
            "user_votes": user_votes,
        }
    
    # =========================================================================
    # Topic Watch Operations
    # =========================================================================
    
    async def watch_topic(
        self,
        topic_id: uuid.UUID,
        user: User,
        notify: bool = True,
    ) -> ForumTopicWatch:
        """Watch a topic for notifications."""
        result = await self.session.execute(
            select(ForumTopicWatch).where(
                ForumTopicWatch.user_id == user.id,
                ForumTopicWatch.topic_id == topic_id,
            )
        )
        watch = result.scalar_one_or_none()
        
        if watch:
            watch.notify_on_reply = notify
        else:
            watch = ForumTopicWatch(
                user_id=user.id,
                topic_id=topic_id,
                notify_on_reply=notify,
                last_read_at=datetime.now(timezone.utc),
            )
            self.session.add(watch)
        
        await self.session.commit()
        await self.session.refresh(watch)
        return watch
    
    async def unwatch_topic(
        self,
        topic_id: uuid.UUID,
        user: User,
    ) -> None:
        """Stop watching a topic."""
        result = await self.session.execute(
            select(ForumTopicWatch).where(
                ForumTopicWatch.user_id == user.id,
                ForumTopicWatch.topic_id == topic_id,
            )
        )
        watch = result.scalar_one_or_none()
        
        if watch:
            await self.session.delete(watch)
            await self.session.commit()
    
    async def get_watched_topics(
        self,
        user: User,
        limit: int = 25,
        offset: int = 0,
        unread_only: bool = False,
    ) -> tuple[list[ForumTopic], int]:
        """Get topics the user is watching."""
        base_query = (
            select(ForumTopic)
            .join(ForumTopicWatch, ForumTopicWatch.topic_id == ForumTopic.id)
            .where(
                ForumTopicWatch.user_id == user.id,
                ForumTopic.deleted_at.is_(None),
            )
        )
        
        if unread_only:
            base_query = base_query.where(
                or_(
                    ForumTopicWatch.last_read_at.is_(None),
                    ForumTopic.last_post_at > ForumTopicWatch.last_read_at,
                )
            )
        
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar()
        
        query = (
            base_query
            .options(selectinload(ForumTopic.author), selectinload(ForumTopic.forum))
            .order_by(ForumTopic.last_post_at.desc().nulls_last())
            .limit(limit)
            .offset(offset)
        )
        
        result = await self.session.execute(query)
        topics = list(result.scalars().all())
        
        return topics, total
    
    async def mark_topic_read(
        self,
        topic_id: uuid.UUID,
        user: User,
    ) -> None:
        """Mark a topic as read."""
        result = await self.session.execute(
            select(ForumTopicWatch).where(
                ForumTopicWatch.user_id == user.id,
                ForumTopicWatch.topic_id == topic_id,
            )
        )
        watch = result.scalar_one_or_none()
        
        if watch:
            watch.last_read_at = datetime.now(timezone.utc)
            await self.session.commit()
    
    # =========================================================================
    # Search Operations
    # =========================================================================
    
    async def search_topics(
        self,
        query: str,
        forum_id: Optional[uuid.UUID] = None,
        author_id: Optional[uuid.UUID] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[ForumTopic], int]:
        """Search topics by title and content."""
        search_term = f"%{query}%"
        
        base_query = select(ForumTopic).where(
            ForumTopic.deleted_at.is_(None),
            or_(
                ForumTopic.title.ilike(search_term),
                ForumTopic.content.ilike(search_term),
            ),
        )
        
        if forum_id:
            base_query = base_query.where(ForumTopic.forum_id == forum_id)
        if author_id:
            base_query = base_query.where(ForumTopic.author_id == author_id)
        
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar()
        
        query_result = (
            base_query
            .options(selectinload(ForumTopic.author), selectinload(ForumTopic.forum))
            .order_by(ForumTopic.last_post_at.desc().nulls_last())
            .limit(limit)
            .offset(offset)
        )
        
        result = await self.session.execute(query_result)
        topics = list(result.scalars().all())
        
        return topics, total
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    async def get_forum_stats(self) -> dict:
        """Get overall forum statistics."""
        topic_count = await self.session.execute(
            select(func.count())
            .select_from(ForumTopic)
            .where(ForumTopic.deleted_at.is_(None))
        )
        
        post_count = await self.session.execute(
            select(func.count())
            .select_from(ForumPost)
            .where(ForumPost.deleted_at.is_(None))
        )
        
        return {
            "total_topics": topic_count.scalar(),
            "total_posts": post_count.scalar(),
        }
