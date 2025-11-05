# BeatSight ML Models

Place trained model weights for the drum classifier in this directory.

- **Default filename:** `best_drum_classifier.pth`
- The processing CLI (`python -m pipeline.process`) automatically loads this file when it exists.
- Override the location via the `--ml-model` flag or the `BEATSIGHT_ML_MODEL_PATH` environment variable.
