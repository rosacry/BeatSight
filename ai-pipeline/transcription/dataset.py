"""Sample dataset manifest for BeatSight drum classification training."""

MODEL_CATALOG = {
    "ml_drum_classifier_v1": {
        "version": 1,
        "released_at": "2025-11-01",
        "sha256": "deadbeef...",
        "label_map": [
            "kick",
            "snare",
            "hihat_closed",
            "hihat_open",
            "crash",
            "ride",
            "tom_high",
            "tom_mid",
            "tom_low"
        ]
    }
}
