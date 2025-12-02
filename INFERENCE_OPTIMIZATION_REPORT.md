# BeatSight Inference Optimization Report

**Generated:** December 1, 2025  
**Target Model:** V5-Large CNN (~2-3M parameters)  
**Target Hardware:** NVIDIA GPUs (A10G, L40S, H100)

---

## Executive Summary

The BeatSight codebase has an **extensive** inference optimization stack with 4 specialized modules containing 15+ distinct optimizations. Most optimizations are **fully implemented** but many are **conditionally used** in production (Modal) depending on available model files and hardware.

| Category | Implemented | Used in Production | Potential Additions |
|----------|-------------|-------------------|---------------------|
| Quantization | 4 | 2 (INT8, FP8) | AWQ, GPTQ (N/A for CNN) |
| CUDA/Kernel | 5 | 3 | Custom Triton kernels |
| Architecture | 3 | 1 | Early Exit, MoE |
| Batching | 2 | 1 | Continuous batching |
| Distillation | 3 | 0 (not in inference) | — |

---

## 1. ALREADY IMPLEMENTED ✅

### 1.1 Quantization Optimizations

| Optimization | File | Speed Improvement | In Production? | Notes |
|-------------|------|-------------------|----------------|-------|
| **Static INT8 Quantization** | `production_optimizations.py` | +15-20% over dynamic INT8 | ✅ Yes | Uses calibration data for optimal scale factors |
| **Dynamic INT8** | `tensorrt_inference.py` | 4x over FP32 | ✅ Yes (fallback) | Simpler but less optimal |
| **FP16 Precision** | `tensorrt_inference.py` | 2-3x over FP32 | ✅ Yes (fallback) | For non-INT8 GPUs |
| **FP8 Quantization** | `revolutionary_optimizations.py` | 2x over INT8 | 🟡 Conditional | Only on H100/L40S (Ada/Hopper GPUs, sm_89+) |

**Production Status:** Modal `GPUProcessor.__enter__` prioritizes:
1. FP8 TensorRT (`.trt` files) → 2x faster on L40S/H100
2. EPContext models → instant cold start
3. Static INT8 ONNX → best quality/speed tradeoff
4. Fallbacks (dynamic INT8, FP16)

### 1.2 CUDA/GPU Optimizations

| Optimization | File | Speed Improvement | In Production? | Notes |
|-------------|------|-------------------|----------------|-------|
| **CUDA Graphs** | `tensorrt_inference.py`, `advanced_optimizations.py` | +10-15% | ✅ Yes | Eliminates kernel launch overhead |
| **IO Binding** | `production_optimizations.py` | +5-10% | ✅ Yes | Pre-allocated GPU buffers, zero-copy |
| **TensorRT Acceleration** | `tensorrt_inference.py` | 2-4x over PyTorch | ✅ Yes | Via ONNX Runtime TensorRT EP |
| **torch.compile** | `production_optimizations.py` | +10-30% | ✅ Yes | Applied to Demucs model in Modal |
| **Multi-Shape CUDA Graphs** | `tensorrt_inference.py` | +10-15% | ✅ Yes | Pre-captures graphs for common batch sizes |

**Code Evidence (modal_app.py:287-302):**
```python
if hasattr(torch, 'compile'):
    self.demucs_model = torch.compile(
        self.demucs_model,
        mode="reduce-overhead",
        fullgraph=False,
    )
```

### 1.3 Advanced Inference Optimizations

| Optimization | File | Speed Improvement | In Production? | Notes |
|-------------|------|-------------------|----------------|-------|
| **EPContext (Pre-compiled TensorRT)** | `advanced_optimizations.py` | Cold start: 30s → <2s | ✅ Yes | Engine embedded in ONNX file |
| **2:4 Structured Sparsity** | `advanced_optimizations.py` | 2x compute on Ampere+ | 🟡 Conditional | Requires sparse model export |
| **Fused Conv+BN+SiLU Kernels** | `revolutionary_optimizations.py` | +20-40% | 🟡 Partial | BN fusion works, full Triton kernels need Linux |
| **GPU Mel-Spectrograms** | `revolutionary_optimizations.py` | 30% faster preprocessing | ❌ Not used | Implemented but not integrated in pipeline |
| **Flash Attention v2** | `revolutionary_optimizations.py` | 2-4x attention speedup | ❌ Not applicable | CNN model doesn't use standard attention |

### 1.4 Batching & Pipeline Optimizations

