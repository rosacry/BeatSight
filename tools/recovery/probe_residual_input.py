"""One frozen residual-audio input contrast on existing MDB development data.

Uses saved stereo-input Demucs stems; no separation, tuning, training or download.
Prepare freezes the protocol and inputs. Run verifies that state before inference.
"""
import argparse
from collections import defaultdict
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np
import soundfile as sf
from scipy.optimize import linear_sum_assignment

from evaluate_adtof import FAMILY_COMPONENTS, REFERENCE_REVISION
from evaluate_mdb import drum_family, scores
from score_timing import evaluate_timing, timing_summary
from transcribe import REPO, sha256
from transcribe_reference import reference_preflight, write_json

ALPHA = .25
FAMILIES = ['KD', 'SD', 'HH', 'TT', 'CY', 'OT']
THRESHOLDS = [.22, .24, .32, .22, .30]


def blend_input(stereo, stem):
    if stereo.ndim != 2 or stereo.shape[0] != 2 or stem.ndim != 1:
        raise ValueError('Expected channel-first stereo mix and mono stem')
    if stereo.shape[1] != len(stem) or not len(stem):
        raise ValueError('Mix and stem timelines differ or are empty')
    if not np.isfinite(stereo).all() or not np.isfinite(stem).all():
        raise ValueError('Nonfinite audio')
    mono = np.mean(stereo, axis=0)
    peak = float(np.max(np.abs(mono)))
    if peak <= 1e-10:
        raise ValueError('Silent mono mix; cannot reconstruct baseline gain')
    # Same operation order as evaluate_stereo.py: scale both channels, then mono.
    normalized_mix = np.mean(stereo / peak, axis=0)
    candidate = stem + np.float32(ALPHA) * (normalized_mix - stem)
    return candidate, peak


def truth_from(path):
    result = defaultdict(list)
    for line in path.read_text().splitlines():
        t, label = line.split()
        if label not in FAMILIES or not np.isfinite(float(t)) or float(t) < 0:
            raise ValueError('Invalid annotation')
        result[label].append(float(t))
    return result


def chart_from_activations(act, picker, labels):
    peaks = picker.pick(act, labels)[0]
    return {'hitObjects': sorted([
        {'time': float(t) * 1000, 'component': FAMILY_COMPONENTS[p]}
        for p, times in peaks.items() for t in times], key=lambda e: e['time'])}


def pool(rows, arm, ms):
    values = [r['scores'][ms][arm] for r in rows]
    counts = {k: sum(v['micro'][k] for v in values) for k in ['tp', 'fp', 'fn']}
    families = {f: scores(**{k: sum(v['by_family'].get(f, {}).get(k, 0) for v in values)
                            for k in ['tp', 'fp', 'fn']}) for f in FAMILIES}
    errors = [e for v in values for f in v['by_family'].values() for e in f['signed_errors_seconds']]
    return {'micro': scores(**counts), 'by_family': families, 'timing': timing_summary(errors)}


def acceptance(baseline, candidate, track_deltas):
    """Frozen development triage only, never an automatic app/default promotion."""
    checks = {
        'pooled_f1_gain_at_least_point01': candidate['micro']['f1'] - baseline['micro']['f1'] >= .01 - 1e-12,
        'precision_loss_at_most_point01': baseline['micro']['precision'] - candidate['micro']['precision'] <= .01 + 1e-12,
        'no_track_f1_loss_over_point02': min(track_deltas) >= -.02 - 1e-12,
        'tom_true_positives_not_lower': candidate['by_family']['TT']['tp'] >= baseline['by_family']['TT']['tp'],
        'snare_recall_loss_at_most_point01': baseline['by_family']['SD']['recall'] - candidate['by_family']['SD']['recall'] <= .01 + 1e-12,
    }
    return {'passes_development_gate': all(checks.values()), 'checks': checks}


