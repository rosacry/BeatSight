"""
Export Package for Drum Classification Models

This package provides tools for exporting trained models to
various formats for production deployment.

Features:
- ONNX Export with dynamic batch size
- INT8/FP16 Quantization for faster inference
- Validation and benchmarking utilities

Usage:
    from training.export import (
        export_onnx,
        quantize_onnx,
        validate_onnx_output,
        benchmark_onnx,
        export_for_deployment,
    )
    
    # Simple export
    export_onnx(model, 'model.onnx')
    
    # Export with quantization
    export_for_deployment(model, 'exports/', export_formats=['onnx', 'fp16', 'int8'])
"""

from training.export.onnx_export import (
    benchmark_onnx,
    export_for_deployment,
    export_onnx,
    quantize_onnx,
    validate_onnx_output,
)

__all__ = [
    'export_onnx',
    'quantize_onnx',
    'validate_onnx_output',
    'benchmark_onnx',
    'export_for_deployment',
]
