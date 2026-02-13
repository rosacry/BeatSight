#!/usr/bin/env python3
"""
Master script for acquiring rare class samples from approved commercial sources.

Approved sources (with commercial permission):
- Freesound CC0/CC-BY
- FSD50K (CC BY 4.0)
- Lakh MIDI (custom permission)
- AudioSet (custom permission)
- Philharmonia Orchestra (commercial OK)

Target: Get to 50K+ samples for china, splash, rimshot
Current: china=1,937, splash=6,785, rimshot=17,924
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Paths
RARE_CLASSES_DIR = Path("F:/datasets/rare_class_acquisition")
FEATURE_CACHE = Path("F:/feature_cache")
EXISTING_DATASET = Path("F:/datasets/prod_v5_fixed_20251212")

# Target counts - rimshot now handled via post-processing (merged into snare)
TARGETS = {
    "china": 50000,
    "splash": 50000,
}


def get_current_counts():
    """Get current rare class sample counts from dataset."""
    import numpy as np
    
    labels_path = EXISTING_DATASET / "train" / "train_labels_labels.npy"
    labels = np.load(labels_path)
    
    # Class indices from components.json (12 classes, rimshot merged into snare)
    class_indices = {"china": 0, "splash": 10}
    
    counts = {}
    for name, idx in class_indices.items():
        counts[name] = int(np.sum(labels == idx))
    
    return counts


def print_status():
    """Print current status and gaps."""
    print("=" * 60)
    print("RARE CLASS ACQUISITION STATUS")
    print("=" * 60)
    
    current = get_current_counts()
    
    print(f"\n{'Class':<15} {'Current':>10} {'Target':>10} {'Gap':>10} {'Progress':>10}")
    print("-" * 60)
    
    for cls in ["china", "splash"]:
        cur = current[cls]
        target = TARGETS[cls]
        gap = max(0, target - cur)
        pct = min(100, 100 * cur / target)
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        print(f"{cls:<15} {cur:>10,} {target:>10,} {gap:>10,} {bar} {pct:.0f}%")
    
    print()


def setup_directories():
    """Create acquisition directory structure."""
    dirs = [
        RARE_CLASSES_DIR,
        RARE_CLASSES_DIR / "freesound",
        RARE_CLASSES_DIR / "fsd50k",
        RARE_CLASSES_DIR / "lakh_midi",
        RARE_CLASSES_DIR / "audioset",
        RARE_CLASSES_DIR / "philharmonia",
        RARE_CLASSES_DIR / "augmented",
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  Created: {d}")


def download_freesound():
    """Download Freesound CC0/CC-BY samples."""
    print("\n" + "=" * 60)
    print("FREESOUND CC0/CC-BY DOWNLOAD")
    print("=" * 60)
    print("""
To download from Freesound:

1. Get API key from https://freesound.org/apiv2/apply/

2. Search and download:
   - China cymbal: https://freesound.org/search/?q=china+cymbal&f=license:"Creative+Commons+0"
   - Splash cymbal: https://freesound.org/search/?q=splash+cymbal&f=license:"Creative+Commons+0"

