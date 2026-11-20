"""One fixed original-wet-drum control; previous separation and models stay frozen."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np
import soundfile as sf

from compare_adt_str import BASE, save, verify
from compare_snare_addition import RULE, add_snares, audit_additions, scoped_root
from evaluate_mdb import drum_family
from probe_residual_input import event_assignments, truth_from
from score_timing import evaluate_timing, match_timing
from transcribe import sha256
from validate_snare_addition import ADTOF, REPO, checked, oaf

PRIOR = BASE / '2026-10-15-snare-validation-01'
TRACK = 'enst-drummer_1-110_minus-one_musette_brushes'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def original_component(wet, mixture_peak):
    """Exactly the wet component's fixed gain before prior Demucs, then mono."""
    if wet.dtype != np.float32 or wet.ndim != 2 or wet.shape[1] != 2 or not len(wet):
        raise ValueError('Expected stereo float32 original wet drums')
    if not np.isfinite(wet).all() or not np.isfinite(mixture_peak) or mixture_peak <= 1e-10:
        raise ValueError('Nonfinite PCM or invalid frozen mixture gain')
    return np.mean((np.float32(.5) * wet.T.copy()) / mixture_peak, axis=0)


def prepare(root):
    root = scoped_root(root)
    verify(read(root / 'evidence/prior-preservation.json')['files'])
    old = read(PRIOR / 'protocol.json')
    spec = next(r for r in old['tracks'] if r['id'] == TRACK)
    assert spec['admitted'] and spec['dataset'] == 'ENST'
    out = root / 'inputs'; out.mkdir(exist_ok=False)
    paths = {role: Path(p) for role, p in spec['source_copies'].items()}
    paths.update(reference=Path(spec['annotation']), source_events=Path(spec['mix']).with_name('reference-events.json'),
                 prepared_mix=Path(spec['mix']), separated=PRIOR / 'adtof' / TRACK / 'drums.wav')
    copies = {}
    for role, source in paths.items():
        folder = out / role; folder.mkdir()
        target = folder / source.name; shutil.copy2(source, target)
        assert sha256(target) == sha256(source); copies[role] = str(target)
    wet, sr = sf.read(copies['wet'], dtype='float32', always_2d=True)
    acc, ar = sf.read(copies['accompaniment'], dtype='float32', always_2d=True)
    mix, mr = sf.read(copies['prepared_mix'], dtype='float32', always_2d=True)
    stem, dr = sf.read(copies['separated'], dtype='float32')
    assert sr == ar == mr == dr == 44100 and wet.shape == acc.shape == mix.shape == (len(stem), 2)
    assert np.array_equal(mix, np.float32(.5) * (wet + acc))
    run = read(PRIOR / 'adtof' / TRACK / 'run.json')
    peak = float(np.abs(mix.T.mean(axis=0)).max()); assert peak == run['mono_peak_divisor']
    original = original_component(wet, peak)
    sf.write(out / 'original-component.wav', original, sr, subtype='FLOAT')
    reread, rate = sf.read(out / 'original-component.wav', dtype='float32')
    assert rate == sr and np.array_equal(original, reread)
    files = list(paths.values()) + [p for p in out.rglob('*') if p.is_file()]
    files += [Path(__file__), Path(__file__).with_name('test_enst_brush_input.py'), root / 'evidence/recovery-measurements.json']
    files += [PRIOR / 'protocol.json', PRIOR / 'comparison/metrics.json']
    for arm in ['adtof', 'oaf', 'comparison']:
        files += [p for p in (PRIOR / arm / TRACK).iterdir() if p.is_file()]
    protected = {e['path']:e['sha256'] for e in old['protected']}
    protected.update({str(p):sha256(p) for p in files})
    protocol = {
        'utc':datetime.now(timezone.utc).isoformat(), 'rule':RULE, 'track':TRACK,
        'hypothesis':'Input differences contribute to brush/snare/tom errors; measure same-checkpoint behavior on original wet drums versus the saved separated stem.',
        'selection':'One 75.16s brush recording fixed by the preceding handoff because it contributed 28/35 false additions. Diagnostic selection, not an independent holdout. No substitutions.',
        'input_formula':'mean((float32(.5) * original_stereo_wet.T.copy()) / frozen_mixture_mono_peak, axis=0). No new peak normalization, shift, filter or separation. Native OaF whole-record normalization remains unchanged.',
        'mixture_peak':peak, 'inputs':copies, 'original_input':str(out/'original-component.wav'),
        'annotation':copies['reference'], 'duration_seconds':len(stem)/sr,
        'settings':old['settings'],
        'measurements':'All-family and SD/TT precision, recall, F1, timing at25/50ms for ADTOF and native E-GMD separately; unchanged merger as secondary diagnostic only. Reuse cached separated outputs. Save all assignments and reference gain/loss sets.',
        'case_followup':'For all28 prior false additions and all37 prior matched additions, report original-input native snare/addition presence within50ms. Descriptive correspondence may reuse nearby predictions, not a one-to-one true-positive score. Audit all original false additions with source labels. No labels/masks/thresholds fitted.',
        'interpretation':'Better original-input scores support an input-condition contribution, but jointly remove separator artifacts and residual accompaniment; they cannot isolate a separator-only cause. Persisting original-input errors show input replacement alone is insufficient on this recording. Report discordant models/families rather than pooling them into a winner.',
        'completion_criteria':'Verify frozen hashes, exact original-input PCM, native decoding and reproduced cached scores; finish both fixed inference arms, inspect error correspondence and report all outcomes. No minimum-gain promotion gate: original drum-only audio is an oracle diagnostic unavailable for arbitrary full songs.',
        'stop':'One input contrast only. No gain/radius/threshold/decoder sweeps, new separation, training/downloads, additional recordings or m!sa drafts. Previous merger rejection remains final. No app/default/user-chart changes.',
        'limits':old['overlap']+' TF2.13 execution is not historical TF1 parity. Labels/bleed/brush technique remain imperfect evidence; source mic is not isolated ground truth.',
        'protected':[{'path':p,'sha256':h} for p,h in sorted(protected.items())],
    }
    save(root/'protocol.json', protocol)
    print(json.dumps({'protocol_entries':len(protected),'mixture_peak':peak,'seconds':protocol['duration_seconds'],'original_peak':float(np.max(np.abs(original)))}))


