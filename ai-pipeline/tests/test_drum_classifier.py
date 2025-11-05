import numpy as np

from pipeline.transcription import drum_classifier


def _sine_pulse(duration: float = 0.2, frequency: float = 120.0, sr: int = 44100):
    samples = int(duration * sr)
    t = np.linspace(0.0, duration, samples, endpoint=False)
    audio = 0.9 * np.sin(2 * np.pi * frequency * t).astype(np.float32)
    return audio, sr


def test_classify_drums_forced_heuristic(monkeypatch):
    audio = _sine_pulse()
    hits = drum_classifier.classify_drums(
        audio,
        [(0.05, 1.0)],
        confidence_threshold=0.0,
        use_ml=False,
    )

    assert hits, "expected at least one classified hit"
    assert hits[0]["ml_based"] is False
    assert drum_classifier.classify_drums.last_classifier_mode == "heuristic"
    assert drum_classifier.classify_drums.last_classifier_model_path is None


def test_classify_drums_missing_model_falls_back(monkeypatch, tmp_path):
    bogus_path = tmp_path / "missing_model.pth"
    audio = _sine_pulse()

    hits = drum_classifier.classify_drums(
        audio,
        [(0.05, 1.0)],
        confidence_threshold=0.0,
        use_ml=True,
        model_path=str(bogus_path),
    )

    assert hits, "fallback should still produce heuristic classifications"
    assert drum_classifier.classify_drums.last_classifier_mode == "heuristic"
    assert hits[0]["ml_based"] is False


def test_env_toggle_disables_ml(monkeypatch):
    monkeypatch.setenv("BEATSIGHT_USE_ML_CLASSIFIER", "0")
    monkeypatch.delenv("BEATSIGHT_ML_MODEL_PATH", raising=False)

    audio = _sine_pulse()
    drum_classifier.classify_drums(
        audio,
        [(0.05, 1.0)],
        confidence_threshold=0.0,
    )

    assert drum_classifier.classify_drums.last_classifier_mode == "heuristic"