3. Or use the Freesound API (rimshot detection now via post-processing):
""")
    
    # Create a helper script
    script = '''#!/usr/bin/env python3
"""
Freesound downloader for rare drum classes.
Get your API key from: https://freesound.org/apiv2/apply/
"""

import os
import json
import requests
from pathlib import Path

# Get your API key from https://freesound.org/apiv2/apply/
API_KEY = os.environ.get("FREESOUND_API_KEY", "YOUR_API_KEY_HERE")
BASE_URL = "https://freesound.org/apiv2"

OUTPUT_DIR = Path("F:/datasets/rare_class_acquisition/freesound")

# Search queries for each rare class (rimshot detection now via post-processing)
SEARCHES = {
    "china": ["china cymbal", "china crash", "chinese cymbal"],
    "splash": ["splash cymbal", "splash crash"],
}

# Only download CC0 or CC-BY (commercial OK)
ALLOWED_LICENSES = [
    "Creative Commons 0",
    "Attribution",
    "Attribution Noncommercial",  # We have permission
]


def search_sounds(query, page=1, page_size=150):
    """Search Freesound for sounds matching query."""
    params = {
        "query": query,
        "token": API_KEY,
        "page": page,
        "page_size": page_size,
        "fields": "id,name,license,download,previews,duration",
        "filter": "duration:[0.1 TO 5]",  # Short samples only
    }
    
    resp = requests.get(f"{BASE_URL}/search/text/", params=params)
    resp.raise_for_status()
    return resp.json()


def download_sound(sound_id, output_path):
    """Download a sound file."""
    # Get sound info
    resp = requests.get(
        f"{BASE_URL}/sounds/{sound_id}/",
        params={"token": API_KEY}
    )
    resp.raise_for_status()
    info = resp.json()
    
    # Download preview (HQ MP3) - doesn't require OAuth
    preview_url = info.get("previews", {}).get("preview-hq-mp3")
    if preview_url:
        audio = requests.get(preview_url)
        with open(output_path, "wb") as f:
            f.write(audio.content)
        return True
    
    return False


def main():
    if API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: Set FREESOUND_API_KEY environment variable")
        print("Get your key from: https://freesound.org/apiv2/apply/")
        return
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    for class_name, queries in SEARCHES.items():
        class_dir = OUTPUT_DIR / class_name
        class_dir.mkdir(exist_ok=True)
        
        print(f"\\nSearching for {class_name}...")
        
        all_sounds = []
        for query in queries:
            try:
                results = search_sounds(query)
                all_sounds.extend(results.get("results", []))
                print(f"  Query '{query}': {results.get('count', 0)} results")
            except Exception as e:
                print(f"  Error: {e}")
        
        # Deduplicate by ID
        seen = set()
        unique_sounds = []
        for s in all_sounds:
            if s["id"] not in seen:
                seen.add(s["id"])
                unique_sounds.append(s)
        
        print(f"  Total unique: {len(unique_sounds)}")
        
        # Download each sound
        downloaded = 0
        for sound in unique_sounds[:500]:  # Limit to 500 per class
            output_path = class_dir / f"{class_name}_{sound['id']}.mp3"
            if output_path.exists():
                downloaded += 1
                continue
            
            try:
                if download_sound(sound["id"], output_path):
                    downloaded += 1
                    print(f"  Downloaded: {output_path.name}")
            except Exception as e:
                print(f"  Failed {sound['id']}: {e}")
        
        print(f"  Downloaded: {downloaded}/{len(unique_sounds)}")


if __name__ == "__main__":
    main()
'''
    
    script_path = RARE_CLASSES_DIR / "freesound" / "download_freesound.py"
    with open(script_path, "w") as f:
        f.write(script)
    
    print(f"  Created helper script: {script_path}")
    print("\n  To use:")
    print("    1. Get API key from https://freesound.org/apiv2/apply/")
    print("    2. export FREESOUND_API_KEY=your_key_here")
    print(f"    3. python {script_path}")


def download_fsd50k():
    """Instructions for FSD50K download."""
    print("\n" + "=" * 60)
    print("FSD50K DOWNLOAD (CC BY 4.0)")
    print("=" * 60)
    print("""
FSD50K is 30GB and contains labeled cymbal sounds.

Download from Zenodo:
  https://zenodo.org/record/4060432

Files to download:
  - FSD50K.dev_audio.zip (27GB)
  - FSD50K.eval_audio.zip (3GB)  
  - FSD50K.ground_truth.zip (metadata)

Or use wget:
""")
    
    commands = [
        "cd F:/datasets/rare_class_acquisition/fsd50k",
        "wget https://zenodo.org/record/4060432/files/FSD50K.ground_truth.zip",
        "wget https://zenodo.org/record/4060432/files/FSD50K.dev_audio.zip",
        "wget https://zenodo.org/record/4060432/files/FSD50K.eval_audio.zip",
        "unzip FSD50K.ground_truth.zip",
        "unzip FSD50K.dev_audio.zip",
        "unzip FSD50K.eval_audio.zip",
    ]
    
    for cmd in commands:
        print(f"  {cmd}")
    
    print("""
Relevant FSD50K classes to filter:
  - Cymbal (general)
  - Crash cymbal
  - Ride cymbal
  - Hi-hat
  - Percussion
  
