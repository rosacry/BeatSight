"""One pooling-only comparison with a source-verified frontend/decoder baseline."""
import argparse
from contextlib import redirect_stdout
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
import soundfile as sf

from audit_adtof_model import FRONTEND
from audit_adtof_frontend import REFERENCE
from decode_adtof_reference import decode_activations
from frontend_adtof_reference import features
from model_adtof_reference import replace_pooling
from probe_residual_input import acceptance, event_assignments, pool, truth_from
from score_timing import evaluate_timing
from transcribe import sha256
from transcribe_reference import reference_preflight, write_json


def prepare(root):
    if root.resolve().drive.upper()!='C:':raise ValueError('Use a scoped C: root')
    audit=json.loads((root/'layer-audit.json').read_text())
    if not all(audit[k] for k in ['candidate_pooling_passes','real_pool_mismatch','gru_equations_pass','local_conv_bn_pass']):
        raise ValueError('Layer audit does not justify this comparison')
    weights=reference_preflight(REFERENCE)
    prior=FRONTEND/'full-recordings'
    p=json.loads((prior/'protocol.json').read_text());m=json.loads((prior/'metrics.json').read_text())
    files={r['path']:r['sha256'] for r in p['prior_files']}
    extra=[weights,prior/'protocol.json',prior/'metrics.json',root/'protocol.json',root/'layer-audit.json',
           Path(__file__),Path(__file__).with_name('model_adtof_reference.py')]
    for path in extra:files[str(path)]=sha256(path)
    rows=[]
    for old in m['tracks']:
        act=prior/old['track']/'activations.npy';pred=prior/old['track']/'predictions.json'
        files[str(act)]=old['candidate_activation_sha256'];files[str(pred)]=old['candidate_prediction_sha256']
        chart=decode_activations(np.load(act));truth=truth_from(Path(old['annotation']))
        if chart!=json.loads(pred.read_text()):raise ValueError('Saved baseline chart changed')
        scores={ms:{'baseline':evaluate_timing(chart,truth,int(ms)/1000)} for ms in ['25','50']}
        if any(scores[ms]['baseline']!=old['scores'][ms]['candidate'] for ms in scores):raise ValueError('Baseline metrics changed')
        rows.append({'track':old['track'],'stem':old['stem'],'annotation':old['annotation'],
                     'baseline_activation':str(act),'scores':scores,'duration_seconds':old['duration_seconds']})
    for path,h in files.items():
        if sha256(Path(path))!=h:raise ValueError(f'Protected source changed: {path}')
    out=root/'full-recordings';out.mkdir(exist_ok=False)
    protocol={'utc':datetime.now(timezone.utc).isoformat(),
        'hypothesis':'Excluding padded positions from max pooling may improve the fixed converted model on saved stems.',
        'change':'Only pooling padding value: negative infinity for finite activation input, replacing zero. No weights, bias, gate, gain, frontend, decoder or threshold changes.',
        'baseline':'Cached source-aligned frontend, pinned model with zero padding, primary decoder',
        'selection':'Same seven existing MDB development recordings, 2461 targets including 32 unsupported OT; unknown training overlap',
        'settings':{'device':'cpu','threads':2,'seed':0,'fps':100,'thresholds':[.22,.24,.32,.22,.30],'ADTOF_USE_KERAS_GRU':'0'},
        'gate_50ms':{'minimum_pooled_f1_gain':.01,'maximum_precision_loss':.01,'maximum_track_f1_loss':.02,
                     'tom_tp_must_not_decrease':True,'maximum_snare_recall_loss':.01},
        'stop_rule':'One source-justified candidate. No score-based variant selection, reserved song tuning or automatic promotion. Failure ends this correction as an accuracy route.',
        'weights':str(weights),'prior_files':[{'path':p,'sha256':h} for p,h in sorted(files.items())],
        'tracks':rows}
    write_json(out/'protocol.json',protocol)
    print(json.dumps({'prepared':len(rows),'protocol_sha256':sha256(out/'protocol.json')}))


