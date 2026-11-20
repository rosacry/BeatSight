"""Freeze and run a small source-conformance audit without installing madmom.

Executes only named, reviewed AST definitions from hash-recorded public sources.
No complete downloaded module, imports or top-level statements are executed.
"""
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import warnings

import numpy as np
from scipy import fftpack
import soundfile as sf

from frontend_adtof_reference import features, filterbank, frame_audio, magnitude
from transcribe import sha256
from transcribe_reference import write_json

RECOVERY = Path('C:/Users/10ros/BeatSight-Recovery')
PRIOR = RECOVERY/'2026-10-15-mdb-residual-input-01'
BASELINE = RECOVERY/'2026-10-14-white-waves-01/stereo-diagnostic'
DATA = RECOVERY/'2026-10-13/diagnostic-mdb-plus-seven-inputs'
REFERENCE = RECOVERY/'2026-10-13/reference-adtof'


def oracle(primary):
    """Selected unmodified algorithm definitions; np.float gets a local alias."""
    for manifest in ['sources.json', 'sources-addendum.json']:
        for row in json.loads((primary/manifest).read_text())['files']:
            # Verify the files that will actually be read, including relocated copies.
            if sha256(primary/Path(row['path']).name) != row['sha256']:
                raise ValueError('Primary source hash changed')
    class NumpyCompat:
        float = float
        def __getattr__(self, name):
            return getattr(np, name)
    scope = {'np': NumpyCompat(), 'fftpack': fftpack, 'FILTER_DTYPE': np.float32,
             'STFT_DTYPE': np.complex64, 'A4': 440., 'FMIN': 30., 'FMAX': 17000.,
             'NORM_FILTERS': True, 'UNIQUE_FILTERS': True}
    selected = {
        'madmom-filters.py': ['log_frequencies', 'frequencies2bins', 'bins2frequencies',
                              'Filter', 'TriangularFilter', 'Filterbank', 'LogarithmicFilterbank'],
        'madmom-signal.py': ['signal_frame'],
        'madmom-stft.py': ['fft_frequencies', 'stft'],
    }
    for filename, names in selected.items():
        tree = ast.parse((primary/filename).read_text())
        nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
        if {n.name for n in nodes} != set(names):
            raise ValueError('Missing reviewed definitions')
        exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), scope)
    bank = np.asarray(scope['LogarithmicFilterbank'](scope['fft_frequencies'](1024,44100),
                                                   num_bands=12, fmin=20, fmax=20000))
    def stages(audio):
        frames = np.stack([scope['signal_frame'](audio, i, 2048, 441)
                           for i in range(int(np.ceil(len(audio)/441)))])
        mag = np.abs(scope['stft'](frames, np.hanning(2048)))
        feat = np.dot(mag, bank)
        feat += 1
        np.log10(feat, out=feat)
        return frames, mag, feat
    return SimpleNamespace(bank=bank, stages=stages)


def prepare(out):
    if out.resolve().drive.upper() != 'C:':
        raise ValueError('Use a scoped C: directory')
    if (out/'protocol.json').exists():
        raise ValueError('Do not replace an existing protocol')
    failure_path = PRIOR/'analysis/failures.json'
    failures = json.loads(failure_path.read_text())
    protected = {failure_path, Path(__file__), Path(__file__).with_name('frontend_adtof_reference.py'),
                 REFERENCE/'src/adtof_pytorch/audio.py'}
    clips = []
    for short, family in [('CoolJazz','SD'), ('FreeJazz','SD'), ('Beatles','TT'), ('FusionJazz','TT')]:
        track = 'MusicDelta_'+short
        event_path = PRIOR/track/'events-50ms.json'
        protected.add(event_path)
        events = json.loads(event_path.read_text())['baseline'][family]['reference']
        entry = next(r for r in failures['tracks'] if r['track'] == track)
        missed = entry['missed_target_activation_audit']['baseline'][family]
        duration = sf.info(BASELINE/f'{track}.drums.wav').duration
        eligible = lambda t: 2 <= t < duration - 2
        raw = [e for e in missed if eligible(e['time']) and e['category']=='raw_below_threshold']
        other = [e for e in missed if eligible(e['time'])]
        target = min(raw or other, key=lambda e:e['time'])
        control = next(e for e in events if eligible(e['time']) and e['matched_prediction'] is not None)
        for role, event in [('miss',target), ('matched_control',control)]:
            start_sample = int(np.floor((event['time']-2)*100))*441
            for source, path in [('mix',DATA/f'{track}_MIX.wav'),('stem',BASELINE/f'{track}.drums.wav')]:
                protected.add(path)
                clips.append({'track':track, 'family':family, 'role':role, 'source':source,
                              'path':str(path), 'anchor_seconds':event['time'],
                              'start_sample':start_sample, 'frames':176400,
                              'miss_category':target['category'] if role=='miss' else None})
    protocol = {
        'utc':datetime.now(timezone.utc).isoformat(), 'purpose':'Source conformance on fixed float32 PCM, not accuracy scoring',
        'selection':'Four fixed track/family pairs, earliest eligible raw-below-threshold miss (else earliest miss) and earliest matched control, each original mix and saved stem; four seconds, grid-aligned starts, no fitted alignment',
        'boundary':'Same decoded float32 mono PCM at 44100 Hz, mix arithmetic channel mean; no normalization/resampling. Full madmom file loader, integer scaling and FFTW are not exercised.',
        'primary_path':'Reviewed madmom v0.16.1 definitions, scipy.fftpack fallback, ADTOF Frame_RNN configuration',
        'comparisons':['port', 'port_with_only_primary_filterbank', 'source_aligned_adapter'],
        'numeric_gate':{'atol':1e-5,'rtol':1e-5,'frame_count_must_match':True},
        'conditional_followup':'If source mismatch is established and adapter passes, one full seven-recording stem comparison with fixed weights/thresholds and primary decoder on both arms; same .01 F1/.01 precision/.02 track-loss/tom-TP/snare-recall development gate as residual comparison. No parameter sweep, reserved-song tuning or automatic promotion.',
        'clips':clips,
        'protected':[{'path':str(p),'sha256':sha256(p)} for p in sorted(protected)],
    }
    with (out/'protocol.json').open('x') as f:json.dump(protocol,f,indent=2)
    print(json.dumps({'prepared_clips':len(clips),'protocol_sha256':sha256(out/'protocol.json')}))