def event_assignments(chart, truth, tolerance):
    """Export individual matches/misses using the scorer's assignment objective."""
    predicted = defaultdict(list)
    for hit in chart['hitObjects']:
        predicted[drum_family(hit['component'])].append(hit['time'] / 1000)
    result = {}
    expected = evaluate_timing(chart, truth, tolerance)
    for f in sorted(truth.keys() | predicted.keys()):
        ref, pred = np.sort(truth.get(f, [])), np.sort(predicted[f])
        matched, used_pred = {}, set()
        if len(ref) and len(pred):
            delta = pred[None, :] - ref[:, None]
            valid = np.abs(delta) <= tolerance + 1e-9
            penalty = (len(ref) + 1) * (tolerance + 1)
            costs = np.full((len(ref), len(pred) + len(ref)), penalty)
            costs[:, :len(pred)] = np.where(valid, np.abs(delta), 2 * penalty)
            ri, pi = linear_sum_assignment(costs)
            for i, j in zip(ri, pi):
                if j < len(pred) and valid[i, j]:
                    matched[int(i)] = float(pred[j]); used_pred.add(int(j))
        counts = expected['by_family'][f]
        if (len(matched), len(pred)-len(used_pred), len(ref)-len(matched)) != tuple(counts[k] for k in ['tp','fp','fn']):
            raise ValueError('Event audit disagrees with canonical scorer')
        result[f] = {
            'reference': [{'index': i, 'time': float(t), 'matched_prediction': matched.get(i)} for i, t in enumerate(ref)],
            'unmatched_predictions': [float(t) for i, t in enumerate(pred) if i not in used_pred],
        }
    return result


