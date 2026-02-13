"""
ONNX Export with Quantization for Production Inference

This module exports PyTorch models to ONNX format with optional quantization
for fast production inference.

Features:
1. ONNX Export - Standard export with dynamic axes for batch size
2. INT8 Quantization - 3-4x speedup with minimal accuracy loss
3. Float16 Export - 2x smaller models for GPU inference
4. Validation - Numerical consistency checks

Expected Benefits:
- 3-4x faster inference with INT8 quantization
- 2x smaller model size with FP16
- Cross-platform deployment (C++, mobile, edge devices)

Usage:
    python export_onnx.py --checkpoint model.pt --output model.onnx --quantize int8
    
    # Or programmatically:
    from training.export.onnx_export import export_onnx, quantize_onnx
    export_onnx(model, 'model.onnx', input_shape=(1, 1, 128, 128))
    quantize_onnx('model.onnx', 'model_int8.onnx', quantization='int8')
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


def export_onnx(
    model: nn.Module,
    output_path: Union[str, Path],
    input_shape: Tuple[int, ...] = (1, 1, 128, 128),
    opset_version: int = 14,
    dynamic_batch: bool = True,
    input_names: List[str] = None,
    output_names: List[str] = None,
    simplify: bool = True,
    verbose: bool = False,
) -> Path:
    """
    Export PyTorch model to ONNX format.
    
    Args:
        model: PyTorch model to export
        output_path: Path for output ONNX file
        input_shape: Shape of input tensor (batch, channels, height, width)
        opset_version: ONNX opset version (14+ recommended)
        dynamic_batch: Allow dynamic batch size
        input_names: Names for input tensors
        output_names: Names for output tensors
        simplify: Use onnx-simplifier to optimize graph
        verbose: Print export details
    
    Returns:
        Path to exported ONNX file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    model.eval()
    
    # Create dummy input
    dummy_input = torch.randn(input_shape)
    
    # Default names
    if input_names is None:
        input_names = ['input']
    if output_names is None:
        output_names = ['output']
    
    # Dynamic axes for batch size
    dynamic_axes = None
    if dynamic_batch:
        dynamic_axes = {
            input_names[0]: {0: 'batch_size'},
            output_names[0]: {0: 'batch_size'},
        }
    
    # Export to ONNX
    logger.info(f"Exporting model to ONNX: {output_path}")
    
    torch.onnx.export(
        model,
        dummy_input,
        str(output_path),
        export_params=True,
        opset_version=opset_version,
        do_constant_folding=True,
        input_names=input_names,
        output_names=output_names,
        dynamic_axes=dynamic_axes,
        verbose=verbose,
    )
    
    # Simplify graph if requested
    if simplify:
        try:
            import onnx
            from onnxsim import simplify as onnx_simplify
            
            logger.info("Simplifying ONNX graph...")
            onnx_model = onnx.load(str(output_path))
            
            # Run simplification
            simplified_model, check = onnx_simplify(onnx_model)
            
            if check:
                onnx.save(simplified_model, str(output_path))
                logger.info("Graph simplified successfully")
            else:
                logger.warning("Simplification check failed, keeping original")
                
        except ImportError:
            logger.warning("onnxsim not installed, skipping simplification")
    
    # Validate export
    try:
        import onnx
        onnx_model = onnx.load(str(output_path))
        onnx.checker.check_model(onnx_model)
        logger.info("ONNX model validation passed")
    except ImportError:
        logger.warning("onnx not installed, skipping validation")
    
    # Log model size
    file_size = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Exported model size: {file_size:.2f} MB")
    
    return output_path


