#!/usr/bin/env python3
"""Fix shard 232 index offsets - they use global indices instead of local."""

import json
from pathlib import Path
import shutil

index_path = Path('F:/feature_cache/train/index.json')
backup_path = Path('F:/feature_cache/train/index.json.bak_synth')

# Restore from backup first (in case previous attempt corrupted it)
if backup_path.exists():
    print('Restoring from backup...')
    shutil.copy(backup_path, index_path)

print('Loading index (this takes ~30 seconds)...')
with open(index_path, encoding='utf-8') as f:
    index = json.load(f)
print(f'Loaded {len(index):,} entries')

# Fix shard 232 entries - convert global idx to local
# Shard 231 has 65536 samples (indices 0-65535)
# Shard 232 has 34120 samples (indices 0-34119)
# But entries were created with global indices continuing from 65536
SHARD_231_SIZE = 65536
SHARD_232_SIZE = 34120

fixed = 0
for key, val in index.items():
    shard_id, sample_idx = val
    if shard_id == 232 and sample_idx >= SHARD_232_SIZE:
        # Convert global index to local (subtract shard 231's size)
        local_idx = sample_idx - SHARD_231_SIZE
        if 0 <= local_idx < SHARD_232_SIZE:
            index[key] = [232, local_idx]
            fixed += 1
        else:
            print(f'WARNING: {key} has invalid index {sample_idx} -> {local_idx}')

print(f'Fixed {fixed:,} entries')

# Verify
s232 = [v[1] for k,v in index.items() if v[0] == 232]
print(f'Shard 232 after fix: {len(s232):,} entries, range {min(s232)}-{max(s232)}')

oob = sum(1 for i in s232 if i >= SHARD_232_SIZE)
if oob > 0:
    print(f'ERROR: Still have {oob} out-of-bounds entries!')
else:
    print('All entries now in valid range!')

print('Saving with UTF-8 encoding...')
with open(index_path, 'w', encoding='utf-8') as f:
    json.dump(index, f)
print(f'Saved {index_path} ({index_path.stat().st_size:,} bytes)')

# Regenerate binary index
print('\nRegenerating binary index...')
import subprocess
subprocess.run([
    'python', 'training/tools/convert_cache_index_to_binary.py',
    '--cache-dir', 'F:/feature_cache/train',
    '--force'
], check=True)

print('\nDone! Restart training now.')
