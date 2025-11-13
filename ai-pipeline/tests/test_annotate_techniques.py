import json
import sys


def test_annotate_techniques_cli(tmp_path, monkeypatch, capsys):
    from training.tools import annotate_techniques  # type: ignore

    manifest = tmp_path / "events.jsonl"
    events = [
        {
            "session_id": "sess1",
            "onset_time": 0.0,
            "tempo_bpm": 120.0,
            "meter": "4/4",
            "components": [
                {"label": "crash", "instrument_variant": "main", "dynamic_bucket": "accent"}
            ],
        },
        {
            "session_id": "sess1",
            "onset_time": 1.0,
            "tempo_bpm": 180.0,
            "meter": "4/4",
            "components": [
                {"label": "crash", "instrument_variant": "stack", "dynamic_bucket": "medium"}
            ],
        },
        {
            "session_id": "sess1",
            "onset_time": 2.0,
            "tempo_bpm": 180.0,
            "meter": "7/8",
            "components": [
                {"label": "ride_bow", "instrument_variant": "main", "dynamic_bucket": "medium"}
            ],
        },
    ]
    with manifest.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")

    output_path = tmp_path / "annotated.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "annotate_techniques.py",
            "--input",
            str(manifest),
            "--output",
            str(output_path),
        ],
    )

    annotate_techniques.main()

    out = capsys.readouterr().out
    assert "metric_modulation" in out
    assert "variable_meter" in out
    assert "multi_cymbal_same_class" in out

    with output_path.open("r", encoding="utf-8") as handle:
        annotated = [json.loads(line) for line in handle if line.strip()]

    assert any("metric_modulation" in event.get("techniques", []) for event in annotated)
    assert any("variable_meter" in event.get("techniques", []) for event in annotated)
    cymbal_events = [event for event in annotated if "multi_cymbal_same_class" in event.get("techniques", [])]
    assert len(cymbal_events) == 2