| Optimization | File | Speed Improvement | In Production? | Notes |
|-------------|------|-------------------|----------------|-------|
| **Speculative Batching** | `advanced_optimizations.py` | Variable (traffic-dependent) | ❌ Not used | Implemented for high-traffic scenarios |
| **Sparse Inference Filter** | `optimized_pipeline.py` | +10-20% | 🟡 Conditional | Skips quiet sections |
| **Batched Onset Detection** | `optimized_pipeline.py` | +5-10% | 🟡 Partial | Parallel CPU onset + GPU spec |
| **Warm Container Pool** | `modal_app.py` | Cold start: 30s → instant | ✅ Yes | `container_idle_timeout=300` |

### 1.5 Model Distillation (Training-time, not Inference)

| Optimization | File | Size Reduction | Accuracy Loss | Status |
|-------------|------|----------------|---------------|--------|
| **Knowledge Distillation** | `distill_model.py` | 50-75% smaller | 5-10% | ✅ Implemented |
| **Self-Distillation (Born-Again)** | `auto_train.sh` | Same size | +1-2% gain | ✅ Implemented |
| **Progressive Layer Pruning** | `distill_model.py` | Variable | Variable | ✅ Implemented |

---

## 2. NOT YET IMPLEMENTED 🔴

### 2.1 High-Impact Additions (Recommended)

| Optimization | Expected Speedup | Complexity | Accuracy Impact | Notes |
|-------------|------------------|------------|-----------------|-------|
| **Custom Triton Kernels** | +20-40% | High | None | Fuse entire forward pass into single kernel |
| **Speculative Decoding** | N/A | N/A | N/A | Not applicable for classification |
| **Early Exit Branches** | +20-50% | Medium | -1-2% | Exit early for high-confidence predictions |
| **NVIDIA TensorRT-LLM** | N/A | N/A | N/A | For transformer models only |

### 2.2 Architecture-Level Optimizations

| Optimization | Expected Benefit | Complexity | Status |
|-------------|------------------|------------|--------|
| **Mixture of Experts (MoE)** | 2-4x speedup at same quality | Very High | Not applicable (too complex for CNN) |
| **Conditional Computation** | +10-30% | High | Worth exploring for multi-class |
| **Channel Pruning** | 30-50% smaller | Medium | Not implemented |
| **Weight Sharing** | 20-40% smaller | Medium | Not implemented |

### 2.3 2024-2025 Cutting-Edge Techniques

| Technique | Paper/Source | Expected Benefit | Feasibility |
|-----------|--------------|------------------|-------------|
| **AWQ (Activation-aware Weight Quantization)** | MIT, 2024 | Better INT4 quality | 🟡 For LLMs, limited CNN benefit |
| **GPTQ** | Frantar et al. | INT4 quantization | 🟡 For LLMs, limited CNN benefit |
| **SmoothQuant** | Xiao et al. 2023 | Better INT8 activation quantization | ✅ Could help with INT8 |
| **FP4/INT4** | NVIDIA Hopper | 4x INT8 speed | 🟡 Accuracy risk for small CNN |
| **ONNX Graph Optimizations** | Microsoft | +5-10% | ✅ Already using ORT optimizations |

---

## 3. GAPS - Partially Implemented or Not Integrated 🟡

### 3.1 Implemented but Not Used in Production

| Optimization | Status | Reason | Action Needed |
|-------------|--------|--------|---------------|
| **GPU Mel-Spectrograms** | Code exists | Not integrated in OptimizedPipeline | Wire `GPUMelSpectrogram` into pipeline |
| **Speculative Batching** | Code exists | Not deployed | Enable in Modal for high-traffic |
| **Flash Attention** | Code exists | CNN uses CoordinateAttention, not MHA | Not applicable |
| **2:4 Sparsity Export** | Code exists | No sparse model files in production | Run sparsity training + export |
| **Distilled Models (Tiny/Distilled)** | Code exists | Single-tier strategy uses V5-Large only | Could use for free tier |

### 3.2 Missing Model Files in Modal Volume

Based on `modal_app.py` model priority list, these files would enable optimizations but may not exist:

```python
# Priority order - higher = faster
"/models/v5_large_fp8.trt"           # FP8 TensorRT engine
"/models/v5_large_epcontext.onnx"    # Pre-compiled TensorRT
"/models/v5_large_sparse_trt.onnx"   # 2:4 sparse TensorRT
"/models/v5_large_static_int8.onnx"  # Static INT8 (likely exists)
```

**Recommendation:** Export and deploy these model variants for maximum performance.

### 3.3 Integration Gaps

| Gap | Current State | Fix |
|-----|---------------|-----|
| **GPU Spectrogram in Pipeline** | `revolutionary_optimizations.py` has `GPUMelSpectrogram` | Call `enable_gpu_spectrograms(pipeline)` in Modal |
| **Sparse Inference Filter** | `optimized_pipeline.py` has filter | Not used in Modal `_process_audio_impl` |
| **BatchedOnsetDetector** | Implemented | Not used in Modal pipeline |

---

