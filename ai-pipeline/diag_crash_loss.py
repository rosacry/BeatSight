#!/usr/bin/env python3
"""
Diagnose where crashes/china are lost through the pipeline stages.

Traces hit counts at each stage:
  Step 4:   classify_drums (raw multi-label output)
  Step 4b:  apply_structured_decoding (Viterbi)
  Step 4b2: apply_genre_aware_decoding
  Step 4b3: repair_with_patterns
  Step 4c:  filter_chart_for_readability
"""

import sys
import os
import copy
from collections import Counter
from pathlib import Path

# Ensure ai-pipeline is importable
sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Path(__file__).parent)


def count_components(hits) -> Counter:
    """Count hit components, collapsing ranked labels (crash_1 -> crash)."""
    c = Counter()
    for h in hits:
        comp = h.get("component", "unknown")
        # Strip _N suffix for counting
        base = comp.rsplit("_", 1)
        if len(base) == 2 and base[1].isdigit():
            comp = base[0]
        c[comp] += 1
    return c


def show_cymbal_counts(label, hits):
    counts = count_components(hits)
    cymbal_keys = ["crash", "china", "splash", "ride_bow", "ride_bell"]
    cymbal_str = ", ".join(f"{k}={counts.get(k, 0)}" for k in cymbal_keys)
    total = len(hits)
    print(f"  {label:35s} | total={total:5d} | {cymbal_str}")


def main():
    input_path = "../test_songs/0101 - Heir of Grief.flac"
    if not Path(input_path).exists():
        print(f"Test song not found: {input_path}")
        return

    # --- Step 1-3: Preprocess, Separate, Detect Onsets ---
    from pipeline.preprocessing import preprocess_audio
    from pipeline.separation.demucs_separator import separate_drums
    from pipeline.transcription.onset_detector import detect_onsets, refine_onsets
    from pipeline.transcription import drum_classifier

    print("=" * 80)
    print("CRASH/CHINA LOSS DIAGNOSTIC")
    print("=" * 80)

    print("\n[1] Loading audio...")
    audio_data, sr = preprocess_audio(input_path)

    print("[2] Separating drums with Demucs...")
    drum_audio = separate_drums((audio_data, sr))

    print("[3] Detecting onsets...")
    det = detect_onsets(drum_audio, sensitivity=60.0)
    onsets = refine_onsets(drum_audio, det.onsets)
    print(f"    Found {len(onsets)} onsets")

    # --- Step 4: Classify ---
    print("[4] Classifying (multi-label, threshold_scale=0.7)...")
    classified = drum_classifier.classify_drums(
        drum_audio,
        onsets,
        confidence_threshold=0.7,
        use_multilabel=True,
        threshold_scale=0.7,
    )
    show_cymbal_counts("After step 4 (classify)", classified)

    # --- Step 4b: Viterbi ---
    try:
        from pipeline.structured_decoder import apply_structured_decoding
        bpm = det.estimated_tempo or 120.0
        hits_4b = apply_structured_decoding(classified, bpm=bpm, offset=0.0)
        show_cymbal_counts("After step 4b (Viterbi)", hits_4b)
    except Exception as e:
        print(f"  Step 4b failed: {e}")
        hits_4b = classified

    # --- Step 4b2: Genre-Aware ---
    try:
        from pipeline.genre_aware_decoder import apply_genre_aware_decoding
        hits_4b2 = apply_genre_aware_decoding(hits_4b, bpm=bpm, offset=0.0)
        show_cymbal_counts("After step 4b2 (genre-aware)", hits_4b2)
    except Exception as e:
        print(f"  Step 4b2 failed: {e}")
        hits_4b2 = hits_4b

    # --- Step 4b3: Pattern Repair ---
    try:
        from pipeline.pattern_library import repair_with_patterns
        hits_4b3 = repair_with_patterns(hits_4b2, bpm=bpm, confidence_threshold=0.6)
        show_cymbal_counts("After step 4b3 (pattern repair)", hits_4b3)
    except Exception as e:
        print(f"  Step 4b3 failed: {e}")
        hits_4b3 = hits_4b2

    # --- Step 4c: Readability ---
    try:
        from pipeline.chart_readability import filter_chart_for_readability
        hits_4c, _readability_stats = filter_chart_for_readability(
            hits_4b3, difficulty="expert", bpm=bpm,
        )
        show_cymbal_counts("After step 4c (readability)", hits_4c)
    except Exception as e:
        print(f"  Step 4c failed: {e}")
        hits_4c = hits_4b3

    print("\n" + "=" * 80)
    print("FULL COMPONENT BREAKDOWN AT EACH STAGE:")
    print("=" * 80)
    for label, hits in [
        ("Step 4 (classify)", classified),
        ("Step 4b (Viterbi)", hits_4b),
        ("Step 4b2 (genre-aware)", hits_4b2),
        ("Step 4b3 (pattern repair)", hits_4b3),
        ("Step 4c (readability)", hits_4c),
    ]:
        print(f"\n{label}:")
        counts = count_components(hits)
        for comp, n in counts.most_common():
            print(f"    {comp}: {n}")

    # --- Check how many were refined by genre-aware decoder ---
    refined_count = sum(1 for h in hits_4b2 if h.get("state_refined", False))
    print(f"\n[INFO] Genre-aware decoder flagged {refined_count} hits as state_refined")
    if refined_count > 0:
        refined_comps = Counter(
            h.get("component", "?") for h in hits_4b2 if h.get("state_refined")
        )
        print(f"  Refined components: {dict(refined_comps)}")


if __name__ == "__main__":
    main()
