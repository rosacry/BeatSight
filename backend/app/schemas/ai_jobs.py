"""Schemas for AI job resources."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.ai_job import AIJobPriority, AIJobState


class QuantizationGrid(str, Enum):
    """Quantization grid options - matches desktop AiGenerationOptions."""

    NONE = "none"
    QUARTER = "quarter"  # 1/4
    EIGHTH = "eighth"  # 1/8
    SIXTEENTH = "sixteenth"  # 1/16 (default)
    THIRTY_SECOND = "thirty_second"  # 1/32


class AIGenerationOptions(BaseModel):
    """AI beatmap generation options.

    Matches desktop BeatSight.Game.AI.AiGenerationOptions for compatibility.
    """

    # Detection parameters
    confidence_threshold: float = Field(
        default=0.3,
        ge=0.1,
        le=0.9,
        description="Minimum confidence for note detection (lower = more notes)",
    )
    detection_sensitivity: int = Field(
        default=60, ge=1, le=100, description="Overall detection sensitivity (1-100)"
    )

    # Drum separation
    enable_drum_separation: bool = Field(
        default=True, description="Isolate drums from the mix before analysis"
    )

    # Quantization
    quantization_grid: QuantizationGrid = Field(
        default=QuantizationGrid.SIXTEENTH, description="Grid to snap detected notes to"
    )
    max_snap_error_ms: float = Field(
        default=12.0,
        ge=1.0,
        le=50.0,
        description="Maximum milliseconds a note can move when snapping",
    )
    force_quantization: bool = Field(
        default=False,
        description="Force all notes to grid (vs. allowing off-grid if closer)",
    )

    # Tempo hints from user
    forced_bpm: Optional[float] = Field(
        default=None, ge=30, le=300, description="Override detected BPM with this value"
    )
    forced_offset_seconds: Optional[float] = Field(
        default=None, description="Override detected offset (seconds)"
    )
    tempo_candidates: Optional[list[float]] = Field(
        default=None, description="BPM candidates to consider during detection"
    )

    # Region selection
    start_time: Optional[float] = Field(
        default=None,
        ge=0,
        description="Process audio starting from this time (seconds)",
    )
    end_time: Optional[float] = Field(
        default=None, description="Process audio up to this time (seconds)"
    )

    # Debug output
    export_debug_analysis: bool = Field(
        default=True, description="Include detailed analysis data in output"
    )

    # ML classifier
    use_ml_classifier: bool = Field(
        default=True,
        description="Use ML model for drum classification (vs. rule-based)",
    )


class AIJobBase(BaseModel):
    song_id: uuid.UUID
    priority: AIJobPriority = Field(default=AIJobPriority.STANDARD)


class AIJobCreate(AIJobBase):
    """Request to create a new AI generation job.

    Matches the options available in desktop's EditorScreen and AiBeatmapGenerator.
    """

    options: AIGenerationOptions = Field(
        default_factory=AIGenerationOptions,
        description="Generation options (defaults match desktop app)",
    )


class AIJobRead(AIJobBase):
    id: uuid.UUID
    state: AIJobState
    error_message: str | None
    requested_by_id: uuid.UUID | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    # Worker heartbeat fields
    worker_id: uuid.UUID | None = None
    last_heartbeat: datetime | None = None
    progress_percent: int | None = None
    progress_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AIJobProgressUpdate(BaseModel):
    """Schema for worker progress updates."""

    worker_id: uuid.UUID
    progress_percent: int = Field(ge=0, le=100)
    progress_message: str | None = Field(default=None, max_length=255)


class QuotaStatusRead(BaseModel):
    """Current quota status for a user."""

    plan: str | None = Field(description="Subscription plan code (null for anonymous)")
    used_this_month: int = Field(description="Jobs used in current billing period")
    used_today: int = Field(description="Jobs used today")
    remaining_month: int = Field(description="Jobs remaining this month")
    remaining_today: int = Field(description="Jobs remaining today")
    limit_month: int = Field(description="Monthly job limit")
    limit_day: int = Field(description="Daily job limit")
    resets_at: datetime | None = Field(description="When the monthly quota resets")
    priority: int = Field(description="Job priority level for this user")


class AIJobEnqueueResponse(BaseModel):
    """Response for job enqueue with quota information."""

    job: AIJobRead
    queue_position: int | None = Field(
        description="Position in queue (0-based), null if already processing"
    )
    estimated_wait_minutes: int | None = Field(
        description="Estimated wait time in minutes"
    )
    quota: QuotaStatusRead
