"""Pydantic schemas for song resources."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.song import MapState, SongStatus


class SongBase(BaseModel):
    title: str = Field(max_length=255)
    artist: str = Field(max_length=255)
    bpm: int | None = Field(default=None, ge=40, le=400)


class SongCreate(SongBase):
    fingerprint_hash: str = Field(max_length=128)


class SongUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    artist: str | None = Field(default=None, max_length=255)
    bpm: int | None = Field(default=None, ge=40, le=400)
    status: SongStatus | None = None
    canonical_map_id: uuid.UUID | None = None


class MapSummary(BaseModel):
    id: uuid.UUID
    difficulty_label: str
    is_canonical: bool
    state: MapState
    current_version_id: uuid.UUID | None

    class Config:
        from_attributes = True


class SongRead(SongBase):
    id: uuid.UUID
    status: SongStatus
    canonical_map_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    maps: list[MapSummary] = []

    class Config:
        from_attributes = True
