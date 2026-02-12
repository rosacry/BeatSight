"""
Diagnostic script: Trace crash/china counts through every pipeline stage.

This reveals exactly where crash and china hits are being lost.
Usage:
    cd c:\github\BeatSight\ai-pipeline
    python scripts/trace_crash_counts.py
"""

import json
import sys
import os
from pathlib import Path
from collections import Counter
from copy import deepcopy

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Input / output
INPUT_AUDIO = str(Path(__file__).parent.parent.parent / "test_songs" / "0101 - Heir of Grief.flac")
OUTPUT_BSM = str(Path(__file__).parent.parent.parent / "test_beatmap_diag.bsm")

CYMBAL_CLASSES = {"crash", "china", "splash", "ride_bow", "ride_bell"}

def count_components(hits, label=""):
    """Count crash/china/splash in a hit list and print summary."""
    counter = Counter(h.get("component", "") for h in hits)
    crash = sum(v for k, v in counter.items() if "crash" in k)
    china = sum(v for k, v in counter.items() if "china" in k)
    splash = sum(v for k, v in counter.items() if "splash" in k)
    ride = sum(v for k, v in counter.items() if "ride" in k)
    tom = sum(v for k, v in counter.items() if "tom" in k)
    total = len(hits)
    print(f"  [{label}] Total={total}  crash={crash}  china={china}  splash={splash}  ride={ride}  tom={tom}")
    if crash + china + splash + ride < 20:
        # Show all cymbal entries
        cymbal_hits = [(h["time"], h["component"], h.get("confidence", 0)) for h in hits 
                       if any(c in h.get("component", "") for c in ["crash", "china", "splash"])]
        if cymbal_hits:
            print(f"    Cymbal detail: {len(cymbal_hits)} entries")
    return counter


