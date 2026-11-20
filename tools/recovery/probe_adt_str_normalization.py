"""One source-justified segment normalization contrast; no fitted gain or sweep."""
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import numpy as np

from compare_adt_str import notes_to_chart, save, verify, token_audit
from probe_adt_str_runtime import BASE, OLD, load_native
from probe_residual_input import acceptance, event_assignments, pool, truth_from
from score_timing import evaluate_timing
from transcribe import sha256


def normalized_rows(rows, normalize):
    """Execute primary normalize separately for each nonzero CPU segment."""
    import torch
    if rows.ndim != 2 or not torch.isfinite(rows).all():
        raise ValueError('Expected finite chunk batch')
    output = []; peaks = []
    for row in rows:
        peak = float(row.abs().max()); peaks.append(peak)
        # Explicit silence extension: primary code would divide by zero.
        output.append(normalize(row) if peak > 0 else row.clone())
    return torch.stack(output), peaks


def prepare(root):
    comparison = json.loads((root / 'comparison.json').read_text())
    assert comparison['same_failure_chunks'] and comparison['exact_token_rows'] == 72
    src = OLD / 'source'
    eval_tree = ast.parse((src / 'data_modules/eval_dataset.py').read_text())
    cls = next(n for n in eval_tree.body if isinstance(n, ast.ClassDef) and n.name == 'EvalDataset')
    getitem = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__getitem__')
    norm_assign = [n for n in getitem.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                   and isinstance(n.value.func, ast.Name) and n.value.func.id == 'normalize']
    assert len(norm_assign) == 1 and ast.unparse(norm_assign[0]) == 'audio = normalize(audio)'
    audio_tree = ast.parse((src / 'utils/audio_utils.py').read_text())
    norm = next(n for n in audio_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'normalize')
    assert ast.unparse(norm.body[0]) == 'return wav_seg / wav_seg.abs().max()'
    parser_text = (src / 'data_modules/text_parser.py').read_text()
    assert 'self.segmenter.chunk_audio_and_notes(audio, notes)' in parser_text
    public = (src / 'adt_transcriber.py').read_text()
    assert 'normalize(' not in public
    old = json.loads((OLD / 'full-recordings/metrics.json').read_text())
    protected = [Path(__file__), root / 'comparison.json', root / 'protocol.json']
    protected += [src / n for n in ['data_modules/eval_dataset.py', 'utils/audio_utils.py',
                                    'data_modules/text_parser.py', 'modules/segmenter.py', 'adt_transcriber.py']]
    rows = []
    for oldrow in old['tracks']:
        audio = OLD / 'full-recordings' / oldrow['track'] / 'input-24khz.npy'
        pred = OLD / 'full-recordings' / oldrow['track'] / 'predictions.json'
        protected += [audio, pred, Path(oldrow['annotation'])]
        rows.append({'track': oldrow['track'], 'input': str(audio), 'annotation': oldrow['annotation'],
            'duration_seconds': oldrow['duration_seconds'],
            'scores': {ms: {'baseline': oldrow['scores'][ms]['baseline'],
                            'unnormalized': oldrow['scores'][ms]['candidate']} for ms in ['25', '50']}})
    out = root / 'segment-normalization'; out.mkdir(exist_ok=False)
    protocol = {'utc': datetime.now(timezone.utc).isoformat(),
        'hypothesis': 'The public helper omits the segment peak normalization explicitly applied by the source evaluation loader; this mismatch may cause failures on quiet stems.',
        'source_evidence': {'eval_getitem_normalization': ast.unparse(norm_assign[0]),
            'primary_function': ast.unparse(norm),
            'segmentation': 'MDBDrumTextParser serializes each Segmenter.chunk_audio_and_notes segment as one dataset item. EvalDataset then resamples and normalizes that item.',
            'public_helper': 'Loads/resamples without peak normalization.'},
        'change': 'Run primary utils.audio_utils.normalize on each nonzero CPU float32 2.56s chunk immediately before native inference; preserve zero chunks as explicit finite-silence extension.',
        'constant': 'Identical cached24kHz inputs, model, custom mapping, greedy max512, batch8, seed0, float32, TF32off. Native final padding/deduplication. No annotation filters or score changes.',
        'limit': 'Isolates this source-semantic mismatch; not complete reproduction of upstream evaluation, which also drops notes crossing segment boundaries and can use different padding. All original targets remain.',
        'baseline': 'Original-parity ADTOF for acceptance; unchanged unnormalized ADT_STR for causal input contrast.',
        'gate_50ms': {'minimum_pooled_f1_gain': .01, 'maximum_precision_loss': .01,
                     'maximum_track_f1_loss': .02, 'tom_tp_must_not_decrease': True, 'maximum_snare_recall_loss': .01},
        'stop_rule': 'One source-defined normalization, no gain levels, beam/threshold/variant sweep. Pass only warrants separate full-song acceptance, never app promotion.',
        'protected': [{'path': str(p.resolve()), 'sha256': sha256(p)} for p in sorted(set(protected))],
        'tracks': rows}
    save(out / 'protocol.json', protocol)
    print(json.dumps({'prepared_normalization_tracks': len(rows), 'protected': len(protocol['protected'])}), flush=True)


