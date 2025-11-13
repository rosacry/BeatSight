import json

import librosa
import numpy as np
import pytest
from scipy.io import wavfile

from pipeline.process import process_audio_file


def test_process_audio_creates_parent_directories(tmp_path):
    sr = 22050
    duration = 1.0
    samples = int(sr * duration)
    times = np.linspace(0.1, 0.8, 4)
    audio = librosa.clicks(times=times, sr=sr, length=samples).astype(np.float32)

    max_val = float(np.max(np.abs(audio)))
    if max_val > 0:
        pcm = np.int16(audio / max_val * 32767)
    else:
        pcm = np.zeros_like(audio, dtype=np.int16)

    input_path = tmp_path / "input.wav"
    wavfile.write(input_path, sr, pcm)

    output_path = tmp_path / "nested" / "result.bsm"
    debug_path = tmp_path / "nested" / "result.debug.json"

    result = process_audio_file(
        str(input_path),
        str(output_path),
        isolate_drums=False,
        confidence_threshold=0.2,
        detection_sensitivity=45.0,
        quantization_grid="sixteenth",
        max_snap_error_ms=20.0,
        debug_output_path=str(debug_path),
        use_ml_classifier=False,
    )

    assert output_path.exists()
    assert debug_path.exists()

    with output_path.open() as f:
        beatmap = json.load(f)

    assert beatmap["metadata"]["title"] == input_path.stem
    assert result["output_path"] == str(output_path)
    assert result["debug_path"] == str(debug_path)
