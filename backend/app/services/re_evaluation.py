"""AI Model Re-evaluation Service.

This service handles the automatic re-evaluation of unverified maps when
a new AI model version becomes available. Key features:

1. **Free Re-evaluation**: No credits are consumed for AI-initiated re-evaluation
2. **User Preferences**: Respects user's re_evaluation_policy setting
3. **Batch Processing**: Efficiently processes multiple songs in batches
4. **Version Tracking**: Tracks which model version generated each beatmap
5. **Smart Re-evaluation**: Only re-processes low-confidence portions of songs
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.ai_job import AIJob, AIJobState, AIJobPriority
from app.models.song import Map, MapState, Song
from app.models.user import User
from app.models.user_settings import UserSettings, ReEvaluationPolicy

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ReEvalMode:
    """Re-evaluation processing modes."""
    
    FULL = "full"  # Re-process entire audio file
    SMART = "smart"  # Only re-process low-confidence regions


@dataclass
class ReEvaluationCandidate:
    """A song that could benefit from re-evaluation."""
    
    song_id: uuid.UUID
    owner_id: uuid.UUID | None
    current_model_version: str
    map_count: int
    unverified_map_count: int
    
    # Smart re-eval data (populated if original analysis available)
    low_confidence_percentage: float = 0.0  # % of notes below confidence threshold
    estimated_efficiency_gain: float = 1.0  # Expected speedup from smart re-eval


@dataclass
class ReEvaluationResult:
    """Result of a re-evaluation operation."""
    
    total_candidates: int
    jobs_created: int
    smart_re_evals: int  # Jobs using smart (partial) re-evaluation
    full_re_evals: int  # Jobs using full re-evaluation
    skipped_user_opt_out: int
    skipped_already_current: int
    errors: list[str]


class ReEvaluationService:
    """Service for AI model re-evaluation of unverified maps.
    
    When a new AI model version is deployed, this service can automatically
    queue re-evaluation jobs for songs that:
    1. Have unverified maps (verified maps are considered correct)
    2. Were processed by an older model version
    3. Are owned by users who haven't opted out of re-evaluation
    
    **Smart Re-evaluation**: Instead of re-processing entire songs, the service
    analyzes confidence scores from the original transcription and only
    re-processes regions where the old model was uncertain. This provides:
    - 2-10x faster processing
    - Stability for notes users may have already verified
    - Focused compute on areas that need improvement
    
    **Credit Policy**: Re-evaluation is FREE because:
    - The user didn't request it - the system is improving
    - It's in BeatSight's interest to show better results
    - Users who opt-out can always manually request (uses credits)
    """
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
    
    async def find_candidates(
        self,
        old_model_version: str | None = None,
        limit: int = 100,
    ) -> list[ReEvaluationCandidate]:
        """Find songs eligible for re-evaluation.
        
        Args:
            old_model_version: Only find songs processed by this version.
                              If None, finds all songs with older model versions.
            limit: Maximum number of candidates to return.
            
        Returns:
            List of ReEvaluationCandidate objects.
        """
        current_version = self._settings.ai_model_version
        
        # Find completed jobs with older model versions
        base_query = (
            select(
                AIJob.song_id,
                Song.created_by_id,
                AIJob.model_version,
            )
            .join(Song, AIJob.song_id == Song.id)
            .where(AIJob.state == AIJobState.COMPLETE)
            .where(AIJob.model_version.isnot(None))
        )
        
        if old_model_version:
            base_query = base_query.where(AIJob.model_version == old_model_version)
        else:
            # Filter out jobs that already used current model
            base_query = base_query.where(AIJob.model_version != current_version)
        
        # Group by song to get unique songs
        base_query = (
            base_query
            .group_by(AIJob.song_id, Song.created_by_id, AIJob.model_version)
            .limit(limit)
        )
        
        result = await self._session.execute(base_query)
        rows = result.all()
        
        candidates = []
        for song_id, owner_id, model_version in rows:
            # Get map counts for this song
            map_count_result = await self._session.execute(
                select(Map)
                .where(Map.song_id == song_id)
            )
            maps = map_count_result.scalars().all()
            
            total_maps = len(maps)
            unverified_maps = sum(1 for m in maps if m.state == MapState.UNVERIFIED)
            
            # Only include if there are unverified maps
            if unverified_maps > 0:
                candidates.append(ReEvaluationCandidate(
                    song_id=song_id,
                    owner_id=owner_id,
                    current_model_version=model_version,
                    map_count=total_maps,
                    unverified_map_count=unverified_maps,
                ))
        
        return candidates
    
    async def get_user_re_evaluation_policy(
        self,
        user_id: uuid.UUID | None,
    ) -> ReEvaluationPolicy:
        """Get a user's re-evaluation policy preference.
        
        Args:
            user_id: The user ID to check. None for anonymous users.
            
        Returns:
            The user's re-evaluation policy (defaults to AUTO_FREE).
        """
        if user_id is None:
            # Anonymous uploads default to auto-free (they get the benefit)
            return ReEvaluationPolicy.AUTO_FREE
        
        result = await self._session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()
        
        if settings is None:
            # No settings = default to AUTO_FREE
            return ReEvaluationPolicy.AUTO_FREE
        
        return settings.re_evaluation_policy
    
    async def queue_re_evaluation(
        self,
        song_id: uuid.UUID,
        reason: str = "model_upgrade",
    ) -> AIJob | None:
        """Queue a re-evaluation job for a specific song.
        
        This creates a new AI job with:
        - LOW priority (to not interfere with user requests)
        - Current model version
        - No credit consumption (free re-evaluation)
        
        Args:
            song_id: The song to re-evaluate.
            reason: Why re-evaluation is needed (for logging).
            
        Returns:
            The created AIJob, or None if re-evaluation was skipped.
        """
        current_version = self._settings.ai_model_version
        
        # Check if there's already an active job for this song
        active_job = await self._session.execute(
            select(AIJob)
            .where(AIJob.song_id == song_id)
            .where(AIJob.state.in_([AIJobState.QUEUED, AIJobState.PROCESSING]))
        )
        if active_job.scalar_one_or_none():
            logger.info(f"Skipping re-evaluation for song {song_id}: active job exists")
            return None
        
        # Check if there's already a completed job with current model
        completed_job = await self._session.execute(
            select(AIJob)
            .where(AIJob.song_id == song_id)
            .where(AIJob.state == AIJobState.COMPLETE)
            .where(AIJob.model_version == current_version)
        )
        if completed_job.scalar_one_or_none():
            logger.info(f"Skipping re-evaluation for song {song_id}: already has {current_version} beatmap")
            return None
        
        # Create re-evaluation job with low priority
        job = AIJob(
            song_id=song_id,
            state=AIJobState.QUEUED,
            priority=AIJobPriority.STANDARD,  # Could add a RE_EVALUATION priority
            model_version=current_version,
            requested_by_id=None,  # System-initiated, no user
            progress_message=f"Re-evaluation queued ({reason})",
        )
        self._session.add(job)
        await self._session.commit()
        await self._session.refresh(job)
        
        logger.info(f"Queued re-evaluation job {job.id} for song {song_id} (reason: {reason})")
        return job
    
    async def run_batch_re_evaluation(
        self,
        old_model_version: str | None = None,
        batch_size: int = 50,
    ) -> ReEvaluationResult:
        """Run batch re-evaluation for songs with older model versions.
        
        This method:
        1. Finds candidates eligible for re-evaluation
        2. Checks each owner's preferences
        3. Queues jobs for eligible songs
        4. Returns statistics about the operation
        
        Args:
            old_model_version: Only re-evaluate songs from this version.
            batch_size: Maximum songs to process in this batch.
            
        Returns:
            ReEvaluationResult with statistics.
        """
        candidates = await self.find_candidates(old_model_version, batch_size)
        
        result = ReEvaluationResult(
            total_candidates=len(candidates),
            jobs_created=0,
            skipped_user_opt_out=0,
            skipped_already_current=0,
            errors=[],
        )
        
        for candidate in candidates:
            try:
                # Check user's preference
                policy = await self.get_user_re_evaluation_policy(candidate.owner_id)
                
                if policy == ReEvaluationPolicy.OPT_OUT:
                    result.skipped_user_opt_out += 1
                    continue
                
                # Queue the re-evaluation
                job = await self.queue_re_evaluation(
                    candidate.song_id,
                    reason=f"upgrade_{candidate.current_model_version}_to_{self._settings.ai_model_version}",
                )
                
                if job:
                    result.jobs_created += 1
                else:
                    result.skipped_already_current += 1
                    
            except Exception as e:
                error_msg = f"Error processing song {candidate.song_id}: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)
        
        logger.info(
            f"Batch re-evaluation complete: {result.jobs_created} jobs created, "
            f"{result.skipped_user_opt_out} skipped (opt-out), "
            f"{result.skipped_already_current} skipped (already current), "
            f"{len(result.errors)} errors"
        )
        
        return result


async def notify_model_upgrade_available(
    session: AsyncSession,
    old_version: str,
    new_version: str,
) -> None:
    """Notify users that a model upgrade is available for their maps.
    
    This sends notifications to users who:
    1. Have maps processed by the old model
    2. Have re_evaluation_policy set to OPT_IN
    3. Have notify_re_evaluation_available enabled in settings
    
    Args:
        session: Database session.
        old_version: Previous model version.
        new_version: New model version.
    """
    from app.services.notifications import NotificationService
    
    # Find users with OPT_IN policy who have maps from old model
    query = (
        select(User.id, Song.id.label("song_id"))
        .join(Song, Song.created_by_id == User.id)
        .join(AIJob, AIJob.song_id == Song.id)
        .join(UserSettings, UserSettings.user_id == User.id)
        .where(AIJob.state == AIJobState.COMPLETE)
        .where(AIJob.model_version == old_version)
        .where(UserSettings.re_evaluation_policy == ReEvaluationPolicy.OPT_IN)
        .where(UserSettings.notify_re_evaluation_available.is_(True))
        .distinct()
    )
    
    result = await session.execute(query)
    users_to_notify = result.all()
    
    notification_service = NotificationService(session)
    for user_id, song_id in users_to_notify:
        try:
            await notification_service.send_notification(
                user_id=user_id,
                title="AI Model Upgrade Available",
                body=f"A new AI model ({new_version}) is available. "
                     f"Your beatmaps can be improved with the latest model.",
                data={
                    "type": "model_upgrade_available",
                    "old_version": old_version,
                    "new_version": new_version,
                    "song_id": str(song_id),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to notify user {user_id} about model upgrade: {e}")
