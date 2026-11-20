"""One fixed ADTOF diagnostic on Adapt's original author-provided drum stem.

Oracle input is unavailable in ordinary audio-to-chart use. This is neither a
new competing end-to-end system nor a tuning/held-out accuracy experiment.
"""
import argparse
from contextlib import redirect_stdout,redirect_stderr
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np
import soundfile as sf
import torch

from clone_hero_scoring import score_chart_agreement
from evaluate_adtof import FAMILY_COMPONENTS
from transcribe import sha256
from transcribe_reference import reference_preflight,write_json


def probe(benchmark,reference_repo,out):
    benchmark,reference_repo,out=benchmark.resolve(),reference_repo.resolve(),out.resolve()
    if out.drive.upper()!='C:' or out.is_relative_to(benchmark):raise ValueError('Use a separate new C: output')
    weights=reference_preflight(reference_repo)
    refpath=benchmark/'prepared-v2/adapt/reference.json'
    prepared=json.loads((benchmark/'prepared-v2/manifest.json').read_text())
    expected=next(s for s in prepared['songs'] if s['id']=='adapt')
    if sha256(refpath)!=expected['reference_sha256']:raise ValueError('Reference changed')
    ref=json.loads(refpath.read_text())
    source=Path(ref['chart']).parent/'drums.ogg'
    src=next(s for s in ref['audio']['sources'] if s['name']=='drums.ogg')
    if sha256(source)!=src['sha256']:raise ValueError('Original drum source changed')
    sys.path.insert(0,str(reference_repo/'src'))
    from adtof_pytorch import transcribe_to_midi,PeakPicker,FRAME_RNN_THRESHOLDS,LABELS_5
    out.mkdir(exist_ok=False)
    write_json(out/'protocol.json',{'created_utc':datetime.now(timezone.utc).isoformat(),
        'purpose':'Fixed original-drum oracle-input contrast to separate source/input losses from remaining model/proxy-label limitations.',
        'song':'adapt','training_overlap':'unknown','reserved_role':'No parameter selection; diagnostic only, not a newly untouched test result',
        'weights_sha256':sha256(weights),'reference_sha256':sha256(refpath),'source_sha256':sha256(source),
        'settings':{'thresholds':FRAME_RNN_THRESHOLDS,'fps':100,'seed':0,'device':'cpu','timing_shift_seconds':0},
        'input':'Decode original drums; same gain and total timeline as the prepared package mix; zero-pad only the 251-sample tail.',
        'gain_caveat':'Saved separated arm uses its original mono-peak normalization. This is an input contrast, not a controlled separator ranking.',
        'code_sha256':sha256(Path(__file__)),'no_tuning':True})
    shutil.copy2(Path(__file__),out/Path(__file__).name)
    y,sr=sf.read(source,dtype='float32',always_2d=True)
    if sr!=ref['audio']['sample_rate'] or len(y)!=src['frames']:raise ValueError('Unexpected source rate/length')
    if y.shape[1]==1:y=np.repeat(y,2,axis=1)
    oracle=np.zeros((ref['audio']['frames'],2),dtype=np.float32)
    oracle[:len(y)]=y*ref['audio']['linear_gain']
    audio=out/'original-drums.wav'
    sf.write(audio,oracle,sr,subtype='FLOAT')
    reread,rate=sf.read(audio,dtype='float32',always_2d=True)
    if rate!=sr or not np.array_equal(reread,oracle):raise ValueError('Oracle PCM write differs')
    torch.set_num_threads(2);torch.manual_seed(0);np.random.seed(0)
    start=time.perf_counter()
    with (out/'inference.log').open('x',encoding='utf8') as log,redirect_stdout(log),redirect_stderr(log):
        act=transcribe_to_midi(audio,out/'reference.mid',weights=weights,device='cpu',return_activations=True)
    logs=(out/'inference.log').read_text()
    if any(x in logs for x in ['Missing keys','Unexpected keys']) or not np.isfinite(act).all():raise ValueError('Invalid parameter load/output')
    np.save(out/'activations.npy',act)
    peaks=PeakPicker(thresholds=FRAME_RNN_THRESHOLDS,fps=100).pick(act,LABELS_5)[0]
    chart={'hitObjects':sorted([{'time':float(t)*1000,'component':FAMILY_COMPONENTS[p]} for p,ts in peaks.items() for t in ts],key=lambda e:e['time'])}
    write_json(out/'predictions.json',chart)
    result={'runtime_seconds':time.perf_counter()-start,'input_sha256':sha256(audio),
            'source_sha256':sha256(source),'linear_gain':ref['audio']['linear_gain'],
            'tail_padding_samples':len(oracle)-len(y),'predictions_sha256':sha256(out/'predictions.json'),
            'interpretation':'Unshifted chart agreement on original-drums oracle input. Not end-to-end accuracy; note identity/completeness and training overlap remain uncertain.',
            'arms':{'original-drums-oracle':score_chart_agreement(chart,ref['events'])}}
    baseline=json.loads((benchmark/'report/rescored-metrics.json').read_text())
    old=next(s for s in baseline['songs'] if s['id']=='adapt')
    for arm,entry in old['arms'].items():
        path=benchmark/'evaluation-01/adapt'/arm/('chart.bsm' if arm=='inherited-faithful' else 'predictions.json')
        if sha256(path)!=entry['predictions_sha256']:raise ValueError('Saved predictions changed')
        rescored=score_chart_agreement(json.loads(path.read_text()),ref['events'])
        if rescored!=entry['scores']:raise ValueError('Reused scores do not reproduce')
        result['arms'][arm]=rescored
    write_json(out/'comparison.json',result)
    print(json.dumps({'runtime_seconds':result['runtime_seconds'],'arms':{a:{v:r['50'][v]['micro'] for v in ['five_family_proxy','cymbals_merged']} for a,r in result['arms'].items()},
                      'oracle_by_family':{f:{k:v for k,v in r.items() if k!='signed_errors_seconds'} for f,r in result['arms']['original-drums-oracle']['50']['five_family_proxy']['by_family'].items()}}),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--benchmark',type=Path,required=True)
    ap.add_argument('--reference-repo',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    a=ap.parse_args();probe(a.benchmark,a.reference_repo,a.output_dir)
