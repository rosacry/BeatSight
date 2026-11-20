"""Conditional, frozen original-drum input diagnostic after runtime controls."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import numpy as np
import soundfile as sf

from compare_adt_str import save, verify, notes_to_chart, token_audit
from probe_adt_str_runtime import BASE, OLD, load_native
from probe_residual_input import truth_from, pool, event_assignments
from score_timing import evaluate_timing
from transcribe import sha256


def prepare(root):
    comparison = json.loads((root / 'comparison.json').read_text())
    if not comparison['same_failure_chunks'] or comparison['exact_token_rows'] != comparison['total_rows']:
        raise ValueError('Resolve runtime differences before changing inputs')
    original = BASE / '2026-10-13/diagnostic-mdb-brush-probe'
    provenance = json.loads((original / 'sources.json').read_text())
    verify(provenance['files'])
    old_metrics = json.loads((OLD / 'full-recordings/metrics.json').read_text())
    protected = [Path(__file__), Path(__file__).with_name('probe_adt_str_runtime.py'),
                 root / 'comparison.json', root / 'protocol.json', original / 'sources.json']
    rows = []
    for name in ['MusicDelta_CoolJazz', 'MusicDelta_FreeJazz']:
        old = next(r for r in old_metrics['tracks'] if r['track'] == name)
        drum = original / f'{name}_Drum.wav'; stem = Path(old['stem'])
        a, b = sf.info(drum), sf.info(stem)
        if a.frames != b.frames or a.samplerate != b.samplerate or a.channels != b.channels:
            raise ValueError('Original/stem timeline or channel mismatch')
        annotation = Path(old['annotation'])
        source_tokens = OLD / 'full-recordings' / name / 'native-tokens.npz'
        native_notes = OLD / 'full-recordings' / name / 'native-notes.npy'
        protected += [drum, stem, annotation, native_notes, source_tokens]
        rows.append({'track': name, 'separated': str(stem), 'original': str(drum),
                     'annotation': str(annotation), 'duration_seconds': a.duration,
                     'old_native_notes': str(native_notes), 'old_tokens': str(source_tokens)})
    out = root / 'original-controls'; out.mkdir(exist_ok=False)
    protocol = {'utc': datetime.now(timezone.utc).isoformat(),
        'question': 'Does the same declared-runtime model fail on corresponding original drums, or only estimated stems?',
        'selection': 'Both already-local CoolJazz and FreeJazz original-drum controls, full recordings; unchanged six-family reference annotations.',
        'contrast': 'Declared runtime on saved separated stems versus original drums. No gain normalization, clipping, alignment, source edits or decoding changes.',
        'settings': json.loads((root / 'protocol.json').read_text())['settings'],
        'limits': 'Oracle input, not end-to-end full-mix accuracy. Recording level/processing and separation differ together; cannot attribute differences solely to separator quality. Development/model-selection overlap remains.',
        'stop_rule': 'One paired input contrast, no level/threshold/checkpoint sweep. Results diagnose scope, never replace prior benchmark or user charts.',
        'protected': [{'path': str(p.resolve()), 'sha256': sha256(p)} for p in sorted(set(protected))],
        'tracks': rows}
    save(out / 'protocol.json', protocol)
    print(json.dumps({'prepared_tracks': len(rows), 'arms': ['separated', 'original'],
                      'protected': len(protocol['protected'])}), flush=True)


def run(root):
    out = root / 'original-controls'; p = json.loads((out / 'protocol.json').read_text())
    verify(p['protected'])
    save(out / 'started.json', {'utc': datetime.now(timezone.utc).isoformat(), 'protocol_sha256': sha256(out / 'protocol.json')})
    torch, model, transcriber, versions = load_native(root, 'declared')
    from adt_transcriber import save_midi
    rows = []
    for source in p['tracks']:
        row = {**source, 'scores': {'25': {}, '50': {}}, 'arms': {}}
        for arm in ['separated', 'original']:
            start = time.perf_counter(); folder = out / source['track'] / arm; folder.mkdir(parents=True)
            waveform = transcriber._load_audio(source[arm])
            np.save(folder / 'input-24khz.npy', waveform.cpu().numpy())
            raw = waveform.cpu().numpy()
            audio_stats = {'peak': float(np.max(np.abs(raw))), 'rms': float(np.sqrt(np.mean(raw ** 2))),
                           'samples': raw.shape[-1], 'sample_rate': transcriber.sample_rate}
            batches = []; native_sample = model.sample
            def capture(*args, **kwargs):
                tokens = native_sample(*args, **kwargs)
                batches.append(tokens.detach().cpu().numpy()); return tokens
            model.sample = capture
            try: notes = transcriber._transcribe_waveform(waveform)
            finally: model.sample = native_sample
            values = notes.numpy(); np.save(folder / 'native-notes.npy', values)
            np.savez_compressed(folder / 'native-tokens.npz', **{f'batch_{i}': b for i, b in enumerate(batches)})
            save_midi(values, folder / 'native-custom-pitches.mid')
            tokens = [t for batch in batches for t in batch]
            audits = [token_audit(t) for t in tokens]
            expected = (raw.shape[-1] + transcriber.chunk_samples - 1) // transcriber.chunk_samples
            assert len(tokens) == expected
            details = {'seconds': time.perf_counter() - start, 'audio': audio_stats,
                       'chunks': len(tokens), 'without_EOS': sum(not a['has_EOS'] for a in audits),
                       'invalid_chunks': [i for i, a in enumerate(audits) if a['issues']],
                       'decoded_unique_notes': len(values), 'token_audits': audits}
            if arm == 'separated':
                details['matches_old_native_notes_exactly'] = bool(np.array_equal(values, np.load(source['old_native_notes'])))
                old_tokens = np.load(source['old_tokens'])
                details['matches_all_old_batch_tokens_exactly'] = all(
                    np.array_equal(b, old_tokens[f'batch_{i}']) for i, b in enumerate(batches))
            chart = notes_to_chart(values); save(folder / 'predictions.json', chart)
            details['predictions_beyond_audio'] = sum(h['time'] / 1000 >= source['duration_seconds'] for h in chart['hitObjects'])
            truth = truth_from(Path(source['annotation']))
            for ms in ['25', '50']:
                row['scores'][ms][arm] = evaluate_timing(chart, truth, int(ms) / 1000)
                save(folder / f'events-{ms}ms.json', event_assignments(chart, truth, int(ms) / 1000))
            row['arms'][arm] = details
            save(folder / 'details.json', details)
            print(json.dumps({'track': source['track'], 'arm': arm, 'scores50': row['scores']['50'][arm]['micro'],
                              'without_EOS': details['without_EOS'], 'seconds': details['seconds']}), flush=True)
        rows.append(row); save(out / source['track'] / 'metrics.json', row)
    verify(p['protected'])
    pooled = {ms: {arm: pool(rows, arm, ms) for arm in ['separated', 'original']} for ms in ['25', '50']}
    result = {'status': 'complete', 'protocol_sha256': sha256(out / 'protocol.json'),
              'runtime_versions': versions, 'tracks': rows, 'pooled': pooled}
    save(out / 'metrics.json', result)
    print(json.dumps({'pooled50': {a: v['micro'] for a, v in pooled['50'].items()}}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--root', type=Path, required=True); a = parser.parse_args()
    {'prepare': prepare, 'run': run}[a.action](a.root)
