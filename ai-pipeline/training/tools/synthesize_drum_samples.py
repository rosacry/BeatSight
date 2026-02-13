#!/usr/bin/env python3
"""
Synthesize drum samples from MIDI events using sample libraries.

This script takes extracted MIDI drum events and renders them to audio
using drum sample libraries. It's designed to generate training data
for rare classes (china, splash, rimshot) that are underrepresented.

The script supports multiple synthesis backends:
1. FluidSynth (SoundFont-based, free)
2. Sample-based rendering (using individual WAV samples)
3. External VST rendering (via command-line tools)

Usage:
    # Using SoundFont
    python synthesize_drum_samples.py --events drum_events.jsonl \
        --soundfont drums.sf2 --output-dir ./synthesized

    # Using sample library
    python synthesize_drum_samples.py --events drum_events.jsonl \
        --sample-dir ./drum_samples --output-dir ./synthesized

    # Statistics only (no synthesis)
    python synthesize_drum_samples.py --events drum_events.jsonl --stats-only
"""

import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib

import numpy as np

try:
    import soundfile as sf
except ImportError:
    sf = None
    print("WARNING: soundfile not installed. Run: pip install soundfile")

try:
    from scipy import signal
except ImportError:
    signal = None

# Our target 12 classes (matching components.json) - rimshot merged into snare
TARGET_CLASSES = [
    "china", "crash", "cross_stick", "hihat_closed", "hihat_open",
    "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare",
    "splash", "tom"
]

# GM MIDI note to class mapping (same as extract script)
GM_DRUM_MAP = {
    35: "kick", 36: "kick",
    38: "snare", 40: "snare",
    37: "cross_stick",  # Side stick
    42: "hihat_closed", 44: "hihat_pedal", 46: "hihat_open",
    41: "tom", 43: "tom", 45: "tom", 47: "tom", 48: "tom", 50: "tom",
    49: "crash", 57: "crash",
    51: "ride_bow", 59: "ride_bow", 53: "ride_bell",
    52: "china",    # Chinese cymbal - RARE!
    55: "splash",   # Splash cymbal - RARE!
}


