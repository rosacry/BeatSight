"""Frozen, recovery-only ADT_STR comparison using reviewed native inference code.

No training, scoring-based selection, source edits, resampling overrides or cleanup.
Custom ADT_STR pitches are NOT General MIDI; preserve their explicit semantics.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

from probe_residual_input import acceptance, event_assignments, pool, truth_from
from score_timing import evaluate_timing
from transcribe import sha256

BASE = Path('C:/Users/10ros/BeatSight-Recovery')
PRIOR = BASE / '2026-10-15-adtof-model-audit-01/full-recordings'
COMPONENTS = {
    35: 'kick', 36: 'kick', 37: 'cross_stick', 38: 'snare',
    39: 'hand_clap', 40: 'snare', 41: 'tom_floor', 42: 'hihat_closed',
    43: 'hihat_pedal', 44: 'hihat_open', 45: 'tom_mid', 46: 'crash',
    47: 'tom_high', 48: 'ride', 49: 'china', 50: 'tambourine',
    51: 'splash', 52: 'cowbell', 53: 'vibraslap', 54: 'congas_timbales',
    55: 'shaker', 56: 'whistle', 57: 'guiro', 58: 'claves',
    59: 'cuica', 60: 'triangle',
}


def save(path, value):
    with Path(path).open('x', encoding='utf8') as f:
        json.dump(value, f, indent=2, allow_nan=False); f.write('\n')


def notes_to_chart(notes):
    events = []
    for onset, offset, pitch, velocity in np.asarray(notes).reshape(-1, 4):
        if not np.isfinite([onset, offset, pitch, velocity]).all() or onset < 0:
            raise ValueError('Invalid decoded note')
        if int(pitch) != pitch or int(pitch) not in COMPONENTS:
            raise ValueError(f'Unmapped custom pitch {pitch}; do not guess GM')
        events.append({'time': float(onset) * 1000,
                       'component': COMPONENTS[int(pitch)],
                       'adt_str_custom_pitch': int(pitch), 'velocity': int(velocity)})
    # No same-family merging, confidence filtering, onset shifts or tail trimming.
    return {'hitObjects': sorted(events, key=lambda x: x['time'])}


def token_audit(tokens):
    """Detect when the native zip-based decoder could misassociate token fields."""
    t = [int(x) for x in tokens]
    issues = []
    if not t or t[0] != 2:
        return {'issues': ['missing_BOS'], 'notes': 0, 'has_EOS': False}
    has_eos = 3 in t
    end = t.index(3) if has_eos else len(t)
    body = t[1:end]
    if has_eos and any(x != 3 for x in t[end:]): issues.append('tokens_after_EOS')
    if body == [0] or not body:
        return {'issues': issues, 'notes': 0, 'has_EOS': has_eos}
    if len(body) % 3: issues.append('incomplete_note')
    for i in range(0, len(body) - 2, 3):
        tm, pitch, velocity = body[i:i + 3]
        if not 4 <= tm < 300: issues.append(f'time_at_{i}')
        if pitch - 300 not in COMPONENTS: issues.append(f'pitch_at_{i + 1}')
        if not 400 <= velocity <= 527: issues.append(f'velocity_at_{i + 2}')
    return {'issues': issues, 'notes': len(body) // 3, 'has_EOS': has_eos}


def verify(entries):
    for r in entries:
        if sha256(Path(r['path'])) != r['sha256']:
            raise ValueError(f'Protected file changed: {r["path"]}')


def prepare(root):
    if root.resolve().parent != BASE or root.drive.upper() != 'C:':
        raise ValueError('Use a separate scoped C: recovery root')
    selection = json.loads((root / 'selection.json').read_text())
    prior = json.loads((PRIOR / 'metrics.json').read_text())
    if prior['status'] != 'complete': raise ValueError('Incomplete baseline')
    files = [root / 'selection.json', PRIOR / 'metrics.json', Path(__file__),
             Path(__file__).with_name('score_timing.py'),
             Path(__file__).with_name('probe_residual_input.py'),
             Path(__file__).with_name('evaluate_mdb.py')]
    files += [p for d in ['source', 'checkpoint'] for p in (root / d).rglob('*') if p.is_file()]
    rows = []
    for old in prior['tracks']:
        pred = PRIOR / old['track'] / 'predictions.json'
        if sha256(pred) != old['candidate_prediction_sha256']:
            raise ValueError('Baseline chart hash changed')
        truth = truth_from(Path(old['annotation']))
        chart = json.loads(pred.read_text())
        scores = {ms: {'baseline': evaluate_timing(chart, truth, int(ms) / 1000)} for ms in ['25', '50']}
        assert all(scores[ms]['baseline'] == old['scores'][ms]['candidate'] for ms in scores)
        files += [Path(old['stem']), Path(old['annotation']), pred]
        rows.append({'track': old['track'], 'stem': old['stem'], 'annotation': old['annotation'],
                     'baseline_predictions': str(pred), 'duration_seconds': old['duration_seconds'],
                     'scores': scores})
    protocol = {
        'utc': datetime.now(timezone.utc).isoformat(), 'selection': selection,
        'hypothesis': 'A different synthetic-trained 26-class Transformer may recover the original ADTOF snare/tom misses.',
        'baseline': 'Verified original-parity ADTOF: source frontend, corrected max pooling, primary decoder. F1 .788049 at 50ms.',
        'input': 'Same seven saved mono FLOAT drum stems, no gain changes or new separation. Native torchaudio loader/resampler to 24kHz.',
        'settings': {'device': 'cuda', 'dtype': 'float32', 'threads': 2, 'seed': 0,
                     'batch_size': 8, 'max_length': 512, 'input_sec': 2.56,
                     'sample_rate': 24000, 'decoder': 'native greedy', 'TF32': False},
        'implementation': 'Unmodified pinned native model, resampler, chunker and tokenizer. Strict safetensors load. Instrument model.sample only to save returned token sequences.',
        'mapping': COMPONENTS, 'mapping_note': 'Source custom pitches 35..60, not GM. Side stick and tambourine are OT under existing MDB taxonomy. Preserve simultaneous and duplicate-family notes.',
        'limits': 'MDB was evaluated upstream and informed authors variant recommendation; development only. Synthetic Lakh overlap unknown. Short complete recordings; estimated stems differ from original drum-only test audio. Native torch2.5.1 compatibility execution, not upstream torch2.8 runtime parity.',
        'gate_50ms': {'minimum_pooled_f1_gain': .01, 'maximum_precision_loss': .01,
                      'maximum_track_f1_loss': .02, 'tom_tp_must_not_decrease': True,
                      'maximum_snare_recall_loss': .01},
        'stop_rule': 'One variant, no tuning/sweep. Failed gate ends candidate before m!sa acceptance songs. Uncertain KLEWS and reserved Adapt excluded. Invalid token grammar prevents interpreting affected scores as reliable.',
        'tail_policy': 'Native final zero-padded chunk retained. Predictions beyond recording end remain false positives; no trimming. Audit chunk count, EOS and grammar.',
        'packages': {p: version(p) for p in ['torch', 'torchaudio', 'transformers', 'numpy', 'safetensors', 'pretty-midi']},
        'prior_files': [{'path': str(p.resolve()), 'sha256': sha256(p)} for p in sorted(set(files))],
        'tracks': rows,
    }
    verify(json.loads((root / 'evidence/prior-preservation.json').read_text())['files'])
    save(root / 'protocol.json', protocol)
    print(json.dumps({'prepared_tracks': len(rows), 'protected_hashes': len(protocol['prior_files']),
                      'baseline50': pool(rows, 'baseline', '50')['micro']}), flush=True)


def run(root):
    protocol = json.loads((root / 'protocol.json').read_text())
    verify(protocol['prior_files'])
    out = root / 'full-recordings'; out.mkdir(exist_ok=False)
    save(out / 'started.json', {'utc': datetime.now(timezone.utc).isoformat(),
                              'protocol_sha256': sha256(root / 'protocol.json')})
    os.environ['HF_HOME'] = str(root / 'cache/hf')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root / 'source'))
    import torch
    from safetensors.torch import load_file
    from config import ADTModelConfig
    from model import ADTModel
    from adt_transcriber import ADTTranscriber, save_midi
    from utils.config_utils import load_config
    torch.set_num_threads(2); torch.manual_seed(0); np.random.seed(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True)
    checkpoint = root / 'checkpoint/setting-tau-0.8'
    cfg = load_config(str(checkpoint / 'adt_config.yaml'))
    assert cfg['inference']['batch_size'] == 8 and cfg['inference']['max_length'] == 512
    assert cfg['tokenizer']['ADTOF_mapping'] is False and cfg['tokenizer']['add_velocity'] is True
    model = ADTModel(ADTModelConfig(**json.loads((checkpoint / 'config.json').read_text())))
    state = load_file(str(checkpoint / 'model.safetensors'))
    status = model.load_state_dict(state, strict=True)
    save(out / 'model-load.json', {'strict': True, 'missing': status.missing_keys,
         'unexpected': status.unexpected_keys, 'tensors': len(state),
         'parameters': sum(p.numel() for p in model.parameters()),
         'device': torch.cuda.get_device_name(0), 'torch': torch.__version__})
    transcriber = ADTTranscriber(model, cfg, device='cuda')
    rows = []
    for source_row in protocol['tracks']:
        row = json.loads(json.dumps(source_row))
        started = time.perf_counter(); folder = out / row['track']; folder.mkdir()
        waveform = transcriber._load_audio(row['stem'])
        np.save(folder / 'input-24khz.npy', waveform.cpu().numpy())
        batches = []
        native_sample = model.sample
        def capture_sample(*args, **kwargs):
            tokens = native_sample(*args, **kwargs)
            batches.append(tokens.detach().cpu().numpy())
            return tokens
        model.sample = capture_sample
        try:
            notes = transcriber._transcribe_waveform(waveform)
        finally:
            model.sample = native_sample
        np.save(folder / 'native-notes.npy', notes.numpy())
        # Native MIDI has custom pitches; not a GM export and not used for scoring.
        save_midi(notes.numpy(), folder / 'native-custom-pitches.mid')
        np.savez_compressed(folder / 'native-tokens.npz', **{f'batch_{i}': b for i, b in enumerate(batches)})
        tokens = [t for batch in batches for t in batch]
        audits = [token_audit(t) for t in tokens]
        expected_chunks = (waveform.shape[-1] + transcriber.chunk_samples - 1) // transcriber.chunk_samples
        assert len(tokens) == expected_chunks
        row['token_audit'] = {'chunks': len(tokens), 'expected_chunks': expected_chunks,
            'without_EOS': sum(not a['has_EOS'] for a in audits),
            'invalid_grammar_chunks': [i for i, a in enumerate(audits) if a['issues']],
            'raw_token_notes': sum(a['notes'] for a in audits), 'native_unique_notes': len(notes),
            'last_chunk_real_samples': int(waveform.shape[-1] - (expected_chunks - 1) * transcriber.chunk_samples),
            'chunks_detail': audits}
        save(folder / 'token-audit.json', row['token_audit'])
        chart = notes_to_chart(notes.numpy()); save(folder / 'predictions.json', chart)
        row['custom_pitch_counts'] = dict(Counter(str(h['adt_str_custom_pitch']) for h in chart['hitObjects']))
        row['predictions_beyond_audio'] = sum(h['time'] / 1000 >= row['duration_seconds'] for h in chart['hitObjects'])
        truth = truth_from(Path(row['annotation']))
        for ms in ['25', '50']:
            row['scores'][ms]['candidate'] = evaluate_timing(chart, truth, int(ms) / 1000)
            save(folder / f'events-{ms}ms.json', event_assignments(chart, truth, int(ms) / 1000))
        row['runtime_seconds'] = time.perf_counter() - started
        row['candidate_prediction_sha256'] = sha256(folder / 'predictions.json')
        rows.append(row); save(folder / 'metrics.json', row)
        print(json.dumps({'track': row['track'], 'runtime_seconds': row['runtime_seconds'],
            'candidate50': row['scores']['50']['candidate']['micro'],
            'invalid_chunks': row['token_audit']['invalid_grammar_chunks']}), flush=True)
    pooled = {ms: {arm: pool(rows, arm, ms) for arm in ['baseline', 'candidate']} for ms in ['25', '50']}
    decision = acceptance(pooled['50']['baseline'], pooled['50']['candidate'],
        [r['scores']['50']['candidate']['micro']['f1'] - r['scores']['50']['baseline']['micro']['f1'] for r in rows])
    valid = all(not r['token_audit']['invalid_grammar_chunks'] and not r['token_audit']['without_EOS'] for r in rows)
    decision['native_token_integrity_passes'] = valid
    decision['passes_development_gate'] &= valid
    verify(protocol['prior_files'])
    result = {'status': 'complete', 'protocol_sha256': sha256(root / 'protocol.json'),
              'tracks': rows, 'pooled': pooled, 'decision': decision,
              'protected_hashes_verified_after': len(protocol['prior_files'])}
    save(out / 'metrics.json', result)
    print(json.dumps({'pooled50': {a: pooled['50'][a]['micro'] for a in pooled['50']}, 'decision': decision}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args(); {'prepare': prepare, 'run': run}[args.action](args.root)
