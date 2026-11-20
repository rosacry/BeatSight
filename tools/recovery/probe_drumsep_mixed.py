"""Frozen six-recording DrumSep family evidence on cached practical pipeline input.

No transcription changes, threshold fitting, download, retraining or separation rerun.
The model/source, energy feature and runtime settings reuse the original-drum audit.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
import numpy as np
import soundfile as sf
import torch
from probe_drumsep_family_evidence import native, read, save, sha, STEMS, feature_values
from probe_residual_input import event_assignments, truth_from

REPO = Path('C:/github/BeatSight')
BASE = Path('C:/Users/10ros/BeatSight-Recovery')
AUDIT = BASE / '2026-10-16-drumsep-audit-01'
VALIDATION = BASE / '2026-10-15-snare-validation-01'


def prepare(root):
    assert not (root / 'protocol.json').exists()
    previous = read(AUDIT / 'protocol.json')
    # Freeze criteria before observing any new separation or feature values.
    gates = dict(minimum_group_size=10, minimum_auroc=.8,
        positive_median_strictly_above_db=0, matched_hh_median_strictly_below_db=0,
        minimum_eligible_recordings=2, minimum_eligible_nonbrush_recordings=1,
        per_recording='Every eligible recording must pass the same AUC and median gates.',
        pooled='All six recordings contribute, including small groups. Same AUC and median gates.',
        small_groups='Descriptive only; inconclusive per recording, no replacement or exclusion.',
        overall='All pooled, eligible-recording and breadth requirements must pass; insufficient breadth is inconclusive, failed numeric gates are failure.')
    save(root / 'gates-preparation.json', dict(utc=datetime.now(timezone.utc).isoformat(), gates=gates,
        rationale='Retain original evidence criterion and require evidence beyond one brush recording; no deployment threshold.'))
    out = root / 'inputs'; out.mkdir(exist_ok=False)
    protected = {str(p): sha(p) for p in [Path(__file__), REPO/'tools/recovery/probe_drumsep_family_evidence.py',
        REPO/'tools/recovery/probe_residual_input.py', REPO/'tools/recovery/score_timing.py',
        REPO/'tools/recovery/evaluate_mdb.py', REPO/'tools/recovery/validate_snare_addition.py',
        REPO/'ai-pipeline/separation/demucs_separator.py', AUDIT/'protocol.json',
        AUDIT/'evidence/runtime-amendment-01.json', AUDIT/'weights/drumsep-six.ckpt',
        AUDIT/'primary/drumsep-config.yaml', AUDIT/'primary/msst-tree.json',
        AUDIT/'primary/source-fetches.json', AUDIT/'evidence/verification.json',
        VALIDATION/'protocol.json', VALIDATION/'adtof/completed.json', root/'gates-preparation.json']}
    for e in read(AUDIT/'primary/source-fetches.json'):
        assert sha(e['path'])==e['sha256'];protected[e['path']]=e['sha256']
    tracks=[]
    for spec in read(VALIDATION/'protocol.json')['tracks']:
        if not spec['admitted']: continue
        assert spec['dataset']=='ENST'
        folder=VALIDATION/'adtof'/spec['id']
        source=folder/'drums.wav'; prediction=folder/'predictions.json'
        cached=VALIDATION/'comparison'/spec['id']/'events-50ms.json'
        run=read(folder/'run.json')
        assert sha(source)==run['stem_sha256'] and sha(prediction)==run['prediction_sha256']
        mono,sr=sf.read(source,dtype='float32')
        assert mono.ndim==1 and sr==44100 and len(mono)==round(spec['duration_seconds']*sr) and np.isfinite(mono).all()
        mix,msr=sf.read(spec['mix'],dtype='float32',always_2d=True)
        assert msr==sr and mix.shape==(len(mono),2)
        peak=float(np.abs(np.mean(mix.T.copy(),axis=0)).max())
        assert peak==run['mono_peak_divisor']
        stereo=np.stack([mono,mono],axis=1)
        target=out/(spec['id']+'.wav')
        sf.write(target,stereo,sr,subtype='FLOAT')
        back,br=sf.read(target,dtype='float32',always_2d=True)
        assert br==sr and np.array_equal(back,stereo) and np.array_equal(back.mean(axis=1),mono)
        truth=truth_from(Path(spec['annotation']))
        matches=event_assignments(read(prediction),truth,.05)
        assert matches==read(cached)['baseline']
        pos=sorted(t for t in matches['HH']['unmatched_predictions'] if any(abs(t-r)<=.05+1e-12 for r in truth['SD']))
        neg=sorted(r['matched_prediction'] for r in matches['HH']['reference'] if r['matched_prediction'] is not None)
        row=dict(id=spec['id'], duration_seconds=spec['duration_seconds'], frames=len(mono),
            source_mono=str(source), input=str(target), prediction=str(prediction), reference=spec['annotation'],
            mix=spec['mix'], prior_run=str(folder/'run.json'), cached_assignments=str(cached),
            mixture_mono_peak_divisor=peak, additional_gain=1, original_mono_fold_exact=True,
            positives=pos, negatives=neg, eligible=len(pos)>=10 and len(neg)>=10,
            brush='brushes' in spec['id'])
        tracks.append(row)
        for file in [source,prediction,cached,folder/'run.json',Path(spec['annotation']),Path(spec['mix']),target]:
            protected[str(file)]=sha(file)
    assert len(tracks)==6 and abs(sum(t['duration_seconds'] for t in tracks)-446.32)<1e-10
    protocol=dict(utc=datetime.now(timezone.utc).isoformat(),
        hypothesis='The unchanged snare/HH energy feature retains discrimination on cached practical mixed-recording pipeline inputs.',
        source_audit=str(AUDIT), baseline_validation=str(VALIDATION),
        input_contract='Cached htdemucs_ft mono FLOAT drum PCM duplicated exactly into two channels, gain1, no normalization/resampling; cached ADTOF events unchanged.',
        input_history='Previous .5*(wet+accompaniment) stereo mixture divided by its mono peak, htdemucs_ft then mean to mono. Source/run hashes and peak recomputed; separation not rerun.',
        comparison_limit='Both upstream separation and stereo-to-duplicated-mono differ from original wet stereo diagnostic; no causal isolation of either.',
        settings=previous['settings'], feature=previous['feature'], gates=gates, tracks=tracks,
        weights=str(AUDIT/'weights/drumsep-six.ckpt'), checkpoint_sha256=previous['checkpoint_sha256'],
        source_revision=previous['source_revision'], code_sha256=sha(Path(__file__)),
        review='Per recording, two lowest-scoring positive cases and two highest-scoring matched HH; ties by timestamp, take all if fewer. One-second mix/cached-drum/snare/HH/tom clips, clipped at edges. No audio relabeling.',
        overlap='Previously exposed six ENST recordings; exact training exclusion unproved. Not independent validation.',
        prohibition='No changed notes, blanket suppression, threshold/window/gain/overlap sweep, checkpoint variants, track replacement, KLEWS or Adapt.',
        protected=[dict(path=p,sha256=h) for p,h in sorted(protected.items())])
    save(root/'protocol.json',protocol)
    print({'protocol_sha256':sha(root/'protocol.json'),'tracks':[{k:t[k] for k in ['id','eligible']}|{'positive':len(t['positives']),'negative':len(t['negatives'])} for t in tracks]},flush=True)


def checked(root):
    p=read(root/'protocol.json')
    assert sha(Path(__file__))==p['code_sha256']
    for e in p['protected']: assert sha(e['path'])==e['sha256'],e['path']
    return p


def infer(root):
    p=checked(root)
    out=root/'separated';out.mkdir(exist_ok=False)
    config,ns=native(AUDIT)
    torch.set_num_threads(2);torch.manual_seed(0);np.random.seed(0)
    torch.backends.cudnn.benchmark=False
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.use_deterministic_algorithms(True)
    device=torch.device('cuda:0');torch.cuda.init()
    model=ns['TFC_TDF_net'](config)
    state=torch.load(p['weights'],map_location='cpu',weights_only=True)
    result=model.load_state_dict(state,strict=True)
    assert not result.missing_keys and not result.unexpected_keys
    prior=read(AUDIT/'separated-02/strict-load.json')
    import hashlib
    assert len(state)==len(prior['entries'])==319
    for e in prior['entries']:
        v=model.state_dict()[e['key']]
        assert torch.equal(v,state[e['key']]) and torch.isfinite(v).all()
        assert hashlib.sha256(v.numpy().tobytes()).hexdigest()==e['sha256']
    save(out/'strict-load.json',dict(tensors=319,scalar_values=sum(v.numel() for v in state.values()),
        matches_prior_load_hash=sha(AUDIT/'separated-02/strict-load.json'),weights_sha256=sha(p['weights'])))
    del state
    model.eval().to(device);runs=[]
    for track in p['tracks']:
        folder=out/track['id'];folder.mkdir(exist_ok=False)
        audio,sr=sf.read(track['input'],dtype='float32',always_2d=True)
        assert audio.shape==(track['frames'],2) and sr==44100
        torch.manual_seed(0);np.random.seed(0);torch.cuda.reset_peak_memory_stats(device)
        started=time.perf_counter()
        stems=ns['demix'](config,model,audio.T.copy(),device,'mdx23c',True)
        torch.cuda.synchronize();elapsed=time.perf_counter()-started
        outputs=[]
        for name in STEMS:
            value=stems[name].T
            assert value.shape==audio.shape and np.isfinite(value).all()
            target=folder/(name+'.wav');sf.write(target,value,sr,subtype='FLOAT')
            back,rate=sf.read(target,dtype='float32',always_2d=True)
            assert rate==sr and np.array_equal(back,value)
            outputs.append(dict(stem=name,path=str(target),sha256=sha(target),frames=len(value)))
        row=dict(id=track['id'],outputs=outputs,seconds=elapsed,
            peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(device),
            peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved(device))
        save(folder/'completed.json',row);runs.append(row)
        print({'id':track['id'],'seconds':elapsed,'complete_stems':6},flush=True)
        del stems
    checked(root)
    save(out/'completed.json',dict(protocol_sha256=sha(root/'protocol.json'),tracks=runs))


def describe(rows):
    pos=np.array([r['sd_over_hh_db'] for r in rows if r['group']=='false_hh_near_sd'])
    neg=np.array([r['sd_over_hh_db'] for r in rows if r['group']=='matched_hh'])
    def stats(a):
        return dict(count=len(a),median_db=float(np.median(a)) if len(a) else None,
                    above_zero=int((a>0).sum()),min_db=float(a.min()) if len(a) else None,max_db=float(a.max()) if len(a) else None)
    diff=pos[:,None]-neg[None,:]
    auc=float(np.mean((diff>0)+.5*(diff==0))) if diff.size else None
    checks=dict(auc_at_least_point8=auc is not None and auc>=.8,
        false_hh_median_above_zero=bool(len(pos) and np.median(pos)>0),
        matched_hh_median_below_zero=bool(len(neg) and np.median(neg)<0))
    eligible=len(pos)>=10 and len(neg)>=10
    return dict(positive=stats(pos),negative=stats(neg),auroc=auc,eligible=eligible,
                gates=checks,status=('pass' if all(checks.values()) else 'fail') if eligible else 'inconclusive_small_group',
                all_hh=len(rows),groups=dict(Counter(r['group'] for r in rows)))


def score(root):
    p=checked(root);completed=read(root/'separated/completed.json')
    assert completed['protocol_sha256']==sha(root/'protocol.json')
    out=root/'family-evidence';out.mkdir(exist_ok=False)
    allrows=[];summaries=[]
    for track,run in zip(p['tracks'],completed['tracks']):
        assert track['id']==run['id']
        truth=truth_from(Path(track['reference']));matches=event_assignments(read(track['prediction']),truth,.05)
        assert matches==read(track['cached_assignments'])['baseline']
        stems={}
        for e in run['outputs']:
            assert sha(e['path'])==e['sha256']
            stems[e['stem']],sr=sf.read(e['path'],dtype='float32',always_2d=True)
            assert sr==44100
        rows=[]
        for h in read(track['prediction'])['hitObjects']:
            if h['component']!='hihat':continue
            t=h['time']/1000
            group='false_hh_near_sd' if t in track['positives'] else 'matched_hh' if t in track['negatives'] else 'other_false_hh'
            rows.append(dict(track=track['id'],time_seconds=t,group=group,
                source_references_within50ms={f:[float(x) for x in times if abs(x-t)<=.05+1e-12] for f,times in truth.items()},
                **feature_values(stems,t,sr)))
        folder=out/track['id'];folder.mkdir(exist_ok=False)
        save(folder/'events.json',rows);summary=dict(id=track['id'],brush=track['brush'],**describe(rows))
        assert summary['eligible']==track['eligible']
        save(folder/'metrics.json',summary);summaries.append(summary);allrows.extend(rows)
    pooled=describe(allrows);eligible=[r for r in summaries if r['eligible']]
    breadth=len(eligible)>=2 and any(not r['brush'] for r in eligible)
    numerical=pooled['status']=='pass' and all(r['status']=='pass' for r in eligible)
    status='fail' if not numerical else 'pass' if breadth else 'inconclusive_breadth'
    result=dict(protocol_sha256=sha(root/'protocol.json'),tracks=summaries,pooled=pooled,
        eligible_recordings=len(eligible),breadth_gate_pass=breadth,overall_status=status,
        interpretation='Diagnostic ranking only, no changed transcription. Previously exposed data and unknown training overlap.')
    save(out/'events.json',allrows);save(out/'metrics.json',result)
    print(result,flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','infer','score'])
    parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve()
    assert root.parent==BASE.resolve() and root.name=='2026-10-16-drumsep-mixed-validation-01'
    {'prepare':prepare,'infer':infer,'score':score}[args.action](root)
