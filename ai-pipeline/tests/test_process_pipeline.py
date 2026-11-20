import json
import warnings

import librosa
import numpy as np
import pytest
from scipy.io import wavfile
from unittest.mock import Mock

from pipeline.process import process_audio_file
from pipeline import process


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

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
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
    n_fft_warnings = [
        warning
        for warning in caught_warnings
        if "n_fft=" in str(warning.message)
    ]
    assert not n_fft_warnings

    with output_path.open() as f:
        beatmap = json.load(f)

    assert beatmap["metadata"]["title"] == input_path.stem
    assert result["output_path"] == str(output_path)
    assert result["debug_path"] == str(debug_path)


@pytest.mark.parametrize("mode", ["transcription", "gameplay"])
def test_no_model_hits_cannot_be_presented_as_a_transcription(tmp_path, monkeypatch, mode):
    sr = 22050
    input_path = tmp_path / "song.wav"
    audio = librosa.clicks(times=[0.2, 0.6, 1.0, 1.4], sr=sr, length=sr * 2)
    wavfile.write(input_path, sr, audio.astype(np.float32))
    output = tmp_path / "chart.bsm"
    output.write_text("existing chart")
    debug = tmp_path / "debug.json"
    classifier = Mock(return_value=[])
    classifier.last_classifier_mode = "multilabel"
    classifier.last_classifier_model_path = "test-model.pt"
    monkeypatch.setattr(process.drum_classifier, "classify_drums", classifier)
    settings = dict(isolate_drums=False, pipeline_mode=mode,
                    debug_output_path=str(debug), use_hihat_refinement=False)
    if mode == "transcription":
        with pytest.raises(ValueError, match="no transcription was saved"):
            process_audio_file(str(input_path), str(output), **settings)
        assert output.read_text() == "existing chart"
        assert not debug.exists()
    else:
        result = process_audio_file(str(input_path), str(output), **settings)
        assert result["success"]
        assert json.loads(debug.read_text())["generation"]["used_fallback"] is True
        assert json.loads(output.read_text())["hitObjects"]
