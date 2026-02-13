"""Multi-mic alignment quality checks for BeatSight drum sessions.

This utility estimates inter-mic delay and long-term drift so sessions with
misaligned microphone recordings can be excluded from validation/test splits as
required by the dataset readiness plan. The analysis runs on transient-heavy
windows around detected onsets and reports median offsets plus drift per pair.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import librosa
import numpy as np
import soundfile as sf


@dataclass
class AlignmentSample:
    """Stores a single onset alignment estimate for a pair of microphones."""

    time_sec: float
    lag_samples: int
    confidence: float


@dataclass
class PairAlignmentReport:
    """Aggregated alignment statistics for a mic pair."""

    anchor: str
    target: str
    median_delay_ms: float
    mean_delay_ms: float
    max_abs_delay_ms: float
    std_delay_ms: float
    drift_samples_per_min: float
    support: int
    pass_delay: bool
    pass_drift: bool
    alerts: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.pass_delay and self.pass_drift


@dataclass
class SessionAlignmentReport:
    """Full report for a session."""

    session_id: str
    sample_rate: int
    anchor_mic: str
    num_onsets: int
    pair_reports: List[PairAlignmentReport]
    passed: bool
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "sample_rate": self.sample_rate,
            "anchor_mic": self.anchor_mic,
            "num_onsets": self.num_onsets,
            "passed": self.passed,
            "alerts": self.alerts,
            "pairs": [
                {
                    "anchor": pair.anchor,
                    "target": pair.target,
                    "median_delay_ms": pair.median_delay_ms,
                    "mean_delay_ms": pair.mean_delay_ms,
                    "max_abs_delay_ms": pair.max_abs_delay_ms,
                    "std_delay_ms": pair.std_delay_ms,
                    "drift_samples_per_min": pair.drift_samples_per_min,
                    "support": pair.support,
                    "pass_delay": pair.pass_delay,
                    "pass_drift": pair.pass_drift,
                    "alerts": pair.alerts,
                }
                for pair in self.pair_reports
            ],
        }


class MultiMicAlignmentAnalyzer:
    """Alignment analysis for a set of microphones."""

    def __init__(
        self,
        max_shift_ms: float = 5.0,
        max_delay_ms: float = 0.25,
        max_drift_samples_per_min: float = 1.0,
        min_support: int = 20,
        onset_window_ms: float = 500.0,
        lookback_ms: float = 120.0,
        resample_rate: Optional[int] = None,
    ) -> None:
        self.max_shift_ms = max_shift_ms
        self.max_delay_ms = max_delay_ms
        self.max_drift_samples_per_min = max_drift_samples_per_min
        self.min_support = min_support
        self.onset_window_ms = onset_window_ms
        self.lookback_ms = lookback_ms
        self.resample_rate = resample_rate

    def analyze(self, session_id: str, audio_map: Dict[str, Tuple[np.ndarray, int]]) -> SessionAlignmentReport:
        if not audio_map:
            raise ValueError("No microphone recordings provided")

        mic_names = sorted(audio_map.keys())
        anchor = mic_names[0]
        anchor_audio, anchor_sr = audio_map[anchor]
        target_sr = self.resample_rate or anchor_sr

        # Resample anchor if requested
        anchor_audio = self._prepare_audio(anchor_audio, anchor_sr, target_sr)
        anchor_sr = target_sr

        onset_frames = self._detect_onsets(anchor_audio, anchor_sr)
        onset_samples = self._filter_onsets(anchor_audio, onset_frames, anchor_sr)

        if len(onset_samples) < self.min_support:
            raise RuntimeError(
                f"Insufficient high-quality onsets ({len(onset_samples)}) for alignment; "
                f"requires at least {self.min_support}."
            )

        reports: List[PairAlignmentReport] = []
        session_passed = True
        session_alerts: List[str] = []

        for mic in mic_names:
            if mic == anchor:
                continue

            audio, sr = audio_map[mic]
            audio = self._prepare_audio(audio, sr, target_sr)

            samples = self._collect_samples(anchor_audio, audio, anchor_sr, onset_samples)
            if len(samples) < self.min_support:
                alert = (
                    f"Mic '{mic}' produced only {len(samples)} usable alignment windows (<{self.min_support}); "
                    "marking as failed."
                )
                pair_report = PairAlignmentReport(
                    anchor=anchor,
                    target=mic,
                    median_delay_ms=float("nan"),
                    mean_delay_ms=float("nan"),
                    max_abs_delay_ms=float("nan"),
                    std_delay_ms=float("nan"),
                    drift_samples_per_min=float("nan"),
                    support=len(samples),
                    pass_delay=False,
                    pass_drift=False,
                    alerts=[alert],
                )
                reports.append(pair_report)
                session_alerts.append(alert)
                session_passed = False
                continue

            pair_report = self._summarize_pair(anchor, mic, samples, anchor_sr)
            reports.append(pair_report)
            if not pair_report.passed:
                session_passed = False
                session_alerts.extend(pair_report.alerts)

        return SessionAlignmentReport(
            session_id=session_id,
            sample_rate=anchor_sr,
            anchor_mic=anchor,
            num_onsets=len(onset_samples),
            pair_reports=reports,
            passed=session_passed,
            alerts=session_alerts,
        )

    def _prepare_audio(self, audio: np.ndarray, sr: int, target_sr: int) -> np.ndarray:
        # Down-mix multi-channel recordings and resample if needed.
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        if sr != target_sr:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
        audio = audio.astype(np.float32)
        audio -= np.mean(audio)
        std = np.std(audio)
        if std > 0:
            audio /= std
        return audio

    def _detect_onsets(self, audio: np.ndarray, sr: int) -> np.ndarray:
        hop_length = 512
        onset_env = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=hop_length)
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sr,
            hop_length=hop_length,
            backtrack=True,
            units="frames",
            pre_max=3,
            post_max=3,
            pre_avg=3,
            post_avg=3,
            delta=0.1,
            wait=0,
        )
        return onset_frames

    def _filter_onsets(self, audio: np.ndarray, frames: np.ndarray, sr: int) -> np.ndarray:
        hop_length = 512
        times = librosa.frames_to_samples(frames, hop_length=hop_length)
        window = int((self.onset_window_ms / 1000.0) * sr)
        lookback = int((self.lookback_ms / 1000.0) * sr)

        usable_onsets: List[int] = []
        for sample_idx in times:
            start = max(sample_idx - lookback, 0)
            end = min(sample_idx + window, len(audio))
            if end - start < 1024:
                continue
            segment = audio[start:end]
            if np.max(np.abs(segment)) < 0.05:
                continue
            usable_onsets.append(sample_idx)

        # Limit to avoid excessive runtime
        max_onsets = 256
        if len(usable_onsets) > max_onsets:
            usable_onsets = usable_onsets[:max_onsets]
        return np.array(usable_onsets, dtype=int)

    def _collect_samples(
        self,
        anchor_audio: np.ndarray,
        target_audio: np.ndarray,
        sr: int,
        onset_samples: np.ndarray,
    ) -> List[AlignmentSample]:
        window = int((self.onset_window_ms / 1000.0) * sr)
        lookback = int((self.lookback_ms / 1000.0) * sr)
        max_shift = int((self.max_shift_ms / 1000.0) * sr)
        samples: List[AlignmentSample] = []

        for onset in onset_samples:
            start = max(onset - lookback, 0)
            end = min(onset + window, len(anchor_audio))
            t_start = start
            t_end = min(onset + window, len(target_audio))
            if t_end - t_start < 1024:
                continue

            anchor_segment = anchor_audio[start:end]
            target_segment = target_audio[t_start:t_end]
            length = min(len(anchor_segment), len(target_segment))
            anchor_segment = anchor_segment[:length]
            target_segment = target_segment[:length]

            delay, confidence = self._estimate_delay(anchor_segment, target_segment, max_shift)
            if delay is None:
                continue
            samples.append(AlignmentSample(time_sec=onset / sr, lag_samples=delay, confidence=confidence))
        return samples

    def _estimate_delay(
        self,
        anchor_segment: np.ndarray,
        target_segment: np.ndarray,
        max_shift: int,
    ) -> Tuple[Optional[int], float]:
        anchor_segment = anchor_segment - np.mean(anchor_segment)
        target_segment = target_segment - np.mean(target_segment)

        if np.std(anchor_segment) == 0 or np.std(target_segment) == 0:
            return None, 0.0

        corr = self._cross_correlation(anchor_segment, target_segment, max_shift)
        if corr is None:
            return None, 0.0

        lags = np.arange(-max_shift, max_shift + 1)
        best_idx = np.argmax(corr)
        best_lag = int(lags[best_idx])
        best_value = corr[best_idx]
        confidence = float(best_value)

        return best_lag, confidence

    def _cross_correlation(
        self,
        anchor_segment: np.ndarray,
        target_segment: np.ndarray,
        max_shift: int,
    ) -> Optional[np.ndarray]:
        length = len(anchor_segment)
        if length == 0 or len(target_segment) != length:
            return None

        # Normalized cross-correlation limited to ±max_shift samples.
        corr = []
        denom = np.linalg.norm(anchor_segment) * np.linalg.norm(target_segment)
        if denom == 0:
            return None

        for lag in range(-max_shift, max_shift + 1):
            if lag < 0:
                ref = anchor_segment[: length + lag]
                tgt = target_segment[-lag:]
            elif lag > 0:
                ref = anchor_segment[lag:]
                tgt = target_segment[: length - lag]
            else:
                ref = anchor_segment
                tgt = target_segment

            if len(ref) < 128:
                corr.append(-np.inf)
                continue

            value = float(np.dot(ref, tgt) / (np.linalg.norm(ref) * np.linalg.norm(tgt)))
            corr.append(value)

        return np.array(corr, dtype=np.float32)

    def _summarize_pair(
        self,
        anchor_name: str,
        target_name: str,
        samples: List[AlignmentSample],
        sr: int,
    ) -> PairAlignmentReport:
        lags = np.array([sample.lag_samples for sample in samples], dtype=np.float32)
        times = np.array([sample.time_sec for sample in samples], dtype=np.float32)

        delays_ms = (lags / sr) * 1000.0
        median_delay = float(np.median(delays_ms))
        mean_delay = float(np.mean(delays_ms))
        std_delay = float(np.std(delays_ms))
        max_abs_delay = float(np.max(np.abs(delays_ms)))

        if len(times) >= 2:
            slope, _ = np.polyfit(times, lags, 1)
        else:
            slope = 0.0
        drift_samples_per_min = float(slope * 60.0)

        pass_delay = math.isfinite(max_abs_delay) and abs(median_delay) <= self.max_delay_ms and max_abs_delay <= self.max_delay_ms * 1.5
        pass_drift = math.isfinite(drift_samples_per_min) and abs(drift_samples_per_min) <= self.max_drift_samples_per_min

        alerts: List[str] = []
        if not pass_delay:
            alerts.append(
                f"Delay threshold exceeded for pair {anchor_name}->{target_name}: "
                f"median {median_delay:.3f} ms, max |delay| {max_abs_delay:.3f} ms"
            )
        if not pass_drift:
            alerts.append(
                f"Drift threshold exceeded for pair {anchor_name}->{target_name}: "
                f"{drift_samples_per_min:.3f} samples/min"
            )

        return PairAlignmentReport(
            anchor=anchor_name,
            target=target_name,
            median_delay_ms=median_delay,
            mean_delay_ms=mean_delay,
            max_abs_delay_ms=max_abs_delay,
            std_delay_ms=std_delay,
            drift_samples_per_min=drift_samples_per_min,
            support=len(samples),
            pass_delay=pass_delay,
            pass_drift=pass_drift,
            alerts=alerts,
        )


def load_session_from_manifest(manifest_path: Path) -> Tuple[str, Dict[str, Tuple[np.ndarray, int]]]:
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    session_id = manifest.get("session_id") or manifest_path.stem
    base_dir = manifest_path.parent
    audio_map: Dict[str, Tuple[np.ndarray, int]] = {}

    for mic in manifest.get("mics", []):
        name = mic["name"]
        rel_path = mic["path"]
        mic_path = (base_dir / rel_path).resolve()
        audio, sr = sf.read(mic_path)
        audio_map[name] = (np.asarray(audio), int(sr))
    return session_id, audio_map


def load_session_from_directory(session_dir: Path) -> Tuple[str, Dict[str, Tuple[np.ndarray, int]]]:
    audio_map: Dict[str, Tuple[np.ndarray, int]] = {}
    for extension in ("*.wav", "*.flac"):
        for path in sorted(session_dir.glob(extension)):
            name = path.stem
            audio, sr = sf.read(path)
            audio_map[name] = (np.asarray(audio), int(sr))
    if not audio_map:
        raise ValueError(f"No audio files found in {session_dir}")
    return session_dir.name, audio_map


def load_session_from_mic_args(entries: Iterable[str]) -> Tuple[str, Dict[str, Tuple[np.ndarray, int]]]:
    audio_map: Dict[str, Tuple[np.ndarray, int]] = {}
    session_id = "session"
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"Mic argument must be NAME=PATH, got '{entry}'")
        name, path_str = entry.split("=", 1)
        path = Path(path_str).expanduser().resolve()
        if session_id == "session":
            session_id = path.parent.name
        audio, sr = sf.read(path)
        audio_map[name] = (np.asarray(audio), int(sr))
    if not audio_map:
        raise ValueError("No microphones provided via --mic")
    return session_id, audio_map


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-mic alignment QC")
    parser.add_argument("inputs", nargs="*", help="Optional NAME=PATH entries when manifest/session-dir not used")
    parser.add_argument("--manifest", type=str, help="JSON manifest describing session microphones")
    parser.add_argument("--session-dir", type=str, help="Directory with per-mic audio files")
    parser.add_argument("--session-id", type=str, help="Override session id")
    parser.add_argument("--anchor-mic", type=str, help="Anchor microphone name (default: sorted first)")
    parser.add_argument("--report", type=str, help="Path to write alignment_report.json")
    parser.add_argument("--max-delay-ms", type=float, default=0.25, help="Maximum acceptable median delay in milliseconds")
    parser.add_argument("--max-drift-samples-per-min", type=float, default=1.0, help="Maximum acceptable drift (samples per minute)")
    parser.add_argument("--max-shift-ms", type=float, default=5.0, help="Search radius for cross-correlation")
    parser.add_argument("--min-support", type=int, default=20, help="Minimum number of usable onsets required per pair")
    parser.add_argument("--onset-window-ms", type=float, default=500.0, help="Window length after onset for alignment snippets")
    parser.add_argument("--lookback-ms", type=float, default=120.0, help="Audio included before onset")
    parser.add_argument("--resample-rate", type=int, help="Resample all mics to this rate before analysis")
    parser.add_argument("--strict", action="store_true", help="Exit with status 1 when report fails thresholds")
    return parser.parse_args(argv)


def build_audio_map(args: argparse.Namespace) -> Tuple[str, Dict[str, Tuple[np.ndarray, int]]]:
    if args.manifest:
        session_id, audio_map = load_session_from_manifest(Path(args.manifest))
    elif args.session_dir:
        session_id, audio_map = load_session_from_directory(Path(args.session_dir))
    elif args.inputs:
        session_id, audio_map = load_session_from_mic_args(args.inputs)
    else:
        raise ValueError("Provide --manifest, --session-dir, or NAME=PATH entries")

    if args.session_id:
        session_id = args.session_id

    return session_id, audio_map


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    try:
        session_id, audio_map = build_audio_map(args)
    except Exception as exc:
        print(f"[align_qc] Failed to load session: {exc}", file=sys.stderr)
        return 2

    analyzer = MultiMicAlignmentAnalyzer(
        max_shift_ms=args.max_shift_ms,
        max_delay_ms=args.max_delay_ms,
        max_drift_samples_per_min=args.max_drift_samples_per_min,
        min_support=args.min_support,
        onset_window_ms=args.onset_window_ms,
        lookback_ms=args.lookback_ms,
        resample_rate=args.resample_rate,
    )

    if args.anchor_mic:
        # Reorder audio map so requested anchor is first.
        if args.anchor_mic not in audio_map:
            print(f"[align_qc] Anchor mic '{args.anchor_mic}' not found", file=sys.stderr)
            return 2
        ordered = {args.anchor_mic: audio_map[args.anchor_mic]}
        for name, value in audio_map.items():
            if name == args.anchor_mic:
                continue
            ordered[name] = value
        audio_map = ordered

    try:
        report = analyzer.analyze(session_id=session_id, audio_map=audio_map)
    except Exception as exc:
        print(f"[align_qc] Analysis failed: {exc}", file=sys.stderr)
        return 3

    print(f"Session: {report.session_id}")
    print(f"Anchor mic: {report.anchor_mic}")
    print(f"Onsets analysed: {report.num_onsets}")
    for pair in report.pair_reports:
        status = "PASS" if pair.passed else "FAIL"
        print(
            f"  {pair.anchor}->{pair.target}: {status} | median {pair.median_delay_ms:.3f} ms | "
            f"max |delay| {pair.max_abs_delay_ms:.3f} ms | drift {pair.drift_samples_per_min:.3f} samples/min "
            f"(support={pair.support})"
        )
        for alert in pair.alerts:
            print(f"    ! {alert}")

    if report.alerts:
        print("Alerts:")
        for alert in report.alerts:
            print(f"  - {alert}")

    if args.report:
        output_path = Path(args.report)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"Report saved to {output_path}")

    if args.strict and not report.passed:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