def difference(a,b):
    n=min(len(a),len(b))
    delta=np.abs(a[:n].astype(float)-b[:n].astype(float))
    return {'shapes':[list(a.shape),list(b.shape)], 'common_frames':n,
            'mae':float(delta.mean()),'mse':float(np.mean(delta**2)), 'max_abs':float(delta.max()),
            'numeric_close_common_frames':bool(np.allclose(a[:n],b[:n],atol=1e-5,rtol=1e-5)),
            'conforms':a.shape==b.shape and bool(np.allclose(a,b,atol=1e-5,rtol=1e-5))}


def synthetic_signals():
    rng=np.random.default_rng(0)
    for length in [1,440,441,442,1024,2048,4409,4410,4411]:
        y=np.zeros(length,dtype=np.float32); y[[0,length//2,length-1]]=1
        yield f'impulses_{length}', y
        yield f'noise_{length}', rng.normal(0,.1,length).astype(np.float32)
    yield 'silence', np.zeros(4410,dtype=np.float32)
    for hz in [20,110,440,1000,5000,19000]:
        yield f'tone_{hz}', (.2*np.sin(2*np.pi*hz*np.arange(4410)/44100)).astype(np.float32)


def run(out):
    protocol=json.loads((out/'protocol.json').read_text())
    for row in protocol['protected']:
        if sha256(Path(row['path']))!=row['sha256']:
            raise ValueError('Frozen input/source changed')
    with (out/'audit-started.json').open('x') as f:json.dump({'protocol_sha256':sha256(out/'protocol.json')},f)
    primary=oracle(out/'primary')
    sys.path.insert(0,str(REFERENCE/'src'))
    from adtof_pytorch.audio import AudioProcessor
    port=AudioProcessor()
    grid=AudioProcessor(); grid.filterbank=primary.bank.T.copy()
    if primary.bank.shape != port.filterbank.T.shape:
        raise ValueError('Model input dimensionality differs')
    def compare(name,y):
        frames, mag, feat=primary.stages(y)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            port_mag=port.compute_stft(y)
        return {'name':name, 'adapter_frames_exact':bool(np.array_equal(frame_audio(y),frames)),
                'adapter_magnitude':difference(magnitude(y),mag),
                'port_magnitude':difference(port_mag.T,mag),
                'port':difference(port.apply_filterbank(port_mag).T,feat),
                'grid_only':difference(grid.apply_filterbank(port_mag).T,feat),
                'adapter':difference(features(y)[:,:,0],feat)}
    synth=[compare(name,y) for name,y in synthetic_signals()]
    clips=[]
    for i,c in enumerate(protocol['clips']):
        y,sr=sf.read(c['path'],start=c['start_sample'],frames=c['frames'],dtype='float32')
        if sr!=44100 or len(y)!=c['frames']:raise ValueError('Unexpected PCM')
        if y.ndim==2:y=y.mean(axis=1)
        clips.append({**c,**compare(str(i),y)})
    result={'protocol_sha256':sha256(out/'protocol.json'),
            'bank_shape':list(primary.bank.shape),
            'adapter_bank_exact':bool(np.array_equal(filterbank(),primary.bank)),
            'changed_port_bands':int(np.any(port.filterbank.T!=primary.bank,axis=0).sum()),
            'bank_max_abs':float(np.max(np.abs(port.filterbank.T-primary.bank))),
            'synthetic':synth,'clips':clips}
    result['adapter_passes']=result['adapter_bank_exact'] and all(
        r['adapter_frames_exact'] and r['adapter_magnitude']['conforms'] and r['adapter']['conforms']
        for r in synth+clips)
    write_json(out/'conformance.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['synthetic','clips']}))
    print(json.dumps({'clip_port_mae_range':[min(r['port']['mae'] for r in clips),max(r['port']['mae'] for r in clips)],
                      'clip_grid_only_max':max(r['grid_only']['max_abs'] for r in clips),
                      'clip_adapter_max':max(r['adapter']['max_abs'] for r in clips)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','run']); parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    {'prepare':prepare,'run':run}[args.action](args.output_dir)
