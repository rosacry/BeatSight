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
from .process import process_audio_file as process_audio_file

# Structured decoding
from .structured_decoder import (
    ViterbiDecoder as ViterbiDecoder,
    DrumState as DrumState,
    TransitionMatrix as TransitionMatrix,
    DecodedEvent as DecodedEvent,
    detect_time_signature as detect_time_signature,
    detect_swing_ratio as detect_swing_ratio,
    apply_structured_decoding as apply_structured_decoding,
)

# Advanced structured decoding
try:
    from .advanced_structured_decoder import (
        BeamSearchDecoder as BeamSearchDecoder,
        CRFDecoder as CRFDecoder,
        EnsembleDecoder as EnsembleDecoder,
        apply_advanced_structured_decoding as apply_advanced_structured_decoding,
    )
except ImportError:
    pass  # Optional PyTorch dependency for Transformer

# Genre-aware decoding
try:
    from .genre_aware_decoder import (
        GenreAwareDecoder as GenreAwareDecoder,
        GenreAwareTransitionMatrix as GenreAwareTransitionMatrix,
        detect_genre as detect_genre,
        apply_genre_aware_decoding as apply_genre_aware_decoding,
        Genre as Genre,
        GenreProfile as GenreProfile,
        GENRE_PROFILES as GENRE_PROFILES,
    )
except ImportError:
    pass

# Pattern library
try:
    from .pattern_library import (
        PatternLibrary as PatternLibrary,
        DrumPattern as DrumPattern,
        PatternCategory as PatternCategory,
        PatternComplexity as PatternComplexity,
        get_pattern_library as get_pattern_library,
        repair_with_patterns as repair_with_patterns,
    )
except ImportError:
    pass

# Adaptive parameters (dynamic, learned configuration)
from .adaptive_parameters import (
    AdaptiveConfig as AdaptiveConfig,
    AudioCharacteristics as AudioCharacteristics,
    MusicStyle as MusicStyle,
    LearnedTransitionMatrix as LearnedTransitionMatrix,
    AdaptiveIOILimits as AdaptiveIOILimits,
    AdaptivePreprocessingParams as AdaptivePreprocessingParams,
    AdaptiveConfidenceThresholds as AdaptiveConfidenceThresholds,
    AdaptiveFocalLossParams as AdaptiveFocalLossParams,
    AdaptiveAugmentationParams as AdaptiveAugmentationParams,
    get_adaptive_config as get_adaptive_config,
    set_adaptive_config as set_adaptive_config,
    adapt_to_audio as adapt_to_audio,
)

# Advanced quantization
from .advanced_quantization import (
    smart_quantize as smart_quantize,
    analyze_subdivisions as analyze_subdivisions,
    auto_quantize_with_subdivision_detection as auto_quantize_with_subdivision_detection,
    SubdivisionType as SubdivisionType,
    SubdivisionGrid as SubdivisionGrid,
    SUBDIVISION_GRIDS as SUBDIVISION_GRIDS,
    # Dynamic detection
    discover_tuplet_ratio as discover_tuplet_ratio,
    detect_arbitrary_swing_ratio as detect_arbitrary_swing_ratio,
    detect_polyrhythm as detect_polyrhythm,
    detect_dynamic_time_signature as detect_dynamic_time_signature,
    detect_metric_modulations as detect_metric_modulations,
    comprehensive_rhythm_analysis as comprehensive_rhythm_analysis,
    # Dynamic grid management
    DynamicGridRegistry as DynamicGridRegistry,
    GRID_REGISTRY as GRID_REGISTRY,
    create_adaptive_grid as create_adaptive_grid,
    quantize_with_dynamic_grid as quantize_with_dynamic_grid,
    # Result types
    QuantizationResult as QuantizationResult,
    ComprehensiveRhythmAnalysis as ComprehensiveRhythmAnalysis,
    PolyrhythmAnalysis as PolyrhythmAnalysis,
    DynamicTimeSignature as DynamicTimeSignature,
    MetricModulation as MetricModulation,
)

# Chart readability
from .chart_readability import (
    ChartReadabilityFilter as ChartReadabilityFilter,
    filter_chart_for_readability as filter_chart_for_readability,
    detect_sections as detect_sections,
    apply_difficulty_curve as apply_difficulty_curve,
    # Dynamic difficulty
    DynamicDifficultyCurve as DynamicDifficultyCurve,
    apply_dynamic_difficulty as apply_dynamic_difficulty,
    # Rules and types
    PhysicalConstraints as PhysicalConstraints,
    ReadabilityRules as ReadabilityRules,
    Limb as Limb,
)

# Beatmap generation
from .beatmap_generator import (
    generate_beatmap as generate_beatmap,
    assign_lanes as assign_lanes,
    assign_lanes_dynamic as assign_lanes_dynamic,
    assign_lanes_static as assign_lanes_static,
    detect_lane_count as detect_lane_count,
    calculate_difficulty as calculate_difficulty,
)

# Dynamic lane layout
try:
    from .dynamic_lane_layout import (
        DynamicLaneLayout as DynamicLaneLayout,
        DynamicLaneLayoutBuilder as DynamicLaneLayoutBuilder,
        LaneDefinition as LaneDefinition,
        ComponentCategory as ComponentCategory,
        classify_component as classify_component,
    )
except ImportError:
    pass  # Optional module

# Manual mapping workflow helpers
try:
    from .manual_mapping_helper import (
        # Main API
        detect_lanes_for_manual_mapping as detect_lanes_for_manual_mapping,
        create_user_specified_lanes as create_user_specified_lanes,
        adjust_lane_configuration as adjust_lane_configuration,
        get_lane_detection_prompt as get_lane_detection_prompt,
        quick_lane_preview as quick_lane_preview,
        # Types
        LaneConfiguration as LaneConfiguration,
        LaneDetectionChoice as LaneDetectionChoice,
    )
except ImportError:
    pass  # Optional module