def adtof(root):
    protocol = checked(root)
    out = root/'adtof'; out.mkdir(exist_ok=False)
    save(out/'started.json', {'utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':sha256(root/'protocol.json')})
    import os
    assert os.environ.get('ADTOF_USE_KERAS_GRU','0') == '0'
    import torch
    from frontend_adtof_reference import features
    from decode_adtof_reference import decode_activations
    from model_adtof_reference import replace_pooling
    from transcribe_reference import reference_preflight
    sys.path.insert(0,str(ADTOF/'src'))
    from adtof_pytorch import create_frame_rnn_model, load_pytorch_weights
    torch.set_num_threads(2); torch.manual_seed(0); np.random.seed(0)
    model=replace_pooling(load_pytorch_weights(create_frame_rnn_model(84),str(reference_preflight(ADTOF)),strict=True)).eval()
    folder=out/TRACK;folder.mkdir();target=folder/'drums.wav'
    shutil.copy2(protocol['original_input'],target);assert sha256(target)==sha256(Path(protocol['original_input']))
    pcm,sr=sf.read(target,dtype='float32');assert sr==44100
    start=time.perf_counter();x=features(pcm);np.save(folder/'features.npy',x)
    with torch.no_grad():act=model(torch.from_numpy(x).unsqueeze(0)).cpu().numpy()
    assert np.isfinite(act).all();np.save(folder/'activations.npy',act)
    chart=decode_activations(act);save(folder/'predictions.json',chart)
    row={'id':TRACK,'prediction_sha256':sha256(folder/'predictions.json'),'stem_sha256':sha256(target),'feature_sha256':sha256(folder/'features.npy'),'activation_sha256':sha256(folder/'activations.npy'),'seconds':time.perf_counter()-start,'notes':len(chart['hitObjects'])}
    save(folder/'run.json',row);verify(protocol['protected'])
    save(out/'completed.json',{'protocol_sha256':sha256(root/'protocol.json'),'tracks':[row]});print(json.dumps(row))


