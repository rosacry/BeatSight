#!/usr/bin/env python3
"""Compute per-group sampling weights for BeatSight event manifests."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple

import sys

_THIS_FILE = Path(__file__).resolve()
_PACKAGE_ROOT = _THIS_FILE.parents[2]
if str(_PACKAGE_ROOT) not in sys.path:  # pragma: no cover - script entry shim
    sys.path.insert(0, str(_PACKAGE_ROOT))

from training.event_loader import iter_filtered_events
from training.tools.console_utils import OutputLogger, ProgressAdapter

try:  # Optional rich summary support.
    from rich import box  # type: ignore[import]
    from rich.table import Table  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    box = None  # type: ignore[assignment]
    Table = None  # type: ignore[assignment]


DEFAULT_PROFILES_PATH = Path(__file__).resolve().parents[1] / "configs" / "sampling_profiles.json"


def compute_weights(
    manifest_path: Path,
    group_field: str,
    min_count: int,
    smoothing: float,
    exponent: float,
    *,
    min_weight: float | None = None,
    max_weight: float | None = None,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, int]]:
    return compute_weights_with_options(
        manifest_path=manifest_path,
        group_field=group_field,
        min_count=min_count,
        smoothing=smoothing,
        exponent=exponent,
        technique_boosts=None,
        dedupe_fields=None,
        max_per_group=None,
        technique_filter=None,
        match_all=False,
        include_unmatched=False,
        min_weight=min_weight,
        max_weight=max_weight,
    )


def compute_weights_with_options(
    manifest_path: Path,
    group_field: str,
    min_count: int,
    smoothing: float,
    exponent: float,
    *,
    technique_boosts: Optional[Dict[str, float]] = None,
    dedupe_fields: Optional[Sequence[str]] = None,
    max_per_group: Optional[int] = None,
    technique_filter: Optional[Sequence[str]] = None,
    match_all: bool = False,
    include_unmatched: bool = False,
    min_weight: float | None = None,
    max_weight: float | None = None,
    progress: ProgressAdapter | None = None,
    logger: OutputLogger | None = None,
    status_interval: int = 50_000,
    stats_out: Optional[Dict[str, int]] = None,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, int]]:
    per_group: Dict[str, Dict[str, Counter[str] | int]] = {}
    technique_totals: Counter[str] = Counter()
    seen_keys_global: set[Tuple[str, ...]] = set()
    technique_filter_tuple: Tuple[str, ...] | None = None
    if technique_filter:
        technique_filter_tuple = tuple(sorted({item for item in technique_filter if item}))
    status_interval = max(int(status_interval or 0), 0)
    processed_events = 0

    def report_progress() -> None:
        if progress is not None and progress.enabled:
            progress.update(
                advance=1,
                processed=processed_events,
                groups=len(per_group),
                techniques=len(technique_totals),
            )
        elif logger is not None and status_interval and processed_events % status_interval == 0:
            logger.print(
                f"Processed {processed_events:,} events -> groups={len(per_group):,}"
            )

    for record in iter_filtered_events(
        manifest_path,
        technique_filter=technique_filter_tuple,
        match_all=match_all,
    ):
        processed_events += 1
        try:
            if technique_filter_tuple and not include_unmatched and not record.matches_filter:
                continue

            event = record.event
            key = event.get(group_field)
            if isinstance(key, list):
                # Some manifests store arrays; fall back to the first element when grouping.
                key = key[0] if key else None
            if not isinstance(key, str) or not key:
                continue

            if dedupe_fields:
                components = tuple(
                    json.dumps(event.get(field), sort_keys=True, separators=(",", ":"))
                    for field in dedupe_fields
                )
                if components in seen_keys_global:
                    continue
                seen_keys_global.add(components)

            entry = per_group.setdefault(key, {"count": 0, "techniques": Counter()})
            if max_per_group is not None and entry["count"] >= max_per_group:
                continue

            entry["count"] = int(entry["count"]) + 1

            for technique in record.techniques:
                if technique:
                    entry["techniques"][technique] += 1  # type: ignore[index]
                    technique_totals[technique] += 1
        finally:
            report_progress()

    if progress is not None and progress.enabled:
        progress.update(
            advance=0,
            processed=processed_events,
            groups=len(per_group),
            techniques=len(technique_totals),
        )
    elif logger is not None and (status_interval <= 0 or processed_events % status_interval != 0):
        logger.print(
            f"Processed {processed_events:,} events -> groups={len(per_group):,}"
        )

    weights: Dict[str, Dict[str, float]] = {}
    for key, data in per_group.items():
        count = int(data["count"])
        if count < min_count:
            continue
        weight = (count + smoothing) ** (-exponent)
        if technique_boosts:
            for technique, factor in technique_boosts.items():
                if data["techniques"].get(technique, 0):  # type: ignore[index]
                    weight *= factor

        if min_weight is not None:
            weight = max(weight, min_weight)
        if max_weight is not None:
            weight = min(weight, max_weight)

        weights[key] = {
            "count": int(count),
            "weight": float(weight),
        }
        if data["techniques"]:  # type: ignore[index]
            weights[key]["technique_counts"] = {
                technique: int(total)
                for technique, total in data["techniques"].items()  # type: ignore[index]
            }

    if stats_out is not None:
        stats_out["processed_events"] = processed_events
        stats_out["groups_retained"] = len(weights)
        stats_out["events_retained"] = sum(int(info["count"]) for info in weights.values())

    return weights, {technique: int(total) for technique, total in technique_totals.items()}


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Path to events JSONL manifest")
    parser.add_argument(
        "--profile",
        type=str,
        help="Optional sampling profile key defined in sampling_profiles.json",
    )
    parser.add_argument(
        "--profiles-path",
        type=Path,
        default=DEFAULT_PROFILES_PATH,
        help=f"Path to sampling profiles JSON (default: {DEFAULT_PROFILES_PATH})",
    )
    parser.add_argument(
        "--group-field",
        default="audio_path",
        choices=["audio_path", "session_id"],
        help="Event field used to aggregate counts (default: audio_path)",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=1,
        help="Drop groups with fewer than this many events (default: 1)",
    )
    parser.add_argument(
        "--smoothing",
        type=float,
        default=0.0,
        help="Additive smoothing before exponentiation (default: 0.0)",
    )
    parser.add_argument(
        "--exponent",
        type=float,
        default=0.5,
        help="Negative exponent used in weight computation (default: 0.5 -> 1/sqrt)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination JSON file for weights",
    )
    parser.add_argument(
        "--technique-boost",
        action="append",
        default=[],
        metavar="TECHNIQUE=FACTOR",
        help="Apply multiplicative factor to groups containing TECHNIQUE (repeatable).",
    )
    parser.add_argument(
        "--dedupe-key",
        type=str,
        help=(
            "Comma-separated list of event fields used to deduplicate entries before counting. "
            "Each combination is only counted once."
        ),
    )
    parser.add_argument(
        "--max-events-per-group",
        type=int,
        help=(
            "Maximum number of events to count per group after deduplication. Additional events are ignored."
        ),
    )
    parser.add_argument(
        "--min-weight",
        type=float,
        help="Clamp the minimum allowed weight (applied after boosts).",
    )
    parser.add_argument(
        "--max-weight",
        type=float,
        help="Clamp the maximum allowed weight (applied after boosts).",
    )
    parser.add_argument(
        "--filter-technique",
        action="append",
        default=[],
        help="Only include events containing the given technique (repeat flag to add more).",
    )
    parser.add_argument(
        "--filter-match-all",
        action="store_true",
        help="Require all filter techniques to be present (default: any).",
    )
    parser.add_argument(
        "--include-unmatched",
        action="store_true",
        help="Keep events that do not match the technique filter when computing counts.",
    )
    parser.add_argument(
        "--status-interval",
        type=int,
        default=50_000,
        help="Emit a plain-text status update every N events when rich output is disabled (default: 50000)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Write log output to this file in addition to the console",
    )
    parser.add_argument(
        "--disable-rich",
        action="store_true",
        help="Disable rich console features even if the dependency is installed",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    setattr(args, "_parser", parser)
    return args


def render_weights_summary(
    weights: Dict[str, Dict[str, float]],
    technique_totals: Dict[str, int],
    stats: Dict[str, int],
    *,
    args: argparse.Namespace,
    logger: OutputLogger,
) -> None:
    processed_events = stats.get("processed_events", 0)
    events_retained = stats.get("events_retained", 0)
    groups_retained = stats.get("groups_retained", len(weights))
    if not events_retained:
        events_retained = sum(int(entry.get("count", 0)) for entry in weights.values())
    if processed_events == 0:
        processed_events = events_retained

    weight_values = [float(entry.get("weight", 0.0)) for entry in weights.values()]
    min_weight = min(weight_values) if weight_values else 0.0
    max_weight = max(weight_values) if weight_values else 0.0
    avg_weight = (sum(weight_values) / len(weight_values)) if weight_values else 0.0

    def fmt_int(value: object) -> str:
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return str(value)

    def fmt_float(value: float) -> str:
        return f"{value:.6f}"

    top_groups = sorted(
        weights.items(),
        key=lambda item: (int(item[1].get("count", 0)), item[0]),
        reverse=True,
    )[:10]
    top_techniques = sorted(
        technique_totals.items(),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )[:10]

    logger.print(f"Weights written to {args.output.as_posix()}")

    if logger.enable_rich and Table is not None:
        summary_kwargs = {"title": "Sampling Weight Summary"}
        if box is not None:
            summary_kwargs["box"] = box.SIMPLE_HEAD
        summary_table = Table(**summary_kwargs)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", justify="right", style="magenta")
        summary_table.add_row("Manifest", args.manifest.as_posix())
        summary_table.add_row("Group field", args.group_field)
        summary_table.add_row("Processed events", fmt_int(processed_events))
        summary_table.add_row("Events retained", fmt_int(events_retained))
        summary_table.add_row("Groups retained", fmt_int(groups_retained))
        summary_table.add_row("Min weight", fmt_float(min_weight))
        summary_table.add_row("Max weight", fmt_float(max_weight))
        summary_table.add_row("Average weight", fmt_float(avg_weight))
        if args.filter_technique:
            summary_table.add_row(
                "Technique filters",
                ", ".join(sorted(args.filter_technique)),
            )
        summary_table.add_row("Match all techniques", "yes" if args.filter_match_all else "no")
        summary_table.add_row("Include unmatched", "yes" if args.include_unmatched else "no")
        logger.print(summary_table)

        if top_groups:
            group_kwargs = {"title": "Top Groups by Event Count"}
            if box is not None:
                group_kwargs["box"] = box.SIMPLE
            group_table = Table(**group_kwargs)
            group_table.add_column("Group", style="cyan")
            group_table.add_column("Events", justify="right", style="magenta")
            group_table.add_column("Weight", justify="right", style="green")
            for group, info in top_groups:
                group_table.add_row(group, fmt_int(info.get("count", 0)), fmt_float(float(info.get("weight", 0.0))))
            logger.print(group_table)

        if top_techniques:
            tech_kwargs = {"title": "Top Techniques"}
            if box is not None:
                tech_kwargs["box"] = box.SIMPLE
            tech_table = Table(**tech_kwargs)
            tech_table.add_column("Technique", style="cyan")
            tech_table.add_column("Count", justify="right", style="magenta")
            for name, total in top_techniques:
                tech_table.add_row(name, fmt_int(total))
            logger.print(tech_table)
    else:
        logger.print("Sampling weight summary:")
        logger.print(f"  Manifest: {args.manifest.as_posix()}")
        logger.print(f"  Group field: {args.group_field}")
        logger.print(f"  Processed events: {fmt_int(processed_events)}")
        logger.print(f"  Events retained: {fmt_int(events_retained)}")
        logger.print(f"  Groups retained: {fmt_int(groups_retained)}")
        logger.print(f"  Weight range: {fmt_float(min_weight)} – {fmt_float(max_weight)} (avg {fmt_float(avg_weight)})")
        if args.filter_technique:
            logger.print("  Technique filters: " + ", ".join(sorted(args.filter_technique)))
        logger.print(
            "  Filters -> match all: {match_all}, include unmatched: {include}".format(
                match_all="yes" if args.filter_match_all else "no",
                include="yes" if args.include_unmatched else "no",
            )
        )
        if top_groups:
            logger.print("  Top groups:")
            for group, info in top_groups:
                logger.print(
                    f"    {group}: {fmt_int(info.get('count', 0))} events @ weight {fmt_float(float(info.get('weight', 0.0)))}"
                )
        if top_techniques:
            logger.print("  Top techniques:")
            for name, total in top_techniques:
                logger.print(f"    {name}: {fmt_int(total)}")
def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    parser: argparse.ArgumentParser = getattr(args, "_parser")
    defaults = {
        action.dest: action.default
        for action in parser._actions
        if hasattr(action, "dest") and action.dest not in {"help"}
    }

    profile_name = getattr(args, "profile", None)
    if profile_name:
        profiles_path = getattr(args, "profiles_path")
        if not profiles_path.exists():
            raise FileNotFoundError(f"Profiles file not found: {profiles_path}")
        with profiles_path.open("r", encoding="utf-8") as handle:
            profiles = json.load(handle)
        if profile_name not in profiles:
            available = ", ".join(sorted(profiles.keys())) or "<none>"
            raise SystemExit(f"Unknown profile '{profile_name}'. Available: {available}")
        profile = profiles[profile_name]

        if args.group_field == defaults.get("group_field") and profile.get("group_field"):
            args.group_field = profile["group_field"]
        if args.min_count == defaults.get("min_count") and profile.get("min_count") is not None:
            args.min_count = int(profile["min_count"])
        if args.smoothing == defaults.get("smoothing") and profile.get("smoothing") is not None:
            args.smoothing = float(profile["smoothing"])
        if args.exponent == defaults.get("exponent") and profile.get("exponent") is not None:
            args.exponent = float(profile["exponent"])
        if args.dedupe_key is None and profile.get("dedupe_fields"):
            args.dedupe_key = ",".join(profile["dedupe_fields"])
        if args.max_events_per_group is None and profile.get("max_events_per_group") is not None:
            args.max_events_per_group = int(profile["max_events_per_group"])
        if args.min_weight is None and profile.get("min_weight") is not None:
            args.min_weight = float(profile["min_weight"])
        if args.max_weight is None and profile.get("max_weight") is not None:
            args.max_weight = float(profile["max_weight"])

        profile_boosts = profile.get("technique_boosts") or {}
        if not args.technique_boost:
            args.technique_boost = [f"{name}={value}" for name, value in profile_boosts.items()]
        else:
            existing = {
                segment.split("=", 1)[0].strip()
                for segment in args.technique_boost
                if "=" in segment
            }
            for name, value in profile_boosts.items():
                if name not in existing:
                    args.technique_boost.append(f"{name}={value}")

        profile_filter = profile.get("technique_filter") or []
        if not args.filter_technique and profile_filter:
            args.filter_technique = list(profile_filter)
        elif profile_filter:
            existing_filters = set(args.filter_technique)
            for item in profile_filter:
                if item not in existing_filters:
                    args.filter_technique.append(item)

        if args.filter_match_all == defaults.get("filter_match_all") and profile.get("filter_match_all") is not None:
            args.filter_match_all = bool(profile["filter_match_all"])
        if args.include_unmatched == defaults.get("include_unmatched") and profile.get("include_unmatched") is not None:
            args.include_unmatched = bool(profile["include_unmatched"])
    else:
        profile = None

    if not args.manifest.exists():
        raise FileNotFoundError(f"Manifest not found: {args.manifest}")

    technique_boosts: Dict[str, float] = {}
    for entry in args.technique_boost or []:
        if "=" not in entry:
            raise SystemExit(f"Invalid --technique-boost format: '{entry}' (expected technique=factor)")
        label, value = entry.split("=", 1)
        label = label.strip()
        if not label:
            raise SystemExit(f"Invalid --technique-boost format: '{entry}' (technique name missing)")
        try:
            factor = float(value)
        except ValueError as exc:
            raise SystemExit(f"Invalid --technique-boost factor '{value}' for technique '{label}'") from exc
        technique_boosts[label] = factor

    dedupe_fields: Sequence[str] | None = None
    if args.dedupe_key:
        dedupe_fields = [field.strip() for field in args.dedupe_key.split(",") if field.strip()]
        if not dedupe_fields:
            dedupe_fields = None

    logger = OutputLogger(enable_rich=not args.disable_rich, log_file=args.log_file)
    summary_stats: Dict[str, int] = {}

    try:
        logger.rule("Sampling Weights")
        logger.print(f"Manifest: {args.manifest.as_posix()}")
        logger.print(f"Output: {args.output.as_posix()}")
        logger.print(
            "Group field: {group} | min count: {min_count} | exponent: {exp}".format(
                group=args.group_field,
                min_count=args.min_count,
                exp=args.exponent,
            )
        )
        if profile_name:
            logger.print(f"Profile: {profile_name}")
        if dedupe_fields:
            logger.print("Deduplication fields: " + ", ".join(dedupe_fields))
        if technique_boosts:
            boost_text = ", ".join(f"{name}={value}" for name, value in sorted(technique_boosts.items()))
            logger.print("Technique boosts: " + boost_text)
        if args.filter_technique:
            filters = ", ".join(sorted(args.filter_technique))
            logger.print(
                "Technique filters: {filters} (match_all={match_all}, include_unmatched={include})".format(
                    filters=filters,
                    match_all="yes" if args.filter_match_all else "no",
                    include="yes" if args.include_unmatched else "no",
                )
            )

        with ProgressAdapter(
            logger,
            "Scanning events",
            fields={"processed": 0, "groups": 0, "techniques": 0},
        ) as progress:
            weights, technique_totals = compute_weights_with_options(
                manifest_path=args.manifest,
                group_field=args.group_field,
                min_count=args.min_count,
                smoothing=args.smoothing,
                exponent=args.exponent,
                technique_boosts=technique_boosts or None,
                dedupe_fields=dedupe_fields,
                max_per_group=args.max_events_per_group,
                technique_filter=args.filter_technique or None,
                match_all=args.filter_match_all,
                include_unmatched=args.include_unmatched,
                min_weight=args.min_weight,
                max_weight=args.max_weight,
                progress=progress,
                logger=logger,
                status_interval=args.status_interval,
                stats_out=summary_stats,
            )

        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "parameters": {
                "manifest": str(args.manifest),
                "group_field": args.group_field,
                "min_count": args.min_count,
                "smoothing": args.smoothing,
                "exponent": args.exponent,
                "technique_boosts": technique_boosts or None,
                "dedupe_fields": list(dedupe_fields) if dedupe_fields else None,
                "max_events_per_group": args.max_events_per_group,
                "technique_filter": args.filter_technique or None,
                "filter_match_all": bool(args.filter_match_all),
                "include_unmatched": bool(args.include_unmatched),
                "profile": profile_name,
                "min_weight": args.min_weight,
                "max_weight": args.max_weight,
            },
            "weights": weights,
        }
        if technique_totals:
            payload["technique_totals"] = technique_totals

        with args.output.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

        render_weights_summary(weights, technique_totals, summary_stats, args=args, logger=logger)
    finally:
        logger.close()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