def quantize_onnx(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    quantization: str = 'int8',  # 'int8', 'uint8', 'fp16'
    calibration_data: Optional[np.ndarray] = None,
    per_channel: bool = True,
) -> Path:
    """
    Quantize ONNX model for faster inference.
    
    Args:
        input_path: Path to input ONNX model
        output_path: Path for quantized output model
        quantization: Quantization type ('int8', 'uint8', 'fp16')
        calibration_data: Representative data for calibration (for int8)
        per_channel: Use per-channel quantization (more accurate)
    
    Returns:
        Path to quantized model
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    if quantization == 'fp16':
        return _convert_to_fp16(input_path, output_path)
    elif quantization in ('int8', 'uint8'):
        return _quantize_to_int(input_path, output_path, quantization, calibration_data, per_channel)
    else:
        raise ValueError(f"Unknown quantization type: {quantization}")


def _convert_to_fp16(
    input_path: Path,
    output_path: Path,
) -> Path:
    """Convert ONNX model to float16."""
    try:
        import onnx
        from onnxconverter_common import float16
        
        logger.info("Converting to FP16...")
        
        model = onnx.load(str(input_path))
        model_fp16 = float16.convert_float_to_float16(model)
        onnx.save(model_fp16, str(output_path))
        
        # Log size reduction
        original_size = input_path.stat().st_size / (1024 * 1024)
        new_size = output_path.stat().st_size / (1024 * 1024)
        reduction = (1 - new_size / original_size) * 100
        
        logger.info(f"FP16 conversion complete: {original_size:.2f} MB -> {new_size:.2f} MB ({reduction:.1f}% reduction)")
        
        return output_path
        
    except ImportError as e:
        raise ImportError(
            "onnxconverter-common required for FP16 conversion. "
            "Install with: pip install onnxconverter-common"
        ) from e


def _quantize_to_int(
    input_path: Path,
    output_path: Path,
    quantization: str,
    calibration_data: Optional[np.ndarray],
    per_channel: bool,
) -> Path:
    """Quantize ONNX model to INT8/UINT8."""
    try:
        import onnx
        from onnxruntime.quantization import (
            CalibrationDataReader,
            QuantFormat,
            QuantType,
            quantize_dynamic,
            quantize_static,
        )
        
        logger.info(f"Quantizing to {quantization.upper()}...")
        
        weight_type = QuantType.QInt8 if quantization == 'int8' else QuantType.QUInt8
        
        if calibration_data is not None:
            # Static quantization (more accurate, requires calibration)
            
            class CalibrationReader(CalibrationDataReader):
                def __init__(self, data: np.ndarray):
                    self.data = data
                    self.index = 0
                
                def get_next(self):
                    if self.index >= len(self.data):
                        return None
                    
                    sample = self.data[self.index:self.index+1]
                    self.index += 1
                    return {'input': sample.astype(np.float32)}
            
            reader = CalibrationReader(calibration_data)
            
            quantize_static(
                str(input_path),
                str(output_path),
                reader,
                quant_format=QuantFormat.QDQ,
                per_channel=per_channel,
                weight_type=weight_type,
            )
        else:
            # Dynamic quantization (no calibration needed)
            quantize_dynamic(
                str(input_path),
                str(output_path),
                weight_type=weight_type,
                per_channel=per_channel,
            )
        
        # Log size reduction
        original_size = input_path.stat().st_size / (1024 * 1024)
        new_size = output_path.stat().st_size / (1024 * 1024)
        reduction = (1 - new_size / original_size) * 100
        
        logger.info(f"Quantization complete: {original_size:.2f} MB -> {new_size:.2f} MB ({reduction:.1f}% reduction)")
        
        return output_path
        
    except ImportError as e:
        raise ImportError(
            "onnxruntime required for quantization. "
            "Install with: pip install onnxruntime"
        ) from e


def validate_onnx_output(
    pytorch_model: nn.Module,
    onnx_path: Union[str, Path],
    test_input: torch.Tensor = None,
    rtol: float = 1e-3,
    atol: float = 1e-5,
) -> bool:
    """
    Validate that ONNX model produces same output as PyTorch model.
    
    Args:
        pytorch_model: Original PyTorch model
        onnx_path: Path to ONNX model
        test_input: Test input tensor (optional)
        rtol: Relative tolerance
        atol: Absolute tolerance
    
    Returns:
        True if outputs match within tolerance
    """
    try:
        import onnxruntime as ort
        
        onnx_path = Path(onnx_path)
        
        # Create test input if not provided
        if test_input is None:
            test_input = torch.randn(1, 1, 128, 128)
        
        # Get PyTorch output
        pytorch_model.eval()
        with torch.no_grad():
            pytorch_output = pytorch_model(test_input).numpy()
        
        # Get ONNX output
        session = ort.InferenceSession(str(onnx_path))
        input_name = session.get_inputs()[0].name
        onnx_output = session.run(None, {input_name: test_input.numpy()})[0]
        
        # Compare outputs
        is_close = np.allclose(pytorch_output, onnx_output, rtol=rtol, atol=atol)
        
        if is_close:
            logger.info("ONNX output validation passed")
        else:
            max_diff = np.abs(pytorch_output - onnx_output).max()
            mean_diff = np.abs(pytorch_output - onnx_output).mean()
            logger.warning(f"ONNX output differs from PyTorch: max_diff={max_diff:.6f}, mean_diff={mean_diff:.6f}")
        
        return is_close
        
    except ImportError:
        logger.warning("onnxruntime not installed, skipping validation")
        return True


def benchmark_onnx(
    onnx_path: Union[str, Path],
    input_shape: Tuple[int, ...] = (1, 1, 128, 128),
    n_runs: int = 100,
    warmup_runs: int = 10,
    use_gpu: bool = False,
) -> Dict[str, float]:
    """
    Benchmark ONNX model inference speed.
    
    Args:
        onnx_path: Path to ONNX model
        input_shape: Shape of input tensor
        n_runs: Number of benchmark runs
        warmup_runs: Number of warmup runs
        use_gpu: Use GPU for inference
    
    Returns:
        Dictionary with timing statistics
    """
    import time
    
    try:
        import onnxruntime as ort
        
        onnx_path = Path(onnx_path)
        
        # Create session
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if use_gpu else ['CPUExecutionProvider']
        session = ort.InferenceSession(str(onnx_path), providers=providers)
        
        input_name = session.get_inputs()[0].name
        test_input = np.random.randn(*input_shape).astype(np.float32)
        
        # Warmup
        for _ in range(warmup_runs):
            session.run(None, {input_name: test_input})
        
        # Benchmark
        times = []
        for _ in range(n_runs):
            start = time.perf_counter()
            session.run(None, {input_name: test_input})
            times.append(time.perf_counter() - start)
        
        times = np.array(times) * 1000  # Convert to ms
        
        results = {
            'mean_ms': float(np.mean(times)),
            'std_ms': float(np.std(times)),
            'min_ms': float(np.min(times)),
            'max_ms': float(np.max(times)),
            'p50_ms': float(np.percentile(times, 50)),
            'p95_ms': float(np.percentile(times, 95)),
            'p99_ms': float(np.percentile(times, 99)),
            'throughput': float(1000 / np.mean(times)),  # samples/sec
        }
        
        logger.info(
            f"Benchmark results: {results['mean_ms']:.2f}±{results['std_ms']:.2f} ms "
            f"({results['throughput']:.0f} samples/sec)"
        )
        
        return results
        
    except ImportError:
        logger.error("onnxruntime not installed")
        return {}


def export_for_deployment(
    model: nn.Module,
    output_dir: Union[str, Path],
    model_name: str = 'drum_classifier',
    input_shape: Tuple[int, ...] = (1, 1, 128, 128),
    export_formats: List[str] = None,
    calibration_data: Optional[np.ndarray] = None,
) -> Dict[str, Path]:
    """
    Export model in multiple formats for deployment.
    
    Args:
        model: PyTorch model to export
        output_dir: Directory for output files
        model_name: Base name for output files
        input_shape: Shape of input tensor
        export_formats: List of formats to export ('onnx', 'fp16', 'int8')
        calibration_data: Calibration data for INT8 quantization
    
    Returns:
        Dictionary mapping format to output path
    """
    if export_formats is None:
        export_formats = ['onnx', 'fp16', 'int8']
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    outputs = {}
    
    # Export base ONNX first
    onnx_path = output_dir / f"{model_name}.onnx"
    export_onnx(model, onnx_path, input_shape)
    outputs['onnx'] = onnx_path
    
    # Validate base export
    validate_onnx_output(model, onnx_path)
    
    # Export FP16
    if 'fp16' in export_formats:
        fp16_path = output_dir / f"{model_name}_fp16.onnx"
        try:
            quantize_onnx(onnx_path, fp16_path, 'fp16')
            outputs['fp16'] = fp16_path
        except Exception as e:
            logger.warning(f"FP16 export failed: {e}")
    
    # Export INT8
    if 'int8' in export_formats:
        int8_path = output_dir / f"{model_name}_int8.onnx"
        try:
            quantize_onnx(onnx_path, int8_path, 'int8', calibration_data)
            outputs['int8'] = int8_path
        except Exception as e:
            logger.warning(f"INT8 export failed: {e}")
    
    # Benchmark all formats
    logger.info("\nBenchmarking all formats:")
    for format_name, path in outputs.items():
        logger.info(f"\n{format_name.upper()}:")
        benchmark_onnx(path, input_shape)
    
    return outputs


def main():
    """Command-line interface for ONNX export."""
    parser = argparse.ArgumentParser(
        description="Export PyTorch models to ONNX with quantization"
    )
    
    parser.add_argument(
        '--checkpoint', '-c',
        type=str,
        required=True,
        help='Path to PyTorch checkpoint (.pt or .pth)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        required=True,
        help='Output path for ONNX model'
    )
    
    parser.add_argument(
        '--model-version',
        type=str,
        default='v2',
        choices=['v1', 'v2', 'v3', 'v4'],
        help='Model architecture version'
    )
    
    parser.add_argument(
        '--num-classes',
        type=int,
        default=21,
        help='Number of output classes'
    )
    
    parser.add_argument(
        '--quantize',
        type=str,
        default=None,
        choices=['fp16', 'int8', 'uint8'],
        help='Quantization type'
    )
    
    parser.add_argument(
        '--benchmark',
        action='store_true',
        help='Run inference benchmark'
    )
    
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate ONNX output matches PyTorch'
    )
    
    parser.add_argument(
        '--opset',
        type=int,
        default=14,
        help='ONNX opset version'
    )
    
    parser.add_argument(
        '--no-simplify',
        action='store_true',
        help='Skip ONNX graph simplification'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Load model
    logger.info(f"Loading checkpoint: {args.checkpoint}")
    
    checkpoint = torch.load(args.checkpoint, map_location='cpu')
    
    # Get model weights
    if isinstance(checkpoint, dict):
        state_dict = checkpoint.get('model_state_dict', checkpoint.get('state_dict', checkpoint))
    else:
        state_dict = checkpoint.state_dict() if hasattr(checkpoint, 'state_dict') else checkpoint
    
    # Create model architecture
    # Import here to avoid circular imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    if args.model_version == 'v1':
        from models.classifier import DrumClassifierCNN
        model = DrumClassifierCNN(num_classes=args.num_classes)
    elif args.model_version == 'v2':
        from models.classifier import DrumClassifierCNNv2
        model = DrumClassifierCNNv2(num_classes=args.num_classes)
    elif args.model_version == 'v3':
        from models.cbam import DrumClassifierCNNv3
        model = DrumClassifierCNNv3(num_classes=args.num_classes)
    elif args.model_version == 'v4':
        from models.coord_attention import DrumClassifierCNNv4
        model = DrumClassifierCNNv4(num_classes=args.num_classes)
    
    model.load_state_dict(state_dict, strict=False)
    model.eval()
    
    # Export to ONNX
    output_path = Path(args.output)
    export_onnx(
        model,
        output_path,
        opset_version=args.opset,
        simplify=not args.no_simplify,
    )
    
    # Validate if requested
    if args.validate:
        validate_onnx_output(model, output_path)
    
    # Quantize if requested
    if args.quantize:
        quantized_path = output_path.with_stem(f"{output_path.stem}_{args.quantize}")
        quantize_onnx(output_path, quantized_path, args.quantize)
        
        if args.validate:
            # Note: quantized models will have some numerical difference
            validate_onnx_output(model, quantized_path, rtol=0.1, atol=0.01)
    
    # Benchmark if requested
    if args.benchmark:
        logger.info("\nBenchmarking ONNX model:")
        benchmark_onnx(output_path)
        
        if args.quantize:
            logger.info(f"\nBenchmarking {args.quantize} model:")
            benchmark_onnx(quantized_path)
    
    logger.info("\nExport complete!")


if __name__ == '__main__':
    main()
