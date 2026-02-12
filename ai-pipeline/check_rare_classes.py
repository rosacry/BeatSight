#!/usr/bin/env python3
"""
Check all raw datasets for rare cymbal classes (china, splash) to ensure 
no data is being missed in the ingestion pipeline.
"""

import mido
from pathlib import Path
import json
from collections import defaultdict

# GM Drum Note Mapping for cymbals
GM_CYMBAL_NOTES = {
    49: 'crash1',
    51: 'ride_bow', 
    52: 'china',      # CRITICAL - this is what we're looking for
    53: 'ride_bell',
    55: 'splash',     # Also rare
    57: 'crash2',
    59: 'ride2'
}

def check_slakh_for_rare_cymbals():
    """Check Slakh2100 MIDI files for china and splash cymbals."""
    print("\n" + "="*60)
    print("SLAKH2100 - Checking for GM China (52) and Splash (55)")
    print("="*60)
    
    slakh_root = Path('E:/data/raw/slakh2100')
    if not slakh_root.exists():
        print(f"ERROR: Slakh not found at {slakh_root}")
        return {}
    
    midi_files = list(slakh_root.glob('**/*.mid'))
    print(f"Found {len(midi_files)} MIDI files")
    
    note_counts = defaultdict(int)
    files_with_china = []
    files_with_splash = []
    
    for i, mf in enumerate(midi_files):
        if i % 500 == 0:
            print(f"Processing {i}/{len(midi_files)}...")
        try:
            mid = mido.MidiFile(mf)
            file_has_china = False
            file_has_splash = False
            
            for track in mid.tracks:
                for msg in track:
                    if msg.type == 'note_on' and msg.velocity > 0:
                        if hasattr(msg, 'channel') and msg.channel == 9:
                            note = msg.note
                            if 49 <= note <= 59:
                                note_counts[note] += 1
                            if note == 52:
                                file_has_china = True
                            if note == 55:
                                file_has_splash = True
            
            if file_has_china:
                files_with_china.append(str(mf))
            if file_has_splash:
                files_with_splash.append(str(mf))
        except Exception as e:
            pass
    
    print("\nCymbal note counts in Slakh:")
    for note in sorted(note_counts.keys()):
        name = GM_CYMBAL_NOTES.get(note, f'unknown_{note}')
        count = note_counts[note]
        marker = " <<<" if note in [52, 55] else ""
        print(f"  Note {note} ({name:10s}): {count:,}{marker}")
    
    print(f"\nFiles with CHINA (52): {len(files_with_china)}")
    for f in files_with_china[:10]:
        print(f"  - {f}")
    if len(files_with_china) > 10:
        print(f"  ... and {len(files_with_china)-10} more")
        
    print(f"\nFiles with SPLASH (55): {len(files_with_splash)}")
    for f in files_with_splash[:10]:
        print(f"  - {f}")
    if len(files_with_splash) > 10:
        print(f"  ... and {len(files_with_splash)-10} more")
    
    return {
        'china_hits': note_counts.get(52, 0),
        'splash_hits': note_counts.get(55, 0),
        'files_with_china': len(files_with_china),
        'files_with_splash': len(files_with_splash)
    }

