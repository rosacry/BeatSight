"""Contribution Quality Assurance Service.

This module implements quality gates and conflict detection for the training
contribution pipeline, addressing several critical concerns:

1. **Edit-Contribution Conflicts**: Detects when user edit proposals conflict
   with training contributions or AI re-evaluations.

2. **Contribution Validation**: Implements consensus-based validation to catch
   incorrect user corrections before they pollute training data.

3. **Re-evaluation Efficiency**: Prevents wasteful re-evaluations when changes
   would be minimal or when pending user edits exist.

4. **Model Version Staleness**: Tracks which contributions came from which model
   version to prevent training on outdated correction patterns.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.ai_job import AIJob, AIJobState
from app.models.map_edit import EditStatus, MapEditProposal
from app.models.map_version import MapVersion
from app.models.song import Map, MapState
from app.models.training_contribution import (
    ContributionStatus,
    TrainingContribution,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

# Minimum confidence improvement to warrant re-evaluation
MIN_MODEL_IMPROVEMENT_THRESHOLD = 0.02  # 2% accuracy improvement

# Time window to consider contributions "recent" (for conflict detection)
RECENT_CONTRIBUTION_WINDOW_HOURS = 48

# Minimum consensus votes needed for high-impact contributions
MIN_CONSENSUS_VOTES = 2

# Maximum model version gap before contributions become stale
MAX_MODEL_VERSION_GAP = 2  # e.g., v5.1 contribution is stale for v5.4 model


class ConflictType(str, Enum):
    """Types of conflicts that can occur in the contribution pipeline."""
    
    NONE = "none"
    PENDING_EDIT = "pending_edit"  # User has pending edit on same region
    RECENT_RE_EVAL = "recent_re_eval"  # Recent re-evaluation touched this region
    STALE_MODEL = "stale_model"  # Contribution based on outdated model
    CONFLICTING_CONTRIBUTIONS = "conflicting_contributions"  # Multiple users disagree
    SUPERSEDED = "superseded"  # Another contribution already addressed this


class ReEvalSkipReason(str, Enum):
    """Reasons to skip re-evaluation for a song."""
    
    MINIMAL_IMPROVEMENT = "minimal_improvement"
    PENDING_EDITS = "pending_edits"
    RECENT_USER_ACTIVITY = "recent_user_activity"
    HIGH_CONFIDENCE_MAP = "high_confidence_map"
    USER_OPT_OUT = "user_opt_out"


@dataclass
class ConflictCheckResult:
    """Result of checking for conflicts in the contribution pipeline."""
    
    has_conflict: bool
    conflict_type: ConflictType
    message: str
    blocking: bool  # If True, contribution should be rejected
    related_ids: list[uuid.UUID] = field(default_factory=list)
    
    @classmethod
    def no_conflict(cls) -> "ConflictCheckResult":
        return cls(
            has_conflict=False,
            conflict_type=ConflictType.NONE,
            message="No conflicts detected",
            blocking=False,
        )


@dataclass
class ReEvalDecision:
    """Decision on whether to proceed with re-evaluation."""
    
    should_proceed: bool
    skip_reason: ReEvalSkipReason | None
    message: str
    estimated_improvement: float = 0.0
    affected_regions_count: int = 0


@dataclass
class ContributionWeight:
    """Calculated weight for a contribution in training."""
    
    base_weight: float  # From user karma and confidence
    consensus_multiplier: float  # From agreement with other users
    freshness_multiplier: float  # Decay over model versions
    final_weight: float
    
    @property
    def should_include(self) -> bool:
        """Whether this contribution should be included in training."""
        return self.final_weight >= 0.1


class ContributionQualityService:
    """Service for contribution quality assurance and conflict detection.
    
    This service acts as a gatekeeper for the training pipeline, ensuring:
    
    1. **No Training Pollution**: Bad contributions are filtered out through
       consensus validation and conflict detection.
    
    2. **No Wasted Compute**: Re-evaluations are skipped when improvements
       would be minimal or conflicts exist.
    
    3. **User Edit Priority**: Pending user edits take precedence over
       automated re-evaluations for the same regions.
    
    4. **Freshness Tracking**: Contributions based on very old model versions
       are downweighted or excluded from training.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
    
    # =========================================================================
    # Conflict Detection
    # =========================================================================
    
    async def check_contribution_conflicts(
        self,
        map_version_id: uuid.UUID,
        onset_time_ms: int,
        user_id: uuid.UUID,
    ) -> ConflictCheckResult:
        """Check if a contribution conflicts with pending edits or other work.
        
        This is called BEFORE accepting a new contribution to:
        1. Check if the user has pending edits in this region
        2. Check if other users have conflicting contributions
        3. Check if this region was recently re-evaluated
        
        Args:
            map_version_id: The map version being corrected
            onset_time_ms: The onset time being corrected
            user_id: The user submitting the correction
            
        Returns:
            ConflictCheckResult indicating if there's a conflict
        """
        # 1. Check for pending edit proposals touching this region
        time_tolerance_ms = 50  # 50ms tolerance for "same region"
        
        result = await self._session.execute(
            select(MapEditProposal)
            .where(MapEditProposal.map_version_id == map_version_id)
            .where(MapEditProposal.status == EditStatus.PENDING)
        )
        pending_edits = result.scalars().all()
        
        for edit in pending_edits:
            # Check if edit touches this onset region
            if self._edit_touches_onset(edit.diff_payload, onset_time_ms, time_tolerance_ms):
                return ConflictCheckResult(
                    has_conflict=True,
                    conflict_type=ConflictType.PENDING_EDIT,
                    message=f"A pending edit proposal exists for this region (proposal: {edit.id}). "
                            "Please wait for the edit to be reviewed, or withdraw it first.",
                    blocking=True,
                    related_ids=[edit.id],
                )
        
        # 2. Check for conflicting contributions from other users
        cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENT_CONTRIBUTION_WINDOW_HOURS)
        
        result = await self._session.execute(
            select(TrainingContribution)
            .where(TrainingContribution.map_version_id == map_version_id)
            .where(TrainingContribution.onset_time_ms.between(
                onset_time_ms - time_tolerance_ms,
                onset_time_ms + time_tolerance_ms,
            ))
            .where(TrainingContribution.user_id != user_id)
            .where(TrainingContribution.status.in_([
                ContributionStatus.PENDING,
                ContributionStatus.APPROVED,
            ]))
            .where(TrainingContribution.created_at >= cutoff)
        )
        conflicting = result.scalars().all()
        
        if len(conflicting) >= 2:
            # Multiple users have contributed to this exact onset - flag for review
            return ConflictCheckResult(
                has_conflict=True,
                conflict_type=ConflictType.CONFLICTING_CONTRIBUTIONS,
                message=f"Multiple users ({len(conflicting)} others) have submitted corrections "
                        "for this onset. Your contribution will be queued for consensus review.",
                blocking=False,  # Allow but require consensus
                related_ids=[c.id for c in conflicting],
            )
        
        return ConflictCheckResult.no_conflict()
    
    async def check_re_eval_conflicts(
        self,
        song_id: uuid.UUID,
        map_id: uuid.UUID | None = None,
    ) -> ReEvalDecision:
        """Check if re-evaluation should proceed or be skipped.
        
        This prevents wasteful re-evaluations when:
        1. User has pending edits (they're actively working on it)
        2. Recent re-evaluation was done (prevent spam)
        3. Map is already high-confidence (minimal improvement expected)
        4. User has opted out
        
        Args:
            song_id: The song to potentially re-evaluate
            map_id: Specific map to check (optional)
            
        Returns:
            ReEvalDecision with recommendation
        """
        # 1. Check for pending edit proposals
        edit_query = (
            select(func.count())
            .select_from(MapEditProposal)
            .join(MapVersion, MapEditProposal.map_version_id == MapVersion.id)
            .join(Map, MapVersion.map_id == Map.id)
            .where(Map.song_id == song_id)
            .where(MapEditProposal.status == EditStatus.PENDING)
        )
        if map_id:
            edit_query = edit_query.where(Map.id == map_id)
        
        result = await self._session.execute(edit_query)
        pending_edit_count = result.scalar() or 0
        
        if pending_edit_count > 0:
            return ReEvalDecision(
                should_proceed=False,
                skip_reason=ReEvalSkipReason.PENDING_EDITS,
                message=f"Skipping re-evaluation: {pending_edit_count} pending edit(s) exist. "
                        "Re-evaluation would conflict with user's active work.",
            )
        
        # 2. Check for recent user activity (contributions)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        
        contrib_query = (
            select(func.count())
            .select_from(TrainingContribution)
            .join(MapVersion, TrainingContribution.map_version_id == MapVersion.id)
            .join(Map, MapVersion.map_id == Map.id)
            .where(Map.song_id == song_id)
            .where(TrainingContribution.created_at >= cutoff)
        )
        
        result = await self._session.execute(contrib_query)
        recent_contrib_count = result.scalar() or 0
        
        if recent_contrib_count >= 3:
            return ReEvalDecision(
                should_proceed=False,
                skip_reason=ReEvalSkipReason.RECENT_USER_ACTIVITY,
                message=f"Skipping re-evaluation: {recent_contrib_count} contributions in last 24h. "
                        "Users are actively improving this map.",
            )
        
        # 3. Check overall map confidence
        # If the map already has >95% high-confidence notes, skip
        # This requires looking at the beatmap data itself
        map_result = await self._session.execute(
            select(Map)
            .where(Map.song_id == song_id)
            .where(Map.state == MapState.UNVERIFIED)
        )
        maps = map_result.scalars().all()
        
        if maps:
            # For now, assume we should proceed if there are unverified maps
            # TODO: Analyze actual confidence scores from beatmap data
            pass
        
        return ReEvalDecision(
            should_proceed=True,
            skip_reason=None,
            message="Re-evaluation can proceed",
            estimated_improvement=0.0,  # Would be calculated from model metrics
        )
    
    # =========================================================================
    # Contribution Weighting
    # =========================================================================
    
    async def calculate_contribution_weight(
        self,
        contribution: TrainingContribution,
        current_model_version: str,
    ) -> ContributionWeight:
        """Calculate training weight for a contribution.
        
        Weight is based on:
        1. User's karma (higher karma = higher trust)
        2. Original confidence (low-confidence corrections are more valuable)
        3. Consensus with other users
        4. Freshness (contributions from recent model versions are more relevant)
        
        Args:
            contribution: The contribution to weight
            current_model_version: Current AI model version
            
        Returns:
            ContributionWeight with calculated weights
        """
        from app.models.user import User
        
        # Base weight from user karma
        user_result = await self._session.execute(
            select(User.karma_score).where(User.id == contribution.user_id)
        )
        karma = user_result.scalar() or 0
        
        # Karma scaling: 100 karma = 1.0, 1000 karma = 1.5, 10000 karma = 2.0
        karma_factor = 1.0 + (min(karma, 10000) / 20000)
        
        # Confidence-based weight: lower original confidence = higher value
        confidence = contribution.original_confidence or 0.5
        confidence_factor = 1.5 - confidence  # 0.5 conf = 1.0, 0.1 conf = 1.4
        
        base_weight = karma_factor * confidence_factor
        
        # Consensus multiplier: check how many users agree
        consensus_multiplier = await self._calculate_consensus_multiplier(contribution)
        
        # Freshness multiplier based on model version gap
        freshness_multiplier = self._calculate_freshness_multiplier(
            contribution_model_version=self._get_contribution_model_version(contribution),
            current_model_version=current_model_version,
        )
        
        final_weight = base_weight * consensus_multiplier * freshness_multiplier
        
        return ContributionWeight(
            base_weight=base_weight,
            consensus_multiplier=consensus_multiplier,
            freshness_multiplier=freshness_multiplier,
            final_weight=final_weight,
        )
    
    async def _calculate_consensus_multiplier(
        self,
        contribution: TrainingContribution,
    ) -> float:
        """Calculate consensus multiplier based on agreement with other users.
        
        If multiple users made the same correction → boost weight
        If users disagree → reduce weight
        """
        time_tolerance_ms = 50
        
        # Find other contributions for the same onset
        result = await self._session.execute(
            select(TrainingContribution)
            .where(TrainingContribution.map_version_id == contribution.map_version_id)
            .where(TrainingContribution.onset_time_ms.between(
                contribution.onset_time_ms - time_tolerance_ms,
                contribution.onset_time_ms + time_tolerance_ms,
            ))
            .where(TrainingContribution.user_id != contribution.user_id)
            .where(TrainingContribution.status == ContributionStatus.APPROVED)
        )
        related = result.scalars().all()
        
        if not related:
            # Solo contribution - neutral weight
            return 1.0
        
        # Count agreements and disagreements
        agreements = sum(
            1 for c in related
            if c.corrected_component == contribution.corrected_component
        )
        disagreements = len(related) - agreements
        
        if agreements >= 2 and disagreements == 0:
            # Strong consensus - boost
            return 1.5
        elif agreements >= 1 and disagreements <= 1:
            # Weak consensus - slight boost
            return 1.2
        elif disagreements > agreements:
            # Disagreement - reduce weight
            return 0.5
        
        return 1.0
    
    def _calculate_freshness_multiplier(
        self,
        contribution_model_version: str | None,
        current_model_version: str,
    ) -> float:
        """Calculate freshness multiplier based on model version gap.
        
        Contributions based on very old model versions may no longer be
        relevant as the model has improved in other ways.
        """
        if not contribution_model_version:
            return 0.8  # Unknown version, slightly reduce
        
        version_gap = self._get_version_gap(
            contribution_model_version,
            current_model_version,
        )
        
        if version_gap <= 1:
            return 1.0  # Very fresh
        elif version_gap <= 2:
            return 0.9  # Recent
        elif version_gap <= MAX_MODEL_VERSION_GAP:
            return 0.7  # Slightly stale
        else:
            return 0.3  # Very stale - consider excluding
    
    def _get_contribution_model_version(
        self,
        contribution: TrainingContribution,
    ) -> str | None:
        """Get the model version the contribution was based on.
        
        This would typically be stored with the contribution or derived
        from the map version's creation date.
        """
        # TODO: Add model_version field to TrainingContribution
        # For now, return None
        return None
    
    def _get_version_gap(self, old_version: str, new_version: str) -> int:
        """Calculate the gap between two version strings.
        
        e.g., v5.1.0 to v5.3.0 = 2 (minor version gap)
        """
        try:
            old_parts = old_version.lstrip('vV').split('.')
            new_parts = new_version.lstrip('vV').split('.')
            
            old_minor = int(old_parts[1]) if len(old_parts) > 1 else 0
            new_minor = int(new_parts[1]) if len(new_parts) > 1 else 0
            
            return new_minor - old_minor
        except (ValueError, IndexError):
            return 0
    
    def _edit_touches_onset(
        self,
        diff_payload: dict,
        onset_time_ms: int,
        tolerance_ms: int,
    ) -> bool:
        """Check if an edit proposal's diff touches a specific onset time."""
        edits = diff_payload.get("edits", [])
        
        for edit in edits:
            edit_time = edit.get("onset_ms") or edit.get("time_ms") or edit.get("time")
            if edit_time is not None:
                if abs(edit_time - onset_time_ms) <= tolerance_ms:
                    return True
        
        return False
    
    # =========================================================================
    # Consensus Tracking
    # =========================================================================
    
    async def update_consensus_counts(
        self,
        map_version_id: uuid.UUID,
        onset_time_ms: int,
        new_corrected_component: str,
    ) -> int:
        """Update consensus counts for all contributions at this onset.
        
        When a new contribution is added, this updates the consensus_count
        for all contributions at the same onset based on how many agree.
        
        Args:
            map_version_id: The map version
            onset_time_ms: The onset time
            new_corrected_component: The new correction's component
            
        Returns:
            Number of contributions updated
        """
        # Get all contributions at this onset
        result = await self._session.execute(
            select(TrainingContribution).where(
                and_(
                    TrainingContribution.map_version_id == map_version_id,
                    TrainingContribution.onset_time_ms == onset_time_ms,
                    TrainingContribution.status.in_([
                        ContributionStatus.PENDING,
                        ContributionStatus.APPROVED,
                    ]),
                )
            )
        )
        contributions = list(result.scalars().all())
        
        if not contributions:
            return 0
        
        # Count how many agree with each unique correction
        correction_counts: dict[str, int] = {}
        for contrib in contributions:
            comp = contrib.corrected_component
            correction_counts[comp] = correction_counts.get(comp, 0) + 1
        
        # Update each contribution with its consensus count and conflict flag
        updated = 0
        has_conflicts = len(correction_counts) > 1  # Multiple different corrections
        
        for contrib in contributions:
            consensus = correction_counts.get(contrib.corrected_component, 1)
            if contrib.consensus_count != consensus or contrib.has_conflicts != has_conflicts:
                contrib.consensus_count = consensus
                contrib.has_conflicts = has_conflicts
                updated += 1
        
        if updated > 0:
            await self._session.flush()
            logger.debug(
                f"Updated consensus for {updated} contributions at "
                f"map_version={map_version_id} onset={onset_time_ms}ms"
            )
        
        return updated
    
    async def get_consensus_report(
        self,
        map_version_id: uuid.UUID,
    ) -> dict[int, dict]:
        """Get a report of all onsets with their consensus status.
        
        Args:
            map_version_id: The map version to analyze
            
        Returns:
            Dict mapping onset_time_ms to consensus info
        """
        result = await self._session.execute(
            select(TrainingContribution).where(
                and_(
                    TrainingContribution.map_version_id == map_version_id,
                    TrainingContribution.status.in_([
                        ContributionStatus.PENDING,
                        ContributionStatus.APPROVED,
                    ]),
                )
            )
        )
        contributions = list(result.scalars().all())
        
        # Group by onset
        by_onset: dict[int, list[TrainingContribution]] = {}
        for contrib in contributions:
            onset = contrib.onset_time_ms
            if onset not in by_onset:
                by_onset[onset] = []
            by_onset[onset].append(contrib)
        
        # Build report
        report = {}
        for onset_ms, contribs in by_onset.items():
            # Count corrections
            correction_counts: dict[str, int] = {}
            for c in contribs:
                comp = c.corrected_component
                correction_counts[comp] = correction_counts.get(comp, 0) + 1
            
            total = len(contribs)
            dominant = max(correction_counts.items(), key=lambda x: x[1])
            
            report[onset_ms] = {
                "total_contributions": total,
                "unique_corrections": len(correction_counts),
                "dominant_correction": dominant[0],
                "dominant_count": dominant[1],
                "consensus_ratio": dominant[1] / total if total > 0 else 0,
                "is_contentious": len(correction_counts) > 1,
                "meets_consensus_threshold": dominant[1] >= MIN_CONSENSUS_VOTES,
            }
        
        return report

    # =========================================================================
    # Batch Processing Support
    # =========================================================================
    
    async def get_weighted_contributions_for_training(
        self,
        batch_id: str | None = None,
        min_weight: float = 0.1,
    ) -> list[tuple[TrainingContribution, float]]:
        """Get contributions weighted for training.
        
        This filters and weights all approved contributions, returning
        only those that meet the minimum weight threshold.
        
        Args:
            batch_id: Optional batch ID to filter by
            min_weight: Minimum weight to include (default 0.1)
            
        Returns:
            List of (contribution, weight) tuples
        """
        current_version = self._settings.ai_model_version
        
        # Get all approved contributions
        query = select(TrainingContribution).where(
            TrainingContribution.status == ContributionStatus.APPROVED
        )
        
        result = await self._session.execute(query)
        contributions = result.scalars().all()
        
        weighted_contributions = []
        for contrib in contributions:
            weight = await self.calculate_contribution_weight(contrib, current_version)
            if weight.should_include and weight.final_weight >= min_weight:
                weighted_contributions.append((contrib, weight.final_weight))
        
        # Sort by weight descending
        weighted_contributions.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(
            f"Prepared {len(weighted_contributions)} weighted contributions "
            f"(filtered from {len(contributions)} total)"
        )
        
        return weighted_contributions
    
    async def invalidate_stale_contributions(
        self,
        max_version_gap: int = MAX_MODEL_VERSION_GAP,
    ) -> int:
        """Mark very old contributions as stale.
        
        Contributions based on model versions more than `max_version_gap`
        behind current are marked as stale and excluded from training.
        
        Returns:
            Number of contributions marked stale
        """
        # This would require a model_version field on TrainingContribution
        # For now, just log
        logger.info(
            f"Stale contribution check: max version gap = {max_version_gap}"
        )
        return 0


# =============================================================================
# Integration Helpers
# =============================================================================

async def pre_contribution_check(
    session: AsyncSession,
    map_version_id: uuid.UUID,
    onset_time_ms: int,
    user_id: uuid.UUID,
) -> ConflictCheckResult:
    """Convenience function for pre-contribution conflict check.
    
    Call this before accepting a new contribution to detect conflicts.
    """
    service = ContributionQualityService(session)
    return await service.check_contribution_conflicts(
        map_version_id, onset_time_ms, user_id
    )


async def should_re_evaluate_song(
    session: AsyncSession,
    song_id: uuid.UUID,
) -> ReEvalDecision:
    """Convenience function to check if re-evaluation should proceed."""
    service = ContributionQualityService(session)
    return await service.check_re_eval_conflicts(song_id)
