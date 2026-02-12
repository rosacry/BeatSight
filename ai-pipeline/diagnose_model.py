#!/usr/bin/env python3
"""
Diagnostic script to investigate finetuned model output quality.

Tests:
1. Load val data from Demucs-augmented datasets and verify model can detect all classes
2. Compare raw probabilities between old and finetuned models
3. Analyze probability distributions per class

Runs on CPU to avoid interfering with GPU training.
"""
import sys
import json
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import torch

# --- Configuration ---
OLD_MODEL = "runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt"
NEW_MODEL = "runs/v5_finetune_demucs/best_multilabel_model_ema.pt"
OLD_THRESHOLDS = "runs/v5_multilabel_final_v3/thresholds.json"
NEW_THRESHOLDS = "runs/v5_finetune_demucs/thresholds.json"

DATASET_ROOT = Path("F:/datasets/multilabel_real_v3")
DEMUCS_DATASETS = [
    "enst_drums_demucs",
    "groove_midi_demucs",
    "egmd_demucs",
]
CLEAN_DATASETS = [
    "enst_drums",
    "groove_midi",
    "egmd",
]

CLASS_NAMES = [
    "china", "crash", "cross_stick", "hihat_closed", "hihat_open",
    "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare", "splash", "tom",
]

DEVICE = "cpu"  # Use CPU to avoid interfering with GPU training


def load_model(model_path, device="cpu"):
    """Load model on specified device."""
    from transcription.multilabel_inference import load_model_checkpoint
    model = load_model_checkpoint(model_path, device=device, num_classes=12)
    model.eval()
    return model


def load_thresholds(thresholds_path):
    """Load per-class thresholds."""
    with open(thresholds_path) as f:
        data = json.load(f)
    if "per_class_thresholds" in data:
        return data["per_class_thresholds"]
    return data


def load_val_batch(dataset_name, max_batches=2):
    """Load pre-extracted val features and labels from a dataset."""
    manifest_path = DATASET_ROOT / dataset_name / f"{dataset_name}_manifest.json"
    if not manifest_path.exists():
        print(f"  [SKIP] {manifest_path} not found")
        return None, None

    with open(manifest_path) as f:
        manifest = json.load(f)

    batches = manifest.get("batches", [])
    val_batches = [b for b in batches if b.get("split") == "val"]

    if not val_batches:
        print(f"  [SKIP] No val batches in {dataset_name}")
        return None, None

    all_features = []
    all_labels = []

    batch_dir = DATASET_ROOT / dataset_name / f"{dataset_name}_batches"
    if not batch_dir.exists():
        # Try without _batches suffix
        batch_dir = DATASET_ROOT / dataset_name

    for batch_info in val_batches[:max_batches]:
        feat_file = batch_dir / batch_info["features"]
        label_file = batch_dir / batch_info["labels"]
        if not feat_file.exists():
            # Try parent directory
            feat_file = DATASET_ROOT / dataset_name / batch_info["features"]
            label_file = DATASET_ROOT / dataset_name / batch_info["labels"]
        if not feat_file.exists():
            continue

        features = np.load(feat_file)
        labels = np.load(label_file)
        all_features.append(features)
        all_labels.append(labels)

    if not all_features:
        print(f"  [SKIP] No feature files found for {dataset_name}")
        return None, None

    return np.concatenate(all_features), np.concatenate(all_labels)


def run_inference(model, features, batch_size=64):
    """Run inference and return raw sigmoid probabilities."""
    all_probs = []
    for i in range(0, len(features), batch_size):
        batch = features[i:i+batch_size]
        x = torch.from_numpy(batch).float().unsqueeze(1)  # (B, 1, 128, 128)
        x = x.to(DEVICE)
        with torch.inference_mode():
            logits = model(x)
            probs = torch.sigmoid(logits)
        all_probs.append(probs.cpu().numpy())
    return np.concatenate(all_probs)


