"""
Central configuration for excluded and remapped drum component classes.

This module is the SINGLE SOURCE OF TRUTH for:
1. Classes to exclude entirely (insufficient samples, ambiguous)
2. Classes to remap to other classes (kit-relative labels → generic)

The build_training_dataset.py and all ingest scripts use this configuration,
so you NEVER need to run cleanup scripts after rebuilding.

To modify:
1. Edit EXCLUDED_CLASSES or LABEL_REMAPPING below
2. Re-run build_training_dataset.py to rebuild
3. That's it - no cleanup needed!

History:
- 2025-11-25: Initial exclusions (shaker, tambourine, drum_mix) based on extreme
  class imbalance causing training instability (2M:1 ratio).
- 2025-11-25: Added crash_1, crash_2 remapping to "crash". These labels are 
  kit-relative, not acoustically consistent. Multi-cymbal distinction is handled
  by the pitch ranking post-processor (instrument_pitch_ranker.py).
"""

from typing import FrozenSet, Set, Dict, Optional

# =============================================================================
# LABEL REMAPPING
# =============================================================================
# Classes that should be remapped to a different label during ingestion/build.
# This is applied BEFORE exclusion checking.
# Format: {"original_label": "target_label"}

LABEL_REMAPPING: Dict[str, str] = {
    # Cymbal variants → unified classes (handled by pitch ranker post-processing)
    "crash_1": "crash",
    "crash_2": "crash", 
    "crash_3": "crash",
    "crash_4": "crash",
    "china_1": "china",
    "china_2": "china",
    "splash_1": "splash",
    "splash_2": "splash",
    
    # Tom variants → unified "tom" class (handled by pitch ranker post-processing)
    # The model learns to recognize "a tom hit", then pitch ranking determines
    # which physical tom (high/mid/low/floor) within each song's context.
    "tom_high": "tom",
    "tom_mid": "tom",
    "tom_low": "tom",
    "tom_high_1": "tom",
    "tom_high_2": "tom",
    "tom_mid_1": "tom",
    "tom_mid_2": "tom",
    "tom_low_1": "tom",
    "tom_low_2": "tom",
    "floor_tom": "tom",
    "rack_tom": "tom",
    
    # Snare articulations → all merge to snare for 12-class model
    # snare_center is just a regular snare hit (center of head)
    "snare_center": "snare",
    # cross_stick is a specific technique, not snare-specific
    "snare_cross_stick": "cross_stick",
    # rimshot merges into snare - detected via acoustic post-processing
    "snare_rimshot": "snare",
    "rimshot": "snare",  # Rimshot detection is handled by RimshotDetector post-processor
    
    # Hi-hat variants
    # hihat_foot_splash is a pedal/foot technique
    "hihat_foot_splash": "hihat_pedal",
    # hihat_splash (stick on partially open hihat) sounds like open hihat
    "hihat_splash": "hihat_open",
    
    # Common aliases
    "bass": "kick",
    "bass_drum": "kick",
    "hh_closed": "hihat_closed",
    "hh_open": "hihat_open",
    "hh_pedal": "hihat_pedal",
}


# =============================================================================
# EXCLUDED CLASSES  
# =============================================================================
# Classes to exclude entirely from training datasets.
# These are filtered out during build_training_dataset.py.

EXCLUDED_CLASSES: FrozenSet[str] = frozenset({
    "shaker",          # 2 samples total - statistically unreliable
    "tambourine",      # 3 samples total - statistically unreliable  
    "drum_mix",        # Represents a mix, not a single drum component
    "cowbell",         # Often poorly labeled, inconsistent across datasets
    "clap",            # Electronic, not acoustic drum
    "aux_percussion",  # Inconsistent grab-bag of miscellaneous sounds
    "cymbal_choke",    # Detected via post-processing (sustain cutoff analysis)
})

# Minimum sample threshold for future warnings (not enforced, just logged)
# Classes below this threshold may produce unreliable predictions
MIN_RECOMMENDED_SAMPLES: int = 100


# =============================================================================
# API FUNCTIONS
# =============================================================================

def remap_label(label: str) -> str:
    """
    Remap a label to its canonical form.
    
    This should be called BEFORE should_exclude_class().
    
    Args:
        label: Original label from ingest script
        
    Returns:
        Remapped label (or original if no remapping defined)
    """
    return LABEL_REMAPPING.get(label, label)


def should_exclude_class(label: str) -> bool:
    """
    Check if a drum component class should be excluded from training.
    
    Note: Call remap_label() first if you want remapping applied.
    
    Args:
        label: Label to check (should already be remapped if desired)
        
    Returns:
        True if the class should be excluded
    """
    return label in EXCLUDED_CLASSES


def process_label(label: str) -> Optional[str]:
    """
    Process a label through remapping and exclusion.
    
    This is the recommended single function to call during ingestion.
    
    Args:
        label: Original label
        
    Returns:
        Processed label, or None if it should be excluded
    """
    remapped = remap_label(label)
    if should_exclude_class(remapped):
        return None
    return remapped


def get_excluded_classes() -> Set[str]:
    """Return mutable copy of excluded classes for external tools."""
    return set(EXCLUDED_CLASSES)


def get_label_remapping() -> Dict[str, str]:
    """Return copy of label remapping dict for external tools."""
    return dict(LABEL_REMAPPING)
