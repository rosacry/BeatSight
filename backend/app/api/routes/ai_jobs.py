"""AI job API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.ai_jobs import AIJobCreate, AIJobRead
from app.services.ai_jobs import AIJobService

router = APIRouter(prefix="/ai-jobs", tags=["ai-jobs"])


@router.post("", response_model=AIJobRead, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_job(
    payload: AIJobCreate,
    session: AsyncSession = Depends(get_db_session),
) -> AIJobRead:
    """Enqueue an AI mapping job."""

    service = AIJobService(session)
    # TODO: Implement OAuth2/JWT authentication, then:
    #   1. Add `current_user: User = Depends(get_current_user)` to route params
    #   2. Pass `requested_by=current_user.id` below
    #   See: backend/app/services/auth.py (to be created), docs/web_backend_architecture.md
    job = await service.enqueue(payload, requested_by=None)
    return AIJobRead.model_validate(job)


@router.get("", response_model=list[AIJobRead])
async def list_jobs(
    song_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> list[AIJobRead]:
    """List AI jobs, optionally filtered by song."""

    service = AIJobService(session)
    jobs = await service.list_jobs(song_id=song_id)
    return [AIJobRead.model_validate(job) for job in jobs]
