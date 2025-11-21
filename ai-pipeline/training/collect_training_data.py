"""
Training Data Collection Utility for Drum Classifier

This script helps collect and label drum samples for training the ML classifier.
"""

import argparse
import json
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np
import soundfile as sf
import librosa


class DrumDataCollector:
    """
    Utility for collecting and managing labeled drum training data.
    """
    
    DRUM_COMPONENTS = [
        "kick",
        "snare_center",
        "snare_rimshot",
        "snare_cross_stick",
        "snare_off",
        "hihat_closed",
        "hihat_open",
        "hihat_half",
        "hihat_pedal",
        "hihat_splash",
        "tom_high",
        "tom_mid",
        "tom_low",
        "ride_bow",
        "ride_bell",
        "ride_edge",
        "crash_1",
        "crash_2",
        "china",
        "splash",
        "cowbell",
        "tambourine",
        "clap",
        "shaker"
    ]
    
    def __init__(self, data_dir: str = "training_data"):
        """
        Initialize data collector.
        
        Args:
            data_dir: Directory to store training data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for each component
        for component in self.DRUM_COMPONENTS:
            (self.data_dir / component).mkdir(exist_ok=True)
        
        self.metadata_file = self.data_dir / "metadata.json"
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load metadata from disk."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {"samples": [], "version": "1.0.0"}
    
    def _save_metadata(self):
        """Save metadata to disk."""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def add_sample(
        self,
        audio_path: str,
        onset_time: float,
        component: str,
        source: str = "manual",
        window_ms: float = 100.0
    ) -> Optional[str]:
        """
        Extract and save a drum sample.
        
        Args:
            audio_path: Path to source audio file
            onset_time: Time of drum hit in seconds
            component: Drum component label
            source: Source of the sample (e.g., "manual", "auto")
            window_ms: Window size in milliseconds
            
        Returns:
            Sample ID if successful, None otherwise
        """
        if component not in self.DRUM_COMPONENTS:
            print(f"Error: Invalid component '{component}'")
            return None
        
        try:
            # Load audio
            audio, sr = librosa.load(audio_path, sr=44100)
            
            # Extract window around onset
            window_samples = int(window_ms * sr / 1000)
            center = int(onset_time * sr)
            start = max(0, center - window_samples // 4)
            end = min(len(audio), center + window_samples)
            
            if end - start < 10:
                print("Error: Window too short")
                return None
            
            window = audio[start:end]
            
            # Generate unique ID
            sample_id = str(uuid.uuid4())
            
            # Save audio sample
            sample_path = self.data_dir / component / f"{sample_id}.wav"
            sf.write(sample_path, window, sr)
            
            # Add to metadata
            self.metadata["samples"].append({
                "id": sample_id,
                "component": component,
                "source_audio": os.path.basename(audio_path),
                "onset_time": onset_time,
                "window_ms": window_ms,
                "sample_rate": sr,
                "source": source,
                "path": str(sample_path.relative_to(self.data_dir))
            })
            
            self._save_metadata()
            
            print(f"Added sample: {component} ({sample_id})")
            return sample_id
            
        except Exception as e:
            print(f"Error adding sample: {e}")
            return None
    
    def extract_from_beatmap(
        self,
        beatmap_path: str,
        audio_path: str
    ) -> int:
        """
        Extract labeled samples from a beatmap file.
        
        Args:
            beatmap_path: Path to .bsm beatmap file
            audio_path: Path to corresponding audio file
            
        Returns:
            Number of samples extracted
        """
        try:
            # Load beatmap
            with open(beatmap_path, 'r') as f:
                beatmap = json.load(f)
            
            count = 0
            for hit in beatmap.get("hitObjects", []):
                onset_time = hit["time"] / 1000.0  # Convert ms to seconds
                component = hit["component"]
                
                if self.add_sample(
                    audio_path,
                    onset_time,
                    component,
                    source="beatmap"
                ):
                    count += 1
            
            print(f"Extracted {count} samples from {beatmap_path}")
            return count
            
        except Exception as e:
            print(f"Error extracting from beatmap: {e}")
            return 0
    
    def get_statistics(self) -> Dict:
        """Get statistics about collected data."""
        stats = {component: 0 for component in self.DRUM_COMPONENTS}
        
        for sample in self.metadata["samples"]:
            component = sample["component"]
            if component in stats:
                stats[component] += 1
        
        stats["total"] = len(self.metadata["samples"])
        return stats
    
    def export_dataset(self, output_dir: str = "dataset"):
        """
        Export dataset in format ready for training.
        
        Creates:
        - train/ directory with samples
        - val/ directory with samples
        - labels.json with mappings
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        train_dir = output_path / "train"
        val_dir = output_path / "val"
        train_dir.mkdir(exist_ok=True)
        val_dir.mkdir(exist_ok=True)
        
        # Split data 80/20
        samples_by_component = {c: [] for c in self.DRUM_COMPONENTS}
        for sample in self.metadata["samples"]:
            component = sample["component"]
            samples_by_component[component].append(sample)
        
        train_samples = []
        val_samples = []
        
        for component, samples in samples_by_component.items():
            n = len(samples)
            split_idx = int(0.8 * n)
            
            train_samples.extend(samples[:split_idx])
            val_samples.extend(samples[split_idx:])
        
        # Copy files and create labels
        def copy_samples(samples, target_dir):
            labels = []
            for sample in samples:
                src = self.data_dir / sample["path"]
                dst = target_dir / f"{sample['id']}.wav"
                
                if src.exists():
                    import shutil
                    shutil.copy(src, dst)
                    labels.append({
                        "file": f"{sample['id']}.wav",
                        "label": sample["component"],
                        "component_idx": self.DRUM_COMPONENTS.index(sample["component"])
                    })
            
            return labels
        
        train_labels = copy_samples(train_samples, train_dir)
        val_labels = copy_samples(val_samples, val_dir)
        
        # Save labels
        with open(output_path / "train_labels.json", 'w') as f:
            json.dump(train_labels, f, indent=2)
        
        with open(output_path / "val_labels.json", 'w') as f:
            json.dump(val_labels, f, indent=2)
        
        # Save component mapping
        with open(output_path / "components.json", 'w') as f:
            json.dump({
                "components": self.DRUM_COMPONENTS,
                "num_classes": len(self.DRUM_COMPONENTS)
            }, f, indent=2)
        
        print(f"Exported dataset to {output_dir}")
        print(f"Training samples: {len(train_labels)}")
        print(f"Validation samples: {len(val_labels)}")


