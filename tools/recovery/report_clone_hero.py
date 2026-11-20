"""Summarize fixed chart agreement and build a local passage review.

Wrong-family pairs are unmatched events close in time, not verified mistakes.
This report never shifts timestamps or tunes models against chart references.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from clone_hero_reference import family_reference
from clone_hero_scoring import prediction_presence, chart_family, score_chart_agreement
from evaluate_mdb import drum_family, scores
from score_timing import timing_summary
from transcribe import sha256
from transcribe_reference import write_json


def match_indices(reference, predicted, tolerance=.05):
    if not reference or not predicted:
        return []
    delta = np.asarray(predicted)[None, :] - np.asarray(reference)[:, None]
    valid = np.abs(delta) <= tolerance + 1e-9
    penalty = (len(reference) + 1) * (tolerance + 1)
    cost = np.full((len(reference), len(predicted) + len(reference)), penalty)
    cost[:, :len(predicted)] = np.where(valid, np.abs(delta), penalty * 2)
    rows, cols = linear_sum_assignment(cost)
    return [(int(r), int(c)) for r, c in zip(rows, cols) if c < len(predicted) and valid[r, c]]


def disagreements(events, chart, tolerance=.05):
    refs = [(t, f) for f, ts in family_reference(events).items() for t in ts]
    preds = [(e["time"]/1000, chart_family(e["component"])) for e in prediction_presence(chart)["hitObjects"]]
    matched_r, matched_p = set(), set()
    for family in {f for _, f in refs + preds}:
        ri = [i for i, e in enumerate(refs) if e[1] == family]
        pi = [i for i, e in enumerate(preds) if e[1] == family]
        for a, b in match_indices([refs[i][0] for i in ri], [preds[i][0] for i in pi], tolerance):
            matched_r.add(ri[a]); matched_p.add(pi[b])
    ri = [i for i in range(len(refs)) if i not in matched_r]
    pi = [i for i in range(len(preds)) if i not in matched_p]
    candidates = []
    for a, b in match_indices([refs[i][0] for i in ri], [preds[i][0] for i in pi], tolerance):
        rt, rf = refs[ri[a]]; pt, pf = preds[pi[b]]
        if rf == pf:
            raise AssertionError("Same-family residual after maximum matching")
        candidates.append({"reference_time": rt, "predicted_time": pt, "reference_family_proxy": rf,
                           "predicted_family": pf, "delta_ms": (pt-rt)*1000})
    return {"unmatched_reference": [{"time": refs[i][0], "family": refs[i][1]} for i in ri],
            "unmatched_predictions": [{"time": preds[i][0], "family": preds[i][1]} for i in pi],
            "possible_family_substitutions": candidates,
            "substitution_counts": dict(Counter(f"{e['reference_family_proxy']}->{e['predicted_family']}" for e in candidates))}


def aggregate(rows, arm, tolerance, view):
    measurements = [s["arms"][arm]["scores"][str(tolerance)][view] for s in rows]
    labels = sorted(set().union(*(set(s["by_family"]) for s in measurements)))
    return {"micro": scores(**{k: sum(s["micro"][k] for s in measurements) for k in ["tp", "fp", "fn"]}),
            "by_family": {f: scores(**{k: sum(s["by_family"].get(f, {}).get(k, 0) for s in measurements)
                                         for k in ["tp", "fp", "fn"]}) for f in labels},
            "timing": timing_summary([v for s in measurements for row in s["by_family"].values()
                                      for v in row["signed_errors_seconds"]])}


HTML = '''<!doctype html><meta charset="utf-8"><title>BeatSight chart-reference review</title>
<style>body{background:#111927;color:#e8edf4;font:16px system-ui;margin:28px;max-width:1400px}h1{font-size:26px}button,select,input{padding:8px;margin:5px;background:#25354d;color:white;border:1px solid #62738c;border-radius:5px}canvas{width:100%;height:440px;background:#172234;border-radius:8px}p{line-height:1.5}.note{color:#ffd592}#status{font-variant-numeric:tabular-nums}audio{width:100%}img{max-width:100%}details{margin:20px 0}</style>
<h1>Clone Hero chart-reference review</h1>
<p class="note">Chart agreement only. All three KLEWS development charts have an unresolved timing flag. Yellow cymbal is shown as HH by convention; cymbal identity, note completeness and pretrained-model overlap remain unverified. No timestamp correction is applied.</p>
<label>Song <select id="song"></select></label><label>Candidate <select id="arm"></select></label><label>Audio <select id="source"><option value="mix">Package mix</option><option value="stem">Estimated drum stem</option></select></label>
<p id="meta"></p><div id="windows"></div>
<label>Start (seconds)<input id="start" type="number" step=".1" value="0"></label><label>Window<select id="span"><option>8</option><option>12</option><option>20</option></select></label><label>Speed<select id="speed"><option value="1">1×</option><option value=".75">0.75×</option><option value=".5">0.5×</option></select></label><label><input id="loop" type="checkbox" checked>Loop window</label><button id="play">Play window</button>
<p id="status"></p><audio id="audio" controls preload="metadata"></audio><canvas id="plot"></canvas>
<p>Upper rows retain the chart’s Pro Drums lanes. Lower rows show broad model families. Click the timeline to seek. Disagreements are review candidates, not verified errors.</p>
<details><summary>Beginning / middle / end acoustic alignment screen</summary><img id="alignment"></details>
<details><summary>Scores and possible substitutions</summary><pre id="scores"></pre></details>
<script>
const data=__DATA__;const $=id=>document.getElementById(id);let current,playing=false;
for(const s of data.songs){let o=new Option(s.title,s.id);$('song').add(o)}
for(const a of data.arms)$('arm').add(new Option(a,a));
const families=['KD','SD','HH','TT','CY','OT'];const pads=['Kick','RedDrum','YellowDrum','BlueDrum','GreenDrum','YellowCymbal','BlueCymbal','GreenCymbal'];
function loadAudio(){let t=$('audio').currentTime;$('audio').src=current[$('source').value];$('audio').playbackRate=+$('speed').value;$('audio').addEventListener('loadedmetadata',()=>{$('audio').currentTime=Math.min(t,$('audio').duration)}, {once:true})}
function choose(){current=data.songs.find(s=>s.id===$('song').value);$('meta').textContent=current.description;$('alignment').src=current.alignment;$('windows').replaceChildren();for(const w of current.windows){let b=document.createElement('button');b.textContent=w.name+' '+w.start.toFixed(2)+'s';b.onclick=()=>{$('start').value=w.start.toFixed(3);$('audio').currentTime=w.start;draw()};$('windows').append(b)}$('start').value=current.windows[0].start.toFixed(3);loadAudio();draw()}
function draw(){let c=$('plot'),d=window.devicePixelRatio||1,w=c.clientWidth,h=440;c.width=w*d;c.height=h*d;let x=c.getContext('2d');x.scale(d,d);let start=+$('start').value,span=+$('span').value,left=130,right=w-20;let X=t=>left+(t-start)/span*(right-left);x.font='12px system-ui';for(let i=0;i<14;i++){let yy=28+i*28;x.fillStyle='#b9c8dc';x.fillText(i<8?pads[i]:families[i-8],8,yy+4);x.strokeStyle='#2c3a50';x.beginPath();x.moveTo(left,yy);x.lineTo(right,yy);x.stroke()}for(let t=Math.ceil(start);t<=start+span;t++){x.fillStyle='#a4b7cf';x.fillText(t+'s',X(t),425)}
for(const e of current.reference){if(e.t<start||e.t>start+span)continue;let y=28+pads.indexOf(e.pad)*28;x.fillStyle=e.double?'#ffa25a':'#69ced5';x.fillRect(X(e.t)-2,y-7,4,14)}for(const e of current.predictions[$('arm').value]){if(e.t<start||e.t>start+span)continue;let y=28+(8+families.indexOf(e.family))*28;x.fillStyle='#e0b4ff';x.beginPath();x.arc(X(e.t),y,3,0,7);x.fill()}
let at=$('audio').currentTime;x.strokeStyle='#ff7183';x.beginPath();x.moveTo(X(at),15);x.lineTo(X(at),415);x.stroke();$('status').textContent=at.toFixed(3)+' / '+current.duration.toFixed(3)+' seconds';$('scores').textContent=JSON.stringify(current.scores[$('arm').value],null,2)}
$('song').onchange=choose;$('arm').onchange=draw;$('source').onchange=loadAudio;$('start').onchange=draw;$('span').onchange=draw;$('speed').onchange=()=>{$('audio').playbackRate=+$('speed').value};$('play').onclick=()=>{$('audio').currentTime=+$('start').value;$('audio').play()};$('audio').ontimeupdate=()=>{if($('loop').checked&&$('audio').currentTime>=+$('start').value+ +$('span').value)$('audio').currentTime=+$('start').value;draw()};$('plot').onclick=e=>{const r=$('plot').getBoundingClientRect();$('audio').currentTime=+$('start').value+Math.max(0,Math.min(1,(e.clientX-r.left-130)/(r.width-150)))*+$('span').value;draw()};window.onresize=draw;choose();
</script>'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    if root.drive.upper() != "C:":
        raise ValueError("C: root required")
    metrics = json.loads((root / "evaluation-01/metrics.json").read_text())
    if metrics["status"] != "complete":
        raise ValueError("Inference not complete")
    out = root / "report"
    out.mkdir(exist_ok=False)
    review = root / "review"
    review.mkdir(exist_ok=False)
    arms = list(metrics["songs"][0]["arms"])
    # Re-score preserved predictions under the explicit CH policy. Retain the
    # original runner's MDB-based metrics as provenance, never overwrite them.
    for song in metrics["songs"]:
        ref = json.loads((root / "prepared-v2" / song["id"] / "reference.json").read_text())
        for arm in arms:
            path = root / "evaluation-01" / song["id"] / arm / ("chart.bsm" if arm == "inherited-faithful" else "predictions.json")
            if sha256(path) != song["arms"][arm]["predictions_sha256"]:
                raise ValueError("Predictions changed")
            chart = json.loads(path.read_text())
            song["arms"][arm]["scores"] = score_chart_agreement(chart, ref["events"])
            song["arms"][arm]["collapsed_same_family_predictions"] = len(chart["hitObjects"]) - len(prediction_presence(chart)["hitObjects"])
    metrics["scoring_policy"] = "CH broad snare includes cross-stick; same-time family presence on both sides; original times retained"
    write_json(out / "rescored-metrics.json", metrics)
    result = {"interpretation": metrics["interpretation"], "metrics_sha256": sha256(root / "evaluation-01/metrics.json"),
              "scoring_policy": metrics["scoring_policy"], "groups": {}, "songs": [], "limits": ["All KLEWS charts need alignment review before model ranking",
              "Five-family mapping uses yellow cymbal=HH convention; merged-cymbal results also reported",
              "Family-presence references collapse simultaneous same-family lanes; raw lanes remain preserved",
              "Possible substitutions may instead be omitted/additional simultaneous hits or reference errors",
              "Reserved split prevents local tuning only; model-training overlap unknown"]}
    for group in ["development", "reserved", "all"]:
        rows = [s for s in metrics["songs"] if group == "all" or s["split"] == group]
        result["groups"][group] = {arm: {str(ms): {view: aggregate(rows, arm, ms, view) for view in ["five_family_proxy", "cymbals_merged"]}
                                                for ms in [25,50]} for arm in arms}
    alignment = json.loads((root / "alignment-01/alignment.json").read_text())
    data = {"arms": arms, "songs": []}
    for s in metrics["songs"]:
        slug = s["id"]
        ref = json.loads((root / "prepared-v2" / slug / "reference.json").read_text())
        row = {"id": slug, "split": s["split"], "arms": {}}
        display = {"id":slug,"title":ref["metadata"]["artist"]+" — "+ref["metadata"]["name"],
                   "description": f"{s['split']} • Chart by {ref['metadata'].get('charter','unknown')} • 2x kicks included • Timing audit pending",
                   "duration":ref["audio"]["duration_seconds"],"mix":f"../prepared-v2/{slug}/mix.wav", "stem":f"../evaluation-01/{slug}/drums.wav",
                   "alignment":f"../alignment-01/{slug}.png", "reference":[{"t":n["time_seconds"],"pad":n["pad"],"double":n["double_kick"]} for n in ref["events"]],
                   "predictions":{},"scores":{},"windows":[]}
        for arm in arms:
            path = root / "evaluation-01" / slug / arm / ("chart.bsm" if arm == "inherited-faithful" else "predictions.json")
            chart = json.loads(path.read_text())
            if sha256(path) != s["arms"][arm]["predictions_sha256"]:
                raise ValueError("Prediction changed")
            mistakes = disagreements(ref["events"], chart)
            write_json(out / f"{slug}.{arm}.disagreements.json", mistakes)
            row["arms"][arm] = {"scores":s["arms"][arm]["scores"], "substitution_counts_50ms":mistakes["substitution_counts"]}
            display["predictions"][arm] = [{"t":e["time"]/1000,"family":chart_family(e["component"])} for e in prediction_presence(chart)["hitObjects"]]
            display["scores"][arm] = {"25ms":s["arms"][arm]["scores"]["25"]["five_family_proxy"]["micro"],
                                     "50ms":s["arms"][arm]["scores"]["50"]["five_family_proxy"]["micro"],
                                     "possible_substitutions_50ms":mistakes["substitution_counts"]}
            if arm == "adtof-stereo-separated" and s["split"] == "development":
                times = [e["time"] for key in ["unmatched_reference", "unmatched_predictions"] for e in mistakes[key]]
                bins = Counter(int(t//8) for t in times)
                if bins:
                    start = bins.most_common(1)[0][0]*8
                    display["windows"].append({"name":"Most disagreements (8s)","start":start})
        # Fixed acoustic windows apply to both splits; no reserved model-error mining.
        display["windows"] = [{"name":w["name"],"start":w["start"]} for w in next(a for a in alignment["songs"] if a["id"]==slug)["windows"]]+display["windows"]
        result["songs"].append(row)
        data["songs"].append(display)
    write_json(out / "summary.json", result)
    write_json(review / "review-data.json", data)
    (review / "review.html").write_text(HTML.replace("__DATA__", json.dumps(data).replace("</", "<\\/")), encoding="utf8")
    print(json.dumps({g:{a:{ms:v["five_family_proxy"]["micro"] for ms,v in m.items()} for a,m in x.items()} for g,x in result["groups"].items()}),flush=True)


if __name__ == "__main__":
    main()
