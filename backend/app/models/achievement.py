"""
Achievement model for user accomplishments tracking.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base

if TYPE_CHECKING:
    pass


class AchievementCategory(str, Enum):
    """Categories for grouping achievements."""

    GENERATION = "generation"  # Beatmap generation milestones
    LEARNING = "learning"  # Practice and learning milestones
    CONTRIBUTION = "contribution"  # Community contribution
    SOCIAL = "social"  # Social features (karma, etc.)
    SPECIAL = "special"  # Limited/seasonal achievements


class Achievement(Base):
    """
    Represents an achievement type that users can earn.

    Achievements are system-defined milestones that track user progress.
    """

    __tablename__ = "achievements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(String(512), nullable=False)
    icon = Column(String(64), nullable=False, default="trophy")  # Icon identifier
    category = Column(
        SQLEnum(AchievementCategory),
        nullable=False,
        default=AchievementCategory.GENERATION,
    )
    points = Column(String(8), nullable=False, default="10")  # XP/points value
    is_hidden = Column(Boolean, nullable=False, default=False)  # Hidden until earned
    is_active = Column(Boolean, nullable=False, default=True)  # Can be earned

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship to user achievements
    user_achievements = relationship("UserAchievement", back_populates="achievement")


class UserAchievement(Base):
    """
    Junction table tracking which achievements users have earned.
    """

    __tablename__ = "user_achievements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    achievement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("achievements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    earned_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")


# Achievement definitions for seeding
ACHIEVEMENT_DEFINITIONS = [
    # Generation achievements
    {
        "slug": "first_beatmap",
        "name": "First Beat",
        "description": "Generate your first beatmap",
        "icon": "music",
        "category": AchievementCategory.GENERATION,
        "points": "10",
    },
    {
        "slug": "five_beatmaps",
        "name": "Getting Started",
        "description": "Generate 5 beatmaps",
        "icon": "collection",
        "category": AchievementCategory.GENERATION,
        "points": "25",
    },
    {
        "slug": "twenty_five_beatmaps",
        "name": "Beatmap Enthusiast",
        "description": "Generate 25 beatmaps",
        "icon": "star",
        "category": AchievementCategory.GENERATION,
        "points": "50",
    },
    {
        "slug": "hundred_beatmaps",
        "name": "Beatmap Master",
        "description": "Generate 100 beatmaps",
        "icon": "crown",
        "category": AchievementCategory.GENERATION,
        "points": "100",
    },
    # Learning achievements
    {
        "slug": "first_practice",
        "name": "Practice Makes Perfect",
        "description": "Complete your first practice session",
        "icon": "graduation-cap",
        "category": AchievementCategory.LEARNING,
        "points": "10",
    },
    {
        "slug": "hour_practiced",
        "name": "Dedicated Student",
        "description": "Practice for a total of 1 hour",
        "icon": "clock",
        "category": AchievementCategory.LEARNING,
        "points": "25",
    },
    {
        "slug": "ten_hours_practiced",
        "name": "Committed Drummer",
        "description": "Practice for a total of 10 hours",
        "icon": "fire",
        "category": AchievementCategory.LEARNING,
        "points": "75",
    },
    # Contribution achievements
    {
        "slug": "first_edit",
        "name": "Editor",
        "description": "Make your first beatmap edit",
        "icon": "pencil",
        "category": AchievementCategory.CONTRIBUTION,
        "points": "10",
    },
    {
        "slug": "helpful_editor",
        "name": "Helpful Editor",
        "description": "Have an edit approved on a public beatmap",
        "icon": "check-circle",
        "category": AchievementCategory.CONTRIBUTION,
        "points": "50",
    },
    # Social achievements
    {
        "slug": "rising_karma",
        "name": "Rising Karma",
        "description": "Reach 100 karma points",
        "icon": "arrow-up",
        "category": AchievementCategory.SOCIAL,
        "points": "25",
    },
    {
        "slug": "karma_champion",
        "name": "Karma Champion",
        "description": "Reach 1000 karma points",
        "icon": "trophy",
        "category": AchievementCategory.SOCIAL,
        "points": "100",
    },
    # Special achievements
    {
        "slug": "early_adopter",
        "name": "Early Adopter",
        "description": "Join BeatSight during the beta period",
        "icon": "rocket",
        "category": AchievementCategory.SPECIAL,
        "points": "50",
        "is_hidden": True,
    },
]
