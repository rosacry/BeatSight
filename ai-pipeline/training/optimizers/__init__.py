"""
Advanced Optimizers for Drum Classification Training

This module provides state-of-the-art optimizers that go beyond standard
SGD/Adam for improved generalization.
"""

from .sam import SAM, ESAM, enable_running_stats, disable_running_stats
from .gradient_centralization import (
    GradientCentralization,
    centralize_gradient,
    wrap_optimizer_with_gc,
)
from .lookahead import (
    Lookahead,
    LookaheadAdam,
    LookaheadSGD,
    wrap_with_lookahead,
)
from .awp import (
    AWP,
    AWPWithSAM,
    get_awp,
)

__all__ = [
    'SAM',
    'ESAM',
    'enable_running_stats',
    'disable_running_stats',
    # Gradient Centralization
    'GradientCentralization',
    'centralize_gradient',
    'wrap_optimizer_with_gc',
    # Lookahead
    'Lookahead',
    'LookaheadAdam',
    'LookaheadSGD',
    'wrap_with_lookahead',
    # AWP
    'AWP',
    'AWPWithSAM',
    'get_awp',
]
