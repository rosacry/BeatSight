"""
Active Learning Package for Drum Classification

This package provides tools for efficient data labeling through
intelligent sample selection.

Strategies:
- Uncertainty Sampling: Select samples model is least confident about
- Diversity Sampling: Select diverse samples covering feature space
- Query-by-Committee: Select samples where ensemble disagrees
- Hybrid: Combine uncertainty and diversity

Usage:
    from training.active import (
        ActiveLearner,
        ActiveLearningConfig,
        UncertaintySampler,
        DiversitySampler,
        QueryByCommitteeSampler,
        HybridSampler,
    )
"""

from training.active.sampler import (
    ActiveLearner,
    ActiveLearningConfig,
    ActiveSampler,
    DiversitySampler,
    HybridSampler,
    QueryByCommitteeSampler,
    UncertaintySampler,
)

__all__ = [
    'ActiveLearner',
    'ActiveLearningConfig',
    'ActiveSampler',
    'DiversitySampler',
    'HybridSampler',
    'QueryByCommitteeSampler',
    'UncertaintySampler',
]
