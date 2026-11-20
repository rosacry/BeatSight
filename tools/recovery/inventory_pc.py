"""Read-only drive metadata inventory; never follows reparse points or opens files.

Output is private: filenames may identify unrelated personal files. Use a NEW
output directory outside repositories. No source file is changed or hashed.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import stat
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', action='append', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out.drive.upper() != 'C:':
        parser.error('Recovery metadata output must be on C:, never the lost drive.')
    out.mkdir(parents=True, exist_ok=False)
    db = sqlite3.connect(out / 'files.sqlite')
    db.executescript('''
      CREATE TABLE files(path TEXT PRIMARY KEY, drive TEXT, ext TEXT, size INTEGER,
                         mtime_ns INTEGER, attributes INTEGER);
      CREATE TABLE directories(path TEXT PRIMARY KEY, drive TEXT);
      CREATE TABLE exclusions(path TEXT, reason TEXT, detail TEXT);
    ''')
    counts = Counter()
    roots = {}
    started = datetime.now(timezone.utc).isoformat()
    last = time.monotonic()
    output_key = os.path.normcase(str(out))
    def status(complete=False):
        db.commit()
        result = {'started_utc': started, 'updated_utc': datetime.now(timezone.utc).isoformat(),
                  'complete': complete, 'roots': roots, 'counts': dict(counts),
                  'method': 'os.scandir metadata only, no reparse traversal or content reads'}
        (out / 'status.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result), flush=True)
    for raw_root in args.root:
        root = Path(raw_root).resolve()
        drive = root.drive
        roots[str(root)] = 'scanning'
        stack = [str(root)]
        while stack:
            parent = stack.pop()
            try:
                if os.path.normcase(parent) == output_key:
                    db.execute('INSERT INTO exclusions VALUES (?,?,?)', (parent, 'output-directory', ''))
                    continue
                with os.scandir(parent) as entries:
                    db.execute('INSERT OR IGNORE INTO directories VALUES (?,?)', (parent, drive))
                    counts['directories'] += 1
                    for entry in entries:
                        try:
                            info = entry.stat(follow_symlinks=False)
                            attrs = getattr(info, 'st_file_attributes', 0)
                            if attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT or entry.is_symlink():
                                db.execute('INSERT INTO exclusions VALUES (?,?,?)',
                                           (entry.path, 'reparse-point', str(attrs)))
                                counts['reparse_points'] += 1
                            elif entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
                            else:
                                db.execute('INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?)',
                                           (entry.path, drive, Path(entry.name).suffix.lower(),
                                            info.st_size, info.st_mtime_ns, attrs))
                                counts['files'] += 1
                                counts['bytes_logical'] += info.st_size
                        except OSError as exc:
                            db.execute('INSERT INTO exclusions VALUES (?,?,?)',
                                       (entry.path, type(exc).__name__, str(exc)))
                            counts['errors'] += 1
            except OSError as exc:
                db.execute('INSERT INTO exclusions VALUES (?,?,?)',
                           (parent, type(exc).__name__, str(exc)))
                counts['errors'] += 1
            if time.monotonic() - last > 15:
                status()
                last = time.monotonic()
        roots[str(root)] = 'complete-with-recorded-exclusions'
        status()
    db.execute('CREATE INDEX file_extensions ON files(ext)')
    db.execute('CREATE INDEX file_sizes ON files(size)')
    status(complete=True)
    db.close()


if __name__ == '__main__':
    main()
