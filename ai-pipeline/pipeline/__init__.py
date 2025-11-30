"""
BeatSight AI Pipeline

Audio-to-beatmap processing system using Demucs and custom ML models.

Key components:
- Structured Decoder: HMM/Viterbi for musically coherent output
- Advanced Structured Decoder: Beam search, Transformer, CRF decoders
- Advanced Quantization: Tuplet, swing, and polyrhythm detection
- Adaptive Parameters: Dynamic, learned parameters that adapt to music
- Chart Readability: Playability rules and difficulty shaping
- Genre-Aware Decoder: Style-specific transition probabilities
- Pattern Library: Common drum pattern recognition and repair
- Beatmap Generator: Full .bsm file generation
"""

__version__ = "1.0.0"

# Core exports
from .process import process_audio_file

# Structured decoding
from .structured_decoder import (
    ViterbiDecoder,
    DrumState,
    TransitionMatrix,
    DecodedEvent,
    detect_time_signature,
    detect_swing_ratio,
    apply_structured_decoding,
)

# Advanced structured decoding
try:
    from .advanced_structured_decoder import (
        BeamSearchDecoder,
        CRFDecoder,
        EnsembleDecoder,
        apply_advanced_structured_decoding,
    )
except ImportError:
    pass  # Optional PyTorch dependency for Transformer

# Genre-aware decoding
try:
    from .genre_aware_decoder import (
        GenreAwareDecoder,
        GenreAwareTransitionMatrix,
        detect_genre,
        apply_genre_aware_decoding,
        Genre,
        GenreProfile,
        GENRE_PROFILES,
    )
except ImportError:
    pass

# Pattern library
try:
    from .pattern_library import (
        PatternLibrary,
        DrumPattern,
        PatternCategory,
        PatternComplexity,
        get_pattern_library,
        repair_with_patterns,
    )
except ImportError:
    pass

# Adaptive parameters (dynamic, learned configuration)
from .adaptive_parameters import (
    AdaptiveConfig,
    AudioCharacteristics,
    MusicStyle,
    LearnedTransitionMatrix,
    AdaptiveIOILimits,
    AdaptivePreprocessingParams,
    AdaptiveConfidenceThresholds,
    AdaptiveFocalLossParams,
    AdaptiveAugmentationParams,
    get_adaptive_config,
    set_adaptive_config,
    adapt_to_audio,
)

# Advanced quantization
from .advanced_quantization import (
    smart_quantize,
    analyze_subdivisions,
    auto_quantize_with_subdivision_detection,
    SubdivisionType,
    SubdivisionGrid,
    SUBDIVISION_GRIDS,
    # Dynamic detection
    discover_tuplet_ratio,
    detect_arbitrary_swing_ratio,
    detect_polyrhythm,
    detect_dynamic_time_signature,
    detect_metric_modulations,
    comprehensive_rhythm_analysis,
    # Dynamic grid management
    DynamicGridRegistry,
    GRID_REGISTRY,
    create_adaptive_grid,
    quantize_with_dynamic_grid,
    # Result types
    QuantizationResult,
    ComprehensiveRhythmAnalysis,
    PolyrhythmAnalysis,
    DynamicTimeSignature,
    MetricModulation,
)

# Chart readability
from .chart_readability import (
    ChartReadabilityFilter,
    filter_chart_for_readability,
    detect_sections,
    apply_difficulty_curve,
    # Dynamic difficulty
    DynamicDifficultyCurve,
    apply_dynamic_difficulty,
    # Rules and types
    PhysicalConstraints,
    ReadabilityRules,
    Limb,
)

# Beatmap generation
from .beatmap_generator import (
    generate_beatmap,
    assign_lanes,
    assign_lanes_dynamic,
    detect_lane_count,  # For manual mapping - detects recommended lane count
    calculate_difficulty,
)

# Dynamic lane layout
try:
    from .dynamic_lane_layout import (
        DynamicLaneLayout,
        DynamicLaneLayoutBuilder,
        LaneDefinition,
        ComponentCategory,
        classify_component,
    )
except ImportError:
    pass  # Optional module

# Manual mapping workflow helpers
try:
    from .manual_mapping_helper import (
        # Main API
        detect_lanes_for_manual_mapping,
        create_user_specified_lanes,
        adjust_lane_configuration,
        get_lane_detection_prompt,
        quick_lane_preview,
        # Types
        LaneConfiguration,
        LaneDetectionChoice,
    )
except ImportError:
    pass  # Optional module
