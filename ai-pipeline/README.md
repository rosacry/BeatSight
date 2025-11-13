# BeatSight AI Pipeline

## Setup

### Install Dependencies

```bash
cd ai-pipeline
python -m venv venv
source venv/bin/activate  # or venv/bin/activate.fish for fish shell
pip install -r requirements.txt
```

### Download Demucs Model

```bash
python -c "import demucs.pretrained; demucs.pretrained.get_model('htdemucs')"
```

## Usage

### Process a Single Audio File

```bash
python -m pipeline.process --input song.mp3 --output beatmap.bsm
```

> **Tip:** The repository includes a `sitecustomize.py` shim, so the command
> works whether you run it from the `ai-pipeline/` directory or the repository
> root.

Add `--ml-model models/best_drum_classifier.pth` to enable the trained ML classifier, or rely on environment variables described below for automation.

### Enable ML Drum Classifier

1. Train or obtain `best_drum_classifier.pth` (see `training/README.md`).
2. Place the file in `ai-pipeline/models/` or point to it explicitly:
   ```bash
   python -m pipeline.process --input song.mp3 --output beatmap.bsm \
       --ml-model models/best_drum_classifier.pth
   ```
3. Alternatively set environment variables:
   - `BEATSIGHT_ML_MODEL_PATH` – absolute/relative path to the `.pth` file
   - `BEATSIGHT_USE_ML_CLASSIFIER=0` – disable ML and force heuristics (default is enabled when a model is available)

Runtime flags `--ml` / `--no-ml` override the environment for a single invocation.

### Run as API Server

```bash
python -m pipeline.server
```

Then access at `http://localhost:8000`

## API Endpoints

- `POST /api/process` - Submit audio file for processing
- `GET /api/process/{job_id}` - Check processing status
- `GET /api/process/{job_id}/result` - Download result

## Architecture

1. **Audio Preprocessing** (`preprocessing.py`)
   - Format conversion
   - Normalization
   - Sample rate standardization

2. **Source Separation** (`separation/demucs_separator.py`)
   - Demucs integration
   - Isolate drum stem

3. **Onset Detection** (`transcription/onset_detector.py`)
   - Spectral flux analysis
   - Peak picking

4. **Drum Classification** (`transcription/drum_classifier.py`)
   - ML classifier (when model is available) with heuristic fallback
   - Component identification

5. **Beatmap Generation** (`beatmap_generator.py`)
   - Timing analysis
   - Difficulty calculation
   - .bsm file creation
