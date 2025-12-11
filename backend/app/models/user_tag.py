"""User tag model for custom profile badges (like osu!'s DEV, VIP, etc.)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .user import User


class UserTag(Base):
    """
    Custom profile tags that admins can assign to users.
    
    Similar to osu!'s profile tags (DEV, VIP, etc.).
    Tags are displayed on user profiles and can have custom colors.
    
    Examples:
        - DEV (red background) - for developers
        - VIP (gold background) - for special contributors
        - MAPPER (purple background) - for notable map creators
    """

    __tablename__ = "user_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Tag display text (e.g., "DEV", "VIP", "MAPPER")
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    
    # Colors stored as hex values (e.g., "#ff5500" or "ff5500")
    background_color: Mapped[str] = mapped_column(String(16), default="#3b82f6")  # Default blue
    text_color: Mapped[str | None] = mapped_column(String(16))  # If null, use contrasting auto color
    
    # Optional description/note for admin reference
    description: Mapped[str | None] = mapped_column(String(255))
    
    # Display order (lower = displayed first)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    
    # Audit fields
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", back_populates="tags", foreign_keys=[user_id]
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_id]
    )

    def __repr__(self) -> str:
        return f"<UserTag(id={self.id}, user_id={self.user_id}, name='{self.name}')>"
