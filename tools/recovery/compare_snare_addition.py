"""One predeclared cached-output snare addition; never edits app/user charts.

Prepare freezes inputs/code before run. No rule parameters are exposed for tuning.
The merger sees predictions only; reference annotations enter scoring afterwards.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np

from compare_adt_str import BASE, save, verify
from evaluate_mdb import drum_family
from probe_residual_input import acceptance, event_assignments, pool, truth_from
from score_timing import evaluate_timing, timing_summary
from transcribe import sha256

OAF = BASE / '2026-10-15-oaf-drums-comparison-01'
RULE = {
    'name': 'native-snare-chronological-addition-v1',
    'native_pitch': 38,
    'native_onset_threshold_strictly_greater_than': .5,
    'collision_radius_ms_inclusive': 50.0,
    'numeric_epsilon_ms': 1e-6,
    'order': 'Ascending native onset time, then original native event index.',
    'priority': 'All baseline SD events win, including future events. Then earlier accepted native additions win.',
    'collision_scope': 'SD only. Other families never block a snare. Rejected native events never block later events.',
    'preservation': 'Retain every baseline event and its fields exactly; copy accepted native events exactly; stable time sort.',
    'rationale': 'Use the existing 50ms evaluation tolerance as a fixed duplicate window, not a score-selected radius. Native >.5 decisions are already cached. No new confidence filter.',
    'known_risk': 'May reject genuine flams/fast rolls within 50ms, or retain duplicate attacks separated by more than 50ms. Earlier onset is not necessarily the strongest or most accurate.',
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def scoped_root(root):
    root = root.resolve()
    if root.parent != BASE or root.drive.upper() != 'C:':
        raise ValueError('Use a new immediate child of the C: recovery root')
    return root


def add_snares(baseline, native):
    """Pure prediction-only merger; audit decisions retain source event indices."""
    for chart in (baseline, native):
        for hit in chart['hitObjects']:
            if not np.isfinite(hit['time']) or hit['time'] < 0:
                raise ValueError('Nonfinite or negative event time')
    hits = deepcopy(baseline['hitObjects'])
    baseline_sd = [(i, h['time']) for i, h in enumerate(hits)
                   if drum_family(h['component']) == 'SD']
    accepted, audit = [], []
    for i, h in sorted(enumerate(native['hitObjects']), key=lambda x: (x[1]['time'], x[0])):
        if h.get('groove_pitch') != RULE['native_pitch']:
            continue
        if h['component'] != 'snare':
            raise ValueError('Native snare pitch/component mapping changed')
        t = h['time']
        radius = RULE['collision_radius_ms_inclusive'] + RULE['numeric_epsilon_ms']
        old = [(j, s) for j, s in baseline_sd if abs(s - t) <= radius]
        new = [(j, s) for j, s in accepted if abs(s - t) <= radius]
        reason = 'baseline_collision' if old else 'addition_collision' if new else 'accepted'
        audit.append({'native_event_index': i, 'time_ms': t, 'decision': reason,
                      'baseline_blocker_indices': [j for j, _ in old],
                      'addition_blocker_native_indices': [j for j, _ in new]})
        if reason == 'accepted':
            hits.append(deepcopy(h)); accepted.append((i, t))
    result = deepcopy(baseline)
    result['hitObjects'] = sorted(hits, key=lambda h: h['time'])
    return result, audit


def prepare(root):
    root = scoped_root(root)
    if (root / 'protocol.json').exists():
        raise FileExistsError('Protocol already frozen')
    preservation = read(root / 'evidence/prior-preservation.json')
    verify(preservation['files'])
    previous = read(OAF / 'full-recordings/metrics.json')
    assert previous['status'] == 'complete'
    rows, files = [], [OAF / 'protocol.json', OAF / 'full-recordings/metrics.json',
                       root / 'evidence/recovery-verification.json']
    files += [Path(__file__).with_name(n) for n in [
        'compare_snare_addition.py', 'test_snare_addition.py', 'compare_adt_str.py',
        'probe_residual_input.py', 'score_timing.py', 'evaluate_mdb.py', 'transcribe.py']]
    for old in previous['tracks']:
        folder = OAF / 'full-recordings' / old['track']
        native_path = folder / 'predictions.json'
        assert sha256(native_path) == old['prediction_sha256']
        row = {k: old[k] for k in ['track', 'stem', 'annotation', 'baseline_predictions', 'duration_seconds']}
        row['native_predictions'] = str(native_path)
        row['native_outputs'] = str(folder / 'native-outputs.npz')
        row['mix'] = str(Path(old['annotation']).with_name(old['track'] + '_MIX.wav'))
        files += [Path(row[k]) for k in ['stem', 'annotation', 'baseline_predictions', 'native_predictions', 'native_outputs', 'mix']]
        rows.append(row)
    protocol = {
        'utc': datetime.now(timezone.utc).isoformat(), 'rule': RULE,
        'hypothesis': 'Native E-GMD snares separated from baseline snare predictions recover missed hits without removing ADTOF coverage or changing any other family.',
        'selection': 'The same seven previously inspected development recordings; KLEWS, Adapt and m!sa excluded from tuning.',
        'tracks': rows,
        'gate_50ms': read(OAF / 'protocol.json')['gate_50ms'],
        'scoring': 'Existing one-to-one maximum cardinality then minimum absolute error matching at 25/50ms; all reference events retained, including OT. No reference-aware selection.',
        'false_addition_review': 'Export every addition and its match at both tolerances; audit all unmatched additions at 50ms for nearest SD, coincident other families, duplicates and reference reassignment. Provide mix/stem excerpts. No label change from model disagreement.',
        'stop_rule': 'Exactly one rule, no threshold/radius/order sweeps. Failed gates reject it. Passing warrants independent validation with frozen rule and full-song m!sa acceptance before any promotion; no automatic promotion.',
        'limits': 'Repeatedly inspected short development recordings; unknown training overlap. Native E-GMD 8-hit snare grouping does not establish snare/x-stick/clap or brush articulation accuracy. Cached TF2.13 execution is not historical TF1 parity.',
        'protected': [{'path': str(p.resolve()), 'sha256': sha256(p)} for p in sorted(set(files))],
    }
    save(root / 'protocol.json', protocol)
    save(root / 'prepared.json', {'utc': datetime.now(timezone.utc).isoformat(),
         'protocol_sha256': sha256(root / 'protocol.json'), 'tracks': len(rows)})
    print(json.dumps({'status': 'prepared', 'tracks': len(rows), 'protected': len(protocol['protected']), 'rule': RULE}))


def nearest(times, t):
    if not times:
        return None
    s = min(times, key=lambda x: (abs(x-t), x))
    return {'time_seconds': s, 'prediction_minus_reference_ms': (t-s)*1000}


def audit_additions(baseline, native, decisions, truth, assignments, native_outputs):
    """Describe all added hits after scoring, without altering the rule/chart."""
    rows = []
    probs = np.load(native_outputs)['onset_probs']
    old_times = [h['time']/1000 for h in baseline['hitObjects'] if drum_family(h['component']) == 'SD']
    for decision in decisions:
        if decision['decision'] != 'accepted':
            continue
        hit = native['hitObjects'][decision['native_event_index']]; t = hit['time']/1000
        frame = round(t * 44100 / 512)
        assert abs(t - frame*512/44100) < 1e-10
        probability = float(probs[frame, 38-21]); assert probability > .5
        row = {**decision, 'native_frame': frame, 'native_probability': probability,
               'nearest_reference_snare': nearest(truth.get('SD', []), t),
               'nearest_baseline_snare': nearest(old_times, t),
               'other_reference_families_within_50ms': {f: [s for s in ts if abs(s-t) <= .05+1e-9]
                    for f, ts in truth.items() if f != 'SD' and any(abs(s-t) <= .05+1e-9 for s in ts)},
               'matches': {}}
        for ms, arms in assignments.items():
            refs = arms['candidate']['SD']['reference']
            matched = [x for x in refs if x['matched_prediction'] == t]
            assert len(matched) <= 1
            if matched:
                ref = matched[0]
                old = arms['baseline']['SD']['reference'][ref['index']]
                row['matches'][ms] = {'reference_index': ref['index'], 'reference_time': ref['time'],
                    'signed_error_ms': (t-ref['time'])*1000,
                    'previously_matched_by_baseline': old['matched_prediction'] is not None}
            else:
                assert t in arms['candidate']['SD']['unmatched_predictions']
                row['matches'][ms] = None
        rows.append(row)
    return rows


def run(root):
    root = scoped_root(root)
    protocol = read(root / 'protocol.json')
    assert protocol['rule'] == RULE
    assert sha256(root / 'protocol.json') == read(root / 'prepared.json')['protocol_sha256']
    verify(protocol['protected'])
    out = root / 'full-recordings'; out.mkdir(exist_ok=False)
    save(out / 'started.json', {'utc': datetime.now(timezone.utc).isoformat(), 'protocol_sha256': sha256(root / 'protocol.json')})
    previous = read(OAF / 'full-recordings/metrics.json')
    rows, added = [], []
    for spec in protocol['tracks']:
        row = deepcopy(spec); folder = out / row['track']; folder.mkdir()
        baseline, native = read(row['baseline_predictions']), read(row['native_predictions'])
        candidate, decisions = add_snares(baseline, native)
        # Validate event preservation using exact serialized event multiplicities.
        counts = lambda c: Counter(json.dumps(h, sort_keys=True) for h in c['hitObjects'])
        assert not counts(baseline) - counts(candidate)
        assert [h for h in candidate['hitObjects'] if drum_family(h['component']) != 'SD'] == [h for h in baseline['hitObjects'] if drum_family(h['component']) != 'SD']
        save(folder / 'predictions.json', candidate); save(folder / 'decisions.json', decisions)
        truth = truth_from(Path(row['annotation']))
        old = next(x for x in previous['tracks'] if x['track'] == row['track'])
        row['scores'], assignments = {}, {}
        for ms in ['25', '50']:
            tolerance = int(ms)/1000
            row['scores'][ms] = {arm: evaluate_timing(chart, truth, tolerance) for arm, chart in [('baseline', baseline), ('candidate', candidate)]}
            assert row['scores'][ms]['baseline'] == old['scores'][ms]['baseline']
            assignments[ms] = {arm: event_assignments(chart, truth, tolerance) for arm, chart in [('baseline', baseline), ('candidate', candidate)]}
            save(folder / f'events-{ms}ms.json', assignments[ms])
        addition_rows = audit_additions(baseline, native, decisions, truth, assignments, row['native_outputs'])
        save(folder / 'additions.json', addition_rows)
        added.extend(dict(x, track=row['track']) for x in addition_rows)
        row['decisions'] = dict(Counter(x['decision'] for x in decisions))
        row['preservation'] = {'baseline_events_exact': len(baseline['hitObjects']), 'non_snare_events_exact': sum(drum_family(h['component']) != 'SD' for h in baseline['hitObjects'])}
        row['prediction_sha256'] = sha256(folder / 'predictions.json')
        rows.append(row); save(folder / 'metrics.json', row)
        print(json.dumps({'track': row['track'], 'decisions': row['decisions'], 'micro50': row['scores']['50']['candidate']['micro']}), flush=True)
    pooled = {ms: {arm: pool(rows, arm, ms) for arm in ['baseline', 'candidate']} for ms in ['25', '50']}
    decision = acceptance(pooled['50']['baseline'], pooled['50']['candidate'],
        [r['scores']['50']['candidate']['micro']['f1'] - r['scores']['50']['baseline']['micro']['f1'] for r in rows])
    summaries = {ms: {'added': len(added), 'matched_additions': sum(a['matches'][ms] is not None for a in added),
                      'unmatched_additions': sum(a['matches'][ms] is None for a in added),
                      'timing': timing_summary([a['matches'][ms]['signed_error_ms']/1000 for a in added if a['matches'][ms]])} for ms in ['25', '50']}
    verify(protocol['protected'])
    save(out / 'metrics.json', {'status': 'complete', 'protocol_sha256': sha256(root / 'protocol.json'),
         'tracks': rows, 'pooled': pooled, 'decision': decision, 'additions': summaries})
    save(root / 'evidence/false-additions.json', {'scope': 'Reference-unmatched additions, not listening-verified labels. All additions at both tolerances retained per recording.',
         'counts': summaries, 'events': [a for a in added if a['matches']['50'] is None]})
    print(json.dumps({'pooled50': pooled['50']['candidate'], 'decision': decision, 'additions': summaries}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    {'prepare': prepare, 'run': run}[args.action](args.root)