def run(root):
    out=root/'full-recordings';protocol=json.loads((out/'protocol.json').read_text())
    for row in protocol['prior_files']:
        if sha256(Path(row['path']))!=row['sha256']:raise ValueError('Frozen source/input changed')
    if os.environ.get('ADTOF_USE_KERAS_GRU','0')!='0':raise ValueError('Model configuration changed')
    with (out/'run-started.json').open('x') as f:json.dump({'utc':datetime.now(timezone.utc).isoformat()},f)
    import torch
    sys.path.insert(0,str(REFERENCE/'src'))
    from adtof_pytorch import create_frame_rnn_model,load_pytorch_weights
    torch.set_num_threads(2);torch.manual_seed(0);np.random.seed(0)
    with (out/'model-load.log').open('x') as log,redirect_stdout(log):
        baseline=load_pytorch_weights(create_frame_rnn_model(84),str(reference_preflight(REFERENCE)),strict=True).eval()
    model=replace_pooling(copy.deepcopy(baseline)).eval()
    if any(not torch.equal(v,model.state_dict()[k]) for k,v in baseline.state_dict().items()):
        raise ValueError('Pooling change altered model weights')
    result={'status':'started','protocol_sha256':sha256(out/'protocol.json'),'tracks':[]}
    for index,row in enumerate(protocol['tracks']):
        start=time.perf_counter();folder=out/row['track'];folder.mkdir()
        y,sr=sf.read(row['stem'],dtype='float32')
        if sr!=44100 or y.ndim!=1:raise ValueError('PCM contract violated')
        x=torch.from_numpy(features(y)).unsqueeze(0)
        if index==0:
            with torch.no_grad():control=baseline(x).cpu().numpy()
            old=np.load(row['baseline_activation'])
            check={'track':row['track'],'exact_saved_activation_reproduction':bool(np.array_equal(control,old)),
                   'max_abs':float(np.max(np.abs(control-old))),'model_state_unchanged':True}
            write_json(out/'baseline-control.json',check)
            if not check['exact_saved_activation_reproduction']:raise ValueError('Baseline did not reproduce')
        with torch.no_grad():act=model(x).cpu().numpy()
        if not np.isfinite(act).all():raise ValueError('Nonfinite output')
        np.save(folder/'activations.npy',act)
        chart=decode_activations(act);write_json(folder/'predictions.json',chart)
        old_chart=decode_activations(np.load(row['baseline_activation']));truth=truth_from(Path(row['annotation']))
        for ms in ['25','50']:
            row['scores'][ms]['candidate']=evaluate_timing(chart,truth,int(ms)/1000)
            write_json(folder/f'events-{ms}ms.json',{'baseline':event_assignments(old_chart,truth,int(ms)/1000),
                                                  'candidate':event_assignments(chart,truth,int(ms)/1000)})
        row['candidate_activation_sha256']=sha256(folder/'activations.npy');row['candidate_prediction_sha256']=sha256(folder/'predictions.json')
        row['runtime_seconds']=time.perf_counter()-start
        result['tracks'].append(row);write_json(out/'metrics.json',result)
        print(json.dumps({'track':row['track'],'baseline50':row['scores']['50']['baseline']['micro'],
                          'candidate50':row['scores']['50']['candidate']['micro']}),flush=True)
    result['pooled']={ms:{arm:pool(result['tracks'],arm,ms) for arm in ['baseline','candidate']} for ms in ['25','50']}
    result['decision']=acceptance(result['pooled']['50']['baseline'],result['pooled']['50']['candidate'],
        [r['scores']['50']['candidate']['micro']['f1']-r['scores']['50']['baseline']['micro']['f1'] for r in result['tracks']])
    for row in protocol['prior_files']:
        if sha256(Path(row['path']))!=row['sha256']:raise ValueError('Protected file changed during run')
    result['prior_files_verified_after_run']=len(protocol['prior_files']);result['status']='complete'
    write_json(out/'metrics.json',result)
    print(json.dumps({'pooled50':{arm:result['pooled']['50'][arm]['micro'] for arm in ['baseline','candidate']},
                      'decision':result['decision']}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();{'prepare':prepare,'run':run}[args.action](args.root)
