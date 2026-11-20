"""Make short, source-traceable listening passages without model predictions.

The 40 ms early click track is a comparison stimulus, never an accepted offset.
Feedback is exported by the reviewer; this tool does not edit any references.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
import soundfile as sf

from transcribe import sha256
from transcribe_reference import write_json


HTML = '''<!doctype html><meta charset="utf-8"><title>BeatSight reference checks</title>
<style>body{background:#101927;color:#e9eff7;font:16px system-ui;max-width:1360px;margin:28px}h1{font-size:26px}p{line-height:1.5}select,input,button,textarea{font:inherit;background:#26364e;color:inherit;border:1px solid #697b97;border-radius:5px;padding:8px;margin:4px}textarea{display:block;width:90%;min-height:70px}label{display:inline-block}audio{width:100%;margin:15px 0}canvas{width:100%;height:360px;background:#172438}.note{color:#ffd493}pre{white-space:pre-wrap}details{margin-top:16px}#clock{font-variant-numeric:tabular-nums}</style>
<h1>Reference listening checks</h1>
<p>Listen to the original package audio, check the chart lanes, and record only what you can identify. No model predictions appear here.</p>
<p class="note">The chart timing and cymbal identities remain unverified. “40 ms early” is a comparison click track, not an accepted correction. Clicks mark chart snares only. A yellow cymbal lane does not prove hi-hat identity.</p>
<label>Passage <select id="passage"></select></label><label>Listen to <select id="source"></select></label><label>Speed <select id="speed"><option value="1">1×</option><option value=".75">0.75×</option><option value=".5">0.5×</option></select></label>
<p id="question"></p><p id="meta"></p><audio id="audio" controls preload="metadata"></audio><p id="clock"></p>
<label>View from clip second <input id="start" type="number" min="0" step=".1" value="0"></label><label>View width <select id="span"><option value="12">12 seconds</option><option value="4">4 seconds</option><option value="1">1 second</option><option value=".25">250 ms</option></select></label><button id="follow">View at playhead</button>
<canvas id="plot"></canvas><p>Waveform: original package mix. Cyan marks: original chart. Orange marks: trial click positions when selected. Click the plot to seek; zoom in to compare attacks.</p>
<label>Timing observation <select id="timing"><option value="unreviewed">Not reviewed</option><option value="aligned">Original chart sounds aligned</option><option value="chart_late">Original chart sounds late</option><option value="chart_early">Original chart sounds early</option><option value="uncertain">Uncertain</option></select></label>
<label>Yellow-pad sound <select id="instrument"><option value="unreviewed">Not reviewed</option><option value="tom">Tom</option><option value="hihat">Hi-hat</option><option value="other_cymbal">Other cymbal</option><option value="mixed">Varies within passage</option><option value="uncertain">Uncertain / not applicable</option></select></label>
<label>Listening notes <textarea id="notes" placeholder="Include the original song time and which sound you mean."></textarea></label>
<p><button id="export">Export observations as JSON</button><span id="saved"></span></p><p>Observations stay in this browser’s local storage until exported. They do not modify charts or model settings.</p>
<details><summary>Passage provenance and chart counts</summary><pre id="provenance"></pre></details>
<script>
const data=__DATA__,$=id=>document.getElementById(id),key='beatsight-reference-audit-2026-10-15';let current,answers={};try{answers=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){}
const pads=['Kick','RedDrum','YellowDrum','BlueDrum','GreenDrum','YellowCymbal','BlueCymbal','GreenCymbal'];
for(const p of data.passages)$('passage').add(new Option(p.title,p.id));
function audioSource(){const t=$('audio').currentTime||0;$('audio').pause();$('audio').src=current.sources[$('source').value].url;$('audio').playbackRate=+$('speed').value;$('audio').addEventListener('loadedmetadata',()=>{$('audio').currentTime=Math.min(t,Math.max(0,$('audio').duration-.01));draw()},{once:true});draw()}
function choose(){current=data.passages.find(p=>p.id===$('passage').value);$('audio').pause();$('source').replaceChildren();for(const [k,v] of Object.entries(current.sources))$('source').add(new Option(v.label,k));$('question').textContent=current.question;$('meta').textContent=current.song+' · '+current.split+' · original song '+current.start_seconds.toFixed(3)+'–'+(current.start_seconds+current.duration_seconds).toFixed(3)+' seconds';$('start').value=0;$('audio').src=current.sources.mix.url;$('audio').playbackRate=+$('speed').value;const a=answers[current.id]||{};$('timing').value=a.timing||'unreviewed';$('instrument').value=a.instrument||'unreviewed';$('notes').value=a.notes||'';$('saved').textContent='';$('provenance').textContent=JSON.stringify(current.provenance,null,2);draw()}
function draw(){if(!current)return;const c=$('plot'),d=window.devicePixelRatio||1,w=c.clientWidth,h=360;c.width=w*d;c.height=h*d;const x=c.getContext('2d');x.scale(d,d);const start=+$('start').value,span=+$('span').value,left=132,right=w-18,X=t=>left+(t-start)/span*(right-left);x.font='12px system-ui';x.fillStyle='#aebfd6';x.fillText('Original mix',8,44);x.strokeStyle='#759bc0';x.beginPath();for(let i=0;i<current.waveform.length;i++){const t=i*current.waveform_step;if(t<start||t>start+span)continue;const a=current.waveform[i];x.moveTo(X(t),44-a*29);x.lineTo(X(t),44+a*29)}x.stroke();for(let i=0;i<8;i++){const y=92+i*29;x.fillStyle='#cbd7e6';x.fillText(pads[i],8,y+4);x.strokeStyle='#33435a';x.beginPath();x.moveTo(left,y);x.lineTo(right,y);x.stroke()}
const variant=current.sources[$('source').value],shift=(variant&&variant.trial_shift_seconds)||0;for(const e of current.events){const t=e.t-current.start_seconds,y=92+pads.indexOf(e.pad)*29;if(t>=start&&t<=start+span){x.fillStyle='#6ed5de';x.fillRect(X(t)-1.5,y-6,3,12)}if(shift&&e.pad==='RedDrum'&&t+shift>=start&&t+shift<=start+span){x.fillStyle='#ffbf6f';x.fillRect(X(t+shift)-1.5,y-9,3,18)}}
const step=span<=1?.05:span<=4?.5:1;for(let t=Math.ceil(start/step)*step;t<=start+span;t+=step){x.fillStyle='#b4c5db';x.fillText((current.start_seconds+t).toFixed(span<=1?3:1),X(t),345)}x.strokeStyle='#ff7786';x.beginPath();x.moveTo(X($('audio').currentTime),8);x.lineTo(X($('audio').currentTime),325);x.stroke();$('clock').textContent='Original song time '+(current.start_seconds+$('audio').currentTime).toFixed(3)+' s · clip '+$('audio').currentTime.toFixed(3)+' / '+current.duration_seconds.toFixed(3)+' s'}
function save(){answers[current.id]={passage_id:current.id,source_reference_sha256:current.provenance.reference_sha256,timing:$('timing').value,instrument:$('instrument').value,notes:$('notes').value,updated_utc:new Date().toISOString()};try{localStorage.setItem(key,JSON.stringify(answers));$('saved').textContent='Saved in this browser'}catch(e){$('saved').textContent='Browser storage unavailable; export to preserve observations'}}
$('passage').onchange=choose;$('source').onchange=audioSource;$('speed').onchange=()=>{$('audio').playbackRate=+$('speed').value};$('start').oninput=draw;$('span').onchange=draw;$('follow').onclick=()=>{$('start').value=Math.max(0,$('audio').currentTime-.1).toFixed(3);draw()};$('audio').ontimeupdate=draw;$('audio').onloadedmetadata=draw;for(const id of ['timing','instrument','notes'])$(id).onchange=save;
$('plot').onclick=e=>{const r=$('plot').getBoundingClientRect(),t=+$('start').value+Math.max(0,Math.min(1,(e.clientX-r.left-132)/(r.width-150)))*+$('span').value;$('audio').currentTime=Math.min(t,current.duration_seconds-.01);draw()};$('export').onclick=()=>{save();const blob=new Blob([JSON.stringify({schema:'beatsight-reference-observations-v1',review_manifest_sha256:data.manifest_sha256,observations:Object.values(answers)},null,2)],{type:'application/json'}),u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download='beatsight-reference-observations.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};window.onresize=draw;choose();
</script>'''


def snare_click_overlay(y, sr, relative_hits, shift):
    clicks = np.zeros(len(y), dtype=np.float32)
    t = np.arange(round(sr * .012)) / sr
    click = (.12 * np.cos(2 * np.pi * 1700 * t) * np.exp(-t / .002)).astype(np.float32)
    placed = []
    for hit in relative_hits:
        sample = round((hit + shift) * sr)
        if sample < 0 or sample + len(click) > len(y):
            continue
        clicks[sample:sample + len(click)] += click
        placed.append(sample)
    gain = 1 / max(1, float(np.abs(y).max()) + .12)
    return (y + clicks[:, None]) * gain, {"common_gain": gain, "click_sample_indices": placed,
            "click_frequency_hz": 1700, "click_length_seconds": .012,
            "trial_shift_seconds": shift, "meaning": "review stimulus only; no reference correction"}


def build(benchmark, audit_root):
    benchmark, audit_root = benchmark.resolve(), audit_root.resolve()
    if audit_root.drive.upper() != 'C:' or audit_root.is_relative_to(benchmark):
        raise ValueError('Use the separate scoped C: audit root')
    out = audit_root / 'review'
    out.mkdir(exist_ok=False)
    (out / 'clips').mkdir()
    audit_path = audit_root / 'validated/audit.json'
    audit = json.loads(audit_path.read_text())
    result = {"audit_sha256": sha256(audit_path), "predictions_used": False,
              "selection": "Fixed beginning/middle/end windows for all songs, plus three chart-only Knuckles contrasts: 0-8,13-21,116-124 seconds",
              "click_trial": "Uniform -40 ms comparison chosen from earlier acoustic flag, not optimized against models; original scores remain unchanged",
              "passages": []}
    # Freeze selection before generating review stimuli.
    write_json(audit_root / 'review-protocol.json', {k:v for k,v in result.items() if k != 'passages'})
    for song in audit['songs']:
        slug = song['id']
        ref_path = benchmark / 'prepared-v2' / slug / 'reference.json'
        audio_path = ref_path.parent / 'mix.wav'
        if sha256(ref_path) != song['reference_sha256'] or sha256(audio_path) != song['audio_sha256']:
            raise ValueError('Prepared source changed')
        ref = json.loads(ref_path.read_text())
        y, sr = sf.read(audio_path, dtype='float32', always_2d=True)
        author_drums = None
        drum_source = None
        for source in ref['audio']['sources']:
            if source['name'] == 'drums.ogg':
                drum_source = Path(ref['chart']).parent / source['name']
                if sha256(drum_source) != source['sha256']:
                    raise ValueError('Original drum stem changed')
                author_drums, dsr = sf.read(drum_source, dtype='float32', always_2d=True)
                if dsr != sr:
                    raise ValueError('Stem sample rate differs')
        windows = [(w['name'],w['start_seconds'],12) for w in song['windows']]
        if slug == 'knuckles':
            windows += [('yellow-pad-intro',0,8),('yellow-cymbal-contrast',13,8),('tom-fill-contrast',116,8)]
        for name, start, duration in windows:
            start_sample = round(start * sr)
            clip = y[start_sample:min(len(y),start_sample + round(duration * sr))]
            start = start_sample / sr
            duration = len(clip) / sr
            pid = f'{slug}-{name}'
            mix_file = out / 'clips' / f'{pid}.mix.wav'
            sf.write(mix_file, clip, sr, subtype='FLOAT')
            events = [{'t':e['time_seconds'],'pad':e['pad']} for e in ref['events'] if start <= e['time_seconds'] < start + duration]
            sources = {'mix':{'label':'Original package mix','url':'clips/'+mix_file.name,'sha256':sha256(mix_file)}}
            if song['split'] == 'development':
                hits = sorted(set(e['t']-start for e in events if e['pad']=='RedDrum'))
                for key, shift, label in [('click-original',0,'Mix + original chart snare clicks'),('click-early',-.04,'Mix + snare clicks 40 ms early (trial)')]:
                    overlay, metadata = snare_click_overlay(clip,sr,hits,shift)
                    path = out/'clips'/f'{pid}.{key}.wav'
                    sf.write(path,overlay,sr,subtype='FLOAT')
                    sources[key] = {'label':label,'url':'clips/'+path.name,'sha256':sha256(path),**metadata}
            if author_drums is not None:
                stem_file = out/'clips'/f'{pid}.author-drums.wav'
                sf.write(stem_file,author_drums[start_sample:start_sample+len(clip)],sr,subtype='FLOAT')
                sources['author-drums'] = {'label':'Original author-provided drum stem','url':'clips/'+stem_file.name,'sha256':sha256(stem_file),
                                          'source':str(drum_source),'source_sha256':sha256(drum_source)}
            block = max(1,round(sr/1000))
            level = np.max(np.abs(clip[:len(clip)//block*block]).reshape(-1,block,clip.shape[1]),axis=(1,2))
            level /= max(float(level.max()),1e-10)
            question = 'Compare snare attacks with the original chart timing. Record uncertain or missing instruments only if you can identify them.'
            if name == 'yellow-pad-intro':
                question = 'The opening repeated yellow-pad notes are marked as toms. Do you hear toms, hi-hat, or another cymbal in this eight-second passage?'
            elif slug == 'knuckles':
                question = 'Compare the repeated yellow-pad sound with the opening passage. Does the sound change when the chart switches between YellowDrum and YellowCymbal?'
            row = {'id':pid,'title':f"{ref['metadata']['name']} — {name.replace('-',' ')}",'song':ref['metadata']['name'],'split':song['split'],
                   'start_seconds':start,'duration_seconds':duration,'sample_rate':sr,'sources':sources,
                   'events':events,'waveform':np.round(level,4).tolist(),'waveform_step':block/sr,'question':question,
                   'provenance':{'reference':str(ref_path),'reference_sha256':sha256(ref_path),'source_audio':str(audio_path),'source_audio_sha256':sha256(audio_path),
                                 'start_sample':start_sample,'frames':len(clip),'sample_rate':sr,'pad_counts':dict(Counter(e['pad'] for e in events)),
                                 'status':'Unreviewed; no listening or label confirmation claimed'}}
            result['passages'].append(row)
    result['passages'].sort(key=lambda p: (p['id'] != 'knuckles-yellow-pad-intro',p['id']))
    write_json(out/'review-data.json',result)
    html_data={**result,'manifest_sha256':sha256(out/'review-data.json')}
    (out/'review.html').write_text(HTML.replace('__DATA__',json.dumps(html_data).replace('</','<\\/')),encoding='utf-8')
    print(json.dumps({'passages':len(result['passages']),'audio_files':sum(len(p['sources']) for p in result['passages']),
                      'review':str(out/'review.html'),'manifest_sha256':html_data['manifest_sha256']}),flush=True)


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--benchmark',type=Path,required=True)
    ap.add_argument('--audit-root',type=Path,required=True)
    args=ap.parse_args()
    build(args.benchmark,args.audit_root)
