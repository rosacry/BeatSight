"""Global Search API routes - unified search across users, songs, forum, and docs.

Inspired by osu!'s unified search experience.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user_optional, get_db_session
from app.models.user import User
from app.models.song import Song, SongStatus
from app.models.forum import ForumTopic, ForumPost

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


# =============================================================================
# Response Models
# =============================================================================


class UserSearchItem(BaseModel):
    """User search result item."""
    id: str
    display_name: str
    username: str
    avatar_url: Optional[str] = None
    karma_score: int = 0

    model_config = {"from_attributes": True}


class MapSearchItem(BaseModel):
    """Beatmap search result item."""
    id: str
    song_id: str
    title: str
    artist: str
    creator_name: str
    creator_id: str
    is_verified: bool = False
    difficulty_rating: Optional[float] = None
    cover_url: Optional[str] = None

    model_config = {"from_attributes": True}


class ForumSearchItem(BaseModel):
    """Forum topic/post search result item."""
    id: str
    title: str
    content_preview: str
    author_name: str
    author_id: str
    forum_name: str
    forum_slug: str
    post_count: int = 0
    created_at: str

    model_config = {"from_attributes": True}


class GlobalSearchResponse(BaseModel):
    """Global search response with categorized results."""
    query: str
    users: list[UserSearchItem]
    users_total: int
    maps: list[MapSearchItem]
    maps_total: int
    forum_topics: list[ForumSearchItem]
    forum_topics_total: int


# =============================================================================
# Search Endpoints
# =============================================================================


@router.get("/global", response_model=GlobalSearchResponse)
async def global_search(
    q: str = Query(min_length=1, max_length=100, description="Search query"),
    limit: int = Query(default=5, ge=1, le=20, description="Results per category"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_current_user_optional),
) -> GlobalSearchResponse:
    """
    Global search across users, maps, and forum.
    
    Returns top results from each category for quick search display.
    """
    search_term = f"%{q.lower()}%"
    
    # Search Users (User model doesn't have deleted_at - uses restriction_level instead)
    user_query = (
        select(User)
        .where(
            and_(
                User.restriction_level != 'banned',
                or_(
                    func.lower(User.display_name).like(search_term),
                    func.lower(User.email).like(search_term)
                )
            )
        )
        .order_by(User.karma_score.desc())
        .limit(limit)
    )
    user_count_query = (
        select(func.count())
        .select_from(User)
        .where(
            and_(
                User.restriction_level != 'banned',
                or_(
                    func.lower(User.display_name).like(search_term),
                    func.lower(User.email).like(search_term)
                )
            )
        )
    )
    
    # Search Songs/Maps
    map_query = (
        select(Song)
        .options(selectinload(Song.creator))
        .where(
            or_(
                func.lower(Song.title).like(search_term),
                func.lower(Song.artist).like(search_term)
            )
        )
        .order_by(Song.created_at.desc())
        .limit(limit)
    )
    map_count_query = (
        select(func.count())
        .select_from(Song)
        .where(
            or_(
                func.lower(Song.title).like(search_term),
                func.lower(Song.artist).like(search_term)
            )
        )
    )
    
    # Search Forum Topics
    forum_query = (
        select(ForumTopic)
        .options(
            selectinload(ForumTopic.author),
            selectinload(ForumTopic.forum)
        )
        .where(
            and_(
                ForumTopic.deleted_at.is_(None),
                or_(
                    func.lower(ForumTopic.title).like(search_term),
                    func.lower(ForumTopic.content).like(search_term)
                )
            )
        )
        .order_by(ForumTopic.created_at.desc())
        .limit(limit)
    )
    forum_count_query = (
        select(func.count())
        .select_from(ForumTopic)
        .where(
            and_(
                ForumTopic.deleted_at.is_(None),
                or_(
                    func.lower(ForumTopic.title).like(search_term),
                    func.lower(ForumTopic.content).like(search_term)
                )
            )
        )
    )
    
    # Execute all queries
    users_result = await db.execute(user_query)
    users = users_result.scalars().all()
    users_count_result = await db.execute(user_count_query)
    users_total = users_count_result.scalar() or 0
    
    maps_result = await db.execute(map_query)
    songs = maps_result.scalars().all()
    maps_count_result = await db.execute(map_count_query)
    maps_total = maps_count_result.scalar() or 0
    
    forum_result = await db.execute(forum_query)
    topics = forum_result.scalars().all()
    forum_count_result = await db.execute(forum_count_query)
    forum_total = forum_count_result.scalar() or 0
    
    # Transform results
    user_items = [
        UserSearchItem(
            id=str(u.id),
            display_name=u.display_name,
            username=u.display_name.lower().replace(" ", "_"),
            avatar_url=u.avatar_url,
            karma_score=u.karma_score or 0
        )
        for u in users
    ]
    
    map_items = [
        MapSearchItem(
            id=str(s.id),
            song_id=str(s.id),
            title=s.title,
            artist=s.artist or "Unknown Artist",
            creator_name=s.owner.display_name if s.owner else "Unknown",
            creator_id=str(s.owner_id) if s.owner_id else "",
            is_verified=getattr(s, 'is_verified', False),
            difficulty_rating=None,
            cover_url=s.cover_url if hasattr(s, 'cover_url') else None
        )
        for s in songs
    ]
    
    forum_items = [
        ForumSearchItem(
            id=str(t.id),
            title=t.title,
            content_preview=t.content[:150] + "..." if len(t.content) > 150 else t.content,
            author_name=t.author.display_name if t.author else "Unknown",
            author_id=str(t.author_id) if t.author_id else "",
            forum_name=t.forum.name if t.forum else "Unknown",
            forum_slug=t.forum.slug if t.forum else "general",
            post_count=t.post_count or 0,
            created_at=t.created_at.isoformat() if t.created_at else ""
        )
        for t in topics
    ]
    
    return GlobalSearchResponse(
        query=q,
        users=user_items,
        users_total=users_total,
        maps=map_items,
        maps_total=maps_total,
        forum_topics=forum_items,
        forum_topics_total=forum_total,
    )


@router.get("/users", response_model=dict)
async def search_users_extended(
    q: str = Query(min_length=1, max_length=100, description="Search query"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict:
    """Extended user search with pagination."""
    search_term = f"%{q.lower()}%"
    offset = (page - 1) * page_size
    
    # User model uses restriction_level instead of deleted_at
    query = (
        select(User)
        .where(
            and_(
                User.restriction_level != 'banned',
                or_(
                    func.lower(User.display_name).like(search_term),
                    func.lower(User.email).like(search_term)
                )
            )
        )
        .order_by(User.karma_score.desc())
        .offset(offset)
        .limit(page_size)
    )
    
    count_query = (
        select(func.count())
        .select_from(User)
        .where(
            and_(
                User.restriction_level != 'banned',
                or_(
                    func.lower(User.display_name).like(search_term),
                    func.lower(User.email).like(search_term)
                )
            )
        )
    )
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    return {
        "items": [
            {
                "id": str(u.id),
                "display_name": u.display_name,
                "username": u.display_name.lower().replace(" ", "_"),
                "avatar_url": u.avatar_url,
                "karma_score": u.karma_score or 0,
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (offset + len(users)) < total,
    }


@router.get("/maps", response_model=dict)
async def search_maps_extended(
    q: str = Query(min_length=1, max_length=100, description="Search query"),
    verified_only: bool = Query(default=False, description="Only show verified maps"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_current_user_optional),
) -> dict:
    """Extended beatmap search with pagination."""
    search_term = f"%{q.lower()}%"
    offset = (page - 1) * page_size
    
    base_conditions = [
        or_(
            func.lower(Song.title).like(search_term),
            func.lower(Song.artist).like(search_term)
        )
    ]
    
    # Add verified filter if requested
    if verified_only:
        base_conditions.append(Song.status == SongStatus.VERIFIED)
    
    query = (
        select(Song)
        .options(selectinload(Song.creator))
        .where(and_(*base_conditions))
        .order_by(Song.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    
    count_query = (
        select(func.count())
        .select_from(Song)
        .where(and_(*base_conditions))
    )
    
    result = await db.execute(query)
    songs = result.scalars().all()
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    return {
        "items": [
            {
                "id": str(s.id),
                "song_id": str(s.id),
                "title": s.title,
                "artist": s.artist or "Unknown Artist",
                "creator_name": s.owner.display_name if s.owner else "Unknown",
                "creator_id": str(s.owner_id) if s.owner_id else "",
                "is_verified": getattr(s, 'is_verified', False),
                "cover_url": getattr(s, 'cover_url', None),
            }
            for s in songs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (offset + len(songs)) < total,
    }
