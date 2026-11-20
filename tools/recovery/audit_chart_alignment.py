"""Independent acoustic alignment screen; never shifts charts or model outputs.

Spectral-flux peaks are candidate transients, not drum truth. Examine beginning,
middle and end using the package audio, without consulting model predictions.
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import stft
import soundfile as sf

from transcribe import sha256
from transcribe_reference import write_json


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prepared", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    out = args.output_dir.resolve()
    if out.drive.upper() != "C:":
        raise ValueError("C: output required")
    out.mkdir(exist_ok=False)
    manifest = json.loads((args.prepared / "manifest.json").read_text())
    result = {"method": "Positive spectral flux, 2048-sample centered STFT; hop about 5 ms; independently screen KD/SD chart events against audio transients over +/-150 ms. No offset applied.",
              "limitations": "A peak can be guitar/vocal or another drum. Lag screen is not listened alignment or note accuracy. Matched model times are not used.", "songs": []}
    for src in manifest["songs"]:
        folder = args.prepared / src["id"]
        ref = json.loads((folder / "reference.json").read_text())
        audio = folder / "mix.wav"
        if sha256(audio) != src["audio"]["sha256"]:
            raise ValueError("Audio changed")
        y, sr = sf.read(audio, dtype="float32", always_2d=True)
        mono = y.mean(axis=1)
        hop = round(sr * .005)
        first, last = ref["events"][0]["time_seconds"], ref["events"][-1]["time_seconds"]
        starts = [max(0, first-1), max(0, (first+last)/2-6), max(0, last-12)]
        fig, axes = plt.subplots(3, 1, figsize=(13, 8), constrained_layout=True)
        rows = []
        for ax, name, start in zip(axes, ["beginning", "middle", "end"], starts):
            end = min(start+12, len(y)/sr)
            lo, hi = max(0, start-.2), min(len(y)/sr, end+.2)
            segment = mono[round(lo*sr):round(hi*sr)]
            f, t, z = stft(segment, fs=sr, nperseg=2048, noverlap=2048-hop, boundary="zeros")
            mag = np.abs(z)
            flux = np.maximum(np.diff(np.log1p(100 * mag), axis=1, prepend=np.zeros((len(f), 1))), 0)
            # Low frequencies emphasize kick, mid frequencies emphasize snare;
            # this is only an acoustic screen, not a classifier.
            bands = {"KD": flux[(f>=30)&(f<250)].mean(axis=0),
                     "SD": flux[(f>=250)&(f<5000)].mean(axis=0)}
            times = t + lo
            lags = np.arange(-.15, .1501, .005)
            evidence = []
            curves = []
            for family, values in bands.items():
                hits = sorted(set(e["time_seconds"] for e in ref["events"]
                                  if e["family_proxy"] == family and start <= e["time_seconds"] <= end))
                if not hits:
                    continue
                values = values / max(float(np.percentile(values, 95)), 1e-9)
                curve = [float(np.interp(np.asarray(hits)+lag, times, values).mean()) for lag in lags]
                best = int(np.argmax(curve))
                evidence.append({"family": family, "notes": len(hits), "best_flux_lag_ms": float(lags[best]*1000),
                                 "zero_lag_flux": curve[len(lags)//2], "best_flux": curve[best]})
                curves.append(curve)
                ax.plot(times, values, lw=.75, alpha=.8, label=f"{family} band flux")
                ax.vlines(hits, 0, 1.5, color="#b35bd2" if family == "SD" else "#187fa8", alpha=.35, lw=.7)
            ax.set(xlim=(start,end), ylim=(0,3), title=f"{src['id']} - {name} (lines: chart kick/snare)", xlabel="audio seconds", ylabel="relative flux")
            ax.legend(loc="upper right")
            rows.append({"name": name, "start": start, "end": end, "bands": evidence,
                         "lag_grid_ms": (lags*1000).tolist(), "flux_curves": curves})
        fig.savefig(out / f"{src['id']}.png", dpi=140)
        plt.close(fig)
        row = {"id": src["id"], "reference_sha256": sha256(folder / "reference.json"), "windows": rows,
               "status": "acoustic screen completed; listening/instrument audit pending"}
        result["songs"].append(row)
        print(json.dumps({"id": src["id"], "windows": [{"name": w["name"], "bands": w["bands"]} for w in rows]}), flush=True)
        write_json(out / "alignment.json", result)


if __name__ == "__main__":
    main()