def nearby(predictions, t):
    return [h for h in predictions if h.get('groove_pitch')==38 and abs(h['time']/1000-t)<=.05+1e-9]


def score(root):
    protocol=checked(root);out=root/'comparison';out.mkdir(exist_ok=False)
    truth=truth_from(Path(protocol['annotation']));result={};all_assignments={};additions_by_input={}
    for arm in ['adtof','oaf']:
        assert read(root/arm/'completed.json')['protocol_sha256']==sha256(root/'protocol.json')
    for condition,base in [('separated',PRIOR),('original',root)]:
        folder=out/condition;folder.mkdir()
        a=read(base/'adtof'/TRACK/'predictions.json');b=read(base/'oaf'/TRACK/'predictions.json')
        merged,decisions=add_snares(a,b);save(folder/'merged.json',merged);save(folder/'decisions.json',decisions)
        if condition=='separated':assert merged==read(PRIOR/'comparison'/TRACK/'predictions.json')
        scores={};assignments={}
        for ms in ['25','50']:
            scores[ms]={model:evaluate_timing(chart,truth,int(ms)/1000) for model,chart in [('adtof',a),('oaf',b),('merged',merged)]}
            assignments[ms]={model:event_assignments(chart,truth,int(ms)/1000) for model,chart in [('adtof',a),('oaf',b),('merged',merged)]}
            save(folder/f'events-{ms}ms.json',assignments[ms])
        for ms in ['25','50']:
            if condition=='separated':
                previous=read(PRIOR/'comparison'/TRACK/'metrics.json')['scores'][ms]
                assert scores[ms]['adtof']==previous['baseline'] and scores[ms]['merged']==previous['candidate']
        audit_assignments={ms:{'baseline':v['adtof'],'candidate':v['merged']} for ms,v in assignments.items()}
        additions=audit_additions(a,b,decisions,truth,audit_assignments,base/'oaf'/TRACK/'native-outputs.npz')
        save(folder/'additions.json',additions);additions_by_input[condition]=additions
        result[condition]={'scores':scores,'decisions':dict(Counter(d['decision'] for d in decisions)),
                           'additions':{ms:{'total':len(additions),'matched':sum(x['matches'][ms] is not None for x in additions),'false':sum(x['matches'][ms] is None for x in additions)} for ms in ['25','50']}}
        all_assignments[condition]=assignments
    changes={}
    for model in ['adtof','oaf','merged']:
        changes[model]={}
        for family in sorted(truth):
            a=all_assignments['separated']['50'][model][family]['reference'];b=all_assignments['original']['50'][model][family]['reference']
            changes[model][family]={'gained':[y for x,y in zip(a,b) if x['matched_prediction'] is None and y['matched_prediction'] is not None],
                                    'lost':[x for x,y in zip(a,b) if x['matched_prediction'] is not None and y['matched_prediction'] is None]}
    original_native=read(root/'oaf'/TRACK/'predictions.json')['hitObjects']
    original_added=[h for h in read(out/'original/merged.json')['hitObjects'] if h.get('groove_pitch')==38]
    correspondence=[{**a,'original_native_snare_within_50ms':nearby(original_native,a['time_ms']/1000),
                     'original_added_snare_within_50ms':nearby(original_added,a['time_ms']/1000)} for a in additions_by_input['separated']]
    save(out/'reference-changes-50ms.json',changes)
    save(out/'prior-addition-correspondence.json',{'scope':protocol['case_followup'],'events':correspondence})
    save(out/'original-false-additions.json',{'events':[a for a in additions_by_input['original'] if a['matches']['50'] is None]})
    summary={'protocol_sha256':sha256(root/'protocol.json'),'track':TRACK,'duration_seconds':protocol['duration_seconds'],'conditions':result,
             'diagnostic_only':True,'promotion':'Forbidden by protocol; prior merger rejection unchanged'}
    save(out/'metrics.json',summary);verify(protocol['protected'])
    print(json.dumps({c:{m:v['scores']['50'][m]['micro'] for m in ['adtof','oaf','merged']} for c,v in result.items()},indent=2))
    print(json.dumps({c:v['additions'] for c,v in result.items()}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','adtof','oaf','score']);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();globals()[args.action](scoped_root(args.root))
