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
   - CNN-based classification
   - Component identification

5. **Beatmap Generation** (`beatmap_generator.py`)
   - Timing analysis
   - Difficulty calculation
   - .bsm file creation
