"""Find auditable acoustic near-duplicates across chart cymbal-pad proxies.

Original author drum stem only; no model event predictions or learned embeddings.
A high similarity flags review, not a verified instrument identity or edit.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil

import numpy as np
from scipy.signal import correlate,correlation_lags,resample_poly
import soundfile as sf

from transcribe import sha256
from transcribe_reference import write_json


def waveform_similarity(a,b,sr=16000):
    a=np.asarray(a,dtype=float)-np.mean(a)
    b=np.asarray(b,dtype=float)-np.mean(b)
    norm=np.linalg.norm(a)*np.linalg.norm(b)
    if norm<1e-12:return {'correlation':None,'lag_ms':None}
    corr=correlate(b,a,mode='full',method='fft')/norm
    lags=correlation_lags(len(b),len(a))
    valid=np.abs(lags)<=round(sr*.005)
    i=int(np.argmax(corr[valid]))
    return {'correlation':float(np.clip(corr[valid][i],-1,1)),'lag_ms':float(lags[valid][i]*1000/sr)}


def screen(benchmark,out):
    benchmark,out=benchmark.resolve(),out.resolve()
    if out.drive.upper()!='C:' or out.is_relative_to(benchmark):raise ValueError('New scoped C: output required')
    refpath=benchmark/'prepared-v2/adapt/reference.json'
    manifest=json.loads((benchmark/'prepared-v2/manifest.json').read_text())
    selected=next(s for s in manifest['songs'] if s['id']=='adapt')
    if sha256(refpath)!=selected['reference_sha256']:raise ValueError('Reference changed')
    ref=json.loads(refpath.read_text())
    audio=Path(ref['chart']).parent/'drums.ogg'
    src=next(s for s in ref['audio']['sources'] if s['name']=='drums.ogg')
    if sha256(audio)!=src['sha256']:raise ValueError('Original drum stem changed')
    out.mkdir(exist_ok=False)
    (out/'clips').mkdir()
    write_json(out/'protocol.json',{'created_utc':datetime.now(timezone.utc).isoformat(),
        'purpose':'Check for near-identical original-drum excerpts crossing the YellowCymbal=HH versus Blue/GreenCymbal=CY proxy boundary.',
        'selection':'All cymbal chart events without any other chart onset in [-30,+90] ms; pairs at least one second apart.',
        'features':'80 ms mono excerpts starting at unchanged chart time, resampled to 16 kHz; 24 log frequency power bins from 100 to 7800 Hz; centered log spectrum cosine is descriptive only and does not filter pairs.',
        'verification':'Exhaustive waveform correlations over eligible event pairs, within +/-5 ms lag. Signed normalized cross-correlation >=.98 defines a review candidate. Same-pad pairs provide a reuse control.',
        'limits':'No claim of true HH/CY identity, exact onset, zero ring/bleed or complete chart annotation. No model settings change or reference relabeling.',
        'reference_sha256':sha256(refpath),'original_drums_sha256':sha256(audio),'code_sha256':sha256(Path(__file__))})
    shutil.copy2(Path(__file__),out/Path(__file__).name)
    y,sr=sf.read(audio,dtype='float32',always_2d=True)
    mono=resample_poly(y.mean(axis=1),160,441) if sr==44100 else None
    if mono is None:raise ValueError('This bounded audit expects the original 44.1 kHz package')
    events=ref['events']; candidates=[];signals=[];features=[]
    edges=np.geomspace(100,7800,25)
    freq=np.fft.rfftfreq(1280,1/16000)
    for index,event in enumerate(events):
        if not event['pad'].endswith('Cymbal'):continue
        t=event['time_seconds']
        if any(i!=index and -.03<=e['time_seconds']-t<=.09 for i,e in enumerate(events)):continue
        start=round(t*16000);signal=mono[start:start+1280]
        if len(signal)!=1280 or np.sqrt(np.mean(signal**2))<1e-6:continue
        spectrum=np.abs(np.fft.rfft(signal*np.hanning(len(signal))))**2
        feature=np.log10(np.array([np.mean(spectrum[(freq>=lo)&(freq<hi)]) for lo,hi in zip(edges[:-1],edges[1:])])+1e-12)
        feature-=feature.mean();feature/=max(float(np.linalg.norm(feature)),1e-12)
        candidates.append({'time_seconds':t,'pad':event['pad'],'family_proxy':event['family_proxy']})
        signals.append(signal);features.append(feature)
    features=np.array(features);similarities=features@features.T
    pairs={'cross_family':[],'same_pad':[]}
    for i,a in enumerate(candidates):
        for j in range(i+1,len(candidates)):
            b=candidates[j]
            if b['time_seconds']-a['time_seconds']<1:continue
            group='cross_family' if a['family_proxy']!=b['family_proxy'] else 'same_pad' if a['pad']==b['pad'] else None
            if group is None:continue
            match=waveform_similarity(signals[i],signals[j])
            pairs[group].append({'a':i,'b':j,'log_spectrum_cosine':float(similarities[i,j]),**match})
    result={'candidates':candidates,'groups':{}}
    for group,rows in pairs.items():
        rows.sort(key=lambda r:r['correlation'] if r['correlation'] is not None else -2,reverse=True)
        selected_rows=rows[:5]
        for k,row in enumerate(selected_rows):
            row['events']=[candidates[row['a']],candidates[row['b']]]
            row['clips']=[]
            for side,idx in [('a',row['a']),('b',row['b'])]:
                t=candidates[idx]['time_seconds'];start=max(0,round((t-.2)*sr));end=min(len(y),round((t+.5)*sr))
                path=out/'clips'/f'{group}-{k+1}-{side}.wav'
                sf.write(path,y[start:end],sr,subtype='FLOAT')
                row['clips'].append({'path':str(path),'sha256':sha256(path),'start_sample':start,'frames':end-start,'source_time_seconds':t})
        result['groups'][group]={'pairs_compared':len(rows),'pairs_at_or_above_point_98':sum(r['correlation'] is not None and r['correlation']>=.98 for r in rows),
                                  'top_five':selected_rows}
    write_json(out/'similarity.json',result)
    print(json.dumps({'candidate_count':len(candidates),'pad_counts':{p:sum(c['pad']==p for c in candidates) for p in ['YellowCymbal','BlueCymbal','GreenCymbal']},
        'groups':{g:{'pairs_compared':r['pairs_compared'],'pairs_ge_point98':r['pairs_at_or_above_point_98'],
                     'top_correlation':r['top_five'][0]['correlation'] if r['top_five'] else None,
                     'top_events':r['top_five'][0]['events'] if r['top_five'] else None} for g,r in result['groups'].items()}}),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--benchmark',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    a=ap.parse_args();screen(a.benchmark,a.output_dir)
