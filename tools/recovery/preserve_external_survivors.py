"""Preserve specific inventoried D: survivors in a NEW C: directory.

Reads originals only. Never restores a Recycle Bin entry in place or loads model
pickle data. Archives include source hashes and are read back for verification.
"""
import argparse
import collections
import hashlib
import json
import shutil
import sqlite3
import time
import zipfile
from pathlib import Path


def digest_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def preserve_recycle(evidence, output):
    inventory = evidence / 'external-drive-inventory/files.sqlite'
    with sqlite3.connect(inventory.as_uri() + '?mode=ro', uri=True) as db:
        candidates = db.execute(
            "SELECT path,size FROM files WHERE path LIKE '%$RECYCLE.BIN%' "
            "AND ext='.wav' ORDER BY path"
        ).fetchall()
    rows = []
    classes = collections.Counter()
    last_report = time.monotonic()
    archive = output / 'recycle-training-clips.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as zipped:
        for source_name, expected_size in candidates:
            source = Path(source_name)
            assert source.drive.upper() == 'D:' and source.parts[1] == '$RECYCLE.BIN'
            before = source.stat()
            assert before.st_size == expected_size, source
            content = source.read_bytes()
            after = source.stat()
            assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
            assert len(content) == expected_size
            member = Path(*source.parts[1:]).as_posix()
            sha = hashlib.sha256(content).hexdigest()
            zipped.writestr(member, content)
            label = source.stem.rsplit('__', 1)[-1]
            classes[label] += 1
            rows.append({'source': str(source), 'member': member, 'bytes': len(content),
                         'sha256': sha, 'filename_label': label})
            if time.monotonic() - last_report > 25:
                print(f'Recycle clips preserved: {len(rows)}/{len(candidates)}', flush=True)
                last_report = time.monotonic()
    save_json(output / 'recycle-training-clips.manifest.json', rows)
    checked = 0
    with zipfile.ZipFile(archive) as zipped:
        assert len(zipped.infolist()) == len(rows)
        for row in rows:
            with zipped.open(row['member']) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == row['sha256']
            checked += 1
    result = {'files': len(rows), 'source_bytes': sum(r['bytes'] for r in rows),
              'archive_bytes': archive.stat().st_size, 'verified_entries': checked,
              'filename_classes': dict(classes), 'archive_sha256': digest_file(archive)}
    save_json(output / 'recycle-training-clips.verification.json', result)
    print(json.dumps(result), flush=True)


def preserve_models(evidence, output):
    candidates = json.loads((evidence / 'external-drive-summary.json').read_text())['models']
    prior = json.loads((evidence.parent / 'preservation_hashes.json').read_text())
    known = collections.defaultdict(list)
    for row in prior:
        known[row['sha256']].append(str(evidence.parent / row['path']))
    rows = []
    for candidate in candidates:
        source = Path(candidate['path'])
        assert source.is_relative_to(Path('D:/cold_storage/runs'))
        before = source.stat()
        assert before.st_size == candidate['bytes']
        sha = digest_file(source)
        row = {'source': str(source), 'bytes': before.st_size, 'sha256': sha}
        if sha in known:
            verified = next((p for p in known[sha] if Path(p).is_file()
                             and digest_file(Path(p)) == sha), None)
            assert verified, f'Previously preserved content no longer verifies: {sha}'
            row.update({'state': 'already_preserved_identical_content', 'verified_copy': verified})
        else:
            destination = output / 'models' / source.relative_to('D:/cold_storage/runs')
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open('rb') as src, destination.open('xb') as dst:
                shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
            assert digest_file(destination) == sha
            row.update({'state': 'new_verified_copy', 'verified_copy': str(destination)})
            known[sha].append(str(destination))
        after = source.stat()
        assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
        rows.append(row)
        print(f'Checkpoint {len(rows)}/{len(candidates)}: {row["state"]}', flush=True)
    save_json(output / 'external-checkpoints.manifest.json', rows)
    print(json.dumps({'checkpoints': len(rows), 'states': dict(collections.Counter(r['state'] for r in rows))}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    assert output.drive.upper() == 'C:' and not output.exists(), 'Require a new C: output directory'
    assert shutil.disk_usage(output.parent).free > 8_000_000_000, 'Insufficient preservation space'
    output.mkdir()
    preserve_recycle(args.evidence_dir, output)
    preserve_models(args.evidence_dir, output)


if __name__ == '__main__':
    main()
