"""Exercise the actual ensemble merge with fixed model probabilities."""
from unittest.mock import Mock

import numpy as np
import pytest

from transcription.multilabel_inference import MultiLabelDrumClassifier


def classifier_with_fixed_predictions():
    classifier = object.__new__(MultiLabelDrumClassifier)
    classifier.idx_to_class = {0: "hihat_closed", 1: "crash", 2: "china"}
    classifier.per_class_thresholds = {name: 0.5 for name in classifier.idx_to_class.values()}
    classifier.threshold = 0.5
    classifier._extract_spectrograms_batch = Mock(return_value=([np.zeros((2, 2))], [0], 0))
    classifier._run_batch_inference = Mock(return_value=np.array([[0.99, 0.6, 0.6]]))
    return classifier


@pytest.mark.parametrize("level", [0.05, 0.3])
def test_disabled_section_gate_preserves_model_predictions_independent_of_global_volume(level):
    classifier = classifier_with_fixed_predictions()
    audio = np.full(4000, level)
    result = classifier.classify_batch_ensemble(audio, audio, 1000, [2.0],
                                                use_rms_section_gating=False)
    assert set(result[0]) == {"hihat_closed", "crash", "china"}


def test_legacy_section_gate_suppresses_even_confident_hihat_in_loud_audio():
    classifier = classifier_with_fixed_predictions()
    audio = np.full(4000, 0.3)
    result = classifier.classify_batch_ensemble(audio, audio, 1000, [2.0])
    assert "hihat_closed" not in result[0]
    assert {"crash", "china"} <= result[0].keys()
