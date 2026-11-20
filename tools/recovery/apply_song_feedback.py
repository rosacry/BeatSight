"""Apply explicit, hash-bound human corrections into a NEW C: package directory.

No heuristic relabeling: each edit must identify exactly one original note.
Timing is unchanged unless a separately reviewed edit explicitly specifies it.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import uuid

from transcribe import REPO, sha256, validate_chart


def apply_edits(chart, edits):
    corrected = deepcopy(chart)
    targets = []
    for edit in edits:
        found = [i for i, note in enumerate(chart["hitObjects"])
                 if note["time"] == edit["time_ms"] and note["component"] == edit["from_component"]]
        if len(found) != 1:
            raise ValueError("Each correction must identify exactly one source note")
        if found[0] in targets:
            raise ValueError("Conflicting corrections for the same source note")
        if edit["operation"] not in ("remove", "relabel"):
            raise ValueError("Only explicit removal and instrument relabeling are supported")
        targets.append(found[0])
    for index, edit in zip(targets, edits):
        if edit["operation"] == "relabel":
            corrected["hitObjects"][index]["component"] = edit["to_component"]
    removed = {i for i, e in zip(targets, edits) if e["operation"] == "remove"}
    corrected["hitObjects"] = [n for i, n in enumerate(corrected["hitObjects"]) if i not in removed]
    # Every surviving note keeps its timestamp and all non-component attributes.
    for index, original in enumerate(chart["hitObjects"]):
        if index not in removed:
            updated = deepcopy(original)
            if index in targets:
                edit = edits[targets.index(index)]
                if edit["operation"] == "relabel":
                    updated["component"] = edit["to_component"]
            assert updated == corrected["hitObjects"][index - sum(i < index for i in removed)]
    return corrected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    feedback = json.loads(args.feedback.read_text(encoding="utf-8"))
    out = args.output_dir.resolve()
    if out.drive.upper() != "C:" or out.exists():
        raise ValueError("Choose a new C: output directory; existing results are never replaced")
    schema = json.loads((REPO / "shared/schemas/beatmap_schema.json").read_text())
    import jsonschema
    prepared = []
    for entry in feedback["songs"]:
        name = entry["output_name"]
        if Path(name).name != name or name in (".", ".."):
            raise ValueError("Output name must be a single directory name")
        source = Path(entry["source_chart"])
        if sha256(source) != entry["source_chart_sha256"]:
            raise ValueError(f"Source chart changed: {source}")
        chart = json.loads(source.read_text(encoding="utf-8"))
        corrected = apply_edits(chart, entry["edits"])
        corrected["metadata"].update(
            title=entry["title"] + " [DRAFT - opening corrected]",
            beatmapId=str(uuid.uuid4()), modifiedAt=datetime.now(timezone.utc).isoformat(),
            description=entry["scope_note"] + " Remaining notes are unreviewed model predictions. "
                "Unreviewed hihat_closed/tom_mid/crash names remain broad-family display aliases; "
                "only the named correction has user-supported instrument identity. "
                "Velocity is constant and grid metadata remains provisional.")
        corrected["editor"]["aiGenerationMetadata"]["manualEdits"] = True
        corrected["metadata"]["tags"].append("user-corrected-opening")
        components = list(dict.fromkeys(n["component"] for n in corrected["hitObjects"]))
        corrected["drumKit"]["components"] = components
        corrected["editor"]["visualLanes"] = max(5, len(components))
        jsonschema.validate(corrected, schema)
        prepared.append((entry, source, chart, corrected))
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(args.feedback, out / "feedback.json")
    results = []
    for entry, source, chart, corrected in prepared:
        folder = out / entry["output_name"]
        folder.mkdir(exist_ok=False)
        copies = []
        for name, hash_key in [(chart["audio"]["filename"], "hash"), (chart["audio"]["drumStem"], "drumStemHash")]:
            if Path(name).name != name:
                raise ValueError("Audio companion must be adjacent to chart")
            expected = chart["audio"][hash_key].removeprefix("sha256:")
            if sha256(source.parent / name) != expected:
                raise ValueError("Source companion hash mismatch")
            target = folder / name
            shutil.copy2(source.parent / name, target)
            if sha256(target) != expected:
                raise ValueError("Audio copy hash mismatch")
            copies.append({"path": str(target), "sha256": expected})
        chart_path = folder / "chart.bsm"
        chart_path.write_text(json.dumps(corrected, indent=2), encoding="utf-8")
        (folder / "READ-ME.txt").write_text(
            "Import chart.bsm with the adjacent audio files present.\n\n" + entry["scope_note"] +
            "\nCorrection source: direct user listening feedback, recorded in ../feedback.json.\n"
            "This does not verify the rest of the song or precise onset timing.\n"
            "Earlier model drafts remain preserved at the source path in ../feedback.json.\n",
            encoding="utf-8")
        results.append({"title": entry["title"], "source_chart": str(source),
            "source_chart_sha256": sha256(source), "chart": str(chart_path), "chart_sha256": sha256(chart_path),
            "before_count": len(chart["hitObjects"]), "after_count": len(corrected["hitObjects"]),
            "validation": validate_chart(corrected, folder), "edits": entry["edits"],
            "copies": copies, "scope": entry["scope_note"], "whole_song_accuracy": None,
            "all_other_notes_unchanged": True, "surviving_timestamps_unchanged": True})
    manifest = {"status": "complete", "feedback_sha256": sha256(out / "feedback.json"),
                "tool_sha256": sha256(Path(__file__).resolve()), "songs": results,
                "model_changed": False, "training_performed": False}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.copy2(Path(__file__).resolve(), out / "apply_song_feedback_as_run.py")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
