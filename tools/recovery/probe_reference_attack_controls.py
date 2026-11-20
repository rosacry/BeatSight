"""Test whether the existing reference attack screen is drum-specific.

Uses Adapt's original packaged stems with frozen chart windows. Does not inspect
model events, infer new ones, alter references, or assert stem-withheld audio is
verified drum-free. Outputs go to a new, separate C: experiment.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

from audit_clone_hero_reference import LAGS, METHOD, attack_envelope, attack_profile
from transcribe import sha256
from transcribe_reference import write_json


PROTOCOL = {
    'question': 'Does the frozen mixed-audio snare attack screen isolate drum evidence, or can other packaged instruments produce a similar lag?',
    'song': 'adapt',
    'input_conditions': ['original_mix', 'original_drums', 'drums_stem_withheld', 'silence'],
    'window_selection': 'Unchanged beginning/middle/end windows from the prior validated audit; no model-error selection',
    'screen': METHOD,
    'measurements': 'Same peak lag and individual support per window; also curve cosine similarity between original drums and withheld condition',
    'decisions': [
        'If withheld inputs show similar lag peaks, the detector is not drum-specific and cannot certify acoustic identity.',
        'If original drums fail the old support gate, gate failure alone cannot be treated as proof of bad reference timing.',
        'No stem result automatically admits a reference or supplies an offset correction.',
    ],
    'limitations': 'Packaged stem names are author provenance, not independent guarantees of zero bleed/percussion. This is a detector-specificity control, not a new transcription or no-drum benchmark.',
    'reserved_policy': 'Adapt remains reserved from model/threshold tuning; this diagnostic changes no candidate setting and derives no transcription rule.',
}


def reconstruct_parts(ref):
    """Mirror the documented package summation, preserving time zero and gain."""
    info = ref['audio']
    size, sr = info['frames'], info['sample_rate']
    full = np.zeros((size, 2), dtype=np.float32)
    drums = np.zeros_like(full)
    other = np.zeros_like(full)
    files = []
    drum_count = 0
    for src in info['sources']:
        path = Path(ref['chart']).parent / src['name']
        if sha256(path) != src['sha256']:
            raise ValueError('Source audio hash changed')
        a, rate = sf.read(path, dtype='float32', always_2d=True)
        if rate != sr or len(a) != src['frames'] or a.shape[1] not in [1,2] or not np.isfinite(a).all():
            raise ValueError('Unexpected source shape or sample rate')
        if a.shape[1] == 1:
            a = np.repeat(a, 2, axis=1)
        full[:len(a)] += a
        if Path(src['name']).stem == 'drums':
            drums[:len(a)] += a
            drum_count += 1
        else:
            other[:len(a)] += a
        files.append({'path': str(path), 'sha256': src['sha256']})
    if drum_count != 1:
        raise ValueError('Exactly one original drums source required')
    gain = info['linear_gain']
    return {k: a * gain for k, a in [('original_mix',full),('original_drums',drums),('drums_stem_withheld',other)]}, sr, files


def safe_profile(times, values, hits):
    if not hits:
        return {'status': 'no anchors', 'notes': 0}
    if not np.any(values):
        return {'status': 'silent; no measurable lag', 'notes': len(hits), 'peak_lag_ms': None,
                'individual_support_within_10_ms': None, 'profile': None}
    return {'status': 'measured', **attack_profile(times, values, hits)}


def screen_decision(windows):
    if any(w.get('status') != 'measured' for w in windows):
        return {'candidate_ms': None, 'passes': False, 'reason': 'At least one window unmeasurable'}
    selected = 5 * round(windows[0]['peak_lag_ms'] / 5)
    return {'candidate_ms': selected,
            'passes': all(w['notes'] >= 5 and abs(w['peak_lag_ms']-selected) <= 10
                          and w['individual_support_within_10_ms'] >= .6 for w in windows)}


def probe(benchmark, prior_audit, output):
    benchmark, prior_audit, output = benchmark.resolve(), prior_audit.resolve(), output.resolve()
    if output.drive.upper() != 'C:' or output.is_relative_to(benchmark) or output.is_relative_to(prior_audit):
        raise ValueError('Choose a new separate C: experiment root')
    ref_path = benchmark/'prepared-v2/adapt/reference.json'
    prepared_path = benchmark/'prepared-v2/manifest.json'
    previous_path = prior_audit/'validated/audit.json'
    ref = json.loads(ref_path.read_text())
    prepared = json.loads(prepared_path.read_text())
    selected = next(s for s in prepared['songs'] if s['id']=='adapt')
    if sha256(ref_path) != selected['reference_sha256']:
        raise ValueError('Reference hash changed')
    previous = next(s for s in json.loads(previous_path.read_text())['songs'] if s['id']=='adapt')
    output.mkdir(exist_ok=False)
    (output/'evidence').mkdir()
    (output/'clips').mkdir()
    write_json(output/'protocol.json', {'created_utc':datetime.now(timezone.utc).isoformat(),
        **PROTOCOL,'benchmark':str(benchmark),'prior_audit':str(prior_audit),
        'reference_sha256':sha256(ref_path),'prior_audit_sha256':sha256(previous_path),
        'code_sha256':{p.name:sha256(p) for p in [Path(__file__), Path(__file__).parent/'audit_clone_hero_reference.py']}})
    for path in [Path(__file__), Path(__file__).parent/'audit_clone_hero_reference.py']:
        shutil.copy2(path,output/'evidence'/path.name)
    arrays,sr,files = reconstruct_parts(ref)
    original_path = ref_path.parent/'mix.wav'
    if sha256(original_path) != selected['audio']['sha256']:
        raise ValueError('Original prepared audio changed')
    original, rate = sf.read(original_path,dtype='float32',always_2d=True)
    if rate != sr or not np.array_equal(original,arrays['original_mix']):
        raise ValueError('Original summation reconstruction differs from prepared PCM')
    reconstruction_error = float(np.max(np.abs(arrays['original_drums']+arrays['drums_stem_withheld']-original)))
    arrays['silence'] = np.zeros_like(arrays['original_mix'])
    result = {'source_files':files,'original_prepared_pcm_reconstructed_exactly':True,
              'parts_sum_max_absolute_rounding_error':reconstruction_error,'sample_rate':sr,
              'conditions':{},'paired_windows':[],'clips':[]}
    fig,axes = plt.subplots(3,1,figsize=(12,9),constrained_layout=True)
    for condition, audio in arrays.items():
        times, values = attack_envelope(audio,sr)
        rows=[]
        for index,w in enumerate(previous['windows']):
            hits=w['anchor_times_seconds']
            row={'name':w['name'],'anchor_times_seconds':hits,**safe_profile(times,values,hits)}
            rows.append(row)
            if row.get('profile') is not None:
                axes[index].plot(LAGS*1000,row['profile'],label=condition)
            if condition != 'silence':
                begin=round(w['start_seconds']*sr)
                clip=audio[begin:begin+12*sr]
                path=output/'clips'/f"adapt-{w['name']}.{condition}.wav"
                sf.write(path,clip,sr,subtype='FLOAT')
                result['clips'].append({'path':str(path),'sha256':sha256(path),'condition':condition,
                    'start_sample':begin,'frames':len(clip),'peak':float(np.abs(clip).max())})
        result['conditions'][condition]={'windows':rows,'screen':screen_decision(rows)}
        print(json.dumps({'condition':condition,'screen':result['conditions'][condition]['screen'],
            'windows':[{k:w.get(k) for k in ['name','notes','status','peak_lag_ms','individual_support_within_10_ms']} for w in rows]}),flush=True)
    for index,w in enumerate(previous['windows']):
        a=result['conditions']['original_drums']['windows'][index]
        b=result['conditions']['drums_stem_withheld']['windows'][index]
        av,bv=np.array(a['profile']),np.array(b['profile'])
        similarity=float(np.dot(av,bv)/(np.linalg.norm(av)*np.linalg.norm(bv)))
        result['paired_windows'].append({'name':w['name'],'drums_vs_withheld_peak_difference_ms':b['peak_lag_ms']-a['peak_lag_ms'],
            'drums_vs_withheld_profile_cosine_similarity':similarity})
        axes[index].axvline(0,color='black',linestyle='--',alpha=.5)
        axes[index].set(title=f"Adapt {w['name']} — same chart anchors, original stems",xlabel='lag from chart (ms)',ylabel='mean normalized rise')
        axes[index].legend()
    fig.savefig(output/'adapt-source-control.png',dpi=140)
    plt.close(fig)
    write_json(output/'controls.json',result)
    print(json.dumps({'paired_windows':result['paired_windows'],'parts_rounding_error':reconstruction_error}),flush=True)


def extend_snare_audit(benchmark, output):
    """Inspect all chart snare anchors, without fitting a shift or using outputs."""
    benchmark,output=benchmark.resolve(),output.resolve()
    if output.drive.upper()!='C:' or output.is_relative_to(benchmark):
        raise ValueError('Separate scoped C: output required')
    prior=json.loads((output/'protocol.json').read_text())
    ref_path=benchmark/'prepared-v2/adapt/reference.json'
    if sha256(ref_path)!=prior['reference_sha256']:
        raise ValueError('Reference changed since source control')
    ref=json.loads(ref_path.read_text())
    source=next(s for s in ref['audio']['sources'] if s['name']=='drums.ogg')
    audio=Path(ref['chart']).parent/source['name']
    if sha256(audio)!=source['sha256']:
        raise ValueError('Original drum stem changed')
    out=output/'full-song'
    out.mkdir(exist_ok=False)
    write_json(out/'protocol.json',{'created_utc':datetime.now(timezone.utc).isoformat(),
        'purpose':'Adaptive follow-up after the original-stem control passed; screen every original snare anchor for temporal drift',
        'selection':'All original SD chart times; fixed 30-second bins from song time zero; no exclusion by model error',
        'rule':'Reuse unchanged attack algorithm. Report support within +/-10 and +/-25 ms of ORIGINAL chart time, not a fitted shift. Individual maxima may be other drum hits.',
        'reference_sha256':sha256(ref_path),'source_sha256':sha256(audio),
        'code_sha256':sha256(Path(__file__)),'no_model_predictions':True})
    shutil.copy2(Path(__file__),out/Path(__file__).name)
    y,sr=sf.read(audio,dtype='float32',always_2d=True)
    times,values=attack_envelope(y,sr)
    hits=sorted(set(e['time_seconds'] for e in ref['events'] if e['family_proxy']=='SD'))
    overall=safe_profile(times,values,hits)
    lags=np.asarray(overall['individual_peak_lags_ms'])
    overall['strongest_rise_within_10_ms_of_original_chart']=int(np.sum(np.abs(lags)<=10))
    overall['strongest_rise_within_25_ms_of_original_chart']=int(np.sum(np.abs(lags)<=25))
    bins=[]
    for start in np.arange(0,len(y)/sr,30):
        selected=[t for t in hits if start<=t<start+30]
        row={'start_seconds':float(start),'end_seconds':float(min(start+30,len(y)/sr)),
             **safe_profile(times,values,selected)}
        if row.get('status')=='measured':
            a=np.array(row['individual_peak_lags_ms'])
            row['within_10_ms_of_original_chart']=int(np.sum(np.abs(a)<=10))
            row['within_25_ms_of_original_chart']=int(np.sum(np.abs(a)<=25))
        bins.append(row)
    result={'overall':overall,'bins':bins,'anchors':[
        {'reference_time_seconds':t,'strongest_rise_lag_ms':float(lag)} for t,lag in zip(hits,lags)],
        'interpretation':'Original-drum temporal support only. Chart snare labels, missed notes, non-snare identity and training exclusion are not established. No reference shift accepted.'}
    write_json(out/'snare-timing.json',result)
    fig,axes=plt.subplots(2,1,figsize=(12,8),constrained_layout=True)
    axes[0].scatter(hits,lags,s=13,alpha=.65)
    axes[0].axhspan(-25,25,alpha=.12,color='green')
    axes[0].axhline(0,color='black',lw=.8)
    axes[0].set(title='Adapt: strongest original-drum energy rise around every chart snare',xlabel='original song time (s)',ylabel='lag from unshifted chart (ms)',ylim=(-105,105))
    for b in bins:
        if b.get('profile') is not None:axes[1].plot(LAGS*1000,b['profile'],label=f"{b['start_seconds']:g}–{b['end_seconds']:.0f}s")
    axes[1].axvline(0,color='black',lw=.8)
    axes[1].set(xlabel='lag from unshifted chart (ms)',ylabel='normalized energy-rise profile')
    axes[1].legend(ncol=5,fontsize=9)
    fig.savefig(out/'snare-timing.png',dpi=140)
    plt.close(fig)
    print(json.dumps({'overall':{k:v for k,v in overall.items() if k not in ['profile','individual_peak_lags_ms']},
                      'bins':[{k:v for k,v in b.items() if k not in ['profile','individual_peak_lags_ms']} for b in bins]}),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--benchmark',type=Path,required=True)
    ap.add_argument('--prior-audit',type=Path)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--extend-full-song',action='store_true')
    a=ap.parse_args()
    if a.extend_full_song:
        extend_snare_audit(a.benchmark,a.output_dir)
    elif a.prior_audit is None:
        ap.error('--prior-audit is required for the initial source control')
    else:
        probe(a.benchmark,a.prior_audit,a.output_dir)
