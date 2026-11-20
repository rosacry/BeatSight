"""One frozen full-recording comparison after the frontend conformance gate."""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
import soundfile as sf

from audit_adtof_frontend import BASELINE, DATA, PRIOR, REFERENCE
from decode_adtof_reference import decode_activations
from frontend_adtof_reference import features
from probe_residual_input import acceptance, event_assignments, pool, truth_from
from score_timing import evaluate_timing
from transcribe import sha256
from transcribe_reference import reference_preflight, write_json


def prepare(root):
    if root.resolve().drive.upper()!='C:':raise ValueError('Use a scoped C: root')
    conformance=json.loads((root/'conformance.json').read_text())
    if not conformance['adapter_passes'] or not conformance['changed_port_bands']:
        raise ValueError('No verified source mismatch')
    weights=reference_preflight(REFERENCE)
    if os.environ.get('ADTOF_USE_KERAS_GRU','0').strip()!='0':raise ValueError('GRU configuration differs')
    old_path=PRIOR/'decoder-source-audit/cached-comparison/metrics.json'
    old=json.loads(old_path.read_text())
    prior=json.loads((PRIOR/'prepared.json').read_text())
    files={r['path']:r['sha256'] for r in prior['prior_files']}
    for p in [weights, old_path, root/'protocol.json', root/'conformance.json', Path(__file__),
              Path(__file__).with_name('frontend_adtof_reference.py'),
              Path(__file__).with_name('decode_adtof_reference.py')]:files[str(p)]=sha256(p)
    for p,h in files.items():
        if sha256(Path(p))!=h:raise ValueError(f'Prior input changed: {p}')
    rows=[]
    for row in old['tracks']:
        track=row['track']; stem=BASELINE/f'{track}.drums.wav'; act=BASELINE/f'{track}.activations.npy'
        if sf.info(stem).subtype!='FLOAT':raise ValueError('Candidate contract is decoded float PCM')
        truth=truth_from(DATA/f'{track}_class.txt')
        chart=decode_activations(np.load(act))
        scores={ms:{'baseline':evaluate_timing(chart,truth,int(ms)/1000)} for ms in ['25','50']}
        if any(scores[ms]['baseline']!=row['scores'][ms]['primary'] for ms in scores):
            raise ValueError('Cached primary baseline did not reproduce')
        rows.append({'track':track,'stem':str(stem),'activation':str(act),
                     'annotation':str(DATA/f'{track}_class.txt'),'scores':scores,
                     'duration_seconds':sf.info(stem).duration})
    out=root/'full-recordings';out.mkdir(exist_ok=False)
    protocol={
        'utc':datetime.now(timezone.utc).isoformat(),
        'hypothesis':'The source-aligned frontend may improve fixed converted-model output on saved drum stems.',
        'selection':'All seven existing MDB development recordings, no reserved or uncertain Clone Hero references',
        'change':'440 Hz anchored filterbank, float64 Hann before complex64 FFT, normal end framing; same decoded mono float32 stem, no gain change',
        'baseline':'Saved port-front-end activations, redecoded with verified primary decoder',
        'candidate':'Source-aligned float-PCM frontend, same pinned converted model, same primary decoder',
        'settings':{'device':'cpu','threads':2,'seed':0,'fps':100,'thresholds':[.22,.24,.32,.22,.30],
                    'ADTOF_USE_KERAS_GRU':os.environ.get('ADTOF_USE_KERAS_GRU','0')},
        'gate_50ms':{'minimum_pooled_f1_gain':.01,'maximum_precision_loss':.01,'maximum_track_f1_loss':.02,
                     'tom_tp_must_not_decrease':True,'maximum_snare_recall_loss':.01},
        'stop_rule':'One candidate; no parameter sweep. Passing warrants separate acceptance-song review only, not app promotion.',
        'limits':'Training overlap unknown; converted model equivalence unverified; short complete recordings; 32 unsupported OT targets retained.',
        'packages':{p:version(p) for p in ['numpy','scipy','torch','soundfile','librosa']},
        'weights':str(weights),'weights_sha256':sha256(weights),
        'source_sha256':sha256(Path(__file__)),
        'prior_files':[{'path':p,'sha256':h} for p,h in sorted(files.items())],
        'tracks':rows}
    write_json(out/'protocol.json',protocol)
    print(json.dumps({'prepared_recordings':len(rows),'protocol_sha256':sha256(out/'protocol.json')}))


