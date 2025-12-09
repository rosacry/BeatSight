"""Training Export Service

Exports approved contributions to training manifest format
for the AI pipeline to consume.

The manifest format is designed to be compatible with the
ai-pipeline training infrastructure.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training_contribution import (
    ContributionStatus,
    CorrectionType,
    TrainingContribution,
)
from app.models.user import User


# Weight multipliers for verifier karma tiers
VERIFIER_KARMA_WEIGHTS = {
    "expert": 1.3,  # 1000+ karma
    "trusted": 1.15,  # 500-999 karma
    "regular": 1.0,  # 100-499 karma
    "new": 0.9,  # <100 karma
}


class TrainingExportService:
    """Service for exporting contributions to training manifest format."""

    MANIFEST_VERSION = "1.1"  # Bumped for verifier karma weighting

    def __init__(self, db: AsyncSession):
        self.db = db
        self._verifier_cache: dict[UUID, int] = {}

    async def generate_manifest(
        self,
        limit: int = 10000,
        include_metadata: bool = True,
        weighted_by_karma: bool = True,
    ) -> dict[str, Any]:
        """Generate a training manifest from approved contributions.

        Args:
            limit: Maximum contributions to include
            include_metadata: Include contributor metadata (anonymized)
            weighted_by_karma: Include karma-based weights for each sample

        Returns:
            Training manifest dictionary ready for JSON export
        """
        # Fetch approved but not yet exported contributions with verifier info
        result = await self.db.execute(
            select(TrainingContribution)
            .where(
                and_(
                    TrainingContribution.status == ContributionStatus.APPROVED,
                    TrainingContribution.exported_to_training.is_(False),
                )
            )
            .limit(limit)
        )
        contributions = result.scalars().all()

        if not contributions:
            return self._create_empty_manifest()

        # Pre-fetch verifier karma scores
        verifier_ids = {c.verifier_id for c in contributions if c.verifier_id}
        await self._cache_verifier_karma(verifier_ids)

        # Build samples
        samples = []
        component_counts: dict[str, int] = {}
        correction_type_counts: dict[str, int] = {}
        user_contributions: dict[UUID, int] = {}
        verifier_stats: dict[str, int] = {
            "expert": 0,
            "trusted": 0,
            "regular": 0,
            "new": 0,
        }

        for c in contributions:
            sample = await self._contribution_to_sample(c, weighted_by_karma)
            samples.append(sample)

            # Track statistics
            if c.corrected_component:
                component_counts[c.corrected_component] = (
                    component_counts.get(c.corrected_component, 0) + 1
                )
            correction_type_counts[c.correction_type.value] = (
                correction_type_counts.get(c.correction_type.value, 0) + 1
            )
            user_contributions[c.user_id] = user_contributions.get(c.user_id, 0) + 1

            # Track verifier tier
            if c.verifier_id:
                tier = self._get_verifier_tier(c.verifier_id)
                verifier_stats[tier] = verifier_stats.get(tier, 0) + 1

        # Generate batch ID based on content hash
        content_hash = hashlib.sha256(
            json.dumps([s["id"] for s in samples], sort_keys=True).encode()
        ).hexdigest()[:16]
        batch_id = f"contrib-{datetime.utcnow().strftime('%Y%m%d')}-{content_hash}"

        manifest = {
            "version": self.MANIFEST_VERSION,
            "batch_id": batch_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "sample_count": len(samples),
            "source": "beatsight_community_contributions",
            "statistics": {
                "component_distribution": component_counts,
                "correction_types": correction_type_counts,
                "unique_contributors": len(user_contributions),
                "avg_contributions_per_user": (
                    len(samples) / len(user_contributions) if user_contributions else 0
                ),
                "verifier_tiers": verifier_stats,
            },
            "samples": samples,
        }

        if include_metadata:
            manifest["metadata"] = {
                "export_timestamp": datetime.utcnow().isoformat() + "Z",
                "weighted": weighted_by_karma,
                "quality_filtered": True,
                "min_karma_threshold": 100,  # From contribution validation
                "verifier_karma_weights": VERIFIER_KARMA_WEIGHTS,
            }

        return manifest

    async def _cache_verifier_karma(self, verifier_ids: set[UUID]) -> None:
        """Pre-fetch verifier karma scores for batch processing."""
        if not verifier_ids:
            return

        result = await self.db.execute(
            select(User.id, User.karma_score).where(User.id.in_(verifier_ids))
        )
        for user_id, karma in result.all():
            self._verifier_cache[user_id] = karma or 0

    def _get_verifier_tier(self, verifier_id: Optional[UUID]) -> str:
        """Get the verifier's karma tier."""
        if not verifier_id:
            return "regular"

        karma = self._verifier_cache.get(verifier_id, 0)

        if karma >= 1000:
            return "expert"
        elif karma >= 500:
            return "trusted"
        elif karma >= 100:
            return "regular"
        else:
            return "new"

    def _get_verifier_weight(self, verifier_id: Optional[UUID]) -> float:
        """Get weight multiplier based on verifier karma."""
        tier = self._get_verifier_tier(verifier_id)
        return VERIFIER_KARMA_WEIGHTS.get(tier, 1.0)

    async def _contribution_to_sample(
        self,
        contribution: TrainingContribution,
        include_weight: bool = True,
    ) -> dict[str, Any]:
        """Convert a contribution to a training sample.

        Training sample format:
        {
            "id": "uuid",
            "map_version_id": "uuid",
            "onset_time_ms": 12345,
            "correction_type": "component_change",
            "original": {
                "component": "snare",
                "confidence": 0.65
            },
            "corrected": {
                "component": "hi-hat",
                "time_ms": 12350,
                "velocity": 80
            },
            "weight": 1.2,  # Based on correction value + verifier karma
            "verifier_tier": "expert"  # Verifier karma tier
        }
        """
        sample: dict[str, Any] = {
            "id": str(contribution.id),
            "map_version_id": str(contribution.map_version_id),
            "onset_time_ms": contribution.onset_time_ms,
            "correction_type": contribution.correction_type.value,
            "original": {
                "component": contribution.original_component,
                "confidence": contribution.original_confidence,
            },
            "corrected": {},
        }

        # Add corrected values based on correction type
        if contribution.corrected_component:
            sample["corrected"]["component"] = contribution.corrected_component
        if contribution.corrected_time_ms is not None:
            sample["corrected"]["time_ms"] = contribution.corrected_time_ms
        if contribution.corrected_velocity is not None:
            sample["corrected"]["velocity"] = contribution.corrected_velocity

        # Add verifier tier
        if contribution.verifier_id:
            sample["verifier_tier"] = self._get_verifier_tier(contribution.verifier_id)

        # Add weight based on correction value and verifier karma
        if include_weight:
            sample["weight"] = self._calculate_sample_weight(contribution)

        return sample

    def _calculate_sample_weight(self, contribution: TrainingContribution) -> float:
        """Calculate training weight for a contribution.

        Higher weights for:
        - Corrections to high-confidence misses (model was wrong but confident)
        - Component changes (more valuable than velocity tweaks)
        - Verified by high-karma verifiers (expert verification = more trust)
        - Pre-calculated user quality weight (from ContributionQualityService)
        
        Lower weights for:
        - Contributions with conflicts (multiple disagreeing corrections)
        - Low consensus count (contentious corrections)

        Returns:
            Weight multiplier (1.0 = normal, >1.0 = more valuable, <1.0 = less)
        """
        # Start with the pre-calculated quality weight from submission
        weight = getattr(contribution, 'training_weight', 1.0)

        # Higher original confidence = model was wrongly confident
        # These samples are especially valuable for training
        if contribution.original_confidence is not None:
            if contribution.original_confidence > 0.9:
                weight *= 1.5  # High-confidence error
            elif contribution.original_confidence > 0.7:
                weight *= 1.2  # Medium-confidence error

        # Component changes are more valuable than timing tweaks
        if contribution.correction_type == CorrectionType.COMPONENT_CHANGE:
            weight *= 1.3
        elif contribution.correction_type == CorrectionType.NOTE_ADDITION:
            weight *= 1.4  # Missing notes are critical
        elif contribution.correction_type == CorrectionType.NOTE_REMOVAL:
            weight *= 1.2  # False positives important too

        # Apply verifier karma weight
        verifier_weight = self._get_verifier_weight(contribution.verifier_id)
        weight *= verifier_weight
        
        # Penalize contributions with conflicts
        if getattr(contribution, 'has_conflicts', False):
            consensus = getattr(contribution, 'consensus_count', 1)
            if consensus < 3:
                weight *= 0.5  # Significant penalty for unresolved conflicts
            elif consensus < 5:
                weight *= 0.75  # Moderate penalty for low consensus
            # With high consensus, conflict is resolved - no penalty

        # Clamp weight to reasonable range
        return round(min(max(weight, 0.1), 3.0), 3)

    def _create_empty_manifest(self) -> dict[str, Any]:
        """Create an empty manifest when no contributions available."""
        return {
            "version": self.MANIFEST_VERSION,
            "batch_id": "",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "sample_count": 0,
            "source": "beatsight_community_contributions",
            "statistics": {
                "component_distribution": {},
                "correction_types": {},
                "unique_contributors": 0,
                "avg_contributions_per_user": 0,
            },
            "samples": [],
        }

    async def mark_as_exported(
        self,
        contribution_ids: list[UUID],
        batch_id: str,
    ) -> int:
        """Mark contributions as exported after successful training integration.

        Args:
            contribution_ids: IDs to mark as exported
            batch_id: The export batch identifier

        Returns:
            Number of contributions marked
        """
        if not contribution_ids:
            return 0

        now = datetime.utcnow()
        count = 0

        for contrib_id in contribution_ids:
            result = await self.db.execute(
                select(TrainingContribution).where(
                    TrainingContribution.id == contrib_id
                )
            )
            contrib = result.scalar_one_or_none()
            if contrib:
                contrib.exported_to_training = True
                contrib.exported_at = now
                contrib.export_batch_id = batch_id
                contrib.status = ContributionStatus.EXPORTED
                count += 1

        await self.db.commit()
        return count

    async def get_export_statistics(self) -> dict[str, Any]:
        """Get statistics about export-ready contributions.

        Returns:
            Dictionary with export statistics
        """
        # Count by status
        result = await self.db.execute(
            select(
                TrainingContribution.status,
                func.count(TrainingContribution.id),
            ).group_by(TrainingContribution.status)
        )
        status_counts = dict(result.all())

        # Count by correction type
        result = await self.db.execute(
            select(
                TrainingContribution.correction_type,
                func.count(TrainingContribution.id),
            )
            .where(TrainingContribution.status == ContributionStatus.APPROVED)
            .group_by(TrainingContribution.correction_type)
        )
        correction_type_counts = {ct.value: count for ct, count in result.all()}

        # Pending export count
        result = await self.db.execute(
            select(func.count(TrainingContribution.id)).where(
                and_(
                    TrainingContribution.status == ContributionStatus.APPROVED,
                    TrainingContribution.exported_to_training.is_(False),
                )
            )
        )
        pending_export = result.scalar() or 0

        return {
            "total_contributions": sum(status_counts.values()),
            "pending_review": status_counts.get(ContributionStatus.PENDING, 0),
            "approved": status_counts.get(ContributionStatus.APPROVED, 0),
            "rejected": status_counts.get(ContributionStatus.REJECTED, 0),
            "exported": status_counts.get(ContributionStatus.EXPORTED, 0),
            "pending_export": pending_export,
            "correction_types_approved": correction_type_counts,
        }
