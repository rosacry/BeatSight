"""Describe the frozen residual-input result; never tune or regenerate predictions."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from probe_residual_input import FAMILIES, THRESHOLDS
from score_timing import timing_summary
from transcribe import sha256
from transcribe_reference import write_json, reference_preflight


def analyze(root):
    protocol = json.loads((root/'protocol.json').read_text())
    prepared = json.loads((root/'prepared.json').read_text())
    metrics = json.loads((root/'metrics.json').read_text())
    if metrics['status'] != 'complete':
        raise ValueError('Inference incomplete')
    reference = Path(protocol['reference_repo'])
    reference_preflight(reference)
    sys.path.insert(0, str(reference/'src'))
    from adtof_pytorch import PeakPicker
    picker = PeakPicker(thresholds=THRESHOLDS, fps=100)
    labels = ['KD','SD','TT','HH','CY']
    out = root/'analysis'; out.mkdir(exist_ok=False)
    shutil.copy2(Path(__file__), out/Path(__file__).name)
    write_json(out/'protocol.json', {
        'purpose': 'Post-result failure localization only; no parameter or prediction changes.',
        'max_activation_window': '+/-50 ms of each unmatched target at 100 fps',
        'buckets': 'Unsupported OT; raw maximum below fixed threshold; raw reaches threshold but local-mean-subtracted maximum does not; otherwise local-max/grouping/timing/assignment.',
        'limits': 'High raw response is not proof of a true onset. Subtraction bucket does not establish a decoder bug or justify changing thresholds.',
        'code_sha256': sha256(Path(__file__)), 'metrics_sha256': sha256(root/'metrics.json'),
        'decoder_sha256': sha256(reference/'src/adtof_pytorch/post_processing.py')})
    totals = {f: Counter() for f in FAMILIES}
    buckets = {a: {f: Counter() for f in FAMILIES} for a in ['baseline','candidate']}
    common_errors = {'baseline': [], 'candidate': []}
    tracks = []
    for row in metrics['tracks']:
        name = row['track']; events = json.loads((root/name/'events-50ms.json').read_text())
        source = next(x for x in prepared['prior_files'] if x['path'].endswith(name+'.activations.npy'))
        if sha256(Path(source['path'])) != source['sha256']:
            raise ValueError('Baseline activations changed')
        changes = {}; track_buckets = {a: {} for a in buckets}
        for f in FAMILIES:
            a = events['baseline'].get(f, {'reference': [], 'unmatched_predictions': []})
            b = events['candidate'].get(f, {'reference': [], 'unmatched_predictions': []})
            gained, lost = [], []
            for u,v in zip(a['reference'],b['reference']):
                assert (u['index'],u['time']) == (v['index'],v['time'])
                if u['matched_prediction'] is None and v['matched_prediction'] is not None: gained.append(u['time'])
                if u['matched_prediction'] is not None and v['matched_prediction'] is None: lost.append(u['time'])
                if u['matched_prediction'] is not None and v['matched_prediction'] is not None:
                    common_errors['baseline'].append(u['matched_prediction']-u['time'])
                    common_errors['candidate'].append(v['matched_prediction']-v['time'])
            delta_fp = len(b['unmatched_predictions'])-len(a['unmatched_predictions'])
            changes[f] = {'gained_reference_times': gained, 'lost_reference_times': lost, 'delta_fp': delta_fp}
            totals[f].update(gained=len(gained), lost=len(lost), delta_fp=delta_fp)
        for arm, path in [('baseline', Path(source['path'])), ('candidate', root/name/'activations.npy')]:
            act = np.load(path)
            if act.ndim == 3 and act.shape[0] == 1: act = act[0]
            if act.ndim != 2 or act.shape[1] != 5 or not np.isfinite(act).all():
                raise ValueError('Invalid activation shape')
            for f in FAMILIES:
                missed = [r for r in events[arm].get(f, {}).get('reference', []) if r['matched_prediction'] is None]
                details = []
                if f != 'OT':
                    i = labels.index(f); processor = picker.processors[i]
                    values = act[:,i].astype(np.float32)
                    processed = np.maximum(0, values-processor._moving_average(values,10,1))
                for target in missed:
                    detail = {'time': target['time']}
                    if f == 'OT':
                        category = 'unsupported_family'
                    else:
                        start = max(0, int(np.ceil((target['time']-.05)*100-1e-9)))
                        end = min(len(act), int(np.floor((target['time']+.05)*100+1e-9))+1)
                        raw_peak, contrast_peak = float(values[start:end].max()), float(processed[start:end].max())
                        category = ('raw_below_threshold' if raw_peak < THRESHOLDS[i] else
                                    'local_mean_subtraction_below_threshold' if contrast_peak < THRESHOLDS[i] else
                                    'local_max_grouping_timing_or_assignment')
                        detail.update(raw_peak=raw_peak, processed_peak=contrast_peak, threshold=THRESHOLDS[i])
                    detail['category'] = category; details.append(detail); buckets[arm][f][category] += 1
                track_buckets[arm][f] = details
        tracks.append({'track': name, 'changes': changes, 'missed_target_activation_audit': track_buckets})
    result = {'family_changes': totals, 'miss_buckets': buckets, 'tracks': tracks,
              'timing_on_common_matched_targets': {a: timing_summary(v) for a,v in common_errors.items()}}
    write_json(out/'failures.json', result)
    fig, axes = plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
    names = [r['track'].removeprefix('MusicDelta_') for r in metrics['tracks']]
    positions = np.arange(len(names))
    for offset, arm, label in [(-.18,'baseline','Saved stereo-separated'),(.18,'candidate','25% residual added')]:
        axes[0].barh(positions+offset,[r['scores']['50'][arm]['micro']['f1'] for r in metrics['tracks']],height=.36,label=label)
    axes[0].set(yticks=positions,yticklabels=names,xlim=(0,1),xlabel='50 ms F1 against existing annotations')
    axes[0].legend(fontsize=8,loc='upper center',bbox_to_anchor=(.5,-.18)); axes[0].invert_yaxis()
    positions = np.arange(5)
    axes[1].bar(positions-.18,[totals[f]['gained']-totals[f]['lost'] for f in FAMILIES[:5]],width=.36,label='Change in true positives')
    axes[1].bar(positions+.18,[totals[f]['delta_fp'] for f in FAMILIES[:5]],width=.36,label='Change in false positives')
    axes[1].set(xticks=positions,xticklabels=FAMILIES[:5],ylabel='Candidate minus saved baseline')
    axes[1].axhline(0,color='black',lw=.6)
    axes[1].legend(fontsize=8,loc='upper center',bbox_to_anchor=(.5,-.18))
    fig.suptitle('Fixed residual-input candidate rejected on development recordings')
    fig.savefig(out/'comparison.png',dpi=150); plt.close(fig)
    print(json.dumps({k:v for k,v in result.items() if k!='tracks'}),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    analyze(parser.parse_args().root.resolve())
