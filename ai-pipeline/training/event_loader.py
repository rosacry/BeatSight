"""Helpers to iterate BeatSight manifests with technique-aware filtering."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class EventRecord:
    """Structured manifest entry emitted by :class:`ManifestEventLoader`."""

    index: int
    event: Dict[str, object]
    techniques: Tuple[str, ...]
    matches_filter: bool


@dataclass(frozen=True)
class ManifestSummary:
    """Lightweight summary describing manifest counts and technique coverage."""

    total_events: int
    technique_counts: Dict[str, int]


class ManifestEventLoader:
    """Stream events from a JSONL manifest without loading it entirely into memory.

    Parameters
    ----------
    manifest_path:
        Path to the events JSONL file.
    technique_filter:
        Optional iterable of technique labels. When supplied, :meth:`__iter__`
        yields every event but the :attr:`EventRecord.matches_filter` attribute
        indicates whether the event includes **any** of the requested
        techniques. Set ``match_all=True`` to require all techniques.
    match_all:
        Switch the filter behaviour between "any" (default) and "all".
    """

    def __init__(
        self,
        manifest_path: Path | str,
        *,
        technique_filter: Optional[Sequence[str]] = None,
        match_all: bool = False,
    ) -> None:
        self.manifest_path = Path(manifest_path)
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")

        self._technique_filter = tuple(sorted({t for t in (technique_filter or []) if t}))
        self._match_all = match_all

    def __iter__(self) -> Iterator[EventRecord]:
        technique_set = set(self._technique_filter)
        require_all = self._match_all and bool(technique_set)

        with self.manifest_path.open("r", encoding="utf-8") as handle:
            for index, raw in enumerate(handle):
                raw = raw.strip()
                if not raw:
                    continue
                event = json.loads(raw)
                techniques = tuple(sorted({t for t in (event.get("techniques") or []) if isinstance(t, str)}))

                if not technique_set:
                    matches = bool(techniques)
                elif require_all:
                    matches = technique_set.issubset(techniques)
                else:
                    matches = bool(technique_set.intersection(techniques))

                yield EventRecord(
                    index=index,
                    event=event,
                    techniques=techniques,
                    matches_filter=matches,
                )

    def summary(self, include_unmatched: bool = False) -> ManifestSummary:
        total = 0
        counts: Dict[str, int] = {}

        for record in self:
            total += 1
            if not record.techniques and not include_unmatched:
                continue
            for technique in record.techniques:
                counts[technique] = counts.get(technique, 0) + 1

        return ManifestSummary(total_events=total, technique_counts=counts)


def iter_filtered_events(
    manifest_path: Path | str,
    *,
    technique_filter: Optional[Sequence[str]] = None,
    match_all: bool = False,
) -> Iterable[EventRecord]:
    """Convenience wrapper that forwards to :class:`ManifestEventLoader`."""

    loader = ManifestEventLoader(
        manifest_path,
        technique_filter=technique_filter,
        match_all=match_all,
    )
    return loader
