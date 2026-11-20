"""Frozen native-runtime comparison on saved ADT_STR failure/control batches."""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

from compare_adt_str import save, verify, token_audit
from transcribe import sha256

BASE = Path('C:/Users/10ros/BeatSight-Recovery')
OLD = BASE / '2026-10-15-adt-str-comparison-01'


def batch_audio(waveform, batch_index, chunk_samples=61440, batch_size=8):
    if waveform.ndim != 2 or waveform.shape[0] != 1:
        raise ValueError('Expected saved mono waveform')
    chunks = []
    for i in range(batch_index * batch_size, (batch_index + 1) * batch_size):
        start = i * chunk_samples
        if start >= waveform.shape[1]: break
        a = waveform[0, start:start + chunk_samples]
        chunks.append(np.pad(a, (0, chunk_samples - len(a))))
    if not chunks: raise ValueError('Batch outside waveform')
    return np.stack(chunks)


def trim_eos(tokens):
    values = np.asarray(tokens)
    ends = np.flatnonzero(values == 3)
    return values[:int(ends[0]) + 1] if len(ends) else values


def prepare(root):
    if root.resolve().parent != BASE or root.drive.upper() != 'C:':
        raise ValueError('Use separate scoped C: directory')
    old = json.loads((OLD / 'full-recordings/metrics.json').read_text())
    protected = [Path(__file__), Path(__file__).with_name('compare_adt_str.py'),
                 OLD / 'protocol.json', OLD / 'full-recordings/metrics.json', root / 'runtime-plan.json']
    protected += [Path(e['path']) for e in json.loads((OLD / 'protocol.json').read_text())['prior_files']]
    selections = []
    for row in old['tracks']:
        failed = row['token_audit']['invalid_grammar_chunks']
        indices = sorted(set(i // 8 for i in failed))
        if row['track'] == 'MusicDelta_80sRock': indices = [0]
        if not indices: continue
        folder = OLD / 'full-recordings' / row['track']
        waveform_path = folder / 'input-24khz.npy'
        tokens_path = folder / 'native-tokens.npz'
        protected += [waveform_path, tokens_path]
        audio = np.load(waveform_path); tokens = np.load(tokens_path)
        for index in indices:
            name = f'{row["track"]}-batch{index:02d}'
            x = batch_audio(audio, index)
            expected = tokens[f'batch_{index}']
            assert len(x) == len(expected)
            path = root / 'inputs' / f'{name}.npz'
            np.savez_compressed(path, audio=x, expected_tokens=expected)
            protected.append(path)
            selections.append({'name': name, 'track': row['track'], 'batch_index': index,
                'chunk_indices': list(range(index * 8, index * 8 + len(x))),
                'prior_failed_chunks': [i for i in failed if i // 8 == index],
                'input': str(path), 'rows': len(x)})
    assert sum(len(s['prior_failed_chunks']) for s in selections) == 11
    protocol = {'utc': datetime.now(timezone.utc).isoformat(),
        'question': 'Do the observed malformed/truncated greedy sequences reproduce under the declared native runtime?',
        'selection': 'All eleven failed chunks, their original batch companions, and first 80sRock control batch. Nine batches / 72 chunks. No selection by new scores.',
        'boundary': 'Identical cached float32 24kHz tensors; file decoding and resampling are deliberately outside this test.',
        'source': str(OLD / 'source'), 'checkpoint': str(OLD / 'checkpoint/setting-tau-0.8'),
        'settings': {'seed': 0, 'device': 'cuda', 'dtype': 'float32', 'threads': 2,
                     'batch_size': 8, 'max_length': 512, 'TF32': False, 'deterministic': True},
        'runtimes': {'compat': {'torch': '2.5.1+cu121', 'torchaudio': '2.5.1+cu121', 'transformers': '4.57.3'},
                     'declared': {'torch': '2.8.0+cu128', 'torchaudio': '2.8.0+cu128', 'transformers': '5.3.0'}},
        'controls': 'Compat must reproduce each saved greedy token sequence before cross-runtime interpretation. Compare mel, encoder and logits under first <=64 identical cached-prefix tokens.',
        'numeric_tolerance': {'atol': 1e-5, 'rtol': 1e-4},
        'decision': 'Exact tokens/decoded notes and reproduced failures close this tested runtime explanation. Differences require documenting affected chunks; no automatic score substitution or variant tuning.',
        'conditional_next': 'If eleven failures reproduce, one frozen original-drum CoolJazz/FreeJazz diagnostic in this same declared runtime. This is an input-domain oracle, not full-mix accuracy.',
        'protected': [{'path': str(p.resolve()), 'sha256': sha256(p)} for p in sorted(set(protected))],
        'batches': selections}
    verify(json.loads((root / 'evidence/prior-preservation.json').read_text())['files'])
    save(root / 'protocol.json', protocol)
    print(json.dumps({'batches': len(selections), 'chunks': sum(r['rows'] for r in selections),
                      'prior_failures': 11, 'protected': len(protocol['protected'])}), flush=True)


def load_native(root, runtime):
    p = json.loads((root / 'protocol.json').read_text())
    verify(p['protected'])
    os.environ['HF_HOME'] = str(root / 'runtime-cache/hf')
    os.environ['HF_HUB_OFFLINE'] = '1'; os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    sys.dont_write_bytecode = True
    sys.path.insert(0, p['source'])
    import torch
    from safetensors.torch import load_file
    from config import ADTModelConfig
    from model import ADTModel
    from adt_transcriber import ADTTranscriber
    from utils.config_utils import load_config
    actual = {k: version(k) for k in ['torch', 'torchaudio', 'transformers']}
    assert actual == p['runtimes'][runtime], actual
    torch.set_num_threads(2); torch.manual_seed(0); np.random.seed(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True)
    checkpoint = Path(p['checkpoint'])
    model = ADTModel(ADTModelConfig(**json.loads((checkpoint / 'config.json').read_text())))
    status = model.load_state_dict(load_file(str(checkpoint / 'model.safetensors')), strict=True)
    assert not status.missing_keys and not status.unexpected_keys
    transcriber = ADTTranscriber(model, load_config(str(checkpoint / 'adt_config.yaml')), device='cuda')
    return torch, model, transcriber, actual


def run(root, runtime):
    p = json.loads((root / 'protocol.json').read_text())
    out = root / runtime; out.mkdir(exist_ok=False)
    save(out / 'started.json', {'utc': datetime.now(timezone.utc).isoformat(), 'protocol_sha256': sha256(root / 'protocol.json')})
    torch, model, transcriber, versions = load_native(root, runtime)
    from utils.utils import create_mask_plain
    save(out / 'runtime.json', {'packages': versions, 'python': sys.version,
                               'gpu': torch.cuda.get_device_name(0), 'strict_weight_load': True})
    rows = []
    for row in p['batches']:
        start = time.perf_counter(); data = np.load(row['input'])
        x = torch.from_numpy(data['audio']).to('cuda')
        reference = data['expected_tokens']
        prefix = torch.from_numpy(reference[:, :min(64, reference.shape[1] - 1)]).to('cuda')
        with torch.no_grad():
            mel = model.compute_spectrogram(x)
            enc = model.encoder(model.project_to_mel(mel))
            mask, _ = create_mask_plain(prefix.shape[1], None, x.device)
            logits = model.decoder(prefix, enc, mask, None)
            tokens = model.sample(x, None, None, max_length=512, start_token=2, end_token=3)
        values = tokens.cpu().numpy()
        np.savez_compressed(out / f'{row["name"]}.npz', tokens=values,
            mel=mel.cpu().numpy(), encoder=enc.cpu().numpy(), logits=logits.cpu().numpy())
        exact = [np.array_equal(trim_eos(a), trim_eos(b)) for a, b in zip(reference, values)]
        record = {**row, 'seconds': time.perf_counter() - start,
            'cached_tokens_exact_by_row': exact, 'audits': [token_audit(t) for t in values]}
        rows.append(record); save(out / f'{row["name"]}.json', record)
        print(json.dumps({'runtime': runtime, 'batch': row['name'], 'seconds': record['seconds'],
            'cached_exact_rows': sum(exact), 'without_EOS': sum(not a['has_EOS'] for a in record['audits'])}), flush=True)
        if runtime == 'compat' and not all(exact): raise ValueError('Compat failed saved-output reproduction')
    verify(p['protected'])
    save(out / 'result.json', {'status': 'complete', 'protocol_sha256': sha256(root / 'protocol.json'), 'batches': rows})


def compare(root):
    p = json.loads((root / 'protocol.json').read_text()); verify(p['protected'])
    runs = {a: json.loads((root / a / 'result.json').read_text()) for a in ['compat', 'declared']}
    assert all(r['status'] == 'complete' and r['protocol_sha256'] == sha256(root / 'protocol.json') for r in runs.values())
    rows = []
    for b in p['batches']:
        old = np.load(root / 'compat' / f'{b["name"]}.npz')
        new = np.load(root / 'declared' / f'{b["name"]}.npz')
        native = next(r for r in runs['declared']['batches'] if r['name'] == b['name'])
        stats = {}
        for k in ['mel', 'encoder', 'logits']:
            stats[k] = {'max_abs': float(np.max(np.abs(old[k] - new[k]))),
                        'close': bool(np.allclose(old[k], new[k], **p['numeric_tolerance']))}
        stats['shared_prefix_argmax_exact'] = bool(np.array_equal(old['logits'].argmax(-1), new['logits'].argmax(-1)))
        exact = [bool(np.array_equal(trim_eos(a), trim_eos(c))) for a, c in zip(old['tokens'], new['tokens'])]
        failures = [i for i, audit in zip(b['chunk_indices'], native['audits']) if not audit['has_EOS'] or audit['issues']]
        rows.append({'name': b['name'], 'statistics': stats, 'tokens_exact_by_row': exact,
                     'prior_failures': b['prior_failed_chunks'], 'declared_failures': failures})
    result = {'protocol_sha256': sha256(root / 'protocol.json'), 'batches': rows,
              'compat_reproduces_all_saved_tokens': all(all(b['cached_tokens_exact_by_row']) for b in runs['compat']['batches']),
              'exact_token_rows': sum(sum(r['tokens_exact_by_row']) for r in rows),
              'total_rows': sum(len(r['tokens_exact_by_row']) for r in rows),
              'same_failure_chunks': all(r['prior_failures'] == r['declared_failures'] for r in rows),
              'declared_failure_count': sum(len(r['declared_failures']) for r in rows),
              'max_stage_differences': {k: max(r['statistics'][k]['max_abs'] for r in rows) for k in ['mel', 'encoder', 'logits']},
              'all_stages_close': all(r['statistics'][k]['close'] for r in rows for k in ['mel', 'encoder', 'logits'])}
    save(root / 'comparison.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'batches'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'run', 'compare'])
    parser.add_argument('--root', type=Path, required=True); parser.add_argument('--runtime', choices=['compat', 'declared'])
    a = parser.parse_args()
    if a.action == 'run':
        if not a.runtime: parser.error('--runtime required for run')
        run(a.root, a.runtime)
    else: {'prepare': prepare, 'compare': compare}[a.action](a.root)
