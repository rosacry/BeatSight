"""Quick script to list F: drive contents"""
import os
from pathlib import Path

f_drive = Path("F:/")
print("F:/ contents:")
for item in sorted(f_drive.iterdir()):
    if item.is_dir():
        # Count files in dir
        try:
            files = list(item.iterdir())[:100]
            print(f"  [DIR] {item.name} ({len(files)}+ items)")
        except:
            print(f"  [DIR] {item.name}")
    else:
        print(f"  {item.name}")

# Check multilabel directories specifically
for name in ["multilabel_real", "multilabel_real_v2"]:
    path = f_drive / name
    if path.exists():
        print(f"\n{name}:")
        batches = list(path.glob("batch_*.npz"))
        manifest = path / "manifest.json"
        print(f"  Batch files: {len(batches)}")
        print(f"  Manifest exists: {manifest.exists()}")
        if batches:
            # Check first batch
            import numpy as np
            data = np.load(batches[0])
            print(f"  First batch keys: {list(data.keys())}")
            for k in data.keys():
                print(f"    {k}: shape={data[k].shape}, dtype={data[k].dtype}")
