"""Salvage checksum-named MIDI members from a damaged local Lakh archive.

Original is read-only. All output goes into a new C: directory. Tar paths are
never extracted onto disk; accepted files go into a ZIP with fixed safe names.
Only members whose bytes match the MD5 in their original LMD filename qualify.
"""
import argparse
import collections
import hashlib
import json
import mmap
import re
import shutil
import tarfile
import time
import zipfile
import zlib
from pathlib import Path


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--synthesis-list', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    assert output.drive.upper() == 'C:' and not output.exists()
    assert shutil.disk_usage(output.parent).free > 15_000_000_000
    assert args.source.is_file()
    before = args.source.stat()
    output.mkdir()
    compressed = output / 'original-damaged-lmd_full.tar.gz'
    sha = hashlib.sha256()
    with args.source.open('rb') as source, compressed.open('xb') as copy:
        while block := source.read(8 * 1024 * 1024):
            copy.write(block)
            sha.update(block)
    with compressed.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == sha.hexdigest()
    after = args.source.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    print('Damaged original copied and hash-verified', flush=True)
    result = {'source': str(args.source), 'source_bytes': before.st_size,
              'source_sha256': sha.hexdigest(), 'copy_verified': True}
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
    partial = output / 'partial-inflated.tar'
    inflated = 0
    with compressed.open('rb') as source, partial.open('xb') as target:
        try:
            while block := source.read(1024 * 1024):
                data = inflater.decompress(block)
                inflated += len(data)
                assert inflated < 12_000_000_000, 'Unexpected inflated size'
                target.write(data)
            target.write(inflater.flush())
            result['gzip_reached_verified_end'] = inflater.eof
            result['gzip_trailing_bytes'] = len(inflater.unused_data)
        except zlib.error as exc:
            result.update({'gzip_reached_verified_end': False, 'gzip_error': str(exc)})
    result['partial_tar_bytes'] = partial.stat().st_size
    print('Inflated bytes', result['partial_tar_bytes'], 'verified gzip end',
          result['gzip_reached_verified_end'], flush=True)
    pattern = re.compile(r'lmd_full/([0-9a-f])/([0-9a-f]{32})\.mid')
    rows = []
    rejected = []
    seen = set()
    skipped_blocks = 0
    valid_headers = 0
    last_report = time.monotonic()
    recovered_zip = output / 'checksum-verified-midi.zip'
    with partial.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data, \
            zipfile.ZipFile(recovered_zip, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zipped:
        offset = 0
        while offset + 512 <= len(data):
            header = data[offset:offset + 512]
            try:
                info = tarfile.TarInfo.frombuf(header, 'utf-8', 'surrogateescape')
            except tarfile.HeaderError:
                offset += 512
                skipped_blocks += 1
                continue
            valid_headers += 1
            match = pattern.fullmatch(info.name)
            if match and info.isfile() and 0 < info.size < 20_000_000:
                end = offset + 512 + info.size
                if end <= len(data):
                    body = data[offset + 512:end]
                    observed = hashlib.md5(body).hexdigest()
                    if observed == match.group(2):
                        if info.name not in seen:
                            zipped.writestr(info.name, body)
                            rows.append({'member': info.name, 'bytes': len(body),
                                         'sha256': hashlib.sha256(body).hexdigest(),
                                         'md5_matches_name': True, 'tar_offset': offset,
                                         'midi_header': body.startswith(b'MThd')})
                            seen.add(info.name)
                    else:
                        rejected.append({'name': info.name, 'offset': offset,
                                         'reason': 'filename MD5 mismatch', 'observed_md5': observed})
                else:
                    rejected.append({'name': info.name, 'offset': offset, 'reason': 'truncated body'})
            # Valid tar headers provide a bounded size; invalid areas are searched
            # one aligned block at a time so one damaged header cannot hide all later MIDI.
            if 0 <= info.size < 20_000_000 and offset + 512 + info.size <= len(data):
                offset += 512 + ((info.size + 511) // 512) * 512
            else:
                offset += 512
            if time.monotonic() - last_report > 25:
                print('Verified MIDI', len(rows), 'tar offset', offset, flush=True)
                last_report = time.monotonic()
    save(output / 'midi-manifest.json', rows)
    with zipfile.ZipFile(recovered_zip) as zipped:
        for row in rows:
            with zipped.open(row['member']) as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == row['sha256']
    synth = json.loads(args.synthesis_list.read_text())
    wanted = {Path(r['file']).name for records in synth['files_by_class'].values() for r in records}
    available = {Path(r['member']).name for r in rows}
    result.update({'recovered_files': len(rows), 'zip_entries_verified': len(rows),
                   'recovered_source_bytes': sum(r['bytes'] for r in rows),
                   'zip_bytes': recovered_zip.stat().st_size, 'valid_tar_headers': valid_headers,
                   'skipped_invalid_header_blocks': skipped_blocks, 'rejected_members': rejected,
                   'missing_midi_header': sum(not r['midi_header'] for r in rows),
                   'historical_synthesis_selected_files': len(wanted),
                   'historical_synthesis_selected_recovered': len(wanted & available),
                   'historical_synthesis_selected_missing': len(wanted - available),
                   'caveat': 'A byte-valid original MIDI may still be malformed musically; not all MIDI parsed.'})
    save(output / 'salvage-result.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'rejected_members'}), flush=True)


if __name__ == '__main__':
    main()
