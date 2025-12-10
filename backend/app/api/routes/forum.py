"""Forum API routes.

Provides endpoints for:
- Browsing categories and forums
- Creating, reading, updating topics
- Creating, reading, updating posts
- Voting on topics and posts
- Managing topic watches
- Poll voting
- Search
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, get_current_user_optional
from app.models.forum import ForumPostVoteType
from app.models.user import User
from app.services.forum import (
    ForumLockedError,
    ForumNotFoundError,
    ForumService,
    InsufficientPermissionError,
    PollEndedError,
    PollNotFoundError,
    PollVoteChangeError,
    PostNotFoundError,
    SelfVoteError,
    TopicLockedError,
    TopicNotFoundError,
)


router = APIRouter(prefix="/forum", tags=["forum"])


# =============================================================================
# Response Models
# =============================================================================


class UserSummary(BaseModel):
    """Brief user info for display."""
    id: str
    display_name: str
    avatar_url: Optional[str] = None
    karma_score: int


class CategoryResponse(BaseModel):
    """Forum category response."""
    id: str
    name: str
    description: Optional[str] = None
    display_order: int
    icon: Optional[str] = None
    color: Optional[str] = None
    forums: list["ForumSummaryResponse"] = []


class ForumSummaryResponse(BaseModel):
    """Brief forum info."""
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    topic_count: int
    post_count: int
    is_visible: bool = True
    allow_topics: bool = True  # Inverse of is_locked
    last_post_at: Optional[datetime] = None


class ForumResponse(BaseModel):
    """Detailed forum info."""
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    topic_count: int
    post_count: int
    min_karma_to_post: int
    min_karma_to_create_topic: int
    requires_email_verified: bool
    requires_phone_verified: bool
    allow_polls: bool
    enable_voting: bool
    is_locked: bool
    last_post_at: Optional[datetime] = None
    category: Optional["CategoryResponse"] = None


class TopicSummaryResponse(BaseModel):
    """Brief topic info for listing."""
    id: str
    title: str
    slug: str
    topic_type: str
    status: str
    view_count: int
    reply_count: int
    vote_score: int
    has_poll: bool
    author: Optional[UserSummary] = None
    created_at: datetime
    last_post_at: Optional[datetime] = None


class TopicResponse(BaseModel):
    """Detailed topic info."""
    id: str
    forum_id: str
    title: str
    slug: str
    content: str
    topic_type: str
    status: str
    tags: Optional[list[str]] = None
    view_count: int
    reply_count: int
    vote_score: int
    has_poll: bool
    author: Optional[UserSummary] = None
    forum: Optional[ForumSummaryResponse] = None
    created_at: datetime
    updated_at: datetime
    last_post_at: Optional[datetime] = None
    user_vote: Optional[str] = None  # "upvote", "downvote", or None
    poll: Optional["PollResponse"] = None


class PostResponse(BaseModel):
    """Forum post response."""
    id: str
    topic_id: str
    content: str
    position: int
    upvote_count: int
    downvote_count: int
    vote_score: int
    edit_count: int
    last_edited_at: Optional[datetime] = None
    edit_reason: Optional[str] = None
    author: Optional[UserSummary] = None
    created_at: datetime
    reply_to_id: Optional[str] = None
    user_vote: Optional[str] = None


class VoteResponse(BaseModel):
    """Vote action response."""
    upvotes: int
    downvotes: int
    score: int
    user_vote: Optional[str] = None


class PollOptionResponse(BaseModel):
    """Poll option response."""
    id: str
    text: str
    vote_count: int
    percentage: float


class PollResponse(BaseModel):
    """Poll response."""
    id: str
    title: str
    max_options: int
    allow_vote_change: bool
    total_votes: int
    results_hidden: bool
    ends_at: Optional[str] = None
    has_ended: bool
    options: list[PollOptionResponse]
    user_votes: list[str] = []


class TopicWatchResponse(BaseModel):
    """Topic watch status."""
    topic_id: str
    is_watching: bool
    notify_on_reply: bool


class ForumStatsResponse(BaseModel):
    """Forum statistics."""
    total_topics: int
    total_posts: int


class PaginatedTopicsResponse(BaseModel):
    """Paginated topic list."""
    items: list[TopicSummaryResponse]
    total: int
    limit: int
    offset: int


class PaginatedPostsResponse(BaseModel):
    """Paginated post list."""
    items: list[PostResponse]
    total: int
    limit: int
    offset: int


# =============================================================================
# Request Models
# =============================================================================


class CreateTopicRequest(BaseModel):
    """Request to create a topic."""
    title: str = Field(..., min_length=3, max_length=255)
    content: str = Field(..., min_length=10)
    tags: Optional[list[str]] = None
    poll: Optional["CreatePollRequest"] = None


class UpdateTopicRequest(BaseModel):
    """Request to update a topic."""
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    content: Optional[str] = Field(None, min_length=10)
    tags: Optional[list[str]] = None


class CreatePostRequest(BaseModel):
    """Request to create a post."""
    content: str = Field(..., min_length=1)
    reply_to_id: Optional[str] = None


class UpdatePostRequest(BaseModel):
    """Request to update a post."""
    content: str = Field(..., min_length=1)
    edit_reason: Optional[str] = Field(None, max_length=255)


class VoteRequest(BaseModel):
    """Vote action request."""
    action: str = Field(..., pattern="^(upvote|downvote)$")


class CreatePollRequest(BaseModel):
    """Request to create a poll with a topic."""
    title: str = Field(..., min_length=1, max_length=255)
    options: list[str] = Field(..., min_length=2, max_length=10)
    max_options: int = Field(1, ge=1)
    allow_vote_change: bool = True
    hide_results: bool = False
    length_days: Optional[int] = Field(None, ge=0)


class PollVoteRequest(BaseModel):
    """Request to vote on a poll."""
    option_ids: list[str]


class TopicSearchRequest(BaseModel):
    """Search request for topics."""
    query: str = Field(..., min_length=2)
    forum_id: Optional[str] = None


# Update forward references
CategoryResponse.model_rebuild()
ForumResponse.model_rebuild()
TopicResponse.model_rebuild()


# =============================================================================
# Helper Functions
# =============================================================================


def user_to_summary(user: Optional[User]) -> Optional[UserSummary]:
    """Convert user to summary."""
    if user is None:
        return None
    return UserSummary(
        id=str(user.id),
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        karma_score=user.karma_score,
    )


# =============================================================================
# Category Endpoints
# =============================================================================


@router.get("/categories", response_model=list[CategoryResponse])
async def get_categories(
    session: AsyncSession = Depends(get_db_session),
) -> list[CategoryResponse]:
    """Get all forum categories with their forums."""
    service = ForumService(session)
    categories = await service.get_all_categories()
    
    return [
        CategoryResponse(
            id=str(cat.id),
            name=cat.name,
            description=cat.description,
            display_order=cat.display_order,
            icon=cat.icon,
            color=cat.color,
            forums=[
                ForumSummaryResponse(
                    id=str(f.id),
                    name=f.name,
                    slug=f.slug,
                    description=f.description,
                    icon=f.icon,
                    color=f.color,
                    topic_count=f.topic_count,
                    post_count=f.post_count,
                    is_visible=f.is_visible,
                    allow_topics=not f.is_locked,  # Allow topics if not locked
                    last_post_at=f.last_post_at,
                )
                for f in cat.forums
            ],
        )
        for cat in categories
    ]


# =============================================================================
# Forum Endpoints
# =============================================================================


@router.get("/forums/{forum_slug}", response_model=ForumResponse)
async def get_forum(
    forum_slug: str,
    session: AsyncSession = Depends(get_db_session),
) -> ForumResponse:
    """Get forum details by slug."""
    service = ForumService(session)
    
    try:
        forum = await service.get_forum_by_slug(forum_slug)
    except ForumNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forum not found",
        )
    
    return ForumResponse(
        id=str(forum.id),
        name=forum.name,
        slug=forum.slug,
        description=forum.description,
        icon=forum.icon,
        color=forum.color,
        topic_count=forum.topic_count,
        post_count=forum.post_count,
        min_karma_to_post=forum.min_karma_to_post,
        min_karma_to_create_topic=forum.min_karma_to_create_topic,
        requires_email_verified=forum.requires_email_verified,
        requires_phone_verified=forum.requires_phone_verified,
        allow_polls=forum.allow_polls,
        enable_voting=forum.enable_voting,
        is_locked=forum.is_locked,
        last_post_at=forum.last_post_at,
        category=CategoryResponse(
            id=str(forum.category.id),
            name=forum.category.name,
            description=forum.category.description,
            display_order=forum.category.display_order,
            icon=forum.category.icon,
            color=forum.category.color,
        ) if forum.category else None,
    )


@router.get("/forums/{forum_slug}/topics", response_model=PaginatedTopicsResponse)
async def get_forum_topics(
    forum_slug: str,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedTopicsResponse:
    """Get topics in a forum."""
    service = ForumService(session)
    
    try:
        forum = await service.get_forum_by_slug(forum_slug)
        topics, total = await service.get_forum_topics(forum.id, limit, offset)
    except ForumNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forum not found",
        )
    
    return PaginatedTopicsResponse(
        items=[
            TopicSummaryResponse(
                id=str(t.id),
                title=t.title,
                slug=t.slug,
                topic_type=t.topic_type.value,
                status=t.status.value,
                view_count=t.view_count,
                reply_count=t.reply_count,
                vote_score=t.vote_score,
                has_poll=t.has_poll,
                author=user_to_summary(t.author),
                created_at=t.created_at,
                last_post_at=t.last_post_at,
            )
            for t in topics
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


# =============================================================================
# Topic Endpoints
# =============================================================================


@router.post("/forums/{forum_slug}/topics", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
    forum_slug: str,
    payload: CreateTopicRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> TopicResponse:
    """Create a new topic in a forum."""
    service = ForumService(session)
    
    try:
        forum = await service.get_forum_by_slug(forum_slug)
        
        # Prepare poll data if provided
        poll_data = None
        if payload.poll:
            from datetime import timedelta, timezone
            ends_at = None
            if payload.poll.length_days:
                ends_at = datetime.now(timezone.utc) + timedelta(days=payload.poll.length_days)
            
            poll_data = {
                "title": payload.poll.title,
                "options": payload.poll.options,
                "max_options": payload.poll.max_options,
                "allow_vote_change": payload.poll.allow_vote_change,
                "hide_results": payload.poll.hide_results,
                "ends_at": ends_at,
            }
        
        topic = await service.create_topic(
            forum_id=forum.id,
            author=current_user,
            title=payload.title,
            content=payload.content,
            tags=payload.tags,
            poll_data=poll_data,
        )
    except ForumNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forum not found",
        )
    except ForumLockedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This forum is locked",
        )
    except InsufficientPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    
    return TopicResponse(
        id=str(topic.id),
        forum_id=str(topic.forum_id),
        title=topic.title,
        slug=topic.slug,
        content=topic.content,
        topic_type=topic.topic_type.value,
        status=topic.status.value,
        tags=topic.tags.split(",") if topic.tags else None,
        view_count=topic.view_count,
        reply_count=topic.reply_count,
        vote_score=topic.vote_score,
        has_poll=topic.has_poll,
        author=user_to_summary(current_user),
        created_at=topic.created_at,
        updated_at=topic.updated_at,
        last_post_at=topic.last_post_at,
    )


@router.get("/topics/{topic_id}", response_model=TopicResponse)
async def get_topic(
    topic_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> TopicResponse:
    """Get a topic by ID."""
    service = ForumService(session)
    
    try:
        topic = await service.get_topic(uuid.UUID(topic_id), increment_views=True)
    except (TopicNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    # Get user's vote if logged in
    user_vote = None
    poll_response = None
    
    if current_user:
        vote_counts = await service._get_topic_vote_counts(topic.id, current_user.id)
        user_vote = vote_counts.get("user_vote")
        
        # Mark as read if watching
        await service.mark_topic_read(topic.id, current_user)
    
    # Get poll if exists
    if topic.has_poll and topic.poll:
        poll_data = await service.get_poll_results(topic.poll.id, current_user)
        poll_response = PollResponse(
            id=poll_data["id"],
            title=poll_data["title"],
            max_options=poll_data["max_options"],
            allow_vote_change=poll_data["allow_vote_change"],
            total_votes=poll_data["total_votes"],
            results_hidden=poll_data["results_hidden"],
            ends_at=poll_data["ends_at"],
            has_ended=poll_data["has_ended"],
            options=[
                PollOptionResponse(
                    id=opt["id"],
                    text=opt["text"],
                    vote_count=opt["vote_count"],
                    percentage=opt["percentage"],
                )
                for opt in poll_data["options"]
            ],
            user_votes=poll_data["user_votes"],
        )
    
    return TopicResponse(
        id=str(topic.id),
        forum_id=str(topic.forum_id),
        title=topic.title,
        slug=topic.slug,
        content=topic.content,
        topic_type=topic.topic_type.value,
        status=topic.status.value,
        tags=topic.tags.split(",") if topic.tags else None,
        view_count=topic.view_count,
        reply_count=topic.reply_count,
        vote_score=topic.vote_score,
        has_poll=topic.has_poll,
        author=user_to_summary(topic.author),
        forum=ForumSummaryResponse(
            id=str(topic.forum.id),
            name=topic.forum.name,
            slug=topic.forum.slug,
            description=topic.forum.description,
            icon=topic.forum.icon,
            color=topic.forum.color,
            topic_count=topic.forum.topic_count,
            post_count=topic.forum.post_count,
            last_post_at=topic.forum.last_post_at,
        ) if topic.forum else None,
        created_at=topic.created_at,
        updated_at=topic.updated_at,
        last_post_at=topic.last_post_at,
        user_vote=user_vote,
        poll=poll_response,
    )


@router.patch("/topics/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: str,
    payload: UpdateTopicRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> TopicResponse:
    """Update a topic."""
    service = ForumService(session)
    
    try:
        topic = await service.update_topic(
            topic_id=uuid.UUID(topic_id),
            user=current_user,
            title=payload.title,
            content=payload.content,
            tags=payload.tags,
        )
    except (TopicNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    except InsufficientPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    
    return TopicResponse(
        id=str(topic.id),
        forum_id=str(topic.forum_id),
        title=topic.title,
        slug=topic.slug,
        content=topic.content,
        topic_type=topic.topic_type.value,
        status=topic.status.value,
        tags=topic.tags.split(",") if topic.tags else None,
        view_count=topic.view_count,
        reply_count=topic.reply_count,
        vote_score=topic.vote_score,
        has_poll=topic.has_poll,
        author=user_to_summary(topic.author),
        created_at=topic.created_at,
        updated_at=topic.updated_at,
        last_post_at=topic.last_post_at,
    )


@router.delete("/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_topic(
    topic_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a topic (soft delete)."""
    service = ForumService(session)
    
    try:
        await service.delete_topic(uuid.UUID(topic_id), current_user)
    except (TopicNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    except InsufficientPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


# =============================================================================
# Post Endpoints
# =============================================================================


@router.get("/topics/{topic_id}/posts", response_model=PaginatedPostsResponse)
async def get_topic_posts(
    topic_id: str,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> PaginatedPostsResponse:
    """Get posts in a topic."""
    service = ForumService(session)
    
    try:
        posts, total = await service.get_topic_posts(uuid.UUID(topic_id), limit, offset)
    except (TopicNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    # Get user votes for these posts
    user_votes = {}
    if current_user:
        from app.models.forum import ForumPostVote
        from sqlalchemy import select
        
        post_ids = [p.id for p in posts]
        result = await session.execute(
            select(ForumPostVote.post_id, ForumPostVote.vote_type).where(
                ForumPostVote.user_id == current_user.id,
                ForumPostVote.post_id.in_(post_ids),
            )
        )
        for row in result.all():
            user_votes[str(row.post_id)] = (
                "upvote" if row.vote_type == ForumPostVoteType.UPVOTE else "downvote"
            )
    
    return PaginatedPostsResponse(
        items=[
            PostResponse(
                id=str(p.id),
                topic_id=str(p.topic_id),
                content=p.content,
                position=p.position,
                upvote_count=p.upvote_count,
                downvote_count=p.downvote_count,
                vote_score=p.vote_score,
                edit_count=p.edit_count,
                last_edited_at=p.last_edited_at,
                edit_reason=p.edit_reason,
                author=user_to_summary(p.author),
                created_at=p.created_at,
                reply_to_id=str(p.reply_to_id) if p.reply_to_id else None,
                user_vote=user_votes.get(str(p.id)),
            )
            for p in posts
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/topics/{topic_id}/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    topic_id: str,
    payload: CreatePostRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Create a new post/reply in a topic."""
    service = ForumService(session)
    
    try:
        reply_to = uuid.UUID(payload.reply_to_id) if payload.reply_to_id else None
        post = await service.create_post(
            topic_id=uuid.UUID(topic_id),
            author=current_user,
            content=payload.content,
            reply_to_id=reply_to,
        )
    except (TopicNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    except TopicLockedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This topic is locked",
        )
    except InsufficientPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    
    return PostResponse(
        id=str(post.id),
        topic_id=str(post.topic_id),
        content=post.content,
        position=post.position,
        upvote_count=post.upvote_count,
        downvote_count=post.downvote_count,
        vote_score=post.vote_score,
        edit_count=post.edit_count,
        last_edited_at=post.last_edited_at,
        edit_reason=post.edit_reason,
        author=user_to_summary(current_user),
        created_at=post.created_at,
        reply_to_id=str(post.reply_to_id) if post.reply_to_id else None,
    )


@router.patch("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: str,
    payload: UpdatePostRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Update a post."""
    service = ForumService(session)
    
    try:
        post = await service.update_post(
            post_id=uuid.UUID(post_id),
            user=current_user,
            content=payload.content,
            edit_reason=payload.edit_reason,
        )
    except (PostNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    except InsufficientPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    
    return PostResponse(
        id=str(post.id),
        topic_id=str(post.topic_id),
        content=post.content,
        position=post.position,
        upvote_count=post.upvote_count,
        downvote_count=post.downvote_count,
        vote_score=post.vote_score,
        edit_count=post.edit_count,
        last_edited_at=post.last_edited_at,
        edit_reason=post.edit_reason,
        author=user_to_summary(post.author),
        created_at=post.created_at,
        reply_to_id=str(post.reply_to_id) if post.reply_to_id else None,
    )


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_post(
    post_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a post (soft delete)."""
    service = ForumService(session)
    
    try:
        await service.delete_post(uuid.UUID(post_id), current_user)
    except (PostNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    except InsufficientPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


# =============================================================================
# Voting Endpoints
# =============================================================================


@router.post("/topics/{topic_id}/vote", response_model=VoteResponse)
async def vote_on_topic(
    topic_id: str,
    payload: VoteRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> VoteResponse:
    """Vote on a topic."""
    service = ForumService(session)
    
    vote_type = (
        ForumPostVoteType.UPVOTE
        if payload.action == "upvote"
        else ForumPostVoteType.DOWNVOTE
    )
    
    try:
        result = await service.vote_on_topic(uuid.UUID(topic_id), current_user, vote_type)
    except (TopicNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    except SelfVoteError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot vote on your own topic",
        )
    except InsufficientPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    
    return VoteResponse(**result)


@router.post("/posts/{post_id}/vote", response_model=VoteResponse)
async def vote_on_post(
    post_id: str,
    payload: VoteRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> VoteResponse:
    """Vote on a post."""
    service = ForumService(session)
    
    vote_type = (
        ForumPostVoteType.UPVOTE
        if payload.action == "upvote"
        else ForumPostVoteType.DOWNVOTE
    )
    
    try:
        result = await service.vote_on_post(uuid.UUID(post_id), current_user, vote_type)
    except (PostNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    except SelfVoteError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot vote on your own post",
        )
    except InsufficientPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    
    return VoteResponse(**result)


# =============================================================================
# Poll Endpoints
# =============================================================================


@router.post("/polls/{poll_id}/vote", response_model=PollResponse)
async def vote_on_poll(
    poll_id: str,
    payload: PollVoteRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> PollResponse:
    """Vote on a poll."""
    service = ForumService(session)
    
    try:
        option_ids = [uuid.UUID(oid) for oid in payload.option_ids]
        poll = await service.vote_on_poll(uuid.UUID(poll_id), current_user, option_ids)
        poll_data = await service.get_poll_results(poll.id, current_user)
    except (PollNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Poll not found",
        )
    except PollEndedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This poll has ended",
        )
    except PollVoteChangeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This poll does not allow changing votes",
        )
    except ForumService as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return PollResponse(
        id=poll_data["id"],
        title=poll_data["title"],
        max_options=poll_data["max_options"],
        allow_vote_change=poll_data["allow_vote_change"],
        total_votes=poll_data["total_votes"],
        results_hidden=poll_data["results_hidden"],
        ends_at=poll_data["ends_at"],
        has_ended=poll_data["has_ended"],
        options=[
            PollOptionResponse(
                id=opt["id"],
                text=opt["text"],
                vote_count=opt["vote_count"],
                percentage=opt["percentage"],
            )
            for opt in poll_data["options"]
        ],
        user_votes=poll_data["user_votes"],
    )


@router.get("/polls/{poll_id}", response_model=PollResponse)
async def get_poll(
    poll_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> PollResponse:
    """Get poll details and results."""
    service = ForumService(session)
    
    try:
        poll_data = await service.get_poll_results(uuid.UUID(poll_id), current_user)
    except (PollNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Poll not found",
        )
    
    return PollResponse(
        id=poll_data["id"],
        title=poll_data["title"],
        max_options=poll_data["max_options"],
        allow_vote_change=poll_data["allow_vote_change"],
        total_votes=poll_data["total_votes"],
        results_hidden=poll_data["results_hidden"],
        ends_at=poll_data["ends_at"],
        has_ended=poll_data["has_ended"],
        options=[
            PollOptionResponse(
                id=opt["id"],
                text=opt["text"],
                vote_count=opt["vote_count"],
                percentage=opt["percentage"],
            )
            for opt in poll_data["options"]
        ],
        user_votes=poll_data["user_votes"],
    )


# =============================================================================
# Watch Endpoints
# =============================================================================


@router.post("/topics/{topic_id}/watch", response_model=TopicWatchResponse)
async def watch_topic(
    topic_id: str,
    notify: bool = Query(True),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> TopicWatchResponse:
    """Watch a topic for notifications."""
    service = ForumService(session)
    
    try:
        watch = await service.watch_topic(uuid.UUID(topic_id), current_user, notify)
    except (TopicNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )
    
    return TopicWatchResponse(
        topic_id=str(topic_id),
        is_watching=True,
        notify_on_reply=watch.notify_on_reply,
    )


@router.delete("/topics/{topic_id}/watch", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def unwatch_topic(
    topic_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Stop watching a topic."""
    service = ForumService(session)
    
    try:
        await service.unwatch_topic(uuid.UUID(topic_id), current_user)
    except (TopicNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Topic not found",
        )


@router.get("/watched", response_model=PaginatedTopicsResponse)
async def get_watched_topics(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> PaginatedTopicsResponse:
    """Get topics the user is watching."""
    service = ForumService(session)
    
    topics, total = await service.get_watched_topics(
        current_user, limit, offset, unread_only
    )
    
    return PaginatedTopicsResponse(
        items=[
            TopicSummaryResponse(
                id=str(t.id),
                title=t.title,
                slug=t.slug,
                topic_type=t.topic_type.value,
                status=t.status.value,
                view_count=t.view_count,
                reply_count=t.reply_count,
                vote_score=t.vote_score,
                has_poll=t.has_poll,
                author=user_to_summary(t.author),
                created_at=t.created_at,
                last_post_at=t.last_post_at,
            )
            for t in topics
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


# =============================================================================
# Search Endpoints
# =============================================================================


@router.get("/search", response_model=PaginatedTopicsResponse)
async def search_topics(
    q: str = Query(..., min_length=2),
    forum_id: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedTopicsResponse:
    """Search for topics."""
    service = ForumService(session)
    
    forum_uuid = uuid.UUID(forum_id) if forum_id else None
    
    topics, total = await service.search_topics(
        query=q,
        forum_id=forum_uuid,
        limit=limit,
        offset=offset,
    )
    
    return PaginatedTopicsResponse(
        items=[
            TopicSummaryResponse(
                id=str(t.id),
                title=t.title,
                slug=t.slug,
                topic_type=t.topic_type.value,
                status=t.status.value,
                view_count=t.view_count,
                reply_count=t.reply_count,
                vote_score=t.vote_score,
                has_poll=t.has_poll,
                author=user_to_summary(t.author),
                created_at=t.created_at,
                last_post_at=t.last_post_at,
            )
            for t in topics
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


# =============================================================================
# Stats Endpoints
# =============================================================================


@router.get("/stats", response_model=ForumStatsResponse)
async def get_forum_stats(
    session: AsyncSession = Depends(get_db_session),
) -> ForumStatsResponse:
    """Get overall forum statistics."""
    service = ForumService(session)
    stats = await service.get_forum_stats()
    
    return ForumStatsResponse(
        total_topics=stats["total_topics"],
        total_posts=stats["total_posts"],
    )