def prepare(args):
    out = args.output_dir.resolve()
    data, baseline, full_mix = args.dataset.resolve(), args.baseline.resolve(), args.full_mix.resolve()
    if out.drive.upper() != 'C:' or any(out.is_relative_to(p) for p in [data, baseline, full_mix]):
        raise ValueError('Use a separate fresh C: experiment directory')
    weights = reference_preflight(args.reference_repo)
    manifest = data / 'sources.json'
    sources = json.loads(manifest.read_text())
    old = json.loads((baseline / 'metrics.json').read_text())
    routing = json.loads((full_mix / 'routing-comparison.json').read_text())
    if old['status'] != 'complete' or sha256(manifest) != old['source_manifest_sha256']:
        raise ValueError('Baseline/data provenance differs')
    if sha256(REPO / 'tools/recovery/evaluate_stereo.py') != old['code_sha256']:
        raise ValueError('Baseline source changed; gain reconstruction needs review')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'evidence').mkdir()
    protocol = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'hypothesis': 'Returning a fixed fraction of removed audio may recover missing drum attacks while retaining separation precision.',
        'alpha': ALPHA, 'formula': 'candidate = saved_mono_stem + .25 * (normalized_mono_mix - saved_mono_stem)',
        'normalization': 'Reconstruct the original stereo-separation input gain using its mono peak. No new peak normalization, clipping, time shift or alignment.',
        'selection': 'All seven previously selected MDB Drums++ development recordings. No Clone Hero or user-song inference.',
        'settings': {'thresholds': THRESHOLDS, 'fps': 100, 'seed': 0, 'device': 'cpu', 'threads': 2},
        'acceptance_50ms': {'minimum_pooled_f1_gain': .01, 'maximum_precision_loss': .01,
                            'maximum_any_track_f1_loss': .02, 'tom_tp_must_not_decrease': True,
                            'maximum_snare_recall_loss': .01},
        'stop_rule': 'One alpha, no sweep or threshold tuning. Failure rejects this candidate; passing only warrants separate acceptance-song review, not promotion.',
        'limits': 'Development evidence with unknown training overlap. Short complete recordings are not commercial full songs. Existing six-family annotations retained, including 32 OT targets unsupported by ADTOF.',
        'full_mix_context': 'Previously run raw full-mix predictions are context only; their different gain is not a controlled endpoint for this contrast.',
        'weights_sha256': sha256(weights), 'reference_revision': REFERENCE_REVISION,
        'reference_repo': str(args.reference_repo.resolve()),
        'code_sha256': sha256(Path(__file__)),
        'packages': {p: version(p) for p in ['numpy', 'torch', 'soundfile', 'librosa', 'scipy']},
    }
    write_json(out / 'protocol.json', protocol)
    for path in [Path(__file__), REPO / 'tools/recovery/score_timing.py', REPO / 'tools/recovery/evaluate_stereo.py']:
        shutil.copy2(path, out / 'evidence' / path.name)
    import librosa
    sys.path.insert(0, str(args.reference_repo / 'src'))
    from adtof_pytorch import PeakPicker, FRAME_RNN_THRESHOLDS, LABELS_5
    if list(FRAME_RNN_THRESHOLDS) != THRESHOLDS:
        raise ValueError('Reference thresholds changed')
    files = []
    def record(path, expected=None):
        actual = sha256(path)
        if expected and actual != expected:
            raise ValueError(f'Prior source changed: {path}')
        files.append({'path': str(path), 'sha256': actual})
        return actual
    record(manifest); record(baseline / 'metrics.json'); record(full_mix / 'routing-comparison.json')
    rows = []
    for src in sources['tracks']:
        name = src['track']; old_row = next(r for r in old['tracks'] if r['track'] == name)
        context = next(r for r in routing['tracks'] if r['track'] == name)
        audio, annotations = data / f'{name}_MIX.wav', data / f'{name}_class.txt'
        stem_path, pred_path = baseline / f'{name}.drums.wav', baseline / f'{name}.predictions.json'
        act_path, context_path = baseline / f'{name}.activations.npy', full_mix / f'{name}.predictions.json'
        for p, expected in [(audio, src['audio_sha256']), (annotations, src['annotation_sha256']),
                            (stem_path, old_row['stem_sha256']), (context_path, context['full_mix_prediction_sha256'])]:
            record(p, expected)
        record(pred_path); record(act_path)
        truth = truth_from(annotations)
        if sum(map(len, truth.values())) != src['reference_events']:
            raise ValueError('Annotation count differs')
        chart = json.loads(pred_path.read_text())
        rederived = chart_from_activations(np.load(act_path), PeakPicker(thresholds=THRESHOLDS, fps=100), LABELS_5)
        if rederived != chart:
            raise ValueError('Saved activations do not reproduce baseline predictions')
        y, sr = librosa.load(audio, sr=44100, mono=False)
        stem, stem_sr = sf.read(stem_path, dtype='float32')
        if sr != stem_sr or sr != src['sample_rate'] or y.shape != (src['channels'], src['frames']):
            raise ValueError('Source rate/shape differs')
        candidate, peak = blend_input(y, stem)
        folder = out / name; folder.mkdir()
        candidate_path = folder / 'input.wav'
        sf.write(candidate_path, candidate, sr, subtype='FLOAT')
        reread, written_sr = sf.read(candidate_path, dtype='float32')
        if written_sr != sr or not np.array_equal(reread, candidate):
            raise ValueError('Candidate PCM roundtrip failed')
        row = {'track': name, 'annotation': str(annotations), 'baseline_predictions': str(pred_path),
               'candidate_input_sha256': sha256(candidate_path), 'duration_seconds': len(stem)/sr,
               'mono_peak_divisor': peak, 'candidate_peak': float(np.max(np.abs(candidate))), 'scores': {}}
        for ms in ['25', '50']:
            row['scores'][ms] = {'baseline': evaluate_timing(chart, truth, int(ms)/1000),
                                'raw_full_mix_context': evaluate_timing(json.loads(context_path.read_text()), truth, int(ms)/1000)}
            if row['scores'][ms]['baseline'] != old_row['scores'][ms]['stereo']:
                raise ValueError('Baseline timing/score reproduction failed')
        rows.append(row)
    prepared = {'status': 'prepared', 'protocol_sha256': sha256(out/'protocol.json'), 'prior_files': files,
                'tracks': rows, 'pooled_baseline': {ms: pool(rows, 'baseline', ms) for ms in ['25','50']}}
    write_json(out/'prepared.json', prepared)
    print(json.dumps({'status': 'prepared', 'tracks': len(rows), 'prior_hash_checks': len(files),
                      'baseline_50': prepared['pooled_baseline']['50']['micro']}), flush=True)


