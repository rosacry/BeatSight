"""Summarize surviving provenance into a recovery ledger without opening audio.

Run from the repository root. Evidence directory must contain manifest-counts.json
and source-path-matches.json from the private recovery inventory. Output is new.
Counts describe records, not an assertion of historical download completeness.
"""
import argparse
import hashlib
import json
from pathlib import Path

SOURCES = [
    ('egmd', 'egmd', 'egmd', 'https://magenta.tensorflow.org/datasets/e-gmd', 'aligned drum audio/MIDI'),
    ('groove_midi', 'groove', 'groove', 'https://magenta.tensorflow.org/datasets/groove', 'aligned drum audio/MIDI'),
    ('slakh2100', 'slakh', 'slakh', 'https://www.slakh.com/', 'synthetic multitrack/MIDI; verify per-kit mapping'),
    ('ENST-Drums', 'enst_drums', 'enst_drums', 'https://perso.telecom-paristech.fr/grichard/ENST-drums/', 'acoustic drums and annotations; access approval recovered'),
    ('cambridge', 'cambridge_multitrack', 'cambridge_multitrack', 'https://www.cambridge-mt.com/ms/mtk/', 'multitrack context; stem records are not note labels'),
    ('idmt_smt_drums_v2', 'idmt_smt_drums_v2', 'idmt_smt_drums_v2', 'https://www.idmt.fraunhofer.de/en/publications/datasets/drums.html', 'kick/snare/hi-hat reference audio and labels'),
    ('MedleyDB', 'medleydb', 'medleydb', 'https://medleydb.weebly.com/', 'multitrack context; both versions have recovered access approvals'),
    ('musdb18_hq', 'musdb_hq', 'musdb_hq', 'https://sigsep.github.io/datasets/musdb.html', 'full mixes and stems; not note annotations'),
    ('signaturesounds', 'signaturesounds', 'signaturesounds', 'https://www.signaturesounds.org/', 'sample packs; 15 ZIPs in recovered order, 11 ingested folder names'),
    ('telefunken', 'telefunken_sessions', 'telefunken_sessions', 'https://www.telefunken-elektroakustik.com/multitracks/', 'session stems; not note annotations'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    counts = {r['file']: r for r in json.loads((args.evidence_dir / 'manifest-counts.json').read_text())}
    external_path = args.evidence_dir / 'external-source-verification.json'
    external = {r['dataset']: r for r in json.loads(external_path.read_text())} if external_path.exists() else {}
    full_hash_path = args.evidence_dir / 'external-small-source-full-hashes.json'
    full_hashes = {r['dataset']: r for r in json.loads(full_hash_path.read_text())} if full_hash_path.exists() else {}
    rows = []
    for name, prov, manifest, url, role in SOURCES:
        path = Path('ai-pipeline/training/data/provenance') / (prov + '_provenance.jsonl')
        n = 0
        unique = set()
        hashed = set()
        for line in path.read_text(encoding='utf-8').splitlines():
            record = json.loads(line)
            n += 1
            unique.update(record.get('sample_paths', []))
            hashed.update(x['path'] for x in record.get('hashes', []) if x.get('sha256'))
        events = counts[manifest + '_events.jsonl']
        verification = external.get(name)
        rows.append({
            'dataset': name, 'provenance_rows': n, 'source_path_references': len(unique),
            'paths_with_recorded_hashes': len(hashed), 'manifest_rows': events['rows'],
            'manifest_bytes': events['bytes'], 'manifest_sha256': events['sha256'],
            'provenance_file': path.as_posix(),
            'provenance_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'current_state': 'raw source present on reconnected D drive; see presence and sampled hash results' if verification else 'external drive verification pending',
            'external_verification': {k: v for k, v in verification.items() if k not in ('checks', 'missing', 'zero_bytes')} if verification else None,
            'complete_recorded_hash_check': {k: v for k, v in full_hashes[name].items() if k != 'checks'} if name in full_hashes else None,
            'missing_references': len(verification['missing']) if verification else None,
            'zero_byte_references': len(verification['zero_bytes']) if verification else None,
            'source_page': url, 'role_and_limits': role,
            'license_state': 'consult primary terms and recovered original messages; inherited summaries are not approval evidence',
        })
    result = {
        'as_of_local': '2026-10-14',
        'evidence_basis': 'current surviving records; canonical provenance variants selected once per source',
        'caveats': [
            'Source references are not a full directory listing of the lost drives.',
            'Do not sum duplicate manifest variants or combined manifests as new data.',
            'No exact total of lost bytes or files can be established from these records.',
            'Initial C/E/F negative matches were superseded when the user connected D: Cold_Raw_Data.',
            'Presence and sampled hashes are distinct from a complete integrity check of every file.',
        ],
        'datasets': rows,
        'source_qualified_path_references': sum(r['source_path_references'] for r in rows),
    }
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, indent=2)
        out.write('\n')
    print(json.dumps({'datasets': len(rows), 'source_path_references': result['source_qualified_path_references']}))


if __name__ == '__main__':
    main()
