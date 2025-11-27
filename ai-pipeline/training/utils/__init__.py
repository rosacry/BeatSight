"""Training utilities package."""

from training.utils.ema import ModelEMA, ModelEMAWithBackup, get_ema_decay
from training.utils.adaptive import ProgressiveAugmentation, get_recommended_schedules
from training.utils.swa import SWAManager, CyclicSWA, SWAPlusEMA, configure_swa
from training.utils.distillation import (
    DistillationLoss,
    FeatureDistillationLoss,
    EnsembleTeacher,
    DistillationTrainer,
    OnlineDistillation,
)
from training.utils.stochastic_depth import (
    DropPath,
    StochasticDepthBlock,
    get_stochastic_depth_rates,
    add_drop_path_to_model,
)

__all__ = [
    # EMA
    "ModelEMA",
    "ModelEMAWithBackup",
    "get_ema_decay",
    # Progressive Augmentation
    "ProgressiveAugmentation",
    "get_recommended_schedules",
    # SWA
    "SWAManager",
    "CyclicSWA",
    "SWAPlusEMA",
    "configure_swa",
    # Distillation
    "DistillationLoss",
    "FeatureDistillationLoss",
    "EnsembleTeacher",
    "DistillationTrainer",
    "OnlineDistillation",
    # Stochastic Depth
    "DropPath",
    "StochasticDepthBlock",
    "get_stochastic_depth_rates",
    "add_drop_path_to_model",
]
