"""
Achievement API endpoints.

Provides endpoints for:
- Listing all available achievements
- Getting user's earned achievements
- Checking achievement progress
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db_session
from app.models import Achievement, AchievementCategory, User, UserAchievement


router = APIRouter(prefix="/achievements", tags=["achievements"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class AchievementResponse(BaseModel):
    """Response schema for an achievement."""
    id: UUID
    slug: str
    name: str
    description: str
    icon: str
    category: AchievementCategory
    points: str
    is_hidden: bool
    earned: bool = False
    earned_at: str | None = None

    model_config = {"from_attributes": True}


class AchievementListResponse(BaseModel):
    """Response schema for listing achievements."""
    achievements: List[AchievementResponse]
    total_earned: int
    total_points: int


class AchievementProgressResponse(BaseModel):
    """Response schema for achievement progress check."""
    beatmaps_generated: int
    total_practice_time_minutes: int
    karma_score: int
    edits_made: int


# ============================================================================
# Endpoints
# ============================================================================


@router.get("", response_model=AchievementListResponse)
async def list_achievements(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    List all achievements with user's earned status.
    
    Returns all active achievements, marking which ones the current user has earned.
    Hidden achievements are only shown if earned.
    """
    # Get all active achievements
    result = await db.execute(
        select(Achievement).where(Achievement.is_active == True)
    )
    all_achievements = result.scalars().all()
    
    # Get user's earned achievements
    earned_result = await db.execute(
        select(UserAchievement)
        .where(UserAchievement.user_id == current_user.id)
        .options(selectinload(UserAchievement.achievement))
    )
    earned_achievements = {ua.achievement_id: ua for ua in earned_result.scalars().all()}
    
    # Build response
    achievements = []
    total_points = 0
    
    for achievement in all_achievements:
        earned = achievement.id in earned_achievements
        earned_at = None
        
        # Skip hidden achievements that aren't earned
        if achievement.is_hidden and not earned:
            continue
        
        if earned:
            earned_at = earned_achievements[achievement.id].earned_at.isoformat()
            total_points += int(achievement.points)
        
        achievements.append(AchievementResponse(
            id=achievement.id,
            slug=achievement.slug,
            name=achievement.name,
            description=achievement.description,
            icon=achievement.icon,
            category=achievement.category,
            points=achievement.points,
            is_hidden=achievement.is_hidden,
            earned=earned,
            earned_at=earned_at,
        ))
    
    # Sort: earned first, then by category, then by points
    achievements.sort(key=lambda a: (not a.earned, a.category.value, -int(a.points)))
    
    return AchievementListResponse(
        achievements=achievements,
        total_earned=len(earned_achievements),
        total_points=total_points,
    )


@router.get("/progress", response_model=AchievementProgressResponse)
async def get_progress(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get user's progress towards achievements.
    
    Returns counts and metrics that are used to determine achievement eligibility.
    """
    from app.models import AIJob
    
    # Count completed beatmap generations
    jobs_result = await db.execute(
        select(func.count(AIJob.id))
        .where(AIJob.requester_id == current_user.id)
        .where(AIJob.state == "complete")
    )
    beatmaps_generated = jobs_result.scalar() or 0
    
    # Practice time tracking not implemented
    total_practice_time_minutes = 0
    
    # Get karma score
    karma_score = current_user.karma_score
    
    # Count edits made
    from app.models import MapEditProposal
    edits_result = await db.execute(
        select(func.count(MapEditProposal.id))
        .where(MapEditProposal.proposer_id == current_user.id)
    )
    edits_made = edits_result.scalar() or 0
    
    return AchievementProgressResponse(
        beatmaps_generated=beatmaps_generated,
        total_practice_time_minutes=total_practice_time_minutes,
        karma_score=karma_score,
        edits_made=edits_made,
    )


@router.get("/{achievement_id}", response_model=AchievementResponse)
async def get_achievement(
    achievement_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get details of a specific achievement.
    """
    result = await db.execute(
        select(Achievement).where(Achievement.id == achievement_id)
    )
    achievement = result.scalar_one_or_none()
    
    if not achievement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Achievement not found",
        )
    
    # Check if user has earned it
    earned_result = await db.execute(
        select(UserAchievement)
        .where(UserAchievement.user_id == current_user.id)
        .where(UserAchievement.achievement_id == achievement_id)
    )
    user_achievement = earned_result.scalar_one_or_none()
    
    # Don't show hidden achievements that aren't earned
    if achievement.is_hidden and not user_achievement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Achievement not found",
        )
    
    return AchievementResponse(
        id=achievement.id,
        slug=achievement.slug,
        name=achievement.name,
        description=achievement.description,
        icon=achievement.icon,
        category=achievement.category,
        points=achievement.points,
        is_hidden=achievement.is_hidden,
        earned=user_achievement is not None,
        earned_at=user_achievement.earned_at.isoformat() if user_achievement else None,
    )
