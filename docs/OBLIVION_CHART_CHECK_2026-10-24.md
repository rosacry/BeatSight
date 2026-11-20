# Oblivion blast beats checked against a real Clone Hero drum chart (2026-10-24, Claude)

User report: the maps "did not detect the blast beats at all during the chorus" of Lorna Shore - Oblivion. The user
found the drum chart on the Clone Hero Discord (`Downloads\drive-download-20261024T220621Z-1-001.zip`: Ziggy,
Customs Creators Collective, pro drums, 5,586 expert notes; not on Encore or RhythmVerse, which only list
guitar charts). Root `C:\Users\10ros\BeatSight-Recovery\2026-10-24-oblivion-chart-01` (CPU only). The zip was
listed and extracted by `safe_extract.py` (zip-slip guard; the `.eof` editor file was skipped; nothing executed),
then processed by `process_dir.py` with corpus v2's own functions and scored with the frozen tools
(`score_chart_song.py`, `sections.py`). The chart was never in any training data. Keep rule v1: kept.

## On the chart's own audio, phase 2 gets the fast sections

| Model | Five-family F1 | Kick | Snare | Toms | Hi-hat | Cymbals |
|---|---|---|---|---|---|---|
| ADTOF | .840 | .932 | .920 | .783 | .411 | .602 |
| Phase 2 (app decode, both rules) | .899 | .978 | .958 | .886 | .532 | .686 |

The densest charted sections run about 11-14 kicks and 6-8 snares per second; phase 2 hits nearly all of them
there (e.g. chart 1:00-1:10: 111/111 kicks, 78/78 snares; 6:50-7:00: 79/79, 83/84).

## On the user's MP3, the densest double-bass sections collapse

The MP3 is the same recording shifted by +22.328 s (activation cross-correlation, constant over the song;
waveform correlation .90), but not the same file content: after alignment and gain the difference is about
-7 dB of the MP3, mostly above 300 Hz (where a metal kick's click is). Both are ~130-145 kbps lossy with a
16 kHz cutoff. Scoring the user's comparison maps against the aligned chart:

| Audio | Model | F1 | Kick | Snare | Hi-hat |
|---|---|---|---|---|---|
| chart audio | phase 2 | .899 | .978 | .958 | .532 |
| user's MP3 | phase 2 | .757 | .791 | .927 | .164 |
| chart audio | ADTOF | .840 | .932 | .920 | .411 |
| user's MP3 | ADTOF | .716 | .757 | .907 | .086 |

Kick hits per 10 s (phase 2, chart audio vs MP3) drop from ~95% to 10-30% at MP3 2:22-2:52, 4:22-4:52, 6:02,
6:42 and 7:02 (the sections flagged earlier as "busy stem, few notes"). Skipping separation does not help.

## Chart conversion check (user: "some of the lanes mixed up")

`midi_dump.py` read the raw `notes.mid`. Every gem converts one-to-one (kick 96: 3,156; red 97: 920; yellow/blue/
green 98-100 split into cymbals and toms by tom markers 110-112 exactly as the exporter did; no Expert+ 2x kick,
no roll lanes, no disco flip, no ghost/accent velocities). The moment in the user's screenshot (2:05.8, chart
audio) matches the MIDI (kick stream, crash on beats, snare + crash at 126.46 s). What the first conversion
missed: Phase Shift sysex on `PART REAL_DRUMS_PS` (song.ini `sysex_high_hat_ctrl`, `sysex_rimshot`): type 5
marks 298 of the 446 yellow cymbals as OPEN hi-hat; type 7 marks 200 snares as rimshots (BeatSight has no rimshot
component; left as snare). Reference charts rebuilt with `hihat_open` (old versions moved to
`comparison-03/superseded/2026-10-24-reference-charts-v1`). Five-family scores are unchanged (hi-hat types merge).
Hi-hat type agreement on the chart audio (phase 2): open 127 open / 31 closed / 140 missed; closed 2 closed /
37 open / 109 missed (ADTOF has one hi-hat output). The app's 2D view puts high/mid/low tom in one "Toms" lane
(Clone Hero has three), a display choice, not chart data.

## Cymbal identity (user: "are you sure the ride is correct? and where is the china?")

Pro drums has only yellow/blue/green cymbal lanes; the chart cannot say which physical cymbal a color is. The
conversion used the Rock Band convention (blue = ride, green = crash), which is unproven for this song. Measured
on the chart audio: blue (332) is fast time-keeping (median spacing 115 ms); phase 2 hears its runs as ride bell
at MP3 1:20-1:26, 1:35-1:48, 3:59-4:05 but as crash at MP3 3:20-3:35, 3:45-3:51 (phase 2 hears Chinas as crash).
Green (390) includes quarter-note runs of 56 hits at MP3 2:20-2:48, 4:29-4:57, 6:40-7:08 (typical breakdown China),
which phase 2 mostly misses or calls crash. So the chart likely uses blue and green for different cymbals per
section; only listening can settle it. Pending: the user names which sections are China; then the reference
chart gets a per-section cymbal mapping.

## Yellow lane = hi-hat AND a second crash (user correction)

The user (who watched the chart played in Clone Hero): the hi-hat parts were right, but the yellow lane also holds
a second crash. Evidence from the chart itself (`scored/yellow-context.json`): all 298 open-marked yellows sit in
hi-hat patterns (293 within 250 ms of another yellow; 5 with a green crash); of the 148 unmarked yellows, 71 are hit
together with a green crash, all of them in the breakdowns (MP3 2:20-2:48, 4:29-4:57, 6:40-7:08) and accents
(3:17-3:44, 7:24-7:39). Ring-time measurements could not separate them (dense cymbal wash). Rule in
`add_reference_chart.py` (v3): open marker -> hihat_open; unmarked and with a green crash (30 ms) or alone (no
yellow within 250 ms, no open marker within 1 s) -> crash2; else hihat_closed. Result: 298 open, 58 closed, 90
second crashes. The app's automatic layout draws crash2 in the Crash lane. v2 moved to
`comparison-03/superseded/2026-10-24-reference-charts-v2`. Five-family scoring merges HH and CY separately, so
moving 90 notes from HH to CY changes the scores slightly; not rescored yet. China: still not encoded in the
chart (no lane); blue/green sections that may be China await the user's ears.

## Conclusions and next steps

- The user heard a real failure, but on this song it is input-specific: the model handles these blast beats on a
  cleaner copy of the same recording. Use the best available source file (FLAC/CD/streaming download).
- Robustness gap for run 2/3: dense double-bass passages are fragile to small master/codec differences. Add
  codec and mastering augmentation (MP3/AAC/Opus re-encodes at 96-160 kbps, limiting/EQ) to training, and test
  separation/inference averaging (Demucs shifts) on such passages. This chart is a ready-made check (MP3 vs chart
  audio) and should stay out of training.
- In the app: `2026-10-24-model-comparison-03` now has "Oblivion - Clone Hero chart (Ziggy)" (the human chart on
  the user's MP3, +22.328 s) next to the ADTOF and Phase 2 maps, and "Oblivion (chart audio)" with ADTOF, Phase 2
  and the chart all on the chart's own audio (app-path maps score .840 / .899 vs the chart, same as above).
