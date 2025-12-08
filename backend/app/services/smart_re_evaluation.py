"""Smart Re-evaluation: Only re-process uncertain portions of a beatmap.

Instead of fully re-transcribing a song when a new model is available,
this module implements an intelligent partial re-evaluation strategy:

1. **Load Original Analysis**: Get confidence scores from original transcription
2. **Identify Low-Confidence Regions**: Find sections where the old model was uncertain
3. **Re-process Only Those Regions**: Run new model on uncertain portions
4. **Merge Results**: Combine high-confidence original notes with new predictions

This provides:
- **Efficiency**: 2-10x faster than full re-processing
- **Stability**: Preserves notes the user may have already verified
- **Quality**: Focuses compute on areas that need improvement
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

# Confidence threshold below which sections are re-evaluated
LOW_CONFIDENCE_THRESHOLD = 0.7  # Re-evaluate notes with < 70% confidence

# Minimum gap between regions to merge them (milliseconds)
REGION_MERGE_GAP_MS = 500

# Buffer around low-confidence regions (milliseconds)
REGION_BUFFER_MS = 250

# Minimum region duration to bother re-evaluating (milliseconds)
MIN_REGION_DURATION_MS = 100


@dataclass
class ConfidenceRegion:
    """A time region with associated confidence score."""
    
    start_ms: int
    end_ms: int
    avg_confidence: float
    note_count: int
    
    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms
    
    @property
    def needs_re_evaluation(self) -> bool:
        return self.avg_confidence < LOW_CONFIDENCE_THRESHOLD


@dataclass
class SmartReEvalPlan:
    """Plan for smart re-evaluation of a beatmap."""
    
    song_id: str
    total_duration_ms: int
    original_model_version: str
    
    # Analysis results
    total_notes: int = 0
    high_confidence_notes: int = 0
    low_confidence_notes: int = 0
    
    # Regions to re-evaluate
    low_confidence_regions: list[ConfidenceRegion] = field(default_factory=list)
    
    # Efficiency stats
    total_region_duration_ms: int = 0
    
    @property
    def re_eval_percentage(self) -> float:
        """Percentage of song that needs re-evaluation."""
        if self.total_duration_ms == 0:
            return 0.0
        return (self.total_region_duration_ms / self.total_duration_ms) * 100
    
    @property
    def efficiency_gain(self) -> float:
        """How much faster this is vs full re-evaluation."""
        if self.re_eval_percentage == 0:
            return float('inf')  # Nothing to re-evaluate
        return 100 / self.re_eval_percentage


@dataclass
class MergedNote:
    """A note from merged re-evaluation results."""
    
    onset_ms: int
    component: str
    confidence: float
    source: str  # "original" or "new_model"


class SmartReEvaluator:
    """Intelligent partial re-evaluation of beatmaps.
    
    Instead of re-processing the entire audio file when a new model
    is available, this class:
    
    1. Analyzes confidence scores from the original transcription
    2. Identifies regions where the old model was uncertain
    3. Only re-processes those specific time regions
    4. Merges high-confidence original notes with new predictions
    
    Example usage:
        evaluator = SmartReEvaluator()
        
        # Analyze original beatmap
        plan = evaluator.create_re_eval_plan(original_analysis)
        
        print(f"Re-evaluating {plan.re_eval_percentage:.1f}% of song")
        print(f"Efficiency gain: {plan.efficiency_gain:.1f}x faster")
        
        # Process only low-confidence regions
        if plan.low_confidence_regions:
            new_notes = await process_regions(audio, plan.low_confidence_regions)
            merged = evaluator.merge_results(original_analysis, new_notes, plan)
    """
    
    def __init__(
        self,
        confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD,
        region_buffer_ms: int = REGION_BUFFER_MS,
        min_region_duration_ms: int = MIN_REGION_DURATION_MS,
    ):
        self.confidence_threshold = confidence_threshold
        self.region_buffer_ms = region_buffer_ms
        self.min_region_duration_ms = min_region_duration_ms
    
    def create_re_eval_plan(
        self,
        original_analysis: dict,
        total_duration_ms: int,
    ) -> SmartReEvalPlan:
        """Create a plan for smart re-evaluation.
        
        Args:
            original_analysis: Original AI analysis with confidence scores.
                Expected format:
                {
                    "notes": [
                        {"onset_ms": 1000, "component": "kick", "confidence": 0.95},
                        {"onset_ms": 1200, "component": "snare", "confidence": 0.45},
                        ...
                    ],
                    "model_version": "v5.0.0"
                }
            total_duration_ms: Total duration of the audio in milliseconds.
            
        Returns:
            SmartReEvalPlan with identified low-confidence regions.
        """
        notes = original_analysis.get("notes", [])
        model_version = original_analysis.get("model_version", "unknown")
        
        plan = SmartReEvalPlan(
            song_id=original_analysis.get("song_id", "unknown"),
            total_duration_ms=total_duration_ms,
            original_model_version=model_version,
            total_notes=len(notes),
        )
        
        if not notes:
            return plan
        
        # Classify notes by confidence
        high_conf_notes = []
        low_conf_notes = []
        
        for note in notes:
            confidence = note.get("confidence", 0.5)
            if confidence >= self.confidence_threshold:
                high_conf_notes.append(note)
            else:
                low_conf_notes.append(note)
        
        plan.high_confidence_notes = len(high_conf_notes)
        plan.low_confidence_notes = len(low_conf_notes)
        
        # Find low-confidence regions
        if low_conf_notes:
            regions = self._find_low_confidence_regions(
                low_conf_notes, total_duration_ms
            )
            plan.low_confidence_regions = regions
            plan.total_region_duration_ms = sum(r.duration_ms for r in regions)
        
        logger.info(
            f"Re-eval plan: {plan.low_confidence_notes}/{plan.total_notes} notes "
            f"in {len(plan.low_confidence_regions)} regions "
            f"({plan.re_eval_percentage:.1f}% of song, {plan.efficiency_gain:.1f}x faster)"
        )
        
        return plan
    
    def _find_low_confidence_regions(
        self,
        low_conf_notes: list[dict],
        total_duration_ms: int,
    ) -> list[ConfidenceRegion]:
        """Group low-confidence notes into contiguous regions.
        
        Notes that are close together (within REGION_MERGE_GAP_MS) are
        grouped into the same region. Each region is buffered by
        REGION_BUFFER_MS on each side.
        """
        if not low_conf_notes:
            return []
        
        # Sort by onset time
        sorted_notes = sorted(low_conf_notes, key=lambda n: n.get("onset_ms", 0))
        
        regions = []
        current_region_notes = [sorted_notes[0]]
        
        for note in sorted_notes[1:]:
            last_note = current_region_notes[-1]
            gap = note.get("onset_ms", 0) - last_note.get("onset_ms", 0)
            
            if gap <= REGION_MERGE_GAP_MS:
                # Merge into current region
                current_region_notes.append(note)
            else:
                # Start new region
                region = self._create_region(current_region_notes, total_duration_ms)
                if region and region.duration_ms >= self.min_region_duration_ms:
                    regions.append(region)
                current_region_notes = [note]
        
        # Don't forget the last region
        if current_region_notes:
            region = self._create_region(current_region_notes, total_duration_ms)
            if region and region.duration_ms >= self.min_region_duration_ms:
                regions.append(region)
        
        return regions
    
    def _create_region(
        self,
        notes: list[dict],
        total_duration_ms: int,
    ) -> ConfidenceRegion | None:
        """Create a ConfidenceRegion from a group of notes."""
        if not notes:
            return None
        
        onset_times = [n.get("onset_ms", 0) for n in notes]
        confidences = [n.get("confidence", 0.5) for n in notes]
        
        # Region bounds with buffer
        start_ms = max(0, min(onset_times) - self.region_buffer_ms)
        end_ms = min(total_duration_ms, max(onset_times) + self.region_buffer_ms)
        
        return ConfidenceRegion(
            start_ms=start_ms,
            end_ms=end_ms,
            avg_confidence=sum(confidences) / len(confidences),
            note_count=len(notes),
        )
    
    def merge_results(
        self,
        original_notes: list[dict],
        new_region_notes: list[dict],
        plan: SmartReEvalPlan,
    ) -> list[MergedNote]:
        """Merge original high-confidence notes with new region predictions.
        
        Args:
            original_notes: All notes from original transcription
            new_region_notes: New notes from re-evaluated regions
            plan: The re-evaluation plan used
            
        Returns:
            Merged list of notes, preferring new model for low-confidence regions
        """
        merged = []
        
        # Keep high-confidence notes from original
        for note in original_notes:
            confidence = note.get("confidence", 0.5)
            onset_ms = note.get("onset_ms", 0)
            
            # Check if this note is in a re-evaluated region
            in_re_eval_region = any(
                r.start_ms <= onset_ms <= r.end_ms
                for r in plan.low_confidence_regions
            )
            
            if not in_re_eval_region and confidence >= self.confidence_threshold:
                merged.append(MergedNote(
                    onset_ms=onset_ms,
                    component=note.get("component", "unknown"),
                    confidence=confidence,
                    source="original",
                ))
        
        # Add all notes from re-evaluated regions
        for note in new_region_notes:
            merged.append(MergedNote(
                onset_ms=note.get("onset_ms", 0),
                component=note.get("component", "unknown"),
                confidence=note.get("confidence", 0.5),
                source="new_model",
            ))
        
        # Sort by onset time
        merged.sort(key=lambda n: n.onset_ms)
        
        # Remove duplicates (within 10ms tolerance)
        deduplicated = self._deduplicate_notes(merged)
        
        logger.info(
            f"Merged results: {len(deduplicated)} notes "
            f"({sum(1 for n in deduplicated if n.source == 'original')} original, "
            f"{sum(1 for n in deduplicated if n.source == 'new_model')} new)"
        )
        
        return deduplicated
    
    def _deduplicate_notes(
        self,
        notes: list[MergedNote],
        tolerance_ms: int = 10,
    ) -> list[MergedNote]:
        """Remove duplicate notes within tolerance, preferring new model."""
        if not notes:
            return []
        
        deduplicated = [notes[0]]
        
        for note in notes[1:]:
            last = deduplicated[-1]
            
            # Check if this is a duplicate
            if abs(note.onset_ms - last.onset_ms) <= tolerance_ms:
                # Same position - prefer new model
                if note.source == "new_model" and last.source == "original":
                    deduplicated[-1] = note
                # Otherwise keep existing (prefer higher confidence)
                elif note.confidence > last.confidence:
                    deduplicated[-1] = note
            else:
                # Not a duplicate
                deduplicated.append(note)
        
        return deduplicated


def should_use_smart_re_eval(
    original_analysis: dict,
    total_duration_ms: int,
    min_efficiency_gain: float = 1.5,
) -> tuple[bool, SmartReEvalPlan]:
    """Determine if smart re-evaluation is worthwhile for this song.
    
    Args:
        original_analysis: Original AI analysis with confidence scores
        total_duration_ms: Total audio duration in milliseconds
        min_efficiency_gain: Minimum efficiency gain to use smart re-eval
        
    Returns:
        Tuple of (should_use_smart, plan)
    """
    evaluator = SmartReEvaluator()
    plan = evaluator.create_re_eval_plan(original_analysis, total_duration_ms)
    
    # If efficiency gain is significant, use smart re-eval
    should_use = plan.efficiency_gain >= min_efficiency_gain
    
    if should_use:
        logger.info(
            f"Using smart re-eval: {plan.efficiency_gain:.1f}x efficiency gain"
        )
    else:
        logger.info(
            f"Using full re-eval: efficiency gain ({plan.efficiency_gain:.1f}x) "
            f"below threshold ({min_efficiency_gain}x)"
        )
    
    return should_use, plan


# =============================================================================
# Example Usage in AI Pipeline
# =============================================================================

async def re_evaluate_song_smart(
    song_id: str,
    audio_path: str,
    original_analysis: dict,
    new_model_version: str,
) -> dict:
    """Re-evaluate a song using smart partial processing.
    
    This is the main entry point for smart re-evaluation.
    
    Args:
        song_id: ID of the song being re-evaluated
        audio_path: Path to audio file
        original_analysis: Original transcription with confidence scores
        new_model_version: Version of new model to use
        
    Returns:
        New analysis dict with merged results
    """
    # Get audio duration (would come from actual audio loading)
    total_duration_ms = original_analysis.get("duration_ms", 300000)  # Default 5 min
    
    # Check if smart re-eval is worthwhile
    use_smart, plan = should_use_smart_re_eval(original_analysis, total_duration_ms)
    
    if not use_smart or not plan.low_confidence_regions:
        # Full re-evaluation needed
        logger.info(f"Full re-evaluation for song {song_id}")
        # Would call full transcription pipeline here
        return {"status": "full_re_eval_needed"}
    
    # Smart re-evaluation
    logger.info(
        f"Smart re-evaluation for song {song_id}: "
        f"processing {len(plan.low_confidence_regions)} regions "
        f"({plan.re_eval_percentage:.1f}% of audio)"
    )
    
    # Process only low-confidence regions with new model
    new_region_notes = []
    for region in plan.low_confidence_regions:
        # Would extract audio segment and run through new model
        # new_segment_notes = await process_audio_segment(
        #     audio_path, 
        #     region.start_ms, 
        #     region.end_ms,
        #     new_model_version
        # )
        # new_region_notes.extend(new_segment_notes)
        pass
    
    # Merge results
    evaluator = SmartReEvaluator()
    merged_notes = evaluator.merge_results(
        original_analysis.get("notes", []),
        new_region_notes,
        plan,
    )
    
    return {
        "song_id": song_id,
        "model_version": new_model_version,
        "re_eval_type": "smart",
        "regions_processed": len(plan.low_confidence_regions),
        "efficiency_gain": plan.efficiency_gain,
        "notes": [
            {
                "onset_ms": n.onset_ms,
                "component": n.component,
                "confidence": n.confidence,
                "source": n.source,
            }
            for n in merged_notes
        ],
    }