def check_enst_annotations():
    """Check ENST-Drums annotations for china and splash."""
    print("\n" + "="*60)
    print("ENST-DRUMS - Checking annotation files")
    print("="*60)
    
    enst_root = Path('E:/data/raw/ENST-Drums')
    if not enst_root.exists():
        print(f"ERROR: ENST not found at {enst_root}")
        return {}
    
    # Find all annotation files
    txt_files = list(enst_root.glob('**/*.txt'))
    print(f"Found {len(txt_files)} annotation files")
    
    label_counts = defaultdict(int)
    files_with_china = []
    files_with_splash = []
    
    for tf in txt_files:
        try:
            with open(tf, 'r') as f:
                lines = f.readlines()
            
            file_labels = set()
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 2:
                    label = parts[-1]  # Label is usually last
                    label_counts[label] += 1
                    file_labels.add(label)
            
            # Check for china variants
            china_labels = [l for l in file_labels if 'ch' in l.lower() and 'hh' not in l.lower()]
            if china_labels:
                files_with_china.append((str(tf), china_labels))
            
            # Check for splash
            splash_labels = [l for l in file_labels if 'spl' in l.lower()]
            if splash_labels:
                files_with_splash.append((str(tf), splash_labels))
                
        except Exception as e:
            pass
    
    print("\nAll unique labels found:")
    for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
        marker = ""
        if 'ch' in label.lower() and 'hh' not in label.lower():
            marker = " <<< CHINA?"
        if 'spl' in label.lower():
            marker = " <<< SPLASH?"
        print(f"  {label:10s}: {count:,}{marker}")
    
    print(f"\nFiles with potential CHINA labels: {len(files_with_china)}")
    for f, labels in files_with_china[:10]:
        print(f"  - {f} ({labels})")
        
    print(f"\nFiles with potential SPLASH labels: {len(files_with_splash)}")
    for f, labels in files_with_splash[:10]:
        print(f"  - {f} ({labels})")
    
    # Count specific china/splash hits
    china_hits = sum(label_counts.get(l, 0) for l in label_counts if 'ch' in l.lower() and 'hh' not in l.lower())
    splash_hits = sum(label_counts.get(l, 0) for l in label_counts if 'spl' in l.lower())
    
    return {
        'china_hits': china_hits,
        'splash_hits': splash_hits,
        'files_with_china': len(files_with_china),
        'files_with_splash': len(files_with_splash)
    }

def check_manifest_coverage():
    """Check current manifests for china/splash counts."""
    print("\n" + "="*60)
    print("CURRENT MANIFEST COVERAGE")
    print("="*60)
    
    manifest_dir = Path('c:/github/BeatSight/ai-pipeline/training/data/manifests')
    
    for manifest_file in sorted(manifest_dir.glob('*.jsonl')):
        print(f"\n{manifest_file.name}:")
        china_count = 0
        splash_count = 0
        total = 0
        
        with open(manifest_file, 'r') as f:
            for line in f:
                try:
                    item = json.loads(line)
                    total += 1
                    labels = item.get('labels', {})
                    if labels.get('china'):
                        china_count += len(labels['china'])
                    if labels.get('splash'):
                        splash_count += len(labels['splash'])
                except:
                    pass
        
        print(f"  Total clips: {total:,}")
        print(f"  China hits: {china_count:,}")
        print(f"  Splash hits: {splash_count:,}")

def check_ingest_scripts():
    """Check ingest scripts for proper china/splash mapping."""
    print("\n" + "="*60)
    print("INGEST SCRIPT MAPPING CHECK")
    print("="*60)
    
    scripts = [
        'c:/github/BeatSight/ai-pipeline/training/ingestion/ingest_slakh.py',
        'c:/github/BeatSight/ai-pipeline/training/ingestion/ingest_enst.py',
    ]
    
    for script_path in scripts:
        script = Path(script_path)
        if script.exists():
            print(f"\n{script.name}:")
            with open(script, 'r') as f:
                content = f.read()
            
            # Look for note/label mapping
            if '52' in content or 'china' in content.lower():
                print("  ✓ Contains china mapping")
            else:
                print("  ✗ NO china mapping found!")
                
            if '55' in content or 'splash' in content.lower():
                print("  ✓ Contains splash mapping")
            else:
                print("  ✗ NO splash mapping found!")
        else:
            print(f"\n{script_path}: NOT FOUND")

if __name__ == '__main__':
    print("="*60)
    print("RARE CLASS DATA VERIFICATION")
    print("Checking E:/data/raw for missed china/splash data")
    print("="*60)
    
    results = {}
    
    # Check Slakh
    results['slakh'] = check_slakh_for_rare_cymbals()
    
    # Check ENST
    results['enst'] = check_enst_annotations()
    
    # Check manifests
    check_manifest_coverage()
    
    # Check ingest scripts
    check_ingest_scripts()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    total_china = results.get('slakh', {}).get('china_hits', 0) + results.get('enst', {}).get('china_hits', 0)
    total_splash = results.get('slakh', {}).get('splash_hits', 0) + results.get('enst', {}).get('splash_hits', 0)
    
    print(f"\nPotential china hits in raw data: {total_china:,}")
    print(f"Potential splash hits in raw data: {total_splash:,}")
    print("\nCheck if these numbers match your manifest totals!")
