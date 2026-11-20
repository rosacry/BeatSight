"""Compare already executed, hash-matched full-recording diagnostic predictions."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from evaluate_mdb import scores
from score_timing import evaluate_timing, timing_summary
from transcribe import sha256


def aggregate(rows):
    totals = {key: sum(row['micro'][key] for row in rows) for key in ('tp', 'fp', 'fn')}
    families = sorted({family for row in rows for family in row['by_family']})
    by_family = {}
    all_errors = []
    for family in families:
        selected = [row['by_family'][family] for row in rows if family in row['by_family']]
        errors = [value for row in selected for value in row['signed_errors_seconds']]
        all_errors.extend(errors)
        by_family[family] = {
            **scores(**{key: sum(row[key] for row in selected) for key in ('tp', 'fp', 'fn')}),
            'timing': timing_summary(errors),
        }
    return {'micro': scores(**totals), 'macro_track_f1': sum(r['micro']['f1'] for r in rows) / len(rows),
            'timing': timing_summary(all_errors), 'by_family': by_family}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--legacy-roots', nargs='+', type=Path, required=True)
    parser.add_argument('--reference-roots', nargs='+', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    source_manifest = json.loads((args.dataset / 'sources.json').read_text())
    result = {'dataset': str(args.dataset), 'dataset_manifest_sha256': sha256(args.dataset / 'sources.json'),
              'annotation_revision': source_manifest['annotation_revision'],
              'training_overlap': source_manifest['training_overlap'],
              'status': 'Diagnostic only; no model promotion or held-out accuracy claim',
              'matching': 'Maximum-cardinality, then minimum absolute timing error; per-family; no time shift',
              'tracks': [], 'systems': {}}
    reference_metrics = [json.loads((p / 'metrics.json').read_text()) for p in args.reference_roots]
    configs = {(m['revision'], m['weights_sha256'], json.dumps(m['thresholds'], sort_keys=True),
                m['separate_drums']) for m in reference_metrics}
    assert len(configs) == 1, 'Reference configurations differ'
    legacy_configs = set()
    for source in source_manifest['tracks']:
        track = source['track']
        audio = args.dataset / (track + '_MIX.wav')
        annotations = args.dataset / (track + '_class.txt')
        assert sha256(audio) == source['audio_sha256']
        assert sha256(annotations) == source['annotation_sha256']
        reference = defaultdict(list)
        for line in annotations.read_text().splitlines():
            time, label = line.split()
            reference[label].append(float(time))
        legacy = [p / track / 'chart.bsm' for p in args.legacy_roots if (p / track / 'chart.bsm').is_file()]
        alternative = [p / (track + '.predictions.json') for p in args.reference_roots
                       if (p / (track + '.predictions.json')).is_file()]
        assert len(legacy) == len(alternative) == 1, 'Require exactly one prediction per system/track'
        run = json.loads((legacy[0].parent / 'run.json').read_text())
        assert run['status'] == 'complete' and run['input']['sha256'] == source['audio_sha256']
        legacy_configs.add(json.dumps({key: run[key] for key in ('models', 'settings', 'code_sha256')}, sort_keys=True))
        records = [r for m in reference_metrics for r in m['tracks'] if r['track'] == track]
        assert len(records) == 1 and records[0]['input_sha256'] == source['audio_sha256']
        row = {'track': track, 'audio_sha256': source['audio_sha256'],
               'annotation_sha256': source['annotation_sha256'], 'duration_seconds': source['duration_seconds'],
               'systems': {}}
        for system, prediction in [('legacy', legacy[0]), ('adtof_separated', alternative[0])]:
            chart = json.loads(prediction.read_text())
            row['systems'][system] = {
                'predictions': str(prediction), 'prediction_sha256': sha256(prediction),
                '25ms': evaluate_timing(chart, reference, 0.025),
                '50ms': evaluate_timing(chart, reference, 0.05),
            }
        result['tracks'].append(row)
    assert len(legacy_configs) == 1, 'Legacy settings, models, or code differ across tracks'
    for system in ('legacy', 'adtof_separated'):
        result['systems'][system] = {
            tolerance: aggregate([row['systems'][system][tolerance] for row in result['tracks']])
            for tolerance in ('25ms', '50ms')
        }
    result['legacy_config'] = json.loads(next(iter(legacy_configs)))
    result['reference_config'] = {key: reference_metrics[0][key] for key in
                                  ('source', 'revision', 'weights_sha256', 'thresholds', 'separate_drums')}
    result['scorer_sha256'] = {name: sha256(Path(__file__).with_name(name)) for name in
                             ('compare_diagnostics.py', 'score_timing.py', 'evaluate_mdb.py')}
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result['systems'], indent=2))


if __name__ == '__main__':
    main()
