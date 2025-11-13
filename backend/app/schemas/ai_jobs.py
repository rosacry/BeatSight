"""Schemas for AI job resources."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.ai_job import AIJobPriority, AIJobState


class AIJobBase(BaseModel):
    song_id: uuid.UUID
    priority: AIJobPriority = Field(default=AIJobPriority.STANDARD)


class AIJobCreate(AIJobBase):
    pass


class AIJobRead(AIJobBase):
    id: uuid.UUID
    state: AIJobState
    error_message: str | None
    requested_by_id: uuid.UUID | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
