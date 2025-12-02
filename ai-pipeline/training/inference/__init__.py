"""
Inference Utilities for Drum Classification

This module provides advanced inference techniques for improved
accuracy and uncertainty estimation at test time.

Optimization Stack (fastest → slowest):
1. revolutionary_optimizations.py - FP8, Flash Attention, Fused Kernels
2. advanced_optimizations.py - EPContext, 2:4 Sparsity, Dynamic Batching
3. production_optimizations.py - Static INT8, IO Binding, torch.compile
4. tensorrt_inference.py - TensorRT, CUDA Graphs, Multi-shape support
5. ultimate.py - Ensemble, TTA, Temperature calibration (accuracy-focused)
"""

from .tta import TTAWrapper, MCDropoutTTA, CombinedTTA

__all__ = [
    'TTAWrapper',
    'MCDropoutTTA', 
    'CombinedTTA',
]
