"""ADTOF Frame_RNN network (BeatSight implementation of the published architecture).

Two CNN blocks (3x3 conv, ReLU, batch norm, 3x3 conv, ReLU, batch norm, frequency
max pooling /3, dropout) feed three bidirectional 60-unit GRUs and a five-way
sigmoid output. With Frame_RNN context 9 the four 3x3 convolutions already supply
the temporal receptive field, so no extra context layer is used.

Pooling follows TensorFlow SAME semantics: padded positions never win the maximum.
torch.nn.GRU matches Keras GRU(reset_after=True) for the converted gate layout.
Both points were verified against the original TensorFlow checkpoint to 1.13e-6
(docs/ADTOF_MODEL_CONVERSION_AUDIT_2026-10-15.md).
"""
import hashlib
from pathlib import Path

import torch
from torch import nn

N_BINS = 84
WEIGHTS_FILENAME = "adtof_frame_rnn_pytorch_weights.pth"
# Converted Frame_RNN_adtofAll_0 weights audited on 2026-10-15 (50 tensors, exact match).
WEIGHTS_SHA256 = "1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320"


class FrequencyMaxPool(nn.Module):
    """Max pool (1, 3) with stride (1, 3) and TensorFlow SAME padding on frequency."""

    def forward(self, x):
        width = x.shape[-1]
        output_width = (width + 2) // 3
        padding = max(0, (output_width - 1) * 3 + 3 - width)
        if padding:
            left = padding // 2
            x = nn.functional.pad(x, (left, padding - left, 0, 0), value=float("-inf"))
        return nn.functional.max_pool2d(x, kernel_size=(1, 3), stride=(1, 3))


def _cnn_block(in_channels, filters):
    return nn.Sequential(
        nn.Conv2d(in_channels, filters, kernel_size=3, padding=1),
        nn.ReLU(),
        nn.BatchNorm2d(filters, eps=1e-3),
        nn.Conv2d(filters, filters, kernel_size=3, padding=1),
        nn.ReLU(),
        nn.BatchNorm2d(filters, eps=1e-3),
        FrequencyMaxPool(),
        nn.Dropout2d(0.3),
    )


class FrameRnn(nn.Module):
    def __init__(self):
        super().__init__()
        self.cnn_blocks = nn.ModuleList([_cnn_block(1, 32), _cnn_block(32, 64)])
        # 84 bins -> 28 -> 10 after two poolings; 10 x 64 channels per frame.
        self.gru_layers = nn.ModuleList([
            nn.GRU(640, 60, batch_first=True, bidirectional=True),
            nn.GRU(120, 60, batch_first=True, bidirectional=True),
            nn.GRU(120, 60, batch_first=True, bidirectional=True),
        ])
        self.output_layer = nn.Linear(120, 5)

    def forward(self, features):
        """features: (batch, frames, 84, 1) -> activations (batch, frames, 5)."""
        batch, frames = features.shape[:2]
        x = features.permute(0, 3, 1, 2)
        for block in self.cnn_blocks:
            x = block(x)
        # Flatten frequency-major, then channels, per frame (matches the original reshape).
        x = x.permute(0, 2, 3, 1).reshape(batch, frames, -1)
        for gru in self.gru_layers:
            x, _ = gru(x)
        return torch.sigmoid(self.output_layer(x))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_model(weights_path):
    """Load the audited converted weights; refuse any other file."""
    weights_path = Path(weights_path)
    if not weights_path.is_file():
        raise FileNotFoundError(
            f"ADTOF weights not found at {weights_path}. Restore the audited file or switch "
            "the transcription engine to Legacy in BeatSight's AI settings.")
    actual = sha256(weights_path)
    if actual != WEIGHTS_SHA256:
        raise ValueError(f"ADTOF weights at {weights_path} have SHA-256 {actual}, not the audited {WEIGHTS_SHA256}.")
    checkpoint = torch.load(weights_path, map_location="cpu", weights_only=True)
    model = FrameRnn()
    model.load_state_dict(checkpoint["model_weights"], strict=True)
    return model.eval()