def analyze_class_probs(probs, labels, class_names, thresholds, threshold_scale=1.0, label=""):
    """Analyze per-class probability distributions."""
    print(f"\n{'='*80}")
    print(f"  {label}")
    print(f"{'='*80}")
    print(f"  Total samples: {len(probs)}")
    print(f"  Threshold scale: {threshold_scale}")

    # Domain gap tiers
    sensitive = {"china", "splash"}
    moderate = {"ride_bell", "cross_stick", "crash"}

    for idx, name in enumerate(class_names):
        mask = labels[:, idx] > 0.5  # Positive samples for this class
        n_pos = mask.sum()
        n_neg = (~mask).sum()

        if n_pos == 0:
            continue

        pos_probs = probs[mask, idx]
        neg_probs = probs[~mask, idx]

        # Compute effective threshold
        base_thr = thresholds.get(name, 0.5)
        if name in sensitive:
            eff_thr = base_thr * (threshold_scale ** 0.75)
        elif name in moderate:
            eff_thr = base_thr * (threshold_scale ** 0.5)
        else:
            eff_thr = base_thr * (threshold_scale ** 0.25)

        # Detection stats
        tp = (pos_probs >= eff_thr).sum()
        fn = (pos_probs < eff_thr).sum()
        fp = (neg_probs >= eff_thr).sum()
        recall = tp / max(n_pos, 1)
        precision = tp / max(tp + fp, 1)

        print(f"\n  {name:15s} | positives={n_pos:6d} | "
              f"base_thr={base_thr:.3f} -> eff={eff_thr:.3f}")
        print(f"  {'':15s} | pos_probs: mean={pos_probs.mean():.3f}, "
              f"median={np.median(pos_probs):.3f}, "
              f"min={pos_probs.min():.3f}, max={pos_probs.max():.3f}, "
              f"std={pos_probs.std():.3f}")
        print(f"  {'':15s} | neg_probs: mean={neg_probs.mean():.4f}, max={neg_probs.max():.3f}")
        print(f"  {'':15s} | TP={tp:5d} FN={fn:5d} FP={fp:5d} | "
              f"recall={recall:.3f} precision={precision:.3f}")

        # Show percentile distribution of positive probs
        percentiles = [10, 25, 50, 75, 90]
        pcts = np.percentile(pos_probs, percentiles)
        pct_str = ", ".join(f"p{p}={v:.3f}" for p, v in zip(percentiles, pcts))
        print(f"  {'':15s} | percentiles: {pct_str}")


def test_1_val_data():
    """Test 1: Compare models on pre-extracted val data."""
    print("\n" + "#"*80)
    print("# TEST 1: Model performance on pre-extracted validation data")
    print("#"*80)

    # Load models
    print("\nLoading old model (CPU)...")
    old_model = load_model(OLD_MODEL, DEVICE)
    print("Loading new model (CPU)...")
    new_model = load_model(NEW_MODEL, DEVICE)

    # Load thresholds
    old_thresholds = load_thresholds(OLD_THRESHOLDS)
    new_thresholds = load_thresholds(NEW_THRESHOLDS)

    # Test on Demucs-augmented val data
    for ds_name in DEMUCS_DATASETS:
        print(f"\n--- Loading {ds_name} ---")
        features, labels = load_val_batch(ds_name, max_batches=2)
        if features is None:
            continue

        print(f"  Loaded {len(features)} samples, shape={features.shape}")

        # Count per-class positives
        class_counts = {CLASS_NAMES[i]: int(labels[:, i].sum()) for i in range(12)}
        print(f"  Class distribution: {class_counts}")

        # Run both models
        print("  Running old model inference...")
        old_probs = run_inference(old_model, features)
        print("  Running new model inference...")
        new_probs = run_inference(new_model, features)

        # Analyze old model
        analyze_class_probs(old_probs, labels, CLASS_NAMES, old_thresholds,
                          threshold_scale=0.7,
                          label=f"OLD model on {ds_name} (threshold_scale=0.7)")

        # Analyze new model with scale=0.7
        analyze_class_probs(new_probs, labels, CLASS_NAMES, new_thresholds,
                          threshold_scale=0.7,
                          label=f"NEW model on {ds_name} (threshold_scale=0.7)")

        # Analyze new model with scale=1.0
        analyze_class_probs(new_probs, labels, CLASS_NAMES, new_thresholds,
                          threshold_scale=1.0,
                          label=f"NEW model on {ds_name} (threshold_scale=1.0)")

    # Also test on clean data
    for ds_name in CLEAN_DATASETS[:1]:  # Just first one for speed
        print(f"\n--- Loading {ds_name} (clean) ---")
        features, labels = load_val_batch(ds_name, max_batches=1)
        if features is None:
            continue

        print(f"  Loaded {len(features)} samples")

        print("  Running new model inference...")
        new_probs = run_inference(new_model, features)

        analyze_class_probs(new_probs, labels, CLASS_NAMES, new_thresholds,
                          threshold_scale=1.0,
                          label=f"NEW model on {ds_name} (CLEAN, threshold_scale=1.0)")


