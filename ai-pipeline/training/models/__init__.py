"""
Advanced Model Architectures for Drum Classification

This module provides state-of-the-art model architectures
with various attention mechanisms and temporal modeling.
"""

from .cbam import (
    CBAM,
    ChannelAttention,
    SpatialAttention,
    CBAMConvBlock,
    DrumClassifierCNNv3,
    EfficientAttention,
)

from .coord_attention import (
    CoordinateAttention,
    CoordAttentionConvBlock,
    DrumClassifierCNNv4,
    MultiTaskLoss,
    coord_attention_small,
    coord_attention_medium,
    coord_attention_large,
)

from .temporal_mamba import (
    TemporalDrumTranscriber,
    MambaBlock,
    SelectiveSSM,
    BeatPositionalEncoding,
    DrumPatternPrior,
    TemporalLoss,
    MambaConfig,
    StreamingTemporalInference,
    temporal_small,
    temporal_medium,
    temporal_large,
)

from .cnn_v5 import (
    DrumClassifierCNNv5,
    CoordAttentionDropPathBlock,
    MultiScaleFusion,
    cnn_v5_small,
    cnn_v5_medium,
    cnn_v5_large,
)

from .beats import (
    BEATsEncoder,
    BEATsFeatureExtractor,
    BEATsDrumClassifier,
    create_beats_encoder,
)

__all__ = [
    # CBAM (v3)
    'CBAM',
    'ChannelAttention',
    'SpatialAttention',
    'CBAMConvBlock',
    'DrumClassifierCNNv3',
    'EfficientAttention',
    # Coordinate Attention (v4)
    'CoordinateAttention',
    'CoordAttentionConvBlock',
    'DrumClassifierCNNv4',
    'MultiTaskLoss',
    'coord_attention_small',
    'coord_attention_medium',
    'coord_attention_large',
    # Temporal Mamba (v5)
    'TemporalDrumTranscriber',
    'MambaBlock',
    'SelectiveSSM',
    'BeatPositionalEncoding',
    'DrumPatternPrior',
    'TemporalLoss',
    'MambaConfig',
    'StreamingTemporalInference',
    'temporal_small',
    'temporal_medium',
    'temporal_large',
    # CNN v5 (Ultimate)
    'DrumClassifierCNNv5',
    'CoordAttentionDropPathBlock',
    'MultiScaleFusion',
    'cnn_v5_small',
    'cnn_v5_medium',
    'cnn_v5_large',
    # BEATs Audio Foundation
    'BEATsEncoder',
    'BEATsFeatureExtractor',
    'BEATsDrumClassifier',
    'create_beats_encoder',
]

