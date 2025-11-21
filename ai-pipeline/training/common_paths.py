"""Centralised path helpers for BeatSight training scripts.

This replaces the historical module that lived in internal tooling.  The
functions intentionally respect the same environment variables used by the
post-export tooling so that CLI overrides continue to work the same way.
"""

from __future__ import annotations

import os
from pathlib import Path


def _repo_root() -> Path:
    env_root = os.environ.get("BEATSIGHT_REPO_ROOT")
    if env_root:
        return Path(env_root)
    # training/common_paths.py -> training -> ai-pipeline -> repo root
    return Path(__file__).resolve().parents[2]


def dataset_root() -> Path:
    """Return the canonical dataset directory used for classifier training."""

    env_dataset = os.environ.get("BEATSIGHT_DATASET_DIR")
    if env_dataset:
        return Path(env_dataset)
    return _repo_root() / "data" / "prod_combined_profile_run"


def feature_cache_root() -> Path:
    """Return the default feature cache directory for mel tensors."""

    env_cache = os.environ.get("BEATSIGHT_CACHE_DIR")
    if env_cache:
        return Path(env_cache)
    return _repo_root() / "data" / "feature_cache" / "prod_combined_warmup"
