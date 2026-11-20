"""Compare unannotated song drafts without treating any model as ground truth.

Writes a new analysis directory with one-to-one agreement, review candidates,
signal alignment proxies, and an offline audio/chart review page. No chart edits.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from evaluate_mdb import drum_family
from score_timing import timing_summary
from transcribe import sha256

FAMILIES = ["KD", "SD", "HH", "TT", "CY", "OT"]


def match_indices(a, b, tolerance=50):
    """Maximum cardinality, minimum timing cost; input milliseconds."""
    if not a or not b:
        return []
    delta = np.asarray(b)[None, :] - np.asarray(a)[:, None]
    valid = np.abs(delta) <= tolerance + 1e-7
    penalty = (len(a) + 1) * (tolerance + 1)
    costs = np.full((len(a), len(a) + len(b)), float(penalty))
    costs[:, :len(b)] = np.where(valid, np.abs(delta), 2 * penalty)
    rows, cols = linear_sum_assignment(costs)
    return [(int(i), int(j), float(delta[i, j])) for i, j in zip(rows, cols)
            if j < len(b) and valid[i, j]]


def pair_agreement(a, b, tolerance):
    summary, candidates, used_a, used_b = {}, [], set(), set()
    for family in FAMILIES:
        ai = [i for i, e in enumerate(a) if e["family"] == family]
        bi = [i for i, e in enumerate(b) if e["family"] == family]
        matches = match_indices([a[i]["time"] for i in ai], [b[i]["time"] for i in bi], tolerance)
        used_a.update(ai[i] for i, _, _ in matches)
        used_b.update(bi[j] for _, j, _ in matches)
        summary[family] = {"a_count": len(ai), "b_count": len(bi), "same_family_pairs": len(matches),
            "a_unpaired": len(ai) - len(matches), "b_unpaired": len(bi) - len(matches),
            "timing_b_minus_a": timing_summary([dt / 1000 for _, _, dt in matches])}
    # Cross-family pairs are possible substitutions OR distinct simultaneous hits.
    ai = [i for i in range(len(a)) if i not in used_a]
    bi = [i for i in range(len(b)) if i not in used_b]
    cross = match_indices([a[i]["time"] for i in ai], [b[i]["time"] for i in bi], tolerance)
    for i, j, dt in cross:
        candidates.append({"kind": "possible_family_disagreement", "a": a[ai[i]], "b": b[bi[j]],
                           "delta_ms": dt})
    candidates.extend({"kind": "a_only_possible_miss_or_extra", "a": a[i]} for i in ai)
    candidates.extend({"kind": "b_only_possible_miss_or_extra", "b": b[i]} for i in bi)
    return {"tolerance_ms": tolerance, "families": summary,
            "cross_family_candidate_pairs": len(cross)}, candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-name", default="review")
    args = parser.parse_args()
    root = args.root.resolve()
    if Path(args.output_name).name != args.output_name:
        raise ValueError("Output name must be a single directory name")
    out = root / args.output_name
    if root.drive.upper() != "C:":
        raise ValueError("New recovery output must be on C:")
    out.mkdir(exist_ok=False)
    paths = {"full-mix": root / "reference-comparison/full-mix/predictions.json",
             "separated": root / "reference-comparison/separated/predictions.json",
             "inherited": root / "inherited-faithful/chart.bsm"}
    if (root / "stereo-probe/predictions.json").is_file():
        paths["stereo"] = root / "stereo-probe/predictions.json"
    arms = {name: [{"time": e["time"], "family": drum_family(e["component"]),
                   "component": e["component"]} for e in json.loads(path.read_text())["hitObjects"]]
            for name, path in paths.items()}
    run = json.loads((root / "reference-comparison/run.json").read_text())
    chart = json.loads((root / "reference-comparison/separated/chart.bsm").read_text())
    duration = run["audio_health"]["duration_seconds"]
    summary = {"title": chart["metadata"]["title"], "duration_seconds": duration,
        "ground_truth": None, "precision": None, "recall": None, "f1": None,
        "accuracy_status": "Unmeasured. Model agreement and signal proxies are not accuracy.",
        "training_overlap": "unknown", "prediction_sha256": {k: sha256(v) for k, v in paths.items()},
        "counts": {k: dict(Counter(e["family"] for e in v)) for k, v in arms.items()}, "pairs": {}}
    all_candidates = []
    pairs = [("full-mix", "separated"), ("separated", "inherited"), ("full-mix", "inherited")]
    if "stereo" in arms:
        pairs += [("separated", "stereo"), ("full-mix", "stereo")]
    for a, b in pairs:
        for tolerance in (25, 50):
            stats, candidates = pair_agreement(arms[a], arms[b], tolerance)
            summary["pairs"][f"{a}__{b}__{tolerance}ms"] = stats
            if tolerance == 50:
                all_candidates.extend(dict(pair=f"{a}__{b}", **c) for c in candidates)
    # A third detector is not a truth source. These are listening priorities only.
    both_ref_not_inherited = []
    for event in arms["separated"]:
        if any(e["family"] == event["family"] and abs(e["time"] - event["time"]) <= 25
               for e in arms["full-mix"]) and not any(
               e["family"] == event["family"] and abs(e["time"] - event["time"]) <= 50
               for e in arms["inherited"]):
            both_ref_not_inherited.append(event)
    summary["reference_agreement_absent_inherited"] = {
        "counts": dict(Counter(e["family"] for e in both_ref_not_inherited)),
        "meaning": "Two inputs to the SAME model agree; neither is independent ground truth."}
    import soundfile as sf
    import librosa
    y, sr = sf.read(root / "reference-comparison/drums.wav", dtype="float32")
    hop = 128
    spectrum = np.abs(librosa.stft(y, n_fft=1024, hop_length=hop))
    frequency = librosa.fft_frequencies(sr=sr, n_fft=1024)
    band_flux = {}
    for band, low, high in [("low", 30, 180), ("mid", 180, 2500), ("high", 4000, 16000)]:
        s = np.log1p(10 * spectrum[(frequency >= low) & (frequency < high)])
        band_flux[band] = np.maximum(0, np.diff(s, axis=1, prepend=s[:, :1])).mean(axis=0)
    band_for_family = {"KD": "low", "SD": "mid", "TT": "mid", "HH": "high", "CY": "high"}
    proxy = {}
    for name, events in arms.items():
        proxy[name] = {}
        for family, band in band_for_family.items():
            differences = []
            for e in events:
                if e["family"] != family:
                    continue
                frame = round(e["time"] / 1000 * sr / hop)
                lo, hi = max(0, frame - 10), min(len(band_flux[band]), frame + 11)
                if lo >= hi:
                    continue
                peak = lo + int(np.argmax(band_flux[band][lo:hi]))
                differences.append((e["time"] - peak * hop / sr * 1000) / 1000)
            proxy[name][family] = timing_summary(differences)
    summary["signal_timing_proxy"] = {"details": "Event minus strongest band spectral-flux frame within +/-29ms. "
        "Centered 1024-sample STFT, 128-sample hop. Circular nearest-local-peak diagnostic; "
        "cannot establish real onset error, instrument identity, or missing-hit counts. No times corrected.",
        "values": proxy}
    sections = []
    for start in np.arange(0, duration, 10):
        counts = {name: dict(Counter(e["family"] for e in events if start * 1000 <= e["time"] < (start + 10) * 1000))
                  for name, events in arms.items()}
        sections.append({"start_seconds": float(start), "counts": counts})
    summary["sections_10_seconds"] = sections
    def save(name, obj):
        (out / name).write_text(json.dumps(obj, indent=2, allow_nan=False), encoding="utf-8")
    save("summary.json", summary)
    save("review-candidates.json", all_candidates)
    save("reference-agreement-absent-inherited.json", both_ref_not_inherited)
    # An offline, synchronized listening aid. Does not synthesize missing notes.
    data = {"title": summary["title"], "duration": duration, "arms": arms,
            "audio": "../reference-comparison/separated/" + chart["audio"]["filename"],
            "stem": "../reference-comparison/drums.wav"}
    html = HTML.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
    (out / "review.html").write_text(html, encoding="utf-8")
    # Static independent signal views for inspecting the model-disagreement regions.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    windows = [(0, 8), (20, 28), (46, 54), (84, 92), (120, 128), (130, 138)]
    for start, end in windows:
        if start >= duration:
            continue
        fig, axes = plt.subplots(len(arms)+1, 1, figsize=(16, 2*(len(arms)+1)), sharex=True, constrained_layout=True)
        frames = np.arange(len(band_flux["high"])) * hop / sr
        sel = (frames >= start) & (frames < end)
        for band in band_flux:
            v = band_flux[band][sel]
            axes[0].plot(frames[sel], v / max(float(np.max(v)), 1e-8), label=band, linewidth=.7)
        axes[0].legend(loc="upper right", ncol=3)
        axes[0].set_ylabel("Band flux\n(normalized)")
        for ax, (name, events) in zip(axes[1:], arms.items()):
            for j, fam in enumerate(FAMILIES):
                ts = [e["time"] / 1000 for e in events if e["family"] == fam and start <= e["time"] / 1000 < end]
                ax.vlines(ts, j - .3, j + .3, color=f"C{j}")
            ax.set_yticks(range(6), FAMILIES)
            ax.set_ylabel(name)
            ax.grid(axis="x", alpha=.2)
        axes[-1].set_xlabel("Seconds in original audio; predictions are unverified")
        axes[-1].set_xlim(start, end)
        fig.suptitle(f"{summary['title']} | {start}-{end}s | Signal and draft disagreements")
        fig.savefig(out / f"review-{start:03}-{end:03}.png", dpi=140)
        plt.close(fig)
    print(json.dumps({"counts": summary["counts"], "reference_agreement_absent_inherited":
                      summary["reference_agreement_absent_inherited"], "output": str(out)}), flush=True)


HTML = r'''<!doctype html><meta charset="utf-8"><title>Drum draft review</title>
<style>body{margin:24px auto;max-width:1400px;padding:0 20px;background:#111622;color:#e7edf8;font:16px system-ui}h1{margin-bottom:8px}p{line-height:1.5;max-width:1100px}.warn{padding:14px;background:#3a2c13;border-left:4px solid #e7b255}button,select,input{font:inherit;margin:5px;padding:8px;background:#25334b;color:white;border:1px solid #63728a;border-radius:5px}button{cursor:pointer}audio{width:100%}canvas{width:100%;min-width:900px;height:650px;background:#172031;margin-top:15px}small{color:#a5b5ca}a{color:#8acbff}</style>
<h1 id="title"></h1><p class="warn">Unreviewed drafts. Differences are possible misses, additions or instrument mistakes—not verified errors. Hi-hat openness, tom identity, cymbal type and dynamics remain unresolved. No song-level accuracy score is available.</p>
<p>Compare the original mix and estimated drum stems against the note lists. Click the plot to seek, play at reduced speed, and review one family at a time. All times refer to the original audio.</p>
<audio id="audio" controls preload="metadata"></audio><div>
<select id="source"><option value="audio">Original mix</option><option value="stem">Estimated drums (mono input)</option><option value="stereoStem">Estimated drums (stereo input)</option></select>
<label>Speed <select id="speed"><option>1</option><option>0.75</option><option>0.5</option></select></label>
<label>Window <select id="window"><option>8</option><option>4</option><option>16</option></select> seconds</label>
<label>Family <select id="family"><option value="all">All</option><option>KD</option><option>SD</option><option>HH</option><option>TT</option><option>CY</option></select></label>
<label><input type="checkbox" id="loop">Loop window</label><span id="clock"></span></div>
<div id="jumps"></div><div style="overflow-x:auto"><canvas id="plot" width="1400" height="650"></canvas></div>
<p><small>KD kick · SD snare · HH hi-hat · TT tom · CY cymbal · OT other. The separated native chart uses hihat_closed / tom_mid / crash as display proxies; those names do not establish articulation. This review page keeps the broad labels.</small></p>
<p><a href="summary.json">Measured agreement and limits</a> · <a href="review-candidates.json">Detailed review candidates</a> · <a href="../practice-stereo-draft/chart.bsm">Current experimental practice draft</a> · <a href="../reference-comparison/separated/chart.bsm">Mono-separated alternative</a> · <a href="../reference-comparison/full-mix/chart.bsm">Full-mix alternative</a></p>
<script>const data=__DATA__;data.stereoStem='../stereo-probe/drums.wav';const $=id=>document.getElementById(id),audio=$('audio'),c=$('plot'),ctx=c.getContext('2d');$('title').textContent=data.title+' — drum review';audio.src=data.audio;c.height=50+195*Object.keys(data.arms).length;c.style.height=c.height+'px';let start=0;
const fams=['KD','SD','HH','TT','CY','OT'],colors=['#bb8aff','#ff7777','#ffe088','#8cce8a','#77c9ff','#bbbbbb'];
function jump(t){start=Math.max(0,Math.min(t,data.duration));audio.currentTime=start;draw()}
for(const t of [0,10,20,30,46,60,84,100,120,130,150,170,190,210,220]){if(t>=data.duration)continue;const b=document.createElement('button');b.textContent=Math.floor(t/60)+':'+String(t%60).padStart(2,'0');b.onclick=()=>jump(t);$('jumps').append(b)}
$('source').onchange=()=>{let t=audio.currentTime,play=!audio.paused;audio.src=data[$('source').value];audio.onloadedmetadata=()=>{audio.currentTime=t;audio.playbackRate=+$('speed').value;if(play)audio.play()}};$('speed').onchange=()=>audio.playbackRate=+$('speed').value;
function draw(){let span=+$('window').value;ctx.clearRect(0,0,c.width,c.height);ctx.font='13px system-ui';let left=115,right=1380,w=right-left;
for(let i=0;i<=span*2;i++){let t=start+i/2,x=left+(t-start)/span*w;ctx.strokeStyle='#2b3b51';ctx.beginPath();ctx.moveTo(x,30);ctx.lineTo(x,c.height-10);ctx.stroke();if(i%2===0){ctx.fillStyle='#b9c8dc';ctx.fillText(t.toFixed(1),x-12,20)}}
Object.entries(data.arms).forEach(([name,events],a)=>{let top=50+a*195;ctx.fillStyle='#ffffff';ctx.fillText(name,5,top);fams.forEach((f,j)=>{let y=top+21+j*26;ctx.fillStyle=colors[j];ctx.fillText(f,70,y+4);if($('family').value!=='all'&&$('family').value!==f)return;for(const e of events){let t=e.time/1000;if(e.family!==f||t<start||t>start+span)continue;let x=left+(t-start)/span*w;ctx.fillRect(x-2,y-7,4,14)}})});
let x=left+(audio.currentTime-start)/span*w;if(x>=left&&x<=right){ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x,30);ctx.lineTo(x,c.height-10);ctx.stroke();ctx.lineWidth=1}$('clock').textContent=audio.currentTime.toFixed(2)+' / '+data.duration.toFixed(2)+'s';}
c.onclick=e=>{let x=(e.clientX-c.getBoundingClientRect().left)/c.getBoundingClientRect().width*c.width;if(x>=115)audio.currentTime=start+(x-115)/(1380-115)*+$('window').value};
$('window').onchange=draw;$('family').onchange=draw;function frame(){let span=+$('window').value;if(!audio.paused&&audio.currentTime>=start+span){if($('loop').checked)audio.currentTime=start;else start=Math.floor(audio.currentTime/span)*span}draw();requestAnimationFrame(frame)}frame();</script>'''


if __name__ == "__main__":
    main()
