"""Helper script to inspect how sitecustomize affects sys.path."""

import sys

print('sitecustomize imported:', 'sitecustomize' in sys.modules)
print('sys.path contents:')
for idx, entry in enumerate(sys.path):
    print(f"  {idx}: {entry!r}")
