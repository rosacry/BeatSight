#!/usr/bin/env python3
"""
Extract crash and ride_bell drum events from Lakh MIDI files.

Uses multiprocessing for speed.
"""

import json
import pretty_midi
from pathlib import Path
from collections import Counter
import time
import warnings
from multiprocessing import Pool, cpu_count
from functools import partial

# Suppress pretty_midi warnings
warnings.filterwarnings('ignore')

# Target classes and their GM MIDI note numbers
TARGET_NOTES = {
    49: 'crash',      # Crash Cymbal 1
    57: 'crash',      # Crash Cymbal 2
    53: 'ride_bell',  # Ride Bell
}

LAKH_MIDI_DIR = Path("F:/datasets/lakh_midi")
OUTPUT_FILE = Path("F:/datasets/lakh_midi/drum_events_crash_ridebell.jsonl")


def process_midi_file(midi_path_str):
    """Process a single MIDI file and return events."""
    midi_path = Path(midi_path_str)
    events = []
    
    try:
        # Skip very large files
        if midi_path.stat().st_size > 2_000_000:
            return events, 0, 1  # events, errors, skipped
        
        pm = pretty_midi.PrettyMIDI(str(midi_path))
        
        for instrument in pm.instruments:
            if instrument.is_drum:
                for note in instrument.notes:
                    if note.pitch in TARGET_NOTES:
                        events.append({
                            'file': str(midi_path.relative_to(LAKH_MIDI_DIR)),
                            'class': TARGET_NOTES[note.pitch],
                            'note': note.pitch,
                            'velocity': note.velocity,
                            'time': round(note.start, 4),
                        })
        return events, 0, 0
    except:
        return [], 1, 0


def main():
    midi_files = list(LAKH_MIDI_DIR.glob("**/*.mid"))
    print(f"Found {len(midi_files):,} MIDI files")
    print(f"Using {cpu_count()} CPU cores")
    
    class_counts = Counter()
    total_events = 0
    total_errors = 0
    total_skipped = 0
    
    start_time = time.time()
    
    # Convert paths to strings for multiprocessing
    midi_paths = [str(p) for p in midi_files]
    
    with open(OUTPUT_FILE, 'w') as out:
        # Use multiprocessing pool
        with Pool(processes=cpu_count()) as pool:
            # Process in chunks for progress reporting
            chunk_size = 1000
            for i in range(0, len(midi_paths), chunk_size):
                chunk = midi_paths[i:i+chunk_size]
                results = pool.map(process_midi_file, chunk)
                
                # Collect results
                for events, err, skip in results:
                    total_errors += err
                    total_skipped += skip
                    for event in events:
                        out.write(json.dumps(event) + '\n')
                        total_events += 1
                        class_counts[event['class']] += 1
                
                # Progress report
                processed = min(i + chunk_size, len(midi_files))
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (len(midi_files) - processed) / rate / 60 if rate > 0 else 0
                print(f"[{processed:,}/{len(midi_files):,}] crash:{class_counts['crash']:,} "
                      f"ride_bell:{class_counts['ride_bell']:,} "
                      f"err:{total_errors} skip:{total_skipped} "
                      f"rate:{rate:.0f}/s ETA:{eta:.1f}min", flush=True)
    
    print(f"\nDone! Extracted {total_events:,} events to {OUTPUT_FILE}")
    print(f"Class distribution:")
    for cls, count in sorted(class_counts.items(), key=lambda x: -x[1]):
        print(f"  {cls}: {count:,}")
    print(f"Errors: {total_errors:,}, Skipped large: {total_skipped:,}")
    print(f"Errors: {errors:,}, Skipped large: {skipped_large:,}")


if __name__ == '__main__':
    main()
