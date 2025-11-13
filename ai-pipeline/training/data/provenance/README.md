# Provenance Record Format

Store ingestion metadata in newline-delimited JSON (`.jsonl`) files. Use the naming pattern `<dataset>_provenance.jsonl`. Each line should capture the following fields:
- `source_set`: dataset identifier (e.g., `cambridge`, `slakh`)
- `session_id`: stable identifier for the session or song
- `sample_paths`: array of absolute or workspace-relative paths for raw assets
- `hashes`: object describing checksum type and value for each asset (prefer SHA256)
- `license_ref`: filename from `training/data/licenses/` summarizing legal terms
- `ingestion_script`: path to the script used (for example `training/tools/ingest_cambridge.py`)
- `ingestion_version`: semantic version or git commit hash of the ingestion tool
- `processing_chain`: ordered list of transforms (resample, normalization, channel fold-down, augmentation)
- `timestamp_utc`: ISO 8601 timestamp when the record was generated
- `techniques`: array drawn from `additionaldrummertech.txt` that are present or annotated in the session
- `notes`: free-text field for edge cases (missing stems, tempo drift, mic substitutions)

Example entry:
```json
{
  "source_set": "cambridge",
  "session_id": "cambridge_0123",
  "sample_paths": [
    "data/raw/cambridge/session0123/drums.wav",
    "data/raw/cambridge/session0123/overheads.wav"
  ],
  "hashes": {
    "drums.wav": {"sha256": "..."},
    "overheads.wav": {"sha256": "..."}
  },
  "license_ref": "licenses/cambridge.md",
  "ingestion_script": "training/tools/ingest_cambridge.py",
  "ingestion_version": "git:abcd1234",
  "processing_chain": ["sox_resample_48k", "lufs_normalize_-23"],
  "timestamp_utc": "2025-11-07T18:42:00Z",
  "techniques": ["ghost_notes", "crash_build", "metric_modulation"],
  "notes": "Tempo map imported from session MIDI; room mics missing"
}
```

Keep the structure consistent so downstream tooling can validate provenance before training.
