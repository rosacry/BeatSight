#!/usr/bin/env python3
"""
Production Model Export Script

Run this after training to create all optimized model variants for deployment.

Usage:
    # On Lambda Labs (after training):
    python -m training.scripts.export_production \
        --checkpoint /workspace/outputs/best_model.pth \
        --output-dir /workspace/outputs/production \
        --cache-dir /workspace/feature_cache

    # This creates:
    # 1. drum_classifier_static_int8.onnx  - Base production model (required)
    # 2. drum_classifier_epcontext.onnx   - Pre-compiled TensorRT (optional)
    # 3. drum_classifier_sparse.onnx      - 2:4 sparse variant (optional)
    # 4. drum_classifier_sparse_trt.onnx  - Sparse TensorRT (optional)

After running:
    1. Upload models to Modal volume:
       modal volume put beatsight-models /workspace/outputs/production /models/
    
    2. Redeploy Modal app:
       modal deploy modal_app.py

Speed comparison:
    Baseline PyTorch:  ~50ms/sample
    Static INT8:       ~7-10ms/sample  ← Default production
    + EPContext:       same speed, <2s cold start instead of 30-60s
    + 2:4 Sparsity:    ~4-6ms/sample   ← Maximum throughput
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Add parent path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def main():
    parser = argparse.ArgumentParser(
        description="Export production-optimized model variants",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--checkpoint",
        required=True,
        help="Path to trained PyTorch checkpoint (.pth)",
    )
    parser.add_argument(
        "--output-dir",
        default="./production_models",
        help="Output directory for exported models",
    )
    parser.add_argument(
        "--cache-dir",
        help="Path to feature cache for calibration data (optional but recommended)",
    )
    parser.add_argument(
        "--model-name",
        default="drum_classifier",
        help="Base name for output files",
    )
    parser.add_argument(
        "--calibration-samples",
        type=int,
        default=1000,
        help="Number of samples for INT8 calibration",
    )
    parser.add_argument(
        "--precision",
        choices=["int8", "fp16"],
        default="int8",
        help="Quantization precision",
    )
    parser.add_argument(
        "--no-epcontext",
        action="store_true",
        help="Skip EPContext export (requires TensorRT)",
    )
    parser.add_argument(
        "--with-sparsity",
        action="store_true",
        help="Also create 2:4 sparse variants",
    )
    parser.add_argument(
        "--with-fp8",
        action="store_true",
        help="Also create FP8 variant (requires H100/L40S/RTX4090)",
    )
    parser.add_argument(
        "--with-early-exit",
        action="store_true",
        help="Also create early exit variant (20-50%% speedup for easy samples)",
    )
    parser.add_argument(
        "--early-exit-thresholds",
        type=float,
        nargs=3,
        default=[0.95, 0.93, 0.90],
        help="Confidence thresholds for early exit [stage1, stage2, stage3]",
    )
    parser.add_argument(
        "--finetune-sparse",
        type=int,
        default=0,
        help="Number of epochs to fine-tune sparse model (0 = no fine-tuning)",
    )
    parser.add_argument(
        "--v5-size",
        choices=["small", "medium", "large"],
        default="large",
        help="V5 model size variant",
    )
    parser.add_argument(
        "--num-classes",
        type=int,
        default=22,
        help="Number of output classes",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger(__name__)
    
    # Validate inputs
    checkpoint_path = Path(args.checkpoint)
    if not checkpoint_path.exists():
        logger.error(f"Checkpoint not found: {checkpoint_path}")
        sys.exit(1)
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 70)
    logger.info("BeatSight Production Model Export")
    logger.info("=" * 70)
    logger.info(f"Checkpoint: {checkpoint_path}")
    logger.info(f"Output dir: {output_dir}")
    logger.info(f"Precision: {args.precision}")
    logger.info("=" * 70)
    
    import numpy as np
    import torch
    
    outputs = {}
    
    # ===========================================================================
    # Step 1: Generate calibration data
    # ===========================================================================
    logger.info("\n[Step 1/4] Generating calibration data...")
    
    calibration_data = None
    if args.cache_dir:
        try:
            from training.inference.production_optimizations import (
                create_calibration_data_from_cache,
            )
            calibration_data = create_calibration_data_from_cache(
                args.cache_dir,
                n_samples=args.calibration_samples,
            )
            logger.info(f"Loaded {len(calibration_data)} calibration samples from cache")
        except Exception as e:
            logger.warning(f"Could not load from cache: {e}")
    
    if calibration_data is None:
        logger.warning("Using random calibration data (less optimal)")
        calibration_data = np.random.randn(
            args.calibration_samples, 1, 128, 128
        ).astype(np.float32)
    
    # ===========================================================================
    # Step 2: Export Static INT8 ONNX
    # ===========================================================================
    logger.info("\n[Step 2/4] Exporting Static INT8 ONNX...")
    
    try:
        from training.inference.production_optimizations import export_static_int8
        
        int8_path = output_dir / f"{args.model_name}_static_int8.onnx"
        
        # Model configuration based on V5 size
        model_kwargs = {
            "v5_size": args.v5_size,
            "num_classes": args.num_classes,
        }
        
        export_static_int8(
            str(checkpoint_path),
            str(int8_path),
            calibration_data,
            model_version="v5",
            model_kwargs=model_kwargs,
        )
        
        outputs["static_int8"] = int8_path
        size_mb = int8_path.stat().st_size / (1024 * 1024)
        logger.info(f"✓ Static INT8 exported: {int8_path} ({size_mb:.1f} MB)")
        
    except Exception as e:
        logger.error(f"Static INT8 export failed: {e}")
        raise
    
    # ===========================================================================
    # Step 3: Export EPContext (Pre-compiled TensorRT)
    # ===========================================================================
    if not args.no_epcontext:
        logger.info("\n[Step 3/4] Exporting EPContext (pre-compiled TensorRT)...")
        
        try:
            from training.inference.advanced_optimizations import (
                export_embedded_tensorrt_engine,
            )
            
            epcontext_path = output_dir / f"{args.model_name}_epcontext.onnx"
            
            export_embedded_tensorrt_engine(
                int8_path,
                epcontext_path,
                calibration_data=calibration_data,
                precision=args.precision,
            )
            
            if epcontext_path.exists():
                outputs["epcontext"] = epcontext_path
                size_mb = epcontext_path.stat().st_size / (1024 * 1024)
                logger.info(f"✓ EPContext exported: {epcontext_path} ({size_mb:.1f} MB)")
            else:
                logger.warning("EPContext export did not create expected output file")
                
        except RuntimeError as e:
            if "TensorRT not available" in str(e):
                logger.warning(
                    "EPContext skipped: TensorRT not available.\n"
                    "Run this on Linux with TensorRT (Lambda Labs or Modal) to create EPContext."
                )
            else:
                logger.warning(f"EPContext export failed: {e}")
        except Exception as e:
            logger.warning(f"EPContext export failed: {e}")
    else:
        logger.info("\n[Step 3/4] EPContext skipped (--no-epcontext)")
    
    # ===========================================================================
    # Step 4: Create 2:4 Sparse Variants (Optional)
    # ===========================================================================
    if args.with_sparsity:
        logger.info("\n[Step 4/4] Creating 2:4 sparse model variant...")
        
        try:
            from training.inference.advanced_optimizations import (
                apply_structured_sparsity,
                export_sparse_model_onnx,
                export_sparse_tensorrt,
                finetune_sparse_model,
            )
            from training.models.cnn_v5 import cnn_v5_large, cnn_v5_medium, cnn_v5_small
            
            # Load model
            checkpoint = torch.load(str(checkpoint_path), map_location='cpu')
            state_dict = checkpoint.get('model_state_dict', checkpoint.get('state_dict', checkpoint))
            
            # Create model
            model_fn = {
                "small": cnn_v5_small,
                "medium": cnn_v5_medium,
                "large": cnn_v5_large,
            }[args.v5_size]
            model = model_fn(num_classes=args.num_classes, use_technique_heads=True)
            model.load_state_dict(state_dict, strict=False)
            
            # Apply 2:4 sparsity
            sparse_model = apply_structured_sparsity(model)
            
            # Save sparse checkpoint
            sparse_checkpoint_path = output_dir / f"{args.model_name}_sparse.pth"
            torch.save({
                'model_state_dict': sparse_model.state_dict(),
                'sparsity': '2:4',
                'v5_size': args.v5_size,
                'num_classes': args.num_classes,
            }, sparse_checkpoint_path)
            outputs["sparse_checkpoint"] = sparse_checkpoint_path
            logger.info(f"✓ Sparse checkpoint saved: {sparse_checkpoint_path}")
            
            # Export sparse ONNX
            sparse_onnx_path = output_dir / f"{args.model_name}_sparse.onnx"
            export_sparse_model_onnx(sparse_model, sparse_onnx_path)
            outputs["sparse_onnx"] = sparse_onnx_path
            
            # Export sparse TensorRT (if available)
            try:
                sparse_trt_path = output_dir / f"{args.model_name}_sparse_trt.onnx"
                export_sparse_tensorrt(sparse_onnx_path, sparse_trt_path)
                outputs["sparse_tensorrt"] = sparse_trt_path
                logger.info(f"✓ Sparse TensorRT exported: {sparse_trt_path}")
            except Exception as e:
                logger.warning(f"Sparse TensorRT export failed (requires TensorRT): {e}")
                
        except Exception as e:
            logger.warning(f"Sparsity export failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        logger.info("\n[Step 4/4] Sparsity skipped (use --with-sparsity to enable)")
    
    # ===========================================================================
    # Step 5: Create FP8 Variant (Optional - for H100/L40S/RTX4090)
    # ===========================================================================
    if args.with_fp8:
        logger.info("\n[Step 5/6] Creating FP8 TensorRT variant...")
        
        try:
            from training.inference.revolutionary_optimizations import (
                export_fp8_tensorrt,
                check_optimization_support,
            )
            
            # Check hardware support
            support = check_optimization_support()
            if support.fp8_supported:
                fp8_path = output_dir / f"{args.model_name}_fp8.trt"
                export_fp8_tensorrt(
                    int8_path,  # Use the INT8 ONNX as base
                    fp8_path,
                    calibration_data=calibration_data,
                )
                if fp8_path.exists():
                    outputs["fp8_tensorrt"] = fp8_path
                    size_mb = fp8_path.stat().st_size / (1024 * 1024)
                    logger.info(f"✓ FP8 TensorRT exported: {fp8_path} ({size_mb:.1f} MB)")
                    logger.info("  → 2× faster than INT8 on H100/L40S/RTX4090!")
            else:
                logger.warning(f"FP8 skipped: {support.fp8_reason}")
                logger.warning("Run on H100, L40S, or RTX 4090 for FP8 support")
                
        except Exception as e:
            logger.warning(f"FP8 export failed: {e}")
            import traceback
            traceback.print_exc()
    
    # ===========================================================================
    # Step 6: Create Early Exit Variant (Optional - 20-50% faster on easy samples)
    # ===========================================================================
    if args.with_early_exit:
        logger.info("\n[Step 6/6] Creating early exit model variant...")
        
        try:
            from training.inference.early_exit import (
                EarlyExitWrapper,
                export_early_exit_onnx,
            )
            from training.models.cnn_v5 import cnn_v5_large, cnn_v5_medium, cnn_v5_small
            
            # Load model
            checkpoint = torch.load(str(checkpoint_path), map_location='cpu')
            state_dict = checkpoint.get('model_state_dict', checkpoint.get('state_dict', checkpoint))
            
            # Create base model
            model_fn = {
                "small": cnn_v5_small,
                "medium": cnn_v5_medium,
                "large": cnn_v5_large,
            }[args.v5_size]
            base_model = model_fn(num_classes=args.num_classes, use_technique_heads=True)
            base_model.load_state_dict(state_dict, strict=False)
            
            # Wrap with early exit
            early_exit_model = EarlyExitWrapper(
                model=base_model,
                confidence_thresholds=args.early_exit_thresholds,
            )
            
            # Save early exit checkpoint (includes exit heads - needs training first)
            early_exit_checkpoint = output_dir / f"{args.model_name}_early_exit.pth"
            torch.save({
                'model_state_dict': early_exit_model.state_dict(),
                'confidence_thresholds': early_exit_model.confidence_thresholds,
                'v5_size': args.v5_size,
                'num_classes': args.num_classes,
            }, early_exit_checkpoint)
            outputs["early_exit_checkpoint"] = early_exit_checkpoint
            
            # Export main model ONNX (exit heads exported separately)
            early_exit_onnx = output_dir / f"{args.model_name}_early_exit.onnx"
            export_early_exit_onnx(early_exit_model, early_exit_onnx)
            outputs["early_exit_onnx"] = early_exit_onnx
            
            logger.info(f"✓ Early exit model exported: {early_exit_checkpoint}")
            logger.info(f"  Thresholds: {args.early_exit_thresholds}")
            logger.info("  → 20-50% speedup for easy samples (kicks, snares, hi-hats)")
            logger.info("")
            logger.info("  NOTE: Early exit heads need fine-tuning for optimal performance:")
            logger.info("    python -m training.scripts.finetune_early_exit \\")
            logger.info(f"        --checkpoint {early_exit_checkpoint} \\")
            logger.info("        --dataset $BEATSIGHT_DATASET_DIR \\")
            logger.info("        --epochs 5")
                
        except Exception as e:
            logger.warning(f"Early exit export failed: {e}")
            import traceback
            traceback.print_exc()
    
    # ===========================================================================
    # Summary
    # ===========================================================================
    logger.info("\n" + "=" * 70)
    logger.info("EXPORT COMPLETE")
    logger.info("=" * 70)
    
    for name, path in outputs.items():
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            logger.info(f"  {name:20} : {path} ({size_mb:.1f} MB)")
    
    logger.info("-" * 70)
    logger.info("NEXT STEPS:")
    logger.info("1. Upload to Modal volume:")
    logger.info(f"   modal volume put beatsight-models {output_dir} /models/")
    logger.info("")
    logger.info("2. Redeploy Modal app:")
    logger.info("   modal deploy modal_app.py")
    logger.info("")
    logger.info("3. Test inference:")
    logger.info("   modal run modal_app.py::GPUProcessor.process --job-id test ...")
    logger.info("=" * 70)
    
    return outputs


if __name__ == "__main__":
    main()
