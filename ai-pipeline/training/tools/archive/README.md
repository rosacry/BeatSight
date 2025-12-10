# Archived Training Scripts

These scripts were created during the hyperparameter ablation study (December 2025) and are no longer needed for production training.

## Why Archived?

After extensive testing, we identified the root causes of class collapse:
1. **Focal Loss gamma too high** - gamma=3.0 + uniform sampling = double emphasis on rare classes
2. **Learning rate too low** - 0.0001 was too conservative; 0.0002 works better
3. **Batch size too large** - 1024 effective was too big; 512 generalizes better

## Final Results

| Config | Data | Key Change | Balanced Acc | vs Baseline |
|--------|------|------------|--------------|-------------|
| V7 (baseline) | 5% | - | 54.27% | - |
| A1 | 5% | LR 0.00005 | 48.93% | -5.34% ❌ |
| **A2** | 5% | **LR 0.0002** | **58.74%** | **+4.47%** ✅ |
| **B1** | 5% | **Batch 512** | **56.60%** | **+2.33%** ✅ |
| **E1** | 10% | **More data** | **61.69%** | **+7.42%** ✅ |

## Production Config

The optimized settings are now in `train_production_final.sh`:
- 100% data (14.6M samples)
- LR = 0.0002
- Effective batch = 512 (batch 256, grad_accum 2)
- Uniform balanced sampling
- Plain CrossEntropy (NO focal loss)
- 100 epochs

## Archived Files

### Quick Test Scripts (Ablation Experiments)
- `quick_test_config.sh` - Original config (caused collapse)
- `quick_test_fixed.sh` - Early fix attempt (sqrt sampling)
- `quick_test_sqrt_focal.sh` - sqrt + focal test
- `quick_test_v2.sh` through `quick_test_v11_ambitious.sh` - Various experiments
- `quick_test_aggressive.sh`, `quick_test_cb_loss.sh`, `quick_test_uniform.sh`
- `smoke_test_v8_v9_v10.sh` - Combined smoke tests

### Ablation Study Scripts
- `ablation_study.sh` - Master ablation script
- `ablation_A2_lr_higher.sh` - LR 0.0002 test (winner!)
- `ablation_B1_batch_smaller.sh` - Batch 512 test (winner!)
- `ablation_E1_more_data.sh` - 10% data test (winner!)

### Other Archived
- `train_v5_balanced_fixed.sh` - Early balanced training attempt
- `v12_production_full.sh` - Superseded by train_production_final.sh
- `best_config.sh` - Old "best" config

## DO NOT DELETE

These scripts document the learning process and may be useful for:
- Understanding why certain settings don't work
- Future hyperparameter tuning
- Reference for similar projects