## 4. Production Deployment Analysis (Modal)

### 4.1 Current Modal Configuration

```python
# From modal_app.py
GPU_TIER = os.environ.get("BEATSIGHT_GPU_TIER", "L40S")  # FP8 capable!
container_idle_timeout = 300  # Warm containers
allow_concurrent_inputs = 4   # Batched requests
```

### 4.2 Optimization Stack Active in Modal

| Layer | Optimization | Active |
|-------|--------------|--------|
| 1 | torch.compile (Demucs) | ✅ |
| 2 | FP8 TensorRT (if `.trt` exists) | 🟡 Conditional |
| 3 | EPContext (if exists) | 🟡 Conditional |
| 4 | Static INT8 + IO Binding | ✅ |
| 5 | CUDA Graphs | ✅ |
| 6 | Warm containers | ✅ |

### 4.3 Inference Speed Estimates

| Configuration | Latency (per sample) | Notes |
|---------------|---------------------|-------|
| Baseline PyTorch | ~50ms | Unoptimized |
| Current (A10G, INT8) | ~7-10ms | Production |
| With L40S + FP8 | ~2-3ms | If FP8 model deployed |
| Theoretical max | ~1-2ms | All optimizations + H100 |

---

## 5. Recommendations

### 5.1 Immediate Actions (High Impact, Low Effort)

1. **Export FP8 TensorRT model** - L40S is default GPU and supports FP8
   ```bash
   python -m training.inference.revolutionary_optimizations export \
       --checkpoint best_model.pth \
       --output-dir models/ \
       --enable-fp8
   ```

2. **Export EPContext model** - Eliminates cold start
   ```bash
   python -m training.inference.advanced_optimizations export-embedded \
       --onnx models/v5_large_static_int8.onnx \
       --output models/v5_large_epcontext.onnx
   ```

3. **Enable GPU spectrograms** - Add to Modal pipeline

### 5.2 Medium-Term (Week 1-2)

1. **Train 2:4 sparse model** - 2x compute speedup
   ```bash
   python -m training.inference.advanced_optimizations apply-sparsity \
       --checkpoint best_model.pth \
       --finetune-epochs 5
   ```

2. **Implement Early Exit** - Skip classifier for obvious predictions

3. **Integrate Sparse Inference Filter** - Skip quiet sections

### 5.3 Long-Term (Month+)

1. **Custom Triton kernels** - Fuse entire forward pass
2. **SmoothQuant** - Better INT8 activation quantization
3. **Explore FP4/INT4** - If accuracy permits

---

## 6. Summary Table

| Optimization | Implemented | In Production | Speed Gain | Effort to Enable |
|-------------|-------------|---------------|------------|------------------|
| Static INT8 | ✅ | ✅ | +15-20% | - |
| CUDA Graphs | ✅ | ✅ | +10-15% | - |
| IO Binding | ✅ | ✅ | +5-10% | - |
| torch.compile | ✅ | ✅ (Demucs) | +10-30% | - |
| EPContext | ✅ | 🟡 | Cold start fix | Export model |
| FP8 | ✅ | 🟡 | 2x over INT8 | Export model |
| 2:4 Sparsity | ✅ | ❌ | 2x compute | Train + export |
| GPU Spectrograms | ✅ | ❌ | +30% preproc | Wire into pipeline |
| Speculative Batching | ✅ | ❌ | Variable | Enable in Modal |
| Flash Attention | ✅ | N/A | N/A | Not applicable |
| Early Exit | ❌ | ❌ | +20-50% | Implement |
| Custom Triton | ❌ | ❌ | +20-40% | High effort |

---

## Appendix: File Reference

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `revolutionary_optimizations.py` | FP8, Flash Attention, Fused Kernels, GPU Spectrograms | `export_fp8_tensorrt`, `apply_flash_attention`, `GPUMelSpectrogram` |
| `advanced_optimizations.py` | EPContext, 2:4 Sparsity, Speculative Batching | `export_embedded_tensorrt_engine`, `apply_structured_sparsity`, `SpeculativeBatcher` |
| `production_optimizations.py` | Static INT8, IO Binding, torch.compile | `export_static_int8`, `IOBoundONNXInference`, `CompiledInference` |
| `tensorrt_inference.py` | TensorRT, CUDA Graphs, Multi-shape support | `CUDAGraphExecutor`, `TensorRTBackend`, `ONNXRuntimeBackend` |
| `optimized_pipeline.py` | End-to-end pipeline, Sparse filter, Batched onset | `OptimizedPipeline`, `SparseInferenceFilter`, `BatchedOnsetDetector` |
| `modal_app.py` | Production deployment | `GPUProcessor`, model loading priority |
| `distill_model.py` | Knowledge distillation | `DistillationTrainer`, `StudentModel` |