def main():
    print(f"=== BeatSight Crash/China Pipeline Trace ===")
    print(f"Input: {INPUT_AUDIO}")
    print()

    if not Path(INPUT_AUDIO).exists():
        print(f"ERROR: Input file not found: {INPUT_AUDIO}")
        sys.exit(1)

    # --- Step 1-2: Preprocess + Separate ---
    from pipeline.preprocessing import preprocess_audio
    from pipeline.separation.demucs_separator import separate_drums

    print("[1] Preprocessing audio...")
    audio_data, sample_rate = preprocess_audio(INPUT_AUDIO)

    print("[2] Separating drums...")
    drum_audio = separate_drums((audio_data, sample_rate))

    # --- Step 3: Onset detection ---
    from pipeline.transcription.onset_detector import detect_onsets, refine_onsets

    print("[3] Detecting onsets...")
    detection_result = detect_onsets(drum_audio, sensitivity=60.0)
    refined_onsets = refine_onsets(drum_audio, detection_result.onsets)
    print(f"  Found {len(refined_onsets)} onsets")

    # --- Step 4: Classification ---
    from pipeline.transcription import drum_classifier

    print("[4] Classifying drums (threshold_scale=0.7)...")
    classified_hits = drum_classifier.classify_drums(
        drum_audio,
        refined_onsets,
        confidence_threshold=0.7,
        use_multilabel=True,
        threshold_scale=0.7,
    )
    count_components(classified_hits, "After classify (step 4)")

    # Snapshot
    hits_after_4 = deepcopy(classified_hits)

    # --- Step 4b: Structured Decoding ---
    try:
        from pipeline.structured_decoder import apply_structured_decoding, detect_time_signature
        hit_times = [h.get("time", 0) for h in classified_hits]
        detected_ts = detect_time_signature(hit_times, 120.0)
        
        print("[4b] Applying structured decoding (Viterbi)...")
        classified_hits = apply_structured_decoding(
            classified_hits, bpm=120.0, offset=0.0,
            time_signature=(detected_ts.numerator, detected_ts.denominator),
        )
        count_components(classified_hits, "After Viterbi (step 4b)")
        
        # Check which crashes were flagged as state_refined
        refined_crashes = [h for h in classified_hits 
                          if h.get("state_refined") and "crash" in h.get("component", "")]
        refined_china = [h for h in classified_hits 
                        if h.get("state_refined") and "china" in h.get("component", "")]
        if refined_crashes or refined_china:
            print(f"    state_refined: {len(refined_crashes)} crash, {len(refined_china)} china")
            for h in refined_crashes[:5]:
                print(f"      crash @ {h['time']:.3f}: decoded_state={h.get('decoded_state')}, "
                      f"viterbi_prob={h.get('viterbi_confidence', h.get('viterbi_prob', 'N/A'))}")
    except Exception as e:
        print(f"  [SKIP] Structured decoding: {e}")

    hits_after_4b = deepcopy(classified_hits)

    # --- Step 4b2: Genre-Aware Decoding ---
    try:
        from pipeline.genre_aware_decoder import apply_genre_aware_decoding, detect_genre

        print("[4b2] Applying genre-aware decoding...")
        genre, genre_conf = detect_genre(classified_hits, 120.0, 1.0)
        print(f"  Detected genre: {genre.value} ({genre_conf:.2f})")
        
        classified_hits = apply_genre_aware_decoding(
            classified_hits, bpm=120.0, offset=0.0,
            time_signature=(4, 4), swing_ratio=1.0,
        )
        count_components(classified_hits, "After genre decoder (step 4b2)")
    except Exception as e:
        print(f"  [SKIP] Genre-aware decoding: {e}")

    hits_after_4b2 = deepcopy(classified_hits)

    # --- Step 4b3: Pattern Repair ---
    try:
        from pipeline.pattern_library import repair_with_patterns

        print("[4b3] Applying pattern repair...")
        classified_hits = repair_with_patterns(
            classified_hits, bpm=120.0, confidence_threshold=0.6,
        )
        count_components(classified_hits, "After pattern repair (step 4b3)")
    except Exception as e:
        print(f"  [SKIP] Pattern repair: {e}")

    hits_after_4b3 = deepcopy(classified_hits)

    # --- Step 4c: Readability Filtering ---
    try:
        from pipeline.chart_readability import filter_chart_for_readability

        print("[4c] Applying readability filter...")
        pre_readability = deepcopy(classified_hits)
        classified_hits, readability_stats = filter_chart_for_readability(
            classified_hits, difficulty="expert", bpm=120.0,
        )
        count_components(classified_hits, "After readability (step 4c)")
        
        # Identify which crashes were removed
        pre_crashes = set(id(h) for h in pre_readability if "crash" in h.get("component", ""))
        post_crashes = set(h.get("time", -1) for h in classified_hits if "crash" in h.get("component", ""))
        removed_crashes = [h for h in pre_readability 
                          if "crash" in h.get("component", "") and h["time"] not in post_crashes]
        
        if removed_crashes:
            print(f"    Readability removed {len(removed_crashes)} crashes")
            # Check co-occurrence: were removed crashes at the same time as other right-hand hits?
            cooccur_count = 0
            for rc in removed_crashes:
                t = rc["time"]
                same_time = [h for h in pre_readability 
                            if abs(h["time"] - t) < 0.001 and h is not rc]
                same_time_rh = [h for h in same_time 
                               if h.get("component", "") in {"hihat_closed", "hihat_open", "ride_bow", "ride_bell", "china", "splash"}]
                if same_time_rh:
                    cooccur_count += 1
            print(f"    Of those, {cooccur_count} co-occurred with another right-hand hit at same onset")
        
        # Same for china
        pre_china = set(h.get("time", -1) for h in pre_readability if "china" in h.get("component", ""))
        post_china_times = set(h.get("time", -1) for h in classified_hits if "china" in h.get("component", ""))
        removed_china = [h for h in pre_readability 
                        if "china" in h.get("component", "") and h["time"] not in post_china_times]
        if removed_china:
            print(f"    Readability removed {len(removed_china)} china")
            
    except Exception as e:
        print(f"  [SKIP] Readability filter: {e}")

    hits_after_4c = deepcopy(classified_hits)

    # --- Step 4d: Pitch Ranking ---
    try:
        from transcription.instrument_pitch_ranker import InstrumentPitchRanker

        print("[4d] Applying pitch ranking...")
        audio_data_for_ranking, sr_for_ranking = drum_audio
        pitch_ranker = InstrumentPitchRanker()

        event_dicts = [
            {"timestamp": h["time"], "label": h["component"],
             "confidence": h.get("class_confidence", h.get("confidence", 0.5))}
            for h in classified_hits
        ]

        ranked_results = pitch_ranker.process_song(event_dicts, audio_data_for_ranking, sr_for_ranking)

        for hit, ranked in zip(classified_hits, ranked_results):
            ranked_label = ranked.get("ranked_label", hit["component"])
            if ranked_label != hit["component"]:
                hit["component"] = ranked_label

        count_components(classified_hits, "After pitch ranking (step 4d)")
    except Exception as e:
        print(f"  [SKIP] Pitch ranking: {e}")

    # --- Summary ---
    print()
    print("=" * 60)
    print("SUMMARY — Crash/China losses at each stage:")
    print("=" * 60)
    
    stages = [
        ("Step 4 (classify)", hits_after_4),
        ("Step 4b (Viterbi)", hits_after_4b),
        ("Step 4b2 (genre)", hits_after_4b2),
        ("Step 4b3 (patterns)", hits_after_4b3),
        ("Step 4c (readability)", hits_after_4c),
        ("Step 4d (pitch rank)", classified_hits),
    ]
    
    for name, hits in stages:
        crash_n = sum(1 for h in hits if "crash" in h.get("component", ""))
        china_n = sum(1 for h in hits if "china" in h.get("component", ""))
        tom_n = sum(1 for h in hits if "tom" in h.get("component", ""))
        print(f"  {name:30s}: crash={crash_n:4d}  china={china_n:4d}  tom={tom_n:4d}  total={len(hits)}")


if __name__ == "__main__":
    main()