def run(root):
    out = root / 'segment-normalization'; p = json.loads((out / 'protocol.json').read_text())
    verify(p['protected']); save(out / 'started.json', {'protocol_sha256': sha256(out / 'protocol.json')})
    torch, model, transcriber, versions = load_native(root, 'declared')
    from utils.audio_utils import normalize
    rows = []
    for source in p['tracks']:
        row = json.loads(json.dumps(source)); start = time.perf_counter()
        folder = out / row['track']; folder.mkdir()
        waveform = torch.from_numpy(np.load(row['input'])).to('cuda')
        batches = []; peaks = []; normalized = []; native_sample = model.sample
        def capture(*args, **kwargs):
            assert not args and 'src' in kwargs
            x, q = normalized_rows(kwargs['src'].cpu(), normalize)
            normalized.append(x.numpy()); peaks.extend(q)
            kwargs['src'] = x.to('cuda')
            tokens = native_sample(**kwargs); batches.append(tokens.detach().cpu().numpy()); return tokens
        model.sample = capture
        try: notes = transcriber._transcribe_waveform(waveform)
        finally: model.sample = native_sample
        np.save(folder / 'native-notes.npy', notes.numpy())
        np.savez_compressed(folder / 'normalized-chunks.npz', **{f'batch_{i}': x for i, x in enumerate(normalized)})
        np.savez_compressed(folder / 'native-tokens.npz', **{f'batch_{i}': x for i, x in enumerate(batches)})
        chart = notes_to_chart(notes.numpy()); save(folder / 'predictions.json', chart)
        audits = [token_audit(t) for batch in batches for t in batch]
        row['audit'] = {'chunks': len(audits), 'without_EOS': sum(not a['has_EOS'] for a in audits),
                        'invalid_chunks': [i for i, a in enumerate(audits) if a['issues']],
                        'pre_normalization_peaks': peaks, 'silent_chunks': sum(x == 0 for x in peaks),
                        'token_audits': audits}
        truth = truth_from(Path(row['annotation']))
        for ms in ['25', '50']:
            row['scores'][ms]['candidate'] = evaluate_timing(chart, truth, int(ms) / 1000)
            save(folder / f'events-{ms}ms.json', event_assignments(chart, truth, int(ms) / 1000))
        row['seconds'] = time.perf_counter() - start
        row['prediction_sha256'] = sha256(folder / 'predictions.json')
        save(folder / 'metrics.json', row); rows.append(row)
        print(json.dumps({'track': row['track'], 'seconds': row['seconds'],
            'scores50': row['scores']['50']['candidate']['micro'], 'invalid_chunks': row['audit']['invalid_chunks']}), flush=True)
    pooled = {ms: {arm: pool(rows, arm, ms) for arm in ['baseline', 'unnormalized', 'candidate']} for ms in ['25', '50']}
    decision = acceptance(pooled['50']['baseline'], pooled['50']['candidate'],
        [r['scores']['50']['candidate']['micro']['f1'] - r['scores']['50']['baseline']['micro']['f1'] for r in rows])
    decision['token_integrity'] = all(not r['audit']['invalid_chunks'] and not r['audit']['without_EOS'] for r in rows)
    decision['passes_development_gate'] &= decision['token_integrity']
    verify(p['protected'])
    save(out / 'metrics.json', {'status': 'complete', 'protocol_sha256': sha256(out / 'protocol.json'),
        'runtime': versions, 'tracks': rows, 'pooled': pooled, 'decision': decision})
    print(json.dumps({'pooled50': {a: v['micro'] for a, v in pooled['50'].items()}, 'decision': decision}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--root', type=Path, required=True); a = parser.parse_args()
    {'prepare': prepare, 'run': run}[a.action](a.root)
