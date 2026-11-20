"""Semantic importer checks, including real YARG .chart/.mid execution.

Set BEATSIGHT_CHART_EXPORTER to the freshly built ChartReference.dll for integration.
"""
import json
import os
from pathlib import Path
import subprocess

import mido
import pytest

from clone_hero_reference import convert_events, family_reference, chart_offset


def export(path):
    dll = os.environ.get("BEATSIGHT_CHART_EXPORTER")
    if not dll:
        pytest.skip("Set BEATSIGHT_CHART_EXPORTER to run real parser checks")
    return json.loads(subprocess.check_output(["dotnet", dll, str(path)], text=True))


def test_chart_tempo_cymbals_double_kick(tmp_path):
    p = tmp_path / "notes.chart"
    p.write_text('''[Song]
{
  Resolution = 192
  Offset = 0.125
}
[SyncTrack]
{
  0 = B 120000
  384 = B 60000
}
[ExpertDrums]
{
  192 = N 2 0
  192 = N 66 0
  384 = N 2 0
  576 = N 32 0
  768 = N 3 0
  768 = N 67 0
}
''')
    parsed = export(p)
    notes = convert_events(parsed, offset_seconds=chart_offset(p))
    assert [n['pad'] for n in notes] == ['YellowCymbal', 'YellowDrum', 'Kick', 'BlueCymbal']
    assert [n['time_seconds'] for n in notes] == pytest.approx([.625, 1.125, 2.125, 3.125])
    assert [n['double_kick'] for n in notes] == [False, False, True, False]
    assert len(next(t for t in parsed['tracks'] if t['difficulty'] == 'Expert')['notes']) == 3


def test_midi_tom_marker_disappears_and_disco_flip(tmp_path):
    p = tmp_path / 'notes.mid'
    midi = mido.MidiFile(ticks_per_beat=480)
    tempo = mido.MidiTrack([mido.MetaMessage('set_tempo', tempo=500000, time=0),
                            mido.MetaMessage('set_tempo', tempo=1000000, time=960)])
    drums = mido.MidiTrack([mido.MetaMessage('track_name', name='PART DRUMS', time=0)])
    absolute = [(480, mido.Message('note_on', note=98, velocity=100)),
                (490, mido.Message('note_off', note=98)),
                (950, mido.Message('note_on', note=110, velocity=100)),
                (960, mido.Message('note_on', note=98, velocity=100)),
                (970, mido.Message('note_off', note=98)),
                (980, mido.Message('note_off', note=110)),
                (1400, mido.MetaMessage('text', text='[mix 3 drums0d]')),
                (1440, mido.Message('note_on', note=97, velocity=100)),
                (1450, mido.Message('note_off', note=97)),
                (1920, mido.Message('note_on', note=95, velocity=100)),
                (1930, mido.Message('note_off', note=95))]
    last = 0
    for tick, msg in absolute:
        msg.time = tick - last
        drums.append(msg)
        last = tick
    midi.tracks.extend([tempo, drums]); midi.save(p)
    notes = convert_events(export(p), delay_ms=10)
    assert [n['pad'] for n in notes] == ['YellowCymbal', 'YellowDrum', 'YellowCymbal', 'Kick']
    assert [n['time_seconds'] for n in notes] == pytest.approx([.51, 1.01, 2.01, 3.01])
    assert notes[-1]['double_kick']


def test_family_presence_retains_distinct_times_and_merges_simultaneous_cymbals():
    events = [{'time_seconds': t, 'family_proxy': f} for t, f in [(1, 'CY'), (1, 'CY'), (1, 'HH'), (1.01, 'CY')]]
    assert family_reference(events) == {'CY': [1, 1.01], 'HH': [1]}
    assert family_reference(events, True) == {'CY': [1, 1.01]}


@pytest.mark.parametrize('delay,offset', [(10, .1), (float('nan'), 0), (0, float('inf'))])
def test_ambiguous_and_nonfinite_offsets_fail(delay, offset):
    with pytest.raises(ValueError):
        convert_events({'tracks': []}, delay, offset)


def test_negative_adjusted_time_fails():
    parsed = {'tracks': [{'difficulty': 'Expert', 'notes': [{'time_seconds': 0, 'pad': 'Kick'}]}]}
    with pytest.raises(ValueError):
        convert_events(parsed, delay_ms=-10)


def test_chart_scoring_side_stick_and_cymbal_presence():
    from clone_hero_scoring import score_chart_agreement
    events = [{'time_seconds': t, 'family_proxy': f} for t, f in [(1,'SD'),(2,'CY'),(2,'CY'),(2,'HH')]]
    chart = {'hitObjects': [{'time': t, 'component': f} for t,f in [(1000,'cross_stick'),(2000,'crash'),(2000,'ride'),(2000,'hihat_closed')]]}
    result = score_chart_agreement(chart, events)
    assert result['25']['five_family_proxy']['micro']['tp'] == 3
    assert result['25']['five_family_proxy']['micro']['f1'] == 1
    assert result['25']['cymbals_merged']['micro']['tp'] == 2


def test_substitution_candidates_preserve_chords_and_one_to_one():
    from report_clone_hero import disagreements
    refs = [{'time_seconds': t, 'family_proxy': f} for t,f in [(1,'KD'),(1,'SD'),(2,'HH'),(3,'TT')]]
    preds = {'hitObjects': [{'time': t, 'component': f} for t,f in [(1000,'kick'),(1000,'snare'),(2010,'tom_mid'),(3010,'crash')]]}
    d = disagreements(refs, preds)
    assert d['substitution_counts'] == {'HH->TT': 1, 'TT->CY': 1}
    assert len(d['unmatched_reference']) == 2
