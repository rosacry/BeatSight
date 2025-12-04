"""
Achievement service for checking and awarding achievements.

This service provides functions to check if users have met achievement criteria
and to automatically award achievements when triggered by user actions.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Achievement, UserAchievement, AIJob, MapEditProposal
from app.logging import get_logger

logger = get_logger(__name__)


# Achievement slug constants
ACHIEVEMENT_FIRST_BEATMAP = "first_beatmap"
ACHIEVEMENT_FIVE_BEATMAPS = "five_beatmaps"
ACHIEVEMENT_TWENTY_FIVE_BEATMAPS = "twenty_five_beatmaps"
ACHIEVEMENT_HUNDRED_BEATMAPS = "hundred_beatmaps"
ACHIEVEMENT_FIRST_EDIT = "first_edit"
ACHIEVEMENT_HELPFUL_EDITOR = "helpful_editor"
ACHIEVEMENT_RISING_KARMA = "rising_karma"
ACHIEVEMENT_KARMA_CHAMPION = "karma_champion"


async def check_and_award_achievement(
    db: AsyncSession,
    user_id: UUID,
    achievement_slug: str,
) -> Optional[UserAchievement]:
    """
    Check if user already has achievement, award if not.

    Returns the UserAchievement if newly awarded, None if already earned or not found.
    """
    # Get achievement by slug
    result = await db.execute(
        select(Achievement)
        .where(Achievement.slug == achievement_slug)
        .where(Achievement.is_active.is_(True))
    )
    achievement = result.scalar_one_or_none()

    if not achievement:
        logger.warning(f"Achievement not found: {achievement_slug}")
        return None

    # Check if already earned
    existing = await db.execute(
        select(UserAchievement)
        .where(UserAchievement.user_id == user_id)
        .where(UserAchievement.achievement_id == achievement.id)
    )
    if existing.scalar_one_or_none():
        return None  # Already earned

    # Award the achievement
    user_achievement = UserAchievement(
        user_id=user_id,
        achievement_id=achievement.id,
        earned_at=datetime.now(timezone.utc),
    )
    db.add(user_achievement)

    logger.info(
        f"Achievement awarded: {achievement_slug} to user {user_id}",
        extra={"achievement": achievement_slug, "user_id": str(user_id)},
    )

    return user_achievement


async def check_beatmap_generation_achievements(
    db: AsyncSession,
    user_id: UUID,
) -> list[str]:
    """
    Check and award beatmap generation achievements.

    Called after a beatmap is successfully generated.
    Returns list of newly awarded achievement slugs.
    """
    awarded = []

    # Count completed jobs for this user
    result = await db.execute(
        select(func.count(AIJob.id))
        .where(AIJob.requester_id == user_id)
        .where(AIJob.state == "complete")
    )
    count = result.scalar() or 0

    # Check milestones (check in order, all that apply)
    if count >= 1:
        if await check_and_award_achievement(db, user_id, ACHIEVEMENT_FIRST_BEATMAP):
            awarded.append(ACHIEVEMENT_FIRST_BEATMAP)

    if count >= 5:
        if await check_and_award_achievement(db, user_id, ACHIEVEMENT_FIVE_BEATMAPS):
            awarded.append(ACHIEVEMENT_FIVE_BEATMAPS)

    if count >= 25:
        if await check_and_award_achievement(
            db, user_id, ACHIEVEMENT_TWENTY_FIVE_BEATMAPS
        ):
            awarded.append(ACHIEVEMENT_TWENTY_FIVE_BEATMAPS)

    if count >= 100:
        if await check_and_award_achievement(db, user_id, ACHIEVEMENT_HUNDRED_BEATMAPS):
            awarded.append(ACHIEVEMENT_HUNDRED_BEATMAPS)

    return awarded


async def check_edit_achievements(
    db: AsyncSession,
    user_id: UUID,
    edit_approved: bool = False,
) -> list[str]:
    """
    Check and award map editing achievements.

    Called after a map edit is created or approved.
    """
    awarded = []

    # Count edits by this user
    result = await db.execute(
        select(func.count(MapEditProposal.id)).where(
            MapEditProposal.proposer_id == user_id
        )
    )
    count = result.scalar() or 0

    if count >= 1:
        if await check_and_award_achievement(db, user_id, ACHIEVEMENT_FIRST_EDIT):
            awarded.append(ACHIEVEMENT_FIRST_EDIT)

    # If edit was approved, check for helpful editor achievement
    if edit_approved:
        if await check_and_award_achievement(db, user_id, ACHIEVEMENT_HELPFUL_EDITOR):
            awarded.append(ACHIEVEMENT_HELPFUL_EDITOR)

    return awarded


async def check_karma_achievements(
    db: AsyncSession,
    user_id: UUID,
    karma_score: int,
) -> list[str]:
    """
    Check and award karma-based achievements.

    Called after karma changes.
    """
    awarded = []

    if karma_score >= 100:
        if await check_and_award_achievement(db, user_id, ACHIEVEMENT_RISING_KARMA):
            awarded.append(ACHIEVEMENT_RISING_KARMA)

    if karma_score >= 1000:
        if await check_and_award_achievement(db, user_id, ACHIEVEMENT_KARMA_CHAMPION):
            awarded.append(ACHIEVEMENT_KARMA_CHAMPION)

    return awarded