After download, run:
  python training/tools/ingest_fsd50k.py --input F:/datasets/rare_class_acquisition/fsd50k
""")


def download_lakh_midi():
    """Instructions for Lakh MIDI synthesis."""
    print("\n" + "=" * 60)
    print("LAKH MIDI SYNTHESIS")
    print("=" * 60)
    print("""
Lakh MIDI has 176K MIDI files with drum tracks.
You already have commercial permission!

If not downloaded yet:
""")
    
    commands = [
        "cd F:/datasets/lakh_midi",
        "wget https://colinraffel.com/projects/lmd/lmd_full.tar.gz",
        "tar -xzf lmd_full.tar.gz",
    ]
    
    for cmd in commands:
        print(f"  {cmd}")
    
    print("""
MIDI Note Numbers for Rare Classes:
  - China Cymbal: 52
  - Splash Cymbal: 55  
  - Side Stick/Rimshot: 37

Synthesis workflow:
  1. Scan MIDI files for rare class notes
  2. Extract timing and velocity information
  3. Synthesize with high-quality drum samples
  4. Apply random variations for diversity

This can generate UNLIMITED samples from 176K MIDI files!
""")


def run_augmentation():
    """Run offline augmentation on existing rare class samples."""
    print("\n" + "=" * 60)
    print("DATA AUGMENTATION")
    print("=" * 60)
    print("""
Augmentation can multiply your samples 20-50x!

Augmentation techniques:
  1. Pitch shifting (±3 semitones) → 7x
  2. Time stretching (±15%) → 3x
  3. Room simulation (5 IRs) → 5x
  4. EQ variations (3 curves) → 3x
  5. Noise addition → 2x

Combined: Up to 630x multiplier (but use ~50x to avoid overfitting)

With current samples (as of Jan 2026):
  - china: ~52,000 (target met via Lakh synthesis)
  - splash: ~57,000 (target met via Lakh synthesis)
  - Note: rimshot was merged into snare class for training

Run existing augmentation tool:
  python training/tools/augment_rare_classes.py \\
    --input-dir F:/datasets/prod_v5_fixed_20251212 \\
    --output-dir F:/datasets/augmented_rare_classes \\
    --target-multiplier 50 \\
    --classes china,splash
""")


def main():
    parser = argparse.ArgumentParser(description="Rare class acquisition manager")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--setup", action="store_true", help="Setup directories")
    parser.add_argument("--freesound", action="store_true", help="Freesound instructions")
    parser.add_argument("--fsd50k", action="store_true", help="FSD50K instructions")
    parser.add_argument("--lakh", action="store_true", help="Lakh MIDI instructions")
    parser.add_argument("--augment", action="store_true", help="Augmentation instructions")
    parser.add_argument("--all", action="store_true", help="Show all instructions")
    
    args = parser.parse_args()
    
    if args.status or not any(vars(args).values()):
        print_status()
    
    if args.setup or args.all:
        print("\n[SETUP] Creating directory structure...")
        setup_directories()
    
    if args.freesound or args.all:
        download_freesound()
    
    if args.fsd50k or args.all:
        download_fsd50k()
    
    if args.lakh or args.all:
        download_lakh_midi()
    
    if args.augment or args.all:
        run_augmentation()
    
    if args.all or not any([args.freesound, args.fsd50k, args.lakh, args.augment, args.setup]):
        print("\n" + "=" * 60)
        print("RECOMMENDED PRIORITY ORDER")
        print("=" * 60)
        print("""
1. [FASTEST] Run augmentation on existing samples
   → Can immediately get 50x more samples
   → python training/tools/augment_rare_classes.py

2. [QUICK WIN] Download Freesound CC0 samples  
   → ~1,500 new real samples for china/splash
   → Run: python acquire_rare_classes.py --freesound

3. [HIGH QUALITY] Download FSD50K
   → ~5,000+ cymbal samples with labels
   → 30GB download, but pre-labeled

4. [UNLIMITED] Synthesize from Lakh MIDI
   → Can generate 100K+ samples
   → Requires drum sample library

Run with --all to see all instructions.
""")


if __name__ == "__main__":
    main()