def test_2_probability_histograms():
    """Test 2: Show probability histograms for china/splash on Demucs data."""
    print("\n" + "#"*80)
    print("# TEST 2: Probability distributions for rare classes on Demucs data")
    print("#"*80)

    new_model = load_model(NEW_MODEL, DEVICE)

    # Collect all Demucs val data
    all_features = []
    all_labels = []
    for ds_name in DEMUCS_DATASETS:
        features, labels = load_val_batch(ds_name, max_batches=3)
        if features is not None:
            all_features.append(features)
            all_labels.append(labels)

    if not all_features:
        print("  No Demucs val data found!")
        return

    features = np.concatenate(all_features)
    labels = np.concatenate(all_labels)
    print(f"\n  Total Demucs val samples: {len(features)}")

    # Run inference
    print("  Running inference...")
    probs = run_inference(new_model, features)

    # Focus on rare classes
    rare_classes = {"china": 0, "splash": 10, "crash": 1, "ride_bell": 7}

    for name, idx in rare_classes.items():
        pos_mask = labels[:, idx] > 0.5
        n_pos = pos_mask.sum()
        if n_pos == 0:
            print(f"\n  {name}: 0 positive samples in Demucs val data!")
            continue

        pos_probs = probs[pos_mask, idx]
        print(f"\n  {name} ({n_pos} positive samples):")
        print(f"    Probability histogram (positive samples only):")

        # Histogram bins
        bins = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        hist, _ = np.histogram(pos_probs, bins=bins)
        for i in range(len(bins) - 1):
            bar = "#" * int(hist[i] / max(1, max(hist)) * 40)
            print(f"    [{bins[i]:.1f}-{bins[i+1]:.1f}): {hist[i]:5d} {bar}")


def test_3_onset_analysis():
    """Test 3: Analyze how many onsets the pipeline detects and classify."""
    print("\n" + "#"*80)
    print("# TEST 3: Onset count analysis from existing .bsm files")
    print("#"*80)

    bsm_files = {
        "original": "../test_beatmap.bsm",
        "threshold_1": "../test_beatmap_threshold_1.bsm",
        "fixed": "../test_beatmap_fixed.bsm",
        "fixed_v2": "../test_beatmap_fixed_v2.bsm",
        "finetuned_demucs": "../test_beatmap_finetuned_demucs.bsm",
    }

    for name, path in bsm_files.items():
        bsm_path = Path(path)
        if not bsm_path.exists():
            continue

        with open(bsm_path) as f:
            bsm = json.load(f)

        hits = bsm.get("hitObjects", [])
        components = {}
        for hit in hits:
            comp = hit.get("component", "unknown")
            components[comp] = components.get(comp, 0) + 1

        # Calculate confidences if available in analysis
        analysis = bsm.get("analysis", {})
        beatmap_confidence = analysis.get("confidence")

        print(f"\n  {name}: {len(hits)} total hits")
        if beatmap_confidence:
            print(f"    Confidence: {beatmap_confidence:.3f}")
        print(f"    BPM: {bsm.get('timing', {}).get('bpm', '?')}")
        for comp, count in sorted(components.items(), key=lambda x: -x[1]):
            pct = 100 * count / max(len(hits), 1)
            print(f"    {comp:20s}: {count:5d} ({pct:5.1f}%)")


if __name__ == "__main__":
    import time
    start = time.time()

    print("BeatSight Model Diagnostic")
    print(f"Device: {DEVICE}")
    print(f"Old model: {OLD_MODEL}")
    print(f"New model: {NEW_MODEL}")

    # Run all tests
    test_3_onset_analysis()  # Quick, no model loading needed
    test_1_val_data()        # Main diagnostic
    test_2_probability_histograms()  # Detailed histograms

    elapsed = time.time() - start
    print(f"\n\nDiagnostic complete in {elapsed:.1f}s")
