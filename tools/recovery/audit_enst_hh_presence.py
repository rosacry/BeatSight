"""One frozen microphone-presence audit; no model execution or note changes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import sys
import numpy as np
import soundfile as sf
from scipy.signal import correlate

BASE=Path('C:/Users/10ros/BeatSight-Recovery')
PREVIOUS=BASE/'2026-10-16-drumsep-mixed-validation-01'
VALIDATION=BASE/'2026-10-15-snare-validation-01'
DATA=Path('D:/data/raw/ENST-Drums')
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def save(p,v):
    with Path(p).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,allow_nan=False)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def source_labels(p):
    rows=[]
    for line in Path(p).read_text().splitlines():
        t,label=line.split();rows.append(dict(time_seconds=float(t),label=label))
    return rows


def prepare(root):
    inputs=root/'inputs';inputs.mkdir(exist_ok=False)
    source_entries=[];protected={str(Path(__file__)):sha(Path(__file__))}
    for f in [PREVIOUS/'protocol.json',PREVIOUS/'review/cases.json',PREVIOUS/'family-evidence/metrics.json',
              VALIDATION/'protocol.json',root/'primary/fetches.json']:
        protected[str(f)]=sha(f)
    for e in read(root/'primary/fetches.json'):protected[e['path']]=e['sha256']
    def copied(source,dest):
        assert source.is_file() and source.drive.upper() in ['C:','D:']
        dest.parent.mkdir(parents=True,exist_ok=True)
        assert not dest.exists();shutil.copy2(source,dest)
        h=sha(source);assert sha(dest)==h
        protected[str(source)]=h;protected[str(dest)]=h
        source_entries.append(dict(source=str(source),copy=str(dest),sha256=h,bytes=source.stat().st_size))
        return dest
    tracks=[]
    old_specs={t['id']:t for t in read(VALIDATION/'protocol.json')['tracks'] if t['admitted']}
    for old in read(PREVIOUS/'protocol.json')['tracks']:
        spec=old_specs[old['id']];d=spec['performer_group'];name=Path(spec['sources']['wet']).name
        hh=copied(DATA/d/'audio/hi-hat'/name,inputs/old['id']/'hh-mic.wav')
        dry=copied(DATA/d/'audio/dry_mix'/name,inputs/old['id']/'dry-mix.wav')
        files=dict(hh_mic=str(hh),snare_mic=spec['source_copies']['snare_mic'],dry_mix=str(dry),
            wet_mix=spec['source_copies']['wet'],demucs=old['source_mono'],
            drumsep_hh=str(PREVIOUS/'separated'/old['id']/'hh.wav'))
        info={}
        for k,v in files.items():
            f=sf.info(v);assert f.samplerate==44100 and f.frames==old['frames']
            assert f.channels==(1 if k in ['hh_mic','snare_mic','demucs'] else 2)
            info[k]=dict(frames=f.frames,sample_rate=f.samplerate,channels=f.channels,subtype=f.subtype)
            protected[v]=sha(v)
        for f in [old['reference'],old['cached_assignments'],old['prediction'],spec['source_copies']['annotation']]:protected[f]=sha(f)
        tracks.append(dict(id=old['id'],files=files,info=info,reference=old['reference'],
            source_annotation=spec['source_copies']['annotation'],assignments=old['cached_assignments']))
    controls=[]
    # Tool-matched controls chosen by filenames, before reading any waveform values.
    choices=[('drummer_1','016_hits_closed-hi-hat_brushes_x3','013_hits_snare-drum_brushes_x5','brushes'),
             ('drummer_2','006_hits_closed-hi-hat_sticks_x5','001_hits_snare-drum_sticks_x5','sticks'),
             ('drummer_3','007_hits_closed-hi-hat_sticks_x5','001_hits_snare-drum_sticks_x5','sticks')]
    for d,hh_name,sd_name,implement in choices:
        for group,name,label in [('hh_present',hh_name,'chh'),('hh_absent_snare',sd_name,'sd')]:
            audio=copied(DATA/d/'audio/hi-hat'/(name+'.wav'),inputs/'controls'/d/(name+'.wav'))
            ann=copied(DATA/d/'annotation'/(name+'.txt'),inputs/'controls'/d/(name+'.txt'))
            labels=source_labels(ann);assert all(r['label']==label for r in labels)
            info=sf.info(audio);assert info.samplerate==44100 and info.channels==1
            assert all(.05<=r['time_seconds']<=info.duration-.05 for r in labels)
            controls.append(dict(drummer=d,implement=implement,group=group,audio=str(audio),annotation=str(ann),events=labels))
    cases=[]
    for old in read(PREVIOUS/'review/cases.json'):
        track=next(t for t in tracks if t['id']==old['track'])
        if old['group']=='matched_hh':
            matches=read(track['assignments'])['baseline']['HH']['reference']
            refs=[e['time'] for e in matches if e['matched_prediction']==old['time_seconds']]
            assert len(refs)==1;anchor=refs[0];label='HH'
        else:
            assert old['group']=='false_hh_near_sd'
            anchor=min(old['source_references_within50ms']['SD'],key=lambda t:(abs(t-old['time_seconds']),t));label='SD'
        cases.append(dict(track=old['track'],prediction_seconds=old['time_seconds'],group=old['group'],
            anchor_seconds=anchor,anchor_reference_family=label,old_ratio_db=old['sd_over_hh_db'],
            source_context=old['source_references_within50ms']))
    assert len(cases)==20 and Counter(c['group'] for c in cases)=={'matched_hh':12,'false_hh_near_sd':8}
    protocol=dict(utc=datetime.now(timezone.utc).isoformat(),
        scope='Source microphone suitability and fixed reviewed cases; no model inference, note rule or reference relabeling.',
        hypothesis='A transient on the HH microphone is selective enough to support direct HH-presence interpretation; test bleed controls first.',
        presence_readout='Broadband stereo/mono mean-square post[anchor,anchor+50ms) versus pre[anchor-50ms,anchor), rounded sample anchor. 10log10((post+1e-12)/(pre+1e-12)). No filtering, lag fitting or gain changes.',
        threshold_db=6.0,
        threshold_rationale='Approximately fourfold power rise is a simple predeclared transient screen, not a calibrated instrument classifier.',
        gates=dict(minimum_positive_events=10,minimum_negative_events=10,minimum_sensitivity=.8,minimum_specificity=.8,
            minimum_each_per_drummer=3,all_drummers_must_meet_rates=True),
        failure_action='If source HH-mic controls fail, stop interpreting this readout as HH presence; stages/cases remain descriptive and cannot establish which stage removed a hi-hat. No parameter repair.',
        controls_limit='Isolated labeled strokes, tool-matched within performer. Drummer1 brush HH chosen because no closed-HH-stick control is present in its local hit inventory. These do not cover every technique or prove song generalization.',
        clock_check='HH-mic and snare-mic against unprocessed dry stereo mean: normalized raw-waveform correlation within +/-50ms in each complete recording third. Record peak lag/correlation; no shifts applied. <=2ms across thirds is supporting common-clock evidence, not source identity.',
        review='All fixed20 prior extreme cases, unmasked; 1s centered on source anchor, six unnormalized audio clips and per-channel waveform. No listening-based relabeling.',
        dataset_limit='HH microphone contains snare bleed per primary paper. Quiet periodic timekeeping strokes may be unannotated, unlike offbeat ghost notes. Labels retained; no automated source-purity assumption.',
        tracks=tracks,controls=controls,cases=cases,source_copies=source_entries,code_sha256=sha(Path(__file__)),
        protected=[dict(path=p,sha256=h) for p,h in sorted(protected.items())])
    save(root/'protocol.json',protocol)
    print(json.dumps(dict(protocol_sha256=sha(root/'protocol.json'),tracks=len(tracks),cases=len(cases),
        control_events=Counter(c['group'] for group in controls for c in [dict(group=group['group'])]*len(group['events'])),
        protected=len(protected),copies=len(source_entries))))


def checked(root):
    p=read(root/'protocol.json');assert sha(Path(__file__))==p['code_sha256']
    for e in p['protected']:assert sha(e['path'])==e['sha256'],e['path']
    return p


def feature(audio,anchor,sr=44100):
    a=int(round(anchor*sr));n=int(round(.05*sr))
    assert 0<=a-n<a+n<=len(audio)
    pre=float(np.mean(audio[a-n:a].astype('float64')**2))
    post=float(np.mean(audio[a:a+n].astype('float64')**2))
    value=float(10*np.log10((post+1e-12)/(pre+1e-12)))
    return dict(pre_energy=pre,post_energy=post,rise_db=value,positive=value>=6,anchor_frame=a,window_frames=n)


def run(root):
    p=checked(root);out=root/'measurements';out.mkdir(exist_ok=False)
    controls=[]
    for group in p['controls']:
        a,sr=sf.read(group['audio'],dtype='float32',always_2d=True);assert sr==44100 and np.isfinite(a).all()
        for e in group['events']:
            controls.append(dict(drummer=group['drummer'],implement=group['implement'],group=group['group'],
                audio=group['audio'],anchor_seconds=e['time_seconds'],**feature(a,e['time_seconds'])))
    def rates(rows):
        pos=[r for r in rows if r['group']=='hh_present'];neg=[r for r in rows if r['group']=='hh_absent_snare']
        return dict(positives=len(pos),negatives=len(neg),tp=sum(r['positive'] for r in pos),
            fp=sum(r['positive'] for r in neg),sensitivity=sum(r['positive'] for r in pos)/len(pos),
            specificity=sum(not r['positive'] for r in neg)/len(neg))
    pooled=rates(controls);by={d:rates([r for r in controls if r['drummer']==d]) for d in sorted({r['drummer'] for r in controls})}
    checks=dict(group_sizes=pooled['positives']>=10 and pooled['negatives']>=10,
        pooled_sensitivity=pooled['sensitivity']>=.8,pooled_specificity=pooled['specificity']>=.8,
        all_drummer_sizes=all(min(v['positives'],v['negatives'])>=3 for v in by.values()),
        all_drummer_rates=all(v['sensitivity']>=.8 and v['specificity']>=.8 for v in by.values()))
    gate=all(checks.values())
    save(out/'controls.json',controls);save(out/'control-gates.json',dict(pooled=pooled,by_drummer=by,checks=checks,passes=gate))
    clock=[];cases=[]
    for track in p['tracks']:
        audio={}
        for name,file in track['files'].items():
            a,sr=sf.read(file,dtype='float32',always_2d=True);assert sr==44100 and np.isfinite(a).all()
            audio[name]=a
        dry=audio['dry_mix'].astype('float64').mean(axis=1)
        edges=np.linspace(0,len(dry),4,dtype=int)
        for name in ['hh_mic','snare_mic']:
            mic=audio[name][:,0].astype('float64')
            for third,(a,b) in enumerate(zip(edges[:-1],edges[1:]),1):
                x=mic[a:b]-mic[a:b].mean();y=dry[a:b]-dry[a:b].mean()
                allcorr=correlate(y,x,mode='full',method='fft');mid=len(x)-1;limit=2205
                segment=allcorr[mid-limit:mid+limit+1];idx=int(np.argmax(np.abs(segment)))
                lag=idx-limit;normal=float(segment[idx]/np.sqrt(np.dot(x,x)*np.dot(y,y)))
                clock.append(dict(track=track['id'],microphone=name,third=third,lag_samples=lag,
                    lag_ms=lag*1000/sr,correlation=normal,within_2ms=abs(lag*1000/sr)<=2))
        for c in p['cases']:
            if c['track']!=track['id']:continue
            cases.append(dict(**c,stages={name:feature(a,c['anchor_seconds']) for name,a in audio.items()},
                stage_loss_attribution='not established' if not gate else 'source-control gate passes; case review still required'))
    save(out/'clock.json',clock);save(out/'cases.json',cases)
    result=dict(source_presence_gate_passes=gate,clock_checks=len(clock),clock_checks_within_2ms=sum(c['within_2ms'] for c in clock),
        case_count=len(cases),decision='Stop microphone-transient-as-HH-presence inference' if not gate else 'Source control passes; no chart rule authorized by this diagnostic',
        no_chart_changes=True,no_inference=True)
    save(out/'summary.json',result);checked(root)
    print(json.dumps(dict(**result,controls=pooled,by_drummer=by),indent=2))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8')
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('action',choices=['prepare','run']);ap.add_argument('--root',type=Path,required=True)
    args=ap.parse_args();root=args.root.resolve()
    assert root.parent==BASE.resolve() and root.name=='2026-10-16-enst-hh-presence-audit-01'
    {'prepare':prepare,'run':run}[args.action](root)
