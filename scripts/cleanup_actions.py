#!/usr/bin/env python3
"""
Cleanup actions based on audit findings.
Run with --dry-run first to see what would happen.
"""

import os
import shutil
import argparse
from pathlib import Path
from datetime import datetime


def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def get_file_size(path):
    try:
        return os.path.getsize(path)
    except:
        return 0


def main():
    parser = argparse.ArgumentParser(description='Cleanup redundant data')
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='Show what would be deleted without actually deleting')
    parser.add_argument('--execute', action='store_true',
                        help='Actually perform deletions')
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    print("=" * 80)
    print("CLEANUP SCRIPT")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'EXECUTE (will delete!)'}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    total_freed = 0
    
    # =========================================================================
    # 1. Delete empty training runs
    # =========================================================================
    print("\n" + "=" * 80)
    print("1. EMPTY TRAINING RUNS (0 bytes)")
    print("=" * 80)
    
    empty_runs = [
        "D:/cold_storage/runs/12class_definitive_phase1",
        "D:/cold_storage/runs/12class_phase2_specaug_focal",
    ]
    
    for run_path in empty_runs:
        p = Path(run_path)
        if p.exists():
            # Verify it's actually empty
            file_count = sum(1 for _ in p.rglob('*') if _.is_file())
            if file_count == 0:
                print(f"  [DELETE] {run_path} (empty)")
                if not dry_run:
                    shutil.rmtree(p)
                    print(f"    -> Deleted")
            else:
                print(f"  [SKIP] {run_path} (has {file_count} files, not empty)")
        else:
            print(f"  [SKIP] {run_path} (doesn't exist)")
    
    # =========================================================================
    # 2. Delete star_drums redundant archives (zip + parts)
    # =========================================================================
    print("\n" + "=" * 80)
    print("2. STAR_DRUMS REDUNDANT ARCHIVES")
    print("   (The FLAC files are already extracted, zip/parts are redundant)")
    print("=" * 80)
    
    star_drums = Path("D:/cold_storage/datasets/star_drums")
    if star_drums.exists():
        # Find zip and part files
        redundant_files = []
        
        for item in star_drums.iterdir():
            if item.is_file():
                if item.suffix == '.zip' or item.name.startswith('STAR_Drums') and '.part-' in item.name:
                    size = get_file_size(item)
                    redundant_files.append((item, size))
        
        if redundant_files:
            print("\nRedundant archive files found:")
            for f, size in redundant_files:
                print(f"  {f.name}: {format_size(size)}")
            
            total_redundant = sum(s for _, s in redundant_files)
            print(f"\n  Total recoverable: {format_size(total_redundant)}")
            total_freed += total_redundant
            
            if not dry_run:
                print("\nDeleting...")
                for f, size in redundant_files:
                    try:
                        f.unlink()
                        print(f"  Deleted: {f.name}")
                    except Exception as e:
                        print(f"  Error deleting {f.name}: {e}")
        else:
            print("  No redundant archive files found")
    
    # =========================================================================
    # 3. Check cambridge references (search manifests)
    # =========================================================================
    print("\n" + "=" * 80)
    print("3. CAMBRIDGE DATASET ANALYSIS (640 GB)")
    print("=" * 80)
    
    cambridge_refs = []
    
    # Search in manifests
    manifest_dir = Path("F:/manifests")
    if manifest_dir.exists():
        print("\nSearching F:/manifests...")
        for manifest in manifest_dir.glob("*.json"):
            try:
                content = manifest.read_text(errors='ignore')
                if 'cambridge' in content.lower():
                    cambridge_refs.append(str(manifest))
            except:
                pass
    
    # Search in ai-pipeline configs (avoiding wandb)
    print("Searching ai-pipeline configs...")
    ai_pipeline = Path("C:/github/BeatSight/ai-pipeline")
    skip_dirs = {'wandb', '__pycache__', '.git', 'node_modules', 'runs'}
    
    for root, dirs, files in os.walk(ai_pipeline):
        # Skip problematic directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        for f in files:
            if f.endswith(('.json', '.yaml', '.yml', '.py')):
                fp = os.path.join(root, f)
                try:
                    with open(fp, 'r', errors='ignore') as file:
                        content = file.read()
                        if 'cambridge' in content.lower():
                            cambridge_refs.append(fp)
                except:
                    pass
    
    # Search in data configs
    print("Searching data configs...")
    data_dir = Path("C:/github/BeatSight/data")
    if data_dir.exists():
        for f in data_dir.rglob("*.json"):
            try:
                content = f.read_text(errors='ignore')
                if 'cambridge' in content.lower():
                    cambridge_refs.append(str(f))
            except:
                pass
    
    if cambridge_refs:
        print(f"\nFound {len(cambridge_refs)} reference(s) to 'cambridge':")
        for ref in cambridge_refs[:20]:
            print(f"  {ref}")
        print("\n  [KEEP] cambridge is still referenced - do not delete")
    else:
        print("\n  No references to 'cambridge' found!")
        print("  This dataset may be unused and could potentially be deleted.")
        print("  However, verify manually before deleting 640 GB of data.")
    
    # =========================================================================
    # 4. Check other raw datasets
    # =========================================================================
    print("\n" + "=" * 80)
    print("4. OTHER RAW DATASETS REFERENCE CHECK")
    print("=" * 80)
    
    raw_datasets = ['egmd', 'slakh2100', 'MedleyDB', 'musdb18_hq', 'telefunken']
    
    for dataset in raw_datasets:
        refs = []
        
        # Quick search in manifests
        if manifest_dir.exists():
            for manifest in manifest_dir.glob("*.json"):
                try:
                    content = manifest.read_text(errors='ignore')
                    if dataset.lower() in content.lower():
                        refs.append(str(manifest))
                except:
                    pass
        
        # Search in pipeline
        for root, dirs, files in os.walk(ai_pipeline):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for f in files:
                if f.endswith(('.json', '.py')):
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, 'r', errors='ignore') as file:
                            content = file.read()
                            if dataset.lower() in content.lower():
                                refs.append(fp)
                    except:
                        pass
        
        if refs:
            print(f"\n  {dataset}: REFERENCED ({len(refs)} refs) - keep")
        else:
            print(f"\n  {dataset}: NO REFERENCES - possibly unused")
    
    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"\nSpace that can be freed immediately:")
    print(f"  Star drums archives: ~336 GB")
    print(f"  Empty runs: ~0 GB")
    print(f"  ─────────────────────")
    print(f"  Total: ~336 GB")
    
    print(f"\nSpace that MAY be freeable (verify first):")
    print(f"  cambridge (if unused): 640 GB")
    print(f"  Other raw datasets: varies")
    
    if dry_run:
        print("\n" + "-" * 80)
        print("This was a DRY RUN. To actually delete, run:")
        print("  python scripts/cleanup_actions.py --execute")
    else:
        print("\n" + "-" * 80)
        print(f"Cleanup complete!")


if __name__ == "__main__":
    main()