def run(root):
    out=root/'full-recordings';protocol=json.loads((out/'protocol.json').read_text())
    for row in protocol['prior_files']:
        if sha256(Path(row['path']))!=row['sha256']:raise ValueError('Frozen input/source changed')
    if os.environ.get('ADTOF_USE_KERAS_GRU','0')!=protocol['settings']['ADTOF_USE_KERAS_GRU']:
        raise ValueError('Model configuration changed')
    weights=reference_preflight(REFERENCE)
    with (out/'run-started.json').open('x') as f:json.dump({'utc':datetime.now(timezone.utc).isoformat()},f)
    import torch
    sys.path.insert(0,str(REFERENCE/'src'))
    from adtof_pytorch import create_frame_rnn_model, load_pytorch_weights, load_audio_for_model
    torch.set_num_threads(2);torch.manual_seed(0);np.random.seed(0)
    with (out/'model-load.log').open('x') as log, redirect_stdout(log):
        model=load_pytorch_weights(create_frame_rnn_model(84),str(weights),strict=True).eval()
    # Reproduce one entire baseline before running the changed feature path.
    control=protocol['tracks'][0]
    with torch.no_grad(): reproduced=model(load_audio_for_model(control['stem'])).cpu().numpy()
    saved=np.load(control['activation'])
    check={'track':control['track'],'exact_saved_activation_reproduction':bool(np.array_equal(reproduced,saved)),
           'max_abs':float(np.max(np.abs(reproduced-saved)))}
    write_json(out/'baseline-control.json',check)
    if not check['exact_saved_activation_reproduction']:raise ValueError('Model control changed')
    result={'status':'started','protocol_sha256':sha256(out/'protocol.json'),'tracks':[]}
    for row in protocol['tracks']:
        start=time.perf_counter();folder=out/row['track'];folder.mkdir()
        y,sr=sf.read(row['stem'],dtype='float32')
        if sr!=44100 or y.ndim!=1:raise ValueError('PCM contract violated')
        feature=features(y)
        with torch.no_grad():act=model(torch.from_numpy(feature).unsqueeze(0)).cpu().numpy()
        if not np.isfinite(act).all():raise ValueError('Nonfinite output')
        np.save(folder/'activations.npy',act)
        chart=decode_activations(act);write_json(folder/'predictions.json',chart)
        baseline=decode_activations(np.load(row['activation']))
        truth=truth_from(Path(row['annotation']))
        for ms in ['25','50']:
            row['scores'][ms]['candidate']=evaluate_timing(chart,truth,int(ms)/1000)
            write_json(folder/f'events-{ms}ms.json',{
                'baseline':event_assignments(baseline,truth,int(ms)/1000),
                'candidate':event_assignments(chart,truth,int(ms)/1000)})
        row['candidate_activation_sha256']=sha256(folder/'activations.npy')
        row['candidate_prediction_sha256']=sha256(folder/'predictions.json')
        row['feature_shape']=list(feature.shape);row['runtime_seconds']=time.perf_counter()-start
        result['tracks'].append(row);write_json(out/'metrics.json',result)
        print(json.dumps({'track':row['track'],'baseline50':row['scores']['50']['baseline']['micro'],
                          'candidate50':row['scores']['50']['candidate']['micro']}),flush=True)
    result['pooled']={ms:{arm:pool(result['tracks'],arm,ms) for arm in ['baseline','candidate']} for ms in ['25','50']}
    result['decision']=acceptance(result['pooled']['50']['baseline'],result['pooled']['50']['candidate'],
        [r['scores']['50']['candidate']['micro']['f1']-r['scores']['50']['baseline']['micro']['f1'] for r in result['tracks']])
    for row in protocol['prior_files']:
        if sha256(Path(row['path']))!=row['sha256']:raise ValueError('Prior input changed during run')
    result['prior_files_verified_after_run']=len(protocol['prior_files']);result['status']='complete'
    write_json(out/'metrics.json',result)
    print(json.dumps({'pooled50':{a:result['pooled']['50'][a]['micro'] for a in ['baseline','candidate']},
                      'decision':result['decision']}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run'])
    parser.add_argument('--root',type=Path,required=True);args=parser.parse_args()
    {'prepare':prepare,'run':run}[args.action](args.root)
