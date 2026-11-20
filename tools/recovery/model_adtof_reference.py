"""Recovery-only correction of the pinned model's SAME max-pool boundary.

TensorFlow's finite-input max pooling excludes padded positions from the maximum.
Batch normalization can make its inputs negative even after a preceding ReLU.
This changes no weights, recurrent equations, frontend, decoder or app default.
"""
import torch
from torch import nn


class ReferenceWidthMaxPool(nn.Module):
    def forward(self, x):
        width = x.shape[-1]
        output_width = (width + 2) // 3
        padding = max(0, (output_width - 1) * 3 + 3 - width)
        left = padding // 2
        if padding:
            x = torch.nn.functional.pad(x, (left, padding-left, 0, 0), value=float('-inf'))
        return torch.nn.functional.max_pool2d(x, kernel_size=(1,3), stride=(1,3))


def replace_pooling(model):
    """Apply only to a newly instantiated experimental model, never a saved file."""
    if len(model.cnn_blocks) != 2:
        raise ValueError('Expected the fixed two-block Frame_RNN')
    for block in model.cnn_blocks:
        if type(block[6]).__name__ != 'SamePadWidthMaxPool':
            raise ValueError('Unexpected model pooling structure')
    for block in model.cnn_blocks:
        block[6] = ReferenceWidthMaxPool()
    return model
