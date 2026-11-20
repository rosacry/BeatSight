"""ADTOF Frame_RNN drum transcription engine for BeatSight.

Implements the published ADTOF Frame_RNN model (Zehren, Alunno and Bientinesi,
ISMIR 2021; Signals 2023) as verified by the 2026-10-15 recovery audits:
madmom-equivalent frontend, TensorFlow-equivalent max pooling, primary madmom
peak picking. The model code here is BeatSight's own implementation.

Weights are NOT part of this repository. They are the ADTOF authors'
Frame_RNN_adtofAll_0 checkpoint converted to PyTorch, licensed CC BY-NC-SA 4.0
(https://github.com/MZehren/ADTOF): non-commercial use with attribution only.
Distribution in a commercial product requires the authors' permission.
"""

FAMILIES = ("kick", "snare", "tom", "hihat", "cymbal")
