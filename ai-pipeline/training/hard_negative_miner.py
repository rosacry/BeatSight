"""Harvest hard negatives (false positives) from inference logs.

Reads model predictions, compares them with optional ground-truth annotations,
and writes high-confidence mismatches to `negatives_manifest.jsonl` for manual
review.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


@dataclass
class Prediction:
	sample_id: str
	session_id: Optional[str]
	audio_path: Optional[str]
	onset_time: Optional[float]
	labels: List[str]
	scores: Dict[str, float]
	base_confidence: float

	def label_confidence(self, label: str) -> float:
		if label in self.scores:
			return float(self.scores[label])
		return float(self.base_confidence)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Harvest hard negatives from predictions")
	parser.add_argument("--predictions", required=True, help="JSONL file with model predictions")
	parser.add_argument("--ground-truth", help="Optional events JSONL providing true labels per sample")
	parser.add_argument("--output", default="negatives_manifest.jsonl", help="Output JSONL path")
	parser.add_argument("--min-confidence", type=float, default=0.6, help="Minimum confidence to consider a candidate")
	parser.add_argument("--max-per-label", type=int, default=200, help="Cap per predicted label")
	parser.add_argument("--max-total", type=int, default=2000, help="Total cap across labels")
	parser.add_argument("--exclude-label", action="append", default=[], help="Labels to ignore")
	parser.add_argument("--dry-run", action="store_true", help="Do not write output, only print summary")
	return parser.parse_args(argv)


def load_ground_truth(path: Path) -> Dict[str, Set[str]]:
	truth: Dict[str, Set[str]] = defaultdict(set)
	with path.open("r", encoding="utf-8") as handle:
		for line in handle:
			line = line.strip()
			if not line:
				continue
			payload = json.loads(line)
			sample_id = payload.get("sample_id")
			if not sample_id:
				continue
			if payload.get("negative_example"):
				continue
			components = payload.get("components") or []
			labels = {
				comp["label"]
				for comp in components
				if isinstance(comp, dict) and comp.get("label")
			}
			if not labels and payload.get("label"):
				labels.add(payload["label"])
			truth[sample_id].update(labels)
	return truth


def load_predictions(path: Path) -> List[Prediction]:
	records: List[Prediction] = []
	with path.open("r", encoding="utf-8") as handle:
		for line in handle:
			line = line.strip()
			if not line:
				continue
			payload = json.loads(line)
			sample_id = payload.get("sample_id")
			if not sample_id:
				continue
			labels_field = payload.get("predicted_labels") or payload.get("labels") or []
			if isinstance(labels_field, str):
				labels = [labels_field]
			else:
				labels = list(labels_field)
			if not labels and payload.get("predicted_label"):
				labels = [payload["predicted_label"]]
			scores = {
				k: float(v)
				for k, v in (payload.get("scores") or payload.get("predicted_scores") or {}).items()
			}
			confidence = float(payload.get("confidence", 0.0))
			records.append(
				Prediction(
					sample_id=sample_id,
					session_id=payload.get("session_id"),
					audio_path=payload.get("audio_path"),
					onset_time=payload.get("onset_time"),
					labels=labels,
					scores=scores,
					base_confidence=confidence,
				)
			)
	return records


def harvest_candidates(
	predictions: Iterable[Prediction],
	ground_truth: Dict[str, Set[str]],
	min_confidence: float,
	max_per_label: int,
	max_total: int,
	excluded_labels: Set[str],
) -> List[Dict]:
	candidates: List[Dict] = []
	seen: Set[Tuple[str, str]] = set()
	label_counts: Dict[str, int] = defaultdict(int)

	for pred in predictions:
		actual_labels = ground_truth.get(pred.sample_id, set()) if ground_truth else set()
		for label in pred.labels:
			if label in excluded_labels:
				continue
			conf = pred.label_confidence(label)
			if conf < min_confidence:
				continue
			key = (pred.sample_id, label)
			if key in seen:
				continue
			if ground_truth and label in actual_labels:
				continue
			if label_counts[label] >= max_per_label:
				continue
			manifest_entry = {
				"sample_id": pred.sample_id,
				"session_id": pred.session_id,
				"audio_path": pred.audio_path,
				"predicted_label": label,
				"confidence": conf,
				"onset_time": pred.onset_time,
				"reason": "high_confidence_false_positive" if ground_truth else "high_confidence_candidate",
			}
			candidates.append(manifest_entry)
			seen.add(key)
			label_counts[label] += 1
			if len(candidates) >= max_total:
				return candidates
	return candidates


def write_manifest(path: Path, entries: Iterable[Dict]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8") as handle:
		for entry in entries:
			handle.write(json.dumps(entry))
			handle.write("\n")


def main(argv: Optional[Sequence[str]] = None) -> int:
	args = parse_args(argv)
	try:
		predictions = load_predictions(Path(args.predictions))
	except Exception as exc:
		print(f"[hard_negative_miner] Failed to load predictions: {exc}", file=sys.stderr)
		return 2

	ground_truth: Dict[str, Set[str]] = {}
	if args.ground_truth:
		try:
			ground_truth = load_ground_truth(Path(args.ground_truth))
		except Exception as exc:
			print(f"[hard_negative_miner] Failed to load ground truth: {exc}", file=sys.stderr)
			return 2

	candidates = harvest_candidates(
		predictions=predictions,
		ground_truth=ground_truth,
		min_confidence=args.min_confidence,
		max_per_label=args.max_per_label,
		max_total=args.max_total,
		excluded_labels=set(args.exclude_label),
	)

	print(
		f"Identified {len(candidates)} hard-negative candidates (min_conf={args.min_confidence}, "
		f"max_total={args.max_total})."
	)

	if args.dry_run:
		return 0

	try:
		write_manifest(Path(args.output), candidates)
	except Exception as exc:
		print(f"[hard_negative_miner] Failed to write manifest: {exc}", file=sys.stderr)
		return 3

	print(f"Manifest written to {args.output}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
