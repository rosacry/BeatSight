# Chart-reference adapter

This research adapter reads original `.chart` or `.mid` files with YARG.Core's
public API. It exports Expert and ExpertPlus Pro Drums, exact parsed seconds,
tick positions, tempo/meter, lanes, dynamics and double-kick flags. It does not
edit charts, infer acoustic instruments, or change the desktop application.

The initial benchmark uses YARG.Core revision
`4b8865781a403a811f42929721436226c77470c6` (LGPL-3.0-or-later, with bundled
Moonscraper BSD-3-Clause code) from
<https://github.com/YARC-Official/YARG.Core>. Keep the checkout/licenses outside
this repo in the scoped experiment. No YARG code is copied into this adapter.

Apply `yarg-difficulty-state.patch` to a **new isolated checkout** of that revision.
It resets the drum mix/disco state for each difficulty. Without the patch, a
synthetic MIDI fixture with a later disco event incorrectly swaps earlier
ExpertPlus notes because Expert's ending state persists. This is a measured
parser defect, not a chart correction. Both source and patch hashes are recorded
in the experiment. Do not apply it to unrelated YARG installs.

Example build, using the current experiment's checkout (PowerShell):

```powershell
$bench = 'C:/Users/10ros/BeatSight-Recovery/2026-10-14-clone-hero-benchmark-01'
dotnet build tools/recovery/ChartReference/ChartReference.csproj -c Release --nologo `
  "-p:YargCorePath=$bench/sources/YARG.Core" --artifacts-path "$bench/parser-build"
$env:BEATSIGHT_CHART_EXPORTER = "$bench/parser-build/bin/ChartReference/release/ChartReference.dll"
./.venv-recovery/Scripts/python.exe -m pytest tools/recovery/test_clone_hero_reference.py -q
```

`clone_hero_reference.py` reads song metadata and applies the recorded chart offset
or ini delay once; simultaneous nonzero values fail pending review. It refuses
known five-lane inputs. Package audio is decoded/summed without temporal shifts;
external absolute `MusicStream` paths embedded by a charter are not followed.
Raw lane notes are retained. The scoring adapter collapses simultaneous
same-family events on both sides and reports both five-family proxies and a
merged-cymbal view. Red pad includes broad snare/side-stick, unlike the MDB-specific
mapping. No color identifies China, exact tom pitch, or hi-hat openness.

This is a bounded research importer, not a universal format converter. More
formats, nonzero dual offsets, unusual stems, five-lane conversions, roll/BRE
omissions, or synthesized/downcharted parts require admission review.

Current commands, provenance, quality flags and restart instructions are in
`docs/CLONE_HERO_BENCHMARK_2026-10-14.md`.