def run(args):
    out = args.output_dir.resolve()
    protocol = json.loads((out/'protocol.json').read_text())
    prepared = json.loads((out/'prepared.json').read_text())
    if (sha256(out/'protocol.json') != prepared['protocol_sha256'] or
            sha256(Path(__file__)) != protocol['code_sha256']):
        raise ValueError('Frozen protocol or code changed')
    for entry in prepared['prior_files']:
        if sha256(Path(entry['path'])) != entry['sha256']:
            raise ValueError('Prior artifact changed after prepare')
    weights = reference_preflight(Path(protocol['reference_repo']))
    for row in prepared['tracks']:
        if sha256(out/row['track']/'input.wav') != row['candidate_input_sha256']:
            raise ValueError('Prepared input changed')
    # A second run may not overwrite a partial or completed experiment.
    with (out/'run-started.json').open('x') as marker:
        json.dump({'utc': datetime.now(timezone.utc).isoformat()}, marker)
    import torch
    sys.path.insert(0, str(Path(protocol['reference_repo'])/'src'))
    from adtof_pytorch import transcribe_to_midi, PeakPicker, LABELS_5
    torch.set_num_threads(2)
    result = {'status': 'started', 'protocol_sha256': prepared['protocol_sha256'], 'tracks': []}
    for row in prepared['tracks']:
        folder = out/row['track']; start = time.perf_counter()
        torch.manual_seed(0); np.random.seed(0)
        with (folder/'inference.log').open('x') as log, redirect_stdout(log), redirect_stderr(log):
            act = transcribe_to_midi(folder/'input.wav', folder/'reference.mid', weights=weights, device='cpu', return_activations=True)
        if not np.isfinite(act).all() or any(s in (folder/'inference.log').read_text() for s in ['Missing keys', 'Unexpected keys']):
            raise ValueError('Invalid model load/output')
        np.save(folder/'activations.npy', act)
        chart = chart_from_activations(act, PeakPicker(thresholds=THRESHOLDS, fps=100), LABELS_5)
        write_json(folder/'predictions.json', chart)
        truth = truth_from(Path(row['annotation']))
        baseline = json.loads(Path(row['baseline_predictions']).read_text())
        for ms in ['25','50']:
            row['scores'][ms]['candidate'] = evaluate_timing(chart, truth, int(ms)/1000)
            write_json(folder/f'events-{ms}ms.json', {
                'baseline': event_assignments(baseline, truth, int(ms)/1000),
                'candidate': event_assignments(chart, truth, int(ms)/1000)})
        row['runtime_seconds'] = time.perf_counter()-start
        row['predictions_sha256'] = sha256(folder/'predictions.json')
        result['tracks'].append(row)
        write_json(out/'metrics.json', result)
        print(json.dumps({'track': row['track'], 'baseline_f1': row['scores']['50']['baseline']['micro']['f1'],
                          'candidate_f1': row['scores']['50']['candidate']['micro']['f1']}), flush=True)
    result['pooled'] = {ms: {arm: pool(result['tracks'], arm, ms)
                            for arm in ['baseline','candidate','raw_full_mix_context']} for ms in ['25','50']}
    result['decision'] = acceptance(result['pooled']['50']['baseline'], result['pooled']['50']['candidate'],
        [r['scores']['50']['candidate']['micro']['f1']-r['scores']['50']['baseline']['micro']['f1'] for r in result['tracks']])
    result['status'] = 'complete'
    for entry in prepared['prior_files']:
        if sha256(Path(entry['path'])) != entry['sha256']:
            raise ValueError('Prior artifact changed during experiment')
    result['prior_hashes_unchanged_after_run'] = len(prepared['prior_files'])
    write_json(out/'metrics.json', result)
    print(json.dumps({'pooled': {ms: {a: v['micro'] for a,v in arms.items()} for ms,arms in result['pooled'].items()},
                      'decision': result['decision']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare','run'])
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--dataset', type=Path)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--full-mix', type=Path)
    parser.add_argument('--reference-repo', type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare':
        if any(getattr(args, k) is None for k in ['dataset','baseline','full_mix','reference_repo']):
            parser.error('Prepare needs --dataset, --baseline, --full-mix and --reference-repo')
        prepare(args)
    else:
        run(args)
