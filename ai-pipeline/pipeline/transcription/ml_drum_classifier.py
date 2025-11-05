"""Compatibility shim forwarding to the standalone transcription module."""

from transcription.ml_drum_classifier import MLDrumClassifier  # noqa: F401


__all__ = ["DrumClassifierModel", "MLDrumClassifier"]


class DrumClassifierModel(MLDrumClassifier):
	"""Compatibility wrapper providing attribute expected by the legacy API."""

	def classify_batch(self, audio, sr, onsets, **kwargs):
		results = []
		for onset in onsets:
			results.append(self.classify_onset(audio, sr, onset, **kwargs))
		return results
