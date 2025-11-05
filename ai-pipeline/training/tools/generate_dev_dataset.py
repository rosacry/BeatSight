#!/usr/bin/env python3
"""Generate a tiny synthetic dataset for the dev three-class training run.

This writes sine-based drum stand-ins into `training/dev_dataset/` so the
training loop has real files to consume. Each class gets a few examples split
into train/val. Waveforms are intentionally simple; the goal is to verify the
training pipeline end-to-end, not model accuracy.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 44100
TRAIN_PER_CLASS = 6
VAL_PER_CLASS = 2
CLASSES = {
    "kick": 60.0,
    "snare": 180.0,
    "hihat_closed": 8000.0,
}


def synth_hit(freq: float, duration: float = 0.35, decay: float = 5.0) -> np.ndarray:
    """Create a decaying sinusoidal burst to mimic simple drum timbres."""
    t = np.linspace(0.0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    envelope = np.exp(-decay * t)
    waveform = np.sin(2 * np.pi * freq * t) * envelope
    return waveform.astype(np.float32)


def write_clip(path: Path, waveform: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, waveform, SAMPLE_RATE)


def build_labels(rows: list[tuple[str, Path]]) -> list[dict[str, object]]:
    labels = []
    for component, rel_path in rows:
        labels.append(
            {
                "file": rel_path.name,
                "label": component,
                "component_idx": list(CLASSES.keys()).index(component),
            }
        )
    return labels


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "dev_dataset"
    train_dir = root / "train"
    val_dir = root / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    train_rows: list[tuple[str, Path]] = []
    val_rows: list[tuple[str, Path]] = []

    rng = np.random.default_rng(1337)

    for component, base_freq in CLASSES.items():
        for idx in range(TRAIN_PER_CLASS):
            freq = base_freq * (1.0 + rng.normal(0.0, 0.02))
            clip = synth_hit(freq)
            target = train_dir / f"{component}_train_{idx:02d}.wav"
            write_clip(target, clip)
            train_rows.append((component, target))

        for idx in range(VAL_PER_CLASS):
            freq = base_freq * (1.0 + rng.normal(0.0, 0.02))
            clip = synth_hit(freq)
            target = val_dir / f"{component}_val_{idx:02d}.wav"
            write_clip(target, clip)
            val_rows.append((component, target))

    with open(root / "train_labels.json", "w", encoding="utf-8") as handle:
        json.dump(build_labels(train_rows), handle, indent=2)

    with open(root / "val_labels.json", "w", encoding="utf-8") as handle:
        json.dump(build_labels(val_rows), handle, indent=2)

    with open(root / "components.json", "w", encoding="utf-8") as handle:
        json.dump(
            {
                "components": list(CLASSES.keys()),
                "num_classes": len(CLASSES),
            },
            handle,
            indent=2,
        )

    print(f"Dev dataset written to {root}")


if __name__ == "__main__":
    main()
