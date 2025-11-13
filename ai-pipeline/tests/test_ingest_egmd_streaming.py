import json
import pathlib
import sys

import mido

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.tools import ingest_egmd  # noqa: E402


def _write_simple_midi(path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    midi = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="Accent", time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120), time=0))
    track.append(mido.Message("note_on", note=36, velocity=105, time=0))
    track.append(mido.Message("note_off", note=36, velocity=0, time=480))
    midi.save(path)


def test_ingest_streams_events_without_buffering(tmp_path: pathlib.Path) -> None:
    dataset_root = tmp_path / "egmd"
    midi_path = dataset_root / "player" / "pattern.mid"
    _write_simple_midi(midi_path)

    events_path = tmp_path / "events.jsonl"
    provenance_path = tmp_path / "provenance.jsonl"

    ingest_egmd.main(
        [
            "--root",
            str(dataset_root),
            "--output-events",
            str(events_path),
            "--output-provenance",
            str(provenance_path),
        ]
    )

    event_lines = events_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(event_lines) == 1
    payload = json.loads(event_lines[0])
    assert payload["components"][0]["label"] == "kick"

    provenance_lines = provenance_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(provenance_lines) == 1
    provenance = json.loads(provenance_lines[0])
    assert provenance["session_id"].endswith("player_pattern")
