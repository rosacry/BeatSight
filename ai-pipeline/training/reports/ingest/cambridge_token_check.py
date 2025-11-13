#!/usr/bin/env python3
"""Analyze Cambridge ingest coverage by reporting unknown stem tokens and related stats."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Sequence
from typing import Dict, List, Optional, Sequence

# Ensure the repository root is importable when the script runs directly.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
AI_PIPELINE_ROOT = REPO_ROOT / "ai-pipeline"

for candidate in (AI_PIPELINE_ROOT, REPO_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from training.tools import ingest_cambridge  # noqa: E402

def _load_inventory_from_file(path: pathlib.Path) -> List[dict]:
    print(f"Loading Cambridge session inventory from {path}...")
    if not path.exists():
        raise SystemExit(f"Inventory file not found: {path}")

    inventory: List[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            inventory.append(json.loads(line))
    if not inventory:
        raise SystemExit(f"Inventory file {path} contains no sessions.")
    print(f" • Loaded {len(inventory)} sessions from inventory JSONL")
    return inventory

def _load_inventory(roots: Sequence[str] | None) -> tuple[List[dict], List[dict]]:
    candidates = roots if roots else ingest_cambridge.DEFAULT_ROOT_CANDIDATES
    print("Resolving Cambridge dataset roots...")
    resolved_roots = ingest_cambridge.discover_dataset_roots(candidates)
    if not resolved_roots:
        raise SystemExit(
            "No Cambridge roots found. Checked: "
            + ", ".join(str(ingest_cambridge.ingest_utils.resolve_repo_path(c)) for c in candidates)
        )
    print(" • Roots: " + ", ".join(str(root) for root in resolved_roots))

    print("Discovering Cambridge session inventory...")
    inventory, root_stats = ingest_cambridge.discover_sessions(resolved_roots)
    if not inventory:
        raise SystemExit("No Cambridge sessions with audio found under the provided roots.")

    for stat in root_stats:
        print(
            " • Root summary: {root} [{tier}] -> {sessions_with_audio} sessions with audio "
            "({skipped_empty} empty dirs, {duplicates} duplicates, {session_dirs} total dirs scanned)".format(
                **stat
            )
        )

    return inventory, root_stats


def _summarize_counter(counter: Counter, limit: int) -> List[Dict[str, int]]:
    return [
        {"value": key, "count": count}
        for key, count in counter.most_common(limit)
    ]


def analyze_inventory(
    inventory: Sequence[Dict[str, object]],
    *,
    top_tokens: int,
    sample_size: int,
) -> Dict[str, object]:
    total_tracks = 0
    label_counter: Counter[str] = Counter()
    technique_counter: Counter[str] = Counter()
    aux_variant_counter: Counter[str] = Counter()
    unknown_tracks: List[str] = []
    unknown_token_counter: Counter[str] = Counter()
    unknown_by_session: Counter[str] = Counter()
    non_drum_counter: Counter[str] = Counter()

    for session in ingest_cambridge.ingest_utils.track_progress(
        inventory, "Analyzing Cambridge stems", total=len(inventory)
    ):
        session_id = str(session["session_id"])
        audio_files = [str(item) for item in session.get("audio_files", [])]

        for audio_rel in audio_files:
            total_tracks += 1
            tokens = ingest_cambridge._tokenize(audio_rel)
            non_drum_hit = ingest_cambridge._match_non_drum(tokens)
            if non_drum_hit:
                non_drum_counter[non_drum_hit] += 1
                continue

            inferred = ingest_cambridge._infer_component(audio_rel)
            if inferred is None:
                unknown_tracks.append(f"{session_id}:{audio_rel}")
                unknown_by_session[session_id] += 1
                unknown_token_counter.update(tokens)
                continue

            label, extras, techniques = inferred
            label_counter[label] += 1
            if extras and isinstance(extras, dict):
                variant = extras.get("instrument_variant")
                if isinstance(variant, str) and variant:
                    aux_variant_counter[variant] += 1
            for technique in techniques:
                technique_counter[technique] += 1

    report: Dict[str, object] = {
        "sessions": len(inventory),
        "total_tracks": total_tracks,
        "classified_tracks": sum(label_counter.values()),
        "unknown_track_count": len(unknown_tracks),
        "unknown_tracks_sample": unknown_tracks[:sample_size],
        "unknown_tokens_top": _summarize_counter(unknown_token_counter, top_tokens),
        "unknown_sessions_top": _summarize_counter(unknown_by_session, min(top_tokens, 30)),
        "label_distribution": dict(label_counter.most_common()),
        "technique_distribution": dict(technique_counter.most_common()),
        "aux_variant_distribution": dict(aux_variant_counter.most_common()),
        "non_drum_keyword_distribution": dict(non_drum_counter.most_common(top_tokens)),
    }

    return report


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roots",
        nargs="*",
        help="Override dataset roots. Defaults mirror ingest_cambridge.py.",
    )
    parser.add_argument(
        "--max-sessions",
        type=int,
        help="Optional limit on total sessions analyzed.",
    )
    parser.add_argument(
        "--max-per-root",
        type=int,
        help="Optional limit on sessions per root.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        help="Seed used when shuffling before applying session limits.",
    )
    parser.add_argument(
        "--top-tokens",
        type=int,
        default=40,
        help="Number of unknown tokens and keywords to include in the report (default: 40).",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=25,
        help="Number of unknown stems to sample in the report (default: 25).",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        help="Optional path to write the JSON report. Defaults to datestamped file under training/reports/ingest.",
    )
    parser.add_argument(
        "--inventory-json",
        type=pathlib.Path,
        help="Optional path to an existing Cambridge session inventory JSONL. When provided (and --refresh-inventory is not set), the file is reused instead of re-scanning the dataset.",
    )
    parser.add_argument(
        "--refresh-inventory",
        action="store_true",
        help="Force a fresh scan of dataset roots even when --inventory-json exists.",
    )
    args = parser.parse_args(argv)

    if args.max_sessions is not None and args.max_sessions < 0:
        parser.error("--max-sessions must be non-negative")
    if args.max_per_root is not None and args.max_per_root < 0:
        parser.error("--max-per-root must be non-negative")
    if args.top_tokens <= 0:
        parser.error("--top-tokens must be positive")
    if args.sample_size <= 0:
        parser.error("--sample-size must be positive")

    return args


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)

    root_stats: List[dict] = []
    if args.inventory_json and args.inventory_json.exists() and not args.refresh_inventory:
        inventory = _load_inventory_from_file(args.inventory_json)
    else:
        inventory, root_stats = _load_inventory(args.roots)
        if args.inventory_json:
            resolved_inventory = ingest_cambridge.ingest_utils.resolve_repo_path(str(args.inventory_json))
            resolved_inventory.parent.mkdir(parents=True, exist_ok=True)
            print(f"Writing fresh inventory to {resolved_inventory} for reuse...")
            ingest_cambridge.write_jsonl(resolved_inventory, inventory)

    working_inventory, selection_info = ingest_cambridge.apply_session_limits(
        inventory,
        args.max_sessions,
        args.max_per_root,
        args.random_seed,
    )
    if not working_inventory:
        raise SystemExit("No sessions selected after applying limits; adjust filtering arguments.")

    report = analyze_inventory(
        working_inventory,
        top_tokens=args.top_tokens,
        sample_size=args.sample_size,
    )

    report.update(
        {
            "inventory_sessions": len(inventory),
            "selection": selection_info,
            "roots": root_stats,
        }
    )

    if args.output is None:
        today = datetime.utcnow().strftime("%Y%m%d")
        args.output = ingest_cambridge.DEFAULT_SUMMARY_DIR / f"cambridge_token_report_{today}.json"

    output_path = ingest_cambridge.ingest_utils.resolve_repo_path(str(args.output))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Token analysis written to {output_path}")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