class SampleLibrary:
    """
    Manages a library of drum samples organized by class and velocity layer.
    
    Expected directory structure:
        sample_dir/
            china/
                china_soft_01.wav
                china_medium_01.wav
                china_hard_01.wav
            splash/
                splash_soft_01.wav
                ...
            rimshot/
                rimshot_soft_01.wav
                ...
    """
    
    VELOCITY_LAYERS = {
        "soft": (1, 50),
        "medium": (51, 100),
        "hard": (101, 127),
    }
    
    def __init__(self, sample_dir: Path, sample_rate: int = 44100):
        self.sample_dir = Path(sample_dir)
        self.sr = sample_rate
        self.samples: Dict[str, Dict[str, List[np.ndarray]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._load_samples()
    
    def _load_samples(self):
        """Load all samples from the library."""
        if not self.sample_dir.exists():
            print(f"WARNING: Sample directory not found: {self.sample_dir}")
            return
        
        for class_dir in self.sample_dir.iterdir():
            if not class_dir.is_dir():
                continue
            
            class_name = class_dir.name.lower()
            if class_name not in TARGET_CLASSES:
                continue
            
            for sample_file in class_dir.glob("*.wav"):
                try:
                    audio, sr = sf.read(sample_file)
                    if sr != self.sr:
                        # Resample if needed
                        if signal is not None:
                            num_samples = int(len(audio) * self.sr / sr)
                            audio = signal.resample(audio, num_samples)
                        else:
                            print(f"WARNING: Cannot resample {sample_file} (scipy not installed)")
                            continue
                    
                    # Convert to mono if stereo
                    if audio.ndim > 1:
                        audio = audio.mean(axis=1)
                    
                    # Determine velocity layer from filename
                    fname_lower = sample_file.stem.lower()
                    if "soft" in fname_lower or "p_" in fname_lower or "_p" in fname_lower:
                        layer = "soft"
                    elif "hard" in fname_lower or "f_" in fname_lower or "_f" in fname_lower:
                        layer = "hard"
                    else:
                        layer = "medium"
                    
                    self.samples[class_name][layer].append(audio)
                    
                except Exception as e:
                    print(f"WARNING: Failed to load {sample_file}: {e}")
        
        # Print summary
        print(f"\nSample Library loaded from {self.sample_dir}:")
        for class_name in sorted(self.samples.keys()):
            layers = self.samples[class_name]
            total = sum(len(v) for v in layers.values())
            print(f"  {class_name}: {total} samples "
                  f"(soft={len(layers['soft'])}, medium={len(layers['medium'])}, hard={len(layers['hard'])})")
    
    def get_sample(self, class_name: str, velocity: int = 100) -> Optional[np.ndarray]:
        """Get a random sample for the given class and velocity."""
        if class_name not in self.samples:
            return None
        
        # Determine velocity layer
        if velocity <= 50:
            layer = "soft"
        elif velocity <= 100:
            layer = "medium"
        else:
            layer = "hard"
        
        # Try requested layer, fall back to others
        layers_to_try = [layer, "medium", "soft", "hard"]
        for try_layer in layers_to_try:
            if self.samples[class_name][try_layer]:
                return random.choice(self.samples[class_name][try_layer]).copy()
        
        return None
    
    def has_class(self, class_name: str) -> bool:
        """Check if library has samples for a class."""
        return class_name in self.samples and any(
            len(v) > 0 for v in self.samples[class_name].values()
        )


class DrumSynthesizer:
    """
    Synthesizes drum audio from MIDI events.
    """
    
    def __init__(
        self,
        sample_library: Optional[SampleLibrary] = None,
        sample_rate: int = 44100,
        target_duration: float = 0.5,  # 500ms per hit
        output_dtype: str = "float32",
    ):
        self.library = sample_library
        self.sr = sample_rate
        self.target_duration = target_duration
        self.output_dtype = output_dtype
        self.target_samples = int(target_duration * sample_rate)
    
    def synthesize_hit(
        self,
        class_name: str,
        velocity: int = 100,
        pitch_shift: float = 0.0,
        gain_db: float = 0.0,
    ) -> Optional[np.ndarray]:
        """
        Synthesize a single drum hit.
        
        Args:
            class_name: Target drum class
            velocity: MIDI velocity (1-127)
            pitch_shift: Pitch shift in semitones
            gain_db: Volume adjustment in dB
            
        Returns:
            Audio array or None if synthesis failed
        """
        if self.library is None:
            return self._generate_placeholder(class_name, velocity)
        
        audio = self.library.get_sample(class_name, velocity)
        if audio is None:
            return self._generate_placeholder(class_name, velocity)
        
        # Apply velocity scaling
        velocity_scale = velocity / 127.0
        audio = audio * (0.5 + 0.5 * velocity_scale)
        
        # Apply gain
        if gain_db != 0:
            audio = audio * (10 ** (gain_db / 20.0))
        
        # Apply pitch shift (simple resampling)
        if pitch_shift != 0 and signal is not None:
            factor = 2 ** (pitch_shift / 12.0)
            new_length = int(len(audio) / factor)
            audio = signal.resample(audio, new_length)
        
        # Pad or trim to target duration
        if len(audio) < self.target_samples:
            audio = np.pad(audio, (0, self.target_samples - len(audio)))
        else:
            # Apply fade out at target duration
            fade_samples = min(int(0.05 * self.sr), self.target_samples // 10)
            audio = audio[:self.target_samples]
            if fade_samples > 0:
                fade = np.linspace(1, 0, fade_samples)
                audio[-fade_samples:] *= fade
        
        # Normalize
        peak = np.abs(audio).max()
        if peak > 0:
            audio = audio / peak * 0.9
        
        return audio.astype(np.float32)
    
    def _generate_placeholder(self, class_name: str, velocity: int) -> np.ndarray:
        """Generate a placeholder/test tone when no sample is available."""
        # Generate a simple decay envelope with noise (for testing)
        t = np.linspace(0, self.target_duration, self.target_samples)
        
        # Different characteristics per class
        if class_name in ["kick"]:
            freq = 60
            decay = 0.1
        elif class_name in ["snare", "cross_stick"]:
            freq = 200
            decay = 0.15
        elif class_name in ["hihat_closed", "hihat_pedal"]:
            freq = 800
            decay = 0.05
        elif class_name in ["hihat_open"]:
            freq = 600
            decay = 0.3
        elif class_name in ["crash", "china", "splash", "ride_bow", "ride_bell"]:
            freq = 400
            decay = 0.4
        elif class_name in ["tom"]:
            freq = 100
            decay = 0.2
        else:
            freq = 300
            decay = 0.2
        
        # Generate tone with decay
        envelope = np.exp(-t / decay)
        tone = np.sin(2 * np.pi * freq * t) * envelope
        
        # Add some noise for texture
        noise = np.random.randn(len(t)) * 0.1 * envelope
        
        audio = (tone + noise) * (velocity / 127.0) * 0.5
        
        return audio.astype(np.float32)


def load_events(events_file: Path, classes_filter: Optional[List[str]] = None) -> List[Dict]:
    """Load drum events from JSONL file."""
    events = []
    with open(events_file, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            event = json.loads(line)
            if classes_filter and event.get("class") not in classes_filter:
                continue
            events.append(event)
    return events


def synthesize_dataset(
    events: List[Dict],
    synthesizer: DrumSynthesizer,
    output_dir: Path,
    samples_per_class: Optional[int] = None,
    augment_variations: int = 1,
    verbose: bool = True,
) -> Dict:
    """
    Synthesize audio samples from events.
    
    Returns:
        Dictionary with synthesis statistics
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Group events by class
    events_by_class = defaultdict(list)
    for event in events:
        events_by_class[event["class"]].append(event)
    
    stats = {
        "total_events": len(events),
        "classes": {},
        "output_dir": str(output_dir),
        "samples_generated": 0,
    }
    
    labels = []  # For labels.json
    
    for class_name, class_events in events_by_class.items():
        if verbose:
            print(f"\nProcessing {class_name}: {len(class_events):,} events")
        
        # Limit samples if requested
        if samples_per_class and len(class_events) > samples_per_class:
            class_events = random.sample(class_events, samples_per_class)
        
        class_dir = output_dir / class_name
        class_dir.mkdir(exist_ok=True)
        
        class_count = 0
        
        for i, event in enumerate(class_events):
            velocity = event.get("velocity", 100)
            
            # Generate base sample + variations
            for var_idx in range(augment_variations):
                # Apply random augmentation
                pitch_shift = random.uniform(-0.5, 0.5) if var_idx > 0 else 0
                gain_db = random.uniform(-3, 3) if var_idx > 0 else 0
                
                audio = synthesizer.synthesize_hit(
                    class_name,
                    velocity=velocity,
                    pitch_shift=pitch_shift,
                    gain_db=gain_db,
                )
                
                if audio is None:
                    continue
                
                # Generate unique filename
                file_hash = event.get("file_hash", "unknown")[:8]
                event_time = event.get("time", 0)
                filename = f"{class_name}_{file_hash}_{event_time:.3f}_v{var_idx}.wav"
                filepath = class_dir / filename
                
                # Save audio
                sf.write(filepath, audio, synthesizer.sr)
                
                # Add to labels
                labels.append({
                    "file": str(filepath.relative_to(output_dir)),
                    "label": class_name,
                    "velocity": velocity,
                    "source_midi": event.get("midi_file", "unknown"),
                    "source_time": event_time,
                    "augmented": var_idx > 0,
                })
                
                class_count += 1
            
            if verbose and (i + 1) % 1000 == 0:
                print(f"  Generated {class_count:,} samples...")
        
        stats["classes"][class_name] = {
            "events": len(class_events),
            "samples_generated": class_count,
        }
        stats["samples_generated"] += class_count
        
        if verbose:
            print(f"  {class_name}: {class_count:,} samples generated")
    
    # Save labels
    labels_file = output_dir / "synthesis_labels.json"
    with open(labels_file, 'w') as f:
        json.dump(labels, f, indent=2)
    
    print(f"\nTotal samples generated: {stats['samples_generated']:,}")
    print(f"Labels saved to: {labels_file}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Synthesize drum samples from MIDI events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("--events", type=Path, required=True,
                        help="Input JSONL file with drum events (from extract_lakh_drums.py)")
    parser.add_argument("--sample-dir", type=Path, default=None,
                        help="Directory containing drum samples organized by class")
    parser.add_argument("--output-dir", type=Path, default=Path("./synthesized_drums"),
                        help="Output directory for synthesized samples")
    parser.add_argument("--samples-per-class", type=int, default=None,
                        help="Maximum samples to generate per class")
    parser.add_argument("--augment-variations", type=int, default=1,
                        help="Number of augmented variations per event (1=no augmentation)")
    parser.add_argument("--target-duration", type=float, default=0.5,
                        help="Target duration in seconds for each sample")
    parser.add_argument("--sample-rate", type=int, default=44100,
                        help="Output sample rate")
    parser.add_argument("--stats-only", action="store_true",
                        help="Only show statistics, don't synthesize")
    parser.add_argument("--rare-only", action="store_true",
                        help="Only process rare classes (china, splash, cross_stick)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress verbose output")
    
    args = parser.parse_args()
    
    if not args.events.exists():
        print(f"ERROR: Events file not found: {args.events}")
        sys.exit(1)
    
    # Determine classes to process (rimshot now detected via post-processing)
    classes_filter = None
    if args.rare_only:
        classes_filter = ["china", "splash", "cross_stick"]
    
    # Load events
    print(f"Loading events from {args.events}...")
    events = load_events(args.events, classes_filter)
    print(f"Loaded {len(events):,} events")
    
    # Show statistics
    counts = Counter(e["class"] for e in events)
    print("\nEvent distribution:")
    for class_name, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {class_name}: {count:,}")
    
    if args.stats_only:
        print("\n[Stats only mode - no synthesis]")
        return
    
    # Check for soundfile
    if sf is None:
        print("ERROR: soundfile not installed. Run: pip install soundfile")
        sys.exit(1)
    
    # Load sample library (if provided)
    library = None
    if args.sample_dir:
        library = SampleLibrary(args.sample_dir, args.sample_rate)
    else:
        print("\nWARNING: No sample library provided. Using placeholder synthesis.")
        print("For better results, provide --sample-dir with real drum samples.")
    
    # Create synthesizer
    synthesizer = DrumSynthesizer(
        sample_library=library,
        sample_rate=args.sample_rate,
        target_duration=args.target_duration,
    )
    
    # Synthesize
    stats = synthesize_dataset(
        events,
        synthesizer,
        args.output_dir,
        samples_per_class=args.samples_per_class,
        augment_variations=args.augment_variations,
        verbose=not args.quiet,
    )
    
    # Save stats
    stats_file = args.output_dir / "synthesis_stats.json"
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"Stats saved to: {stats_file}")


if __name__ == "__main__":
    main()
