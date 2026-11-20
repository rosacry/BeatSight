"""Frozen six-recording isolated HH/snare routing and reconstruction control.

Diagnostic only: unchanged native checkpoint, dry stereo gain1, no note changes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
import time

import numpy as np
import soundfile as sf
import torch

from probe_drumsep_family_evidence import native, read, save, sha, STEMS, WEIGHT_HASH

REPO = Path('C:/github/BeatSight')
BASE = Path('C:/Users/10ros/BeatSight-Recovery')
PREVIOUS = BASE / '2026-10-16-enst-hh-presence-audit-01'
AUDIT = BASE / '2026-10-16-drumsep-audit-01'


def measurement(audio, stems, target):
    """Raw stereo squared-sample sums; no alignment, scale fit or centering."""
    x = np.asarray(audio, dtype=np.float64)
    ys = {name: np.asarray(stems[name], dtype=np.float64) for name in STEMS}
    ex = float(np.sum(x*x))
    assert ex > 0 and np.isfinite(ex)
    energies = {name: float(np.sum(y*y)) for name, y in ys.items()}
    ey = energies[target]
    residual = float(np.sum((x-ys[target])**2))/ex
    leakage = sum(energies[name] for name in STEMS if name != target)/ex
    cosine = float(np.sum(x*ys[target])/np.sqrt(ex*ey)) if ey > 0 else None
    checks = dict(target_strictly_dominant=all(ey > energies[name] for name in STEMS if name != target),
                  target_nse_at_most_point25=residual <= .25,
                  off_target_energy_at_most_point10=leakage <= .10)
    return dict(input_squared_sum=ex, stem_squared_sums=energies,
        target_energy_over_input=ey/ex, target_nse=residual,
        off_target_energy_over_input=leakage, target_cosine=cosine,
        sum_stems_nse=float(np.sum((x-sum(ys.values()))**2))/ex,
        dominant_stem=max(STEMS, key=lambda name: energies[name]),
        checks=checks, passes=all(checks.values()))


def prepare(root):
    assert not (root/'protocol.json').exists()
    preservation = read(root/'evidence/prior-preservation.json')
    assert preservation['all_prior_artifacts_verified'] and preservation['verified_count'] == 2532
    # These diagnostic tolerances are declared before reading any model output.
    gates = dict(target_dominance='Expected stem energy strictly exceeds each other stem.',
        target_nse_max=.25, off_target_energy_over_input_max=.10,
        pass_rule='Every whole recording and every event window must meet all three conditions.',
        rationale='Conservative diagnostic sanity test: expected label routing; raw target residual <=25% of input energy; total off-target squared energy <=10%. Locally chosen, not a published benchmark or promotion criterion.',
        stop='Any failure blocks treating native stems as faithful single-instrument references. No threshold, gain, window, checkpoint or overlap rescue.')
    save(root/'gates-preparation.json', dict(utc=datetime.now(timezone.utc).isoformat(), gates=gates))
    protected = {str(p): sha(p) for p in [Path(__file__),
        REPO/'tools/recovery/probe_drumsep_family_evidence.py', AUDIT/'protocol.json',
        AUDIT/'evidence/runtime-amendment-01.json', AUDIT/'preflight/checks.json',
        AUDIT/'weights/drumsep-six.ckpt', AUDIT/'primary/drumsep-config.yaml',
        AUDIT/'primary/msst-tree.json', AUDIT/'primary/source-fetches.json',
        AUDIT/'separated-02/strict-load.json', PREVIOUS/'protocol.json',
        PREVIOUS/'evidence/isolated-dry-inventory.json', root/'gates-preparation.json']}
    for e in read(AUDIT/'primary/source-fetches.json'):
        assert sha(e['path']) == e['sha256']
        protected[e['path']] = e['sha256']
    tracks, copies = [], []
    controls = read(PREVIOUS/'protocol.json')['controls']
    inventory = read(PREVIOUS/'evidence/isolated-dry-inventory.json')
    assert len(controls) == len(inventory) == 6
    for control, item in zip(controls, inventory):
        source = Path(item['path'])
        assert source.stem == Path(control['audio']).stem and item['group'] == control['group']
        assert sha(source) == item['sha256']
        annotation = source.parents[2]/'annotation'/(source.stem+'.txt')
        assert annotation.read_bytes() == Path(control['annotation']).read_bytes()
        folder = root/'inputs'/control['drummer']/source.stem
        folder.mkdir(parents=True, exist_ok=False)
        for original in [source, annotation]:
            target_path = folder/original.name
            with target_path.open('xb') as stream:
                stream.write(original.read_bytes())
            assert sha(original) == sha(target_path)
            copies.append(dict(source=str(original), copy=str(target_path), sha256=sha(original), bytes=original.stat().st_size))
            protected[str(original)] = sha(original)
            protected[str(target_path)] = sha(target_path)
        audio, sr = sf.read(folder/source.name, dtype='float32', always_2d=True)
        info = sf.info(folder/source.name)
        assert sr == 44100 and audio.shape == (item['frames'], 2) and info.subtype == 'PCM_16'
        assert np.isfinite(audio).all()
        events = [dict(time_seconds=float(line.split()[0]), label=line.split()[1])
                  for line in annotation.read_text().splitlines() if line.strip()]
        assert events == control['events']
        expected = 'hh' if control['group'] == 'hh_present' else 'snare'
        assert {e['label'] for e in events} == ({'chh'} if expected == 'hh' else {'sd'})
        windows = []
        for index, event in enumerate(events):
            center = round(event['time_seconds']*sr)
            start, stop = center-round(.05*sr), center+round(.5*sr)
            assert 0 <= start < center < stop <= len(audio)
            assert not windows or windows[-1]['stop_frame'] <= start
            windows.append(dict(index=index, **event, start_frame=start, stop_frame=stop))
        tracks.append(dict(id=control['drummer']+'_'+source.stem, drummer=control['drummer'],
            implement=control['implement'], target=expected, input=str(folder/source.name),
            annotation=str(folder/annotation.name), source=str(source),
            frames=len(audio), duration_seconds=len(audio)/sr, sample_rate=sr,
            channels=2, input_peak=float(np.abs(audio).max()), windows=windows))
    # Discriminating measurement sanity controls: correct, wrong-family, and lost signal.
    x = np.arange(1, 17, dtype=np.float64).reshape(8, 2)/32
    cases = {}
    for name in ['correct', 'wrong_family', 'lost_signal']:
        ys = {s: np.zeros_like(x) for s in STEMS}
        if name != 'lost_signal':
            ys['hh' if name == 'correct' else 'snare'] = x.copy()
        cases[name] = measurement(x, ys, 'hh')
    assert cases['correct']['passes'] and not cases['wrong_family']['passes'] and not cases['lost_signal']['passes']
    save(root/'evidence/measurement-preflight.json', cases)
    previous = read(AUDIT/'protocol.json')
    assert sha(AUDIT/'weights/drumsep-six.ckpt') == WEIGHT_HASH
    protocol = dict(utc=datetime.now(timezone.utc).isoformat(),
        hypothesis='Unchanged DrumSep preserves labeled isolated HH and snare audio in the expected stem with limited leakage.',
        input_contract='Original full stereo ENST dry_mix PCM16 copied byte-exact; float32 decode only; gain1, no normalization, resampling, channel fold or time shift.',
        selection='All six already inventoried companion dry mixes. Drummer1 brushes because that kit lacks a local closed-HH-stick control; drummers2/3 sticks. No replacement or exclusions.',
        measurement_contract='Float64 sums across both channels. Raw target NSE=sum((input-target)^2)/sum(input^2); off-target ratio=sum(other stem energies)/input energy; uncentered cosine; sum-stems NSE. Energy ratios are not additive signal fractions because stem cross terms exist.',
        event_window='Fixed [-50ms,+500ms) around round(label_time*44100), no overlap or clipping on selected inputs. Full files also measured. No lag or scale fitting.',
        gates=gates, settings=previous['settings'], tracks=tracks, source_copies=copies,
        weights=str(AUDIT/'weights/drumsep-six.ckpt'), checkpoint_sha256=WEIGHT_HASH,
        source_revision=previous['source_revision'], code_sha256=sha(Path(__file__)),
        review='Per file select highest target NSE event and highest off-target energy ratio event, ties earlier index, deduplicate. Show input and all six output clips at unchanged amplitude; waveform panels. Every event retained in metrics.',
        limitations=['Source labels describe intended isolated hits, not guaranteed pure acoustic signals; room noise and sympathetic resonance remain.',
            'These small exposed controls do not establish training exclusion, mixed-hit performance, full-song timing/transcription accuracy or historical runtime parity.',
            'No E-GMD/ADT_STR retry, prior HH-energy or transient threshold rescue, KLEWS/Adapt use, chart/default changes or promotion.'],
        protected=[dict(path=path, sha256=h) for path, h in sorted(protected.items())])
    save(root/'protocol.json', protocol)
    print(dict(protocol_sha256=sha(root/'protocol.json'), protected=len(protected), tracks=len(tracks),
        events=sum(len(t['windows']) for t in tracks), seconds=sum(t['duration_seconds'] for t in tracks)), flush=True)


def checked(root):
    p = read(root/'protocol.json')
    assert sha(Path(__file__)) == p['code_sha256']
    for e in p['protected']:
        assert sha(e['path']) == e['sha256'], e['path']
    return p


def infer(root):
    p = checked(root)
    out = root/'separated'; out.mkdir(exist_ok=False)
    config, ns = native(AUDIT)
    assert config.audio.chunk_size == p['settings']['chunk_samples']
    assert config.inference.num_overlap == 4 and config.inference.batch_size == 1 and config.training.use_amp
    torch.set_num_threads(2); torch.manual_seed(0); np.random.seed(0)
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    device = torch.device('cuda:0'); torch.cuda.init()
    model = ns['TFC_TDF_net'](config)
    state = torch.load(p['weights'], map_location='cpu', weights_only=True)
    result = model.load_state_dict(state, strict=True)
    assert not result.missing_keys and not result.unexpected_keys
    prior = read(AUDIT/'separated-02/strict-load.json')
    assert len(state) == len(prior['entries']) == 319
    for e in prior['entries']:
        value = model.state_dict()[e['key']]
        assert torch.equal(value, state[e['key']]) and torch.isfinite(value).all()
        assert hashlib.sha256(value.numpy().tobytes()).hexdigest() == e['sha256']
    save(out/'strict-load.json', dict(tensors=319, scalar_values=sum(v.numel() for v in state.values()),
        weights_sha256=sha(p['weights']), prior_tensor_manifest_sha256=sha(AUDIT/'separated-02/strict-load.json'),
        python=sys.version, torch=torch.__version__, numpy=np.__version__, cuda=torch.version.cuda,
        device=torch.cuda.get_device_name(device)))
    del state
    model.eval().to(device); runs = []
    for track in p['tracks']:
        folder = out/track['id']; folder.mkdir(exist_ok=False)
        audio, sr = sf.read(track['input'], dtype='float32', always_2d=True)
        assert sr == 44100 and audio.shape == (track['frames'], 2)
        torch.manual_seed(0); np.random.seed(0); torch.cuda.reset_peak_memory_stats(device)
        start = time.perf_counter()
        stems = ns['demix'](config, model, audio.T.copy(), device, 'mdx23c', True)
        torch.cuda.synchronize(); elapsed = time.perf_counter()-start
        outputs = []
        assert list(stems) == STEMS
        for name in STEMS:
            value = stems[name].T
            assert value.shape == audio.shape and np.isfinite(value).all()
            target_path = folder/(name+'.wav')
            sf.write(target_path, value, sr, subtype='FLOAT')
            back, rate = sf.read(target_path, dtype='float32', always_2d=True)
            assert rate == sr and np.array_equal(back, value)
            outputs.append(dict(stem=name, path=str(target_path), sha256=sha(target_path), frames=len(value)))
        row = dict(id=track['id'], outputs=outputs, seconds=elapsed,
            peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(device),
            peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved(device))
        save(folder/'completed.json', row); runs.append(row)
        print(dict(id=track['id'], seconds=elapsed, stems=len(outputs)), flush=True)
        del stems
    checked(root)
    save(out/'completed.json', dict(protocol_sha256=sha(root/'protocol.json'), tracks=runs))


def load_audio(track, run):
    assert track['id'] == run['id']
    audio, sr = sf.read(track['input'], dtype='float32', always_2d=True)
    stems = {}
    for e in run['outputs']:
        assert sha(e['path']) == e['sha256']
        value, rate = sf.read(e['path'], dtype='float32', always_2d=True)
        assert rate == sr == 44100 and value.shape == audio.shape
        stems[e['stem']] = value
    return audio, stems


def score(root):
    p = checked(root); completed = read(root/'separated/completed.json')
    assert completed['protocol_sha256'] == sha(root/'protocol.json')
    out = root/'measurements'; out.mkdir(exist_ok=False)
    summaries, events = [], []
    assert len(completed['tracks']) == len(p['tracks']) == 6
    for track, run in zip(p['tracks'], completed['tracks']):
        audio, stems = load_audio(track, run)
        row = dict(id=track['id'], target=track['target'], **measurement(audio, stems, track['target']))
        local = []
        for window in track['windows']:
            a, b = window['start_frame'], window['stop_frame']
            local.append(dict(id=track['id'], target=track['target'], **window,
                **measurement(audio[a:b], {s: y[a:b] for s, y in stems.items()}, track['target'])))
        row.update(event_count=len(local), events_passing=sum(e['passes'] for e in local))
        summaries.append(row); events.extend(local)
    result = dict(protocol_sha256=sha(root/'protocol.json'), tracks=summaries,
        recording_passes=sum(t['passes'] for t in summaries), recording_count=6,
        event_passes=sum(e['passes'] for e in events), event_count=len(events),
        overall_passes=all(t['passes'] for t in summaries) and all(e['passes'] for e in events))
    save(out/'events.json', events); save(out/'summary.json', result)
    print(result, flush=True)


def review(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from html import escape
    p = checked(root); runs = read(root/'separated/completed.json')['tracks']
    events = read(root/'measurements/events.json')
    out = root/'review'; out.mkdir(exist_ok=False)
    cases, html = [], ['<!doctype html><meta charset="utf-8"><title>Isolated DrumSep control</title>',
        '<h1>Isolated HH/snare control</h1><p>Fixed worst residual/leakage cases; unchanged amplitudes. Source labels retained. No auditory relabeling or full-song claim.</p>']
    for track, run in zip(p['tracks'], runs):
        local = [e for e in events if e['id'] == track['id']]
        selected = sorted({max(local, key=lambda e: (e[key], -e['index']))['index']
                           for key in ['target_nse', 'off_target_energy_over_input']})
        audio, stems = load_audio(track, run)
        sources = {'input': track['input'], **{e['stem']: e['path'] for e in run['outputs']}}
        signals = {'input': audio, **stems}
        fig, axes = plt.subplots(len(selected), 1, figsize=(12, 3.3*len(selected)), squeeze=False)
        for ax, index in zip(axes[:, 0], selected):
            event = next(e for e in local if e['index'] == index)
            a, b = event['start_frame'], event['stop_frame']
            folder = out/(track['id']+'_event'+str(index)); folder.mkdir(exist_ok=False)
            clips = []
            html.append('<h2>'+escape(track['id'])+' at '+str(event['time_seconds'])+'s</h2>')
            for name, value in signals.items():
                file = folder/(name+'.wav'); clip = value[a:b]
                sf.write(file, clip, 44100, subtype='FLOAT')
                back, sr = sf.read(file, dtype='float32', always_2d=True)
                assert sr == 44100 and np.array_equal(back, clip)
                clips.append(dict(name=name, path=str(file), source=sources[name], sha256=sha(file)))
                html.append('<p>'+escape(name)+': <audio controls preload="none" src="'+file.relative_to(out).as_posix()+'"></audio></p>')
            times = (np.arange(a, b)/44100)-event['time_seconds']
            # Same channel and amplitude scale; min/max block envelope preserves sharp attacks.
            for name, color, width in [('input', 'black', 1.0), (track['target'], 'tab:blue', .8),
                ('snare' if track['target'] == 'hh' else 'hh', 'tab:orange', .7)]:
                value = signals[name][a:b, 0]
                blocks = len(value)//22
                grouped = value[:blocks*22].reshape(blocks, 22)
                tt = times[:blocks*22].reshape(blocks, 22).mean(axis=1)
                ax.vlines(tt, grouped.min(axis=1), grouped.max(axis=1), color=color, linewidth=width, label=name)
            ax.set_title(f"{track['id']} {event['time_seconds']:.3f}s | NSE {event['target_nse']:.4f} | leakage {event['off_target_energy_over_input']:.4f}")
            ax.set_xlabel('Seconds relative to source label'); ax.set_ylabel('Left-channel amplitude'); ax.legend()
            cases.append(dict(id=track['id'], index=index, start_frame=a, stop_frame=b, clips=clips))
        fig.tight_layout(); file = out/(track['id']+'.png'); fig.savefig(file, dpi=130); plt.close(fig)
        html.append('<img style="max-width:100%" src="'+file.name+'">')
    save(out/'cases.json', cases)
    with (out/'index.html').open('x', encoding='utf8') as stream:
        stream.write('\n'.join(html))
    print(dict(review_cases=len(cases), exact_clips=sum(len(c['clips']) for c in cases)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'infer', 'score', 'review'])
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args(); root = args.root.resolve()
    assert root.parent == BASE.resolve() and root.name == '2026-10-16-drumsep-isolated-control-01'
    globals()[args.action](root)