def main():
    parser = argparse.ArgumentParser(description="Drum Training Data Collector")
    parser.add_argument(
        "--data-dir",
        default="training_data",
        help="Directory to store training data"
    )
    parser.add_argument(
        "--add-sample",
        nargs=3,
        metavar=("AUDIO", "TIME", "COMPONENT"),
        help="Add a single sample: audio_path onset_time component"
    )
    parser.add_argument(
        "--extract-beatmap",
        nargs=2,
        metavar=("BEATMAP", "AUDIO"),
        help="Extract samples from beatmap: beatmap_path audio_path"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show dataset statistics"
    )
    parser.add_argument(
        "--export",
        metavar="OUTPUT_DIR",
        help="Export dataset for training"
    )
    
    args = parser.parse_args()
    
    collector = DrumDataCollector(args.data_dir)
    
    if args.add_sample:
        audio_path, onset_time, component = args.add_sample
        collector.add_sample(audio_path, float(onset_time), component)
    
    elif args.extract_beatmap:
        beatmap_path, audio_path = args.extract_beatmap
        collector.extract_from_beatmap(beatmap_path, audio_path)
    
    elif args.stats:
        stats = collector.get_statistics()
        print("\nDataset Statistics:")
        print("-" * 40)
        for component, count in stats.items():
            if component != "total":
                print(f"{component:15s}: {count:4d} samples")
        print("-" * 40)
        print(f"{'TOTAL':15s}: {stats['total']:4d} samples")
    
    elif args.export:
        collector.export_dataset(args.export)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
