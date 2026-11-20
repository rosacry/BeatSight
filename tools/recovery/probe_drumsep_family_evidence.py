"""Bounded MDX23C source probes and one frozen brush-family diagnostic.

No transcription rule, chart export, suppression, threshold tuning or training.
Native architecture and demix functions are extracted from hash-pinned source;
unrelated training imports are omitted without changing their function bodies.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import soundfile as sf
import torch
import torch.nn as nn
import torch.distributed as dist
from tqdm.auto import tqdm
import yaml

BASE = Path(r"C:\Users\10ros\BeatSight-Recovery")
COMMIT = "6fdad13686bb7e84d029ec66f9dbe76e65c93ebf"
STEMS = ['kick', 'snare', 'toms', 'hh', 'ride', 'crash']
WEIGHT_HASH = 'd2a4aa53eb584d21eead358a4e66d1882ad182911be018f052b5da73be9096d0'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf8'))


def save(p, obj):
    with Path(p).open('x', encoding='utf8', newline='\n') as f:
        json.dump(obj, f, indent=2, allow_nan=False)


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


class Config(dict):
    """Only attribute access and dictionary membership; no config transformations."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


def config_object(obj):
    if isinstance(obj, dict):
        return Config({k: config_object(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [config_object(v) for v in obj]
    return obj


def native(root):
    tree = read(root / 'primary/msst-tree.json')
    assert tree['sha'] == COMMIT and not tree['truncated']
    entries = {e['path']: e for e in tree['tree']}
    for e in read(root / 'primary/source-fetches.json'):
        p = Path(e['path'])
        assert sha(p) == e['sha256']
        data = p.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == entries[e['relative_path']]['sha']
    config_path = root / 'primary/drumsep-config.yaml'
    assert sha(config_path) == '17d1649a227f841165bdb4c11a42082898192a1ea3ceab7e7e0b9293d6589dd6'
    config = config_object(yaml.load(config_path.read_text(), Loader=yaml.FullLoader))
    assert config.training.instruments == STEMS
    source = root / 'primary/msst'
    model_utils = source / 'utils/model_utils.py'
    wanted = {'prefer_target_instrument', 'is_compiled_model', '_get_accumulation_device',
              '_getWindowingArray', 'demix'}
    nodes = [n for n in ast.parse(model_utils.read_text(encoding='utf8')).body
             if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert len(nodes) == len(wanted)
    ns = dict(globals(), ConfigDict=Config)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(model_utils), 'exec'), ns)
    architecture = source / 'models/mdx23c_tfc_tdf_v3.py'
    nodes = ast.parse(architecture.read_text(encoding='utf8')).body
    omitted = [n for n in nodes if isinstance(n, ast.ImportFrom) and n.module == 'utils.model_utils']
    assert len(omitted) == 1 and omitted[0].names[0].name == 'prefer_target_instrument'
    exec(compile(ast.Module(body=[n for n in nodes if n not in omitted], type_ignores=[]),
                 str(architecture), 'exec'), ns)
    return config, ns


def preflight(root):
    config, ns = native(root)
    out = root / 'preflight'
    out.mkdir(exist_ok=False)
    torch.set_num_threads(2)
    checks = []

    class IdentitySix(nn.Module):
        def forward(self, x):
            return torch.stack([x * (i + 1) / 6 for i in range(6)], dim=1)

    rng = np.random.default_rng(0)
    chunk = config.audio.chunk_size
    border = chunk - chunk // config.inference.num_overlap
    lengths = [1, 1024, chunk - 1, chunk, chunk + 1, 2 * border - 1,
               2 * border, 2 * border + 1, round(75.16 * 44100)]
    for length in lengths:
        audio = rng.uniform(-.5, .5, (2, length)).astype(np.float32)
        result = ns['demix'](config, IdentitySix(), audio, 'cpu', 'mdx23c', False)
        assert list(result) == STEMS
        errors = []
        for i, name in enumerate(STEMS):
            assert result[name].shape == audio.shape and np.isfinite(result[name]).all()
            error = float(np.max(np.abs(result[name] - audio * (i + 1) / 6)))
            assert error < 4e-7, (length, name, error)
            errors.append(error)
        checks.append(dict(kind='native_demix_identity', samples=length, max_error=max(errors),
                           start_and_tail_preserved=True))
    stft = ns['STFT'](config.audio)
    for index in [0, chunk // 2, chunk - 1]:
        x = torch.zeros((1, 2, chunk))
        x[:, :, index] = .5
        y = stft.inverse(stft(x))
        assert y.shape == x.shape and torch.isfinite(y).all()
        assert torch.argmax(y.abs(), dim=-1).tolist() == [[index, index]]
        checks.append(dict(kind='native_stft_impulse', samples=chunk, impulse_index=index,
                           peak_indices=torch.argmax(y.abs(), dim=-1).tolist(),
                           max_error=float(torch.max(torch.abs(y - x)))))
    save(out / 'checks.json', dict(check_count=len(checks), checks=checks,
         limitation='Identity tests validate stitching, mapping and coverage, not network quality. STFT drops the omitted Nyquist bin.'))
    print(json.dumps(dict(source_checks=len(checks), outcome='pass')))


def verify_protocol(root):
    p = read(root / 'protocol.json')
    amended = root / 'evidence/runtime-amendment-01.json'
    expected_code = p['code_sha256']
    if amended.exists():
        amendment = read(amended)
        assert amendment['protocol_sha256'] == sha(root / 'protocol.json')
        assert sha(root / 'evidence/probe-before-runtime-fix.py') == p['code_sha256']
        expected_code = amendment['code_sha256']
    assert sha(Path(__file__)) == expected_code
    for e in p['protected']:
        if Path(e['path']).resolve() == Path(__file__).resolve() and amended.exists():
            assert e['sha256'] == p['code_sha256']
            continue
        assert sha(e['path']) == e['sha256'], e['path']
    return p


def separation_directory(root):
    amended = root / 'evidence/runtime-amendment-01.json'
    name = read(amended)['output_directory'] if amended.exists() else 'separated'
    assert name in ['separated', 'separated-02']
    return root / name


def infer(root):
    protocol = verify_protocol(root)
    weights = root / 'weights/drumsep-six.ckpt'
    assert sha(weights) == WEIGHT_HASH and weights.stat().st_size == 437652699
    config, ns = native(root)
    assert config.inference.num_overlap == 4 and config.inference.batch_size == 1
    assert config.training.use_amp is True
    out = separation_directory(root)
    out.mkdir(exist_ok=False)
    torch.set_num_threads(2)
    torch.manual_seed(0)
    np.random.seed(0)
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    device = torch.device('cuda:0')
    torch.cuda.init()
    torch.cuda.reset_peak_memory_stats(device)
    model = ns['TFC_TDF_net'](config)
    state = torch.load(weights, map_location='cpu', weights_only=True)
    assert isinstance(state, dict) and all(isinstance(v, torch.Tensor) for v in state.values())
    result = model.load_state_dict(state, strict=True)
    assert not result.missing_keys and not result.unexpected_keys
    assert set(state) == set(model.state_dict())
    tensor_entries = []
    for key, value in model.state_dict().items():
        assert torch.equal(value.cpu(), state[key]) and torch.isfinite(value).all(), key
        tensor_entries.append(dict(key=key, shape=list(value.shape), dtype=str(value.dtype),
                                   sha256=hashlib.sha256(value.numpy().tobytes()).hexdigest()))
    save(out / 'strict-load.json', dict(tensors=len(state), scalar_values=sum(v.numel() for v in state.values()),
         trainable_parameters=sum(v.numel() for v in model.parameters()), entries=tensor_entries))
    del state
    model.eval().to(device)
    audio, sr = sf.read(root / 'inputs/original-component-stereo.wav', dtype='float32', always_2d=True)
    assert sr == 44100 and audio.shape == (3314556, 2) and np.isfinite(audio).all()
    started = time.perf_counter()
    predictions = ns['demix'](config, model, audio.T.copy(), device, 'mdx23c', True)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    outputs = []
    for name in STEMS:
        arr = predictions[name]
        assert arr.shape == (2, len(audio)) and np.isfinite(arr).all()
        p = out / (name + '.wav')
        sf.write(p, arr.T, sr, subtype='FLOAT')
        back, br = sf.read(p, dtype='float32', always_2d=True)
        assert br == sr and np.array_equal(back, arr.T)
        outputs.append(dict(stem=name, path=str(p), sha256=sha(p), frames=len(audio),
                            peak=float(np.abs(arr).max()), rms=float(np.sqrt(np.mean(arr.astype(np.float64) ** 2)))))
    save(out / 'completed.json', dict(protocol_sha256=sha(root / 'protocol.json'), outputs=outputs,
         seconds=elapsed, peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(device),
         peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved(device),
         native_code_revision=COMMIT, gain='fixed previous mixture-component gain; no normalization',
         settings=protocol['settings'], no_chart_transcription=True))
    print(json.dumps(dict(seconds=elapsed, output_frames=len(audio), stems=6)))


def feature_values(stems, seconds, sr):
    # Exactly 50ms beginning at the existing ADTOF event, clipped at track end.
    first = int(round(seconds * sr))
    last = min(first + int(round(.05 * sr)), len(stems['snare']))
    assert 0 <= first < last
    energies = {k: float(np.mean(v[first:last].astype(np.float64) ** 2)) for k, v in stems.items()}
    score = float(10 * np.log10((energies['snare'] + 1e-12) / (energies['hh'] + 1e-12)))
    return dict(start_frame=first, stop_frame=last, energies=energies, sd_over_hh_db=score)


def score(root):
    p = verify_protocol(root)
    completed = read(separation_directory(root) / 'completed.json')
    assert completed['protocol_sha256'] == sha(root / 'protocol.json')
    stems = {}
    for e in completed['outputs']:
        assert sha(e['path']) == e['sha256']
        stems[e['stem']], sr = sf.read(e['path'], dtype='float32', always_2d=True)
        assert sr == 44100
    from probe_residual_input import event_assignments, truth_from
    truth = truth_from(Path(p['reference']))
    predictions = read(p['predictions'])
    matches = event_assignments(predictions, truth, .05)
    assert matches == read(p['cached_assignments'])['adtof']
    out = root / 'family-evidence'
    out.mkdir(exist_ok=False)
    save(out / 'baseline-assignments.json', matches)
    # Assignment format is checked rather than guessed by the prepared protocol.
    hh = matches['HH']
    positive_times = p['positive_false_hh_near_sd_seconds']
    negative_times = p['negative_matched_hh_seconds']
    assert negative_times == sorted(r['matched_prediction'] for r in hh['reference']
                                    if r['matched_prediction'] is not None)
    assert all(t in hh['unmatched_predictions'] for t in positive_times)
    all_hh = [h['time'] / 1000 for h in predictions['hitObjects'] if h['component'] == 'hihat']
    rows = []
    for t in all_hh:
        feature = feature_values(stems, t, sr)
        group = 'false_hh_near_sd' if t in positive_times else 'matched_hh' if t in negative_times else 'other_false_hh'
        near = {f: [float(x) for x in times if abs(x - t) <= .05 + 1e-12] for f, times in truth.items()}
        rows.append(dict(time_seconds=t, group=group, source_references_within50ms=near, **feature))
    pos = np.array([r['sd_over_hh_db'] for r in rows if r['group'] == 'false_hh_near_sd'])
    neg = np.array([r['sd_over_hh_db'] for r in rows if r['group'] == 'matched_hh'])
    assert len(pos) == len(positive_times) >= 10 and len(neg) == len(negative_times) >= 10
    pairs = pos[:, None] - neg[None, :]
    auc = float(np.mean((pairs > 0) + .5 * (pairs == 0)))
    def describe(a):
        return dict(count=len(a), min=float(a.min()), median=float(np.median(a)), max=float(a.max()),
                    positive_db=int(np.sum(a > 0)), quartiles=np.quantile(a, [.25, .75]).tolist())
    gates = dict(auroc_at_least_point8=auc >= .8,
                 false_hh_sd_median_above_zero=float(np.median(pos)) > 0,
                 true_hh_median_below_zero=float(np.median(neg)) < 0)
    save(out / 'events.json', rows)
    save(out / 'metrics.json', dict(feature='10log10((50ms stereo snare mean-square +1e-12)/(HH mean-square+1e-12))',
         auroc=auc, false_hh_near_sd=describe(pos), matched_hh=describe(neg), gates=gates,
         passes_diagnostic_gate=all(gates.values()),
         interpretation='Reference-conditioned diagnostic; no events added/removed/relabeled. Not a transcription F1 or held-out result.'))
    print(json.dumps(dict(positive=len(pos), negative=len(neg), auroc=auc, gates=gates)))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'infer', 'score'])
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    assert root.parent == BASE.resolve() and root.is_dir()
    {'preflight': preflight, 'infer': infer, 'score': score}[args.action](root)
