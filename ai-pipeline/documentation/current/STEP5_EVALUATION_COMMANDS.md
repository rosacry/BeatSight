# Step 5 Evaluation Commands

Last updated: 2026-02-13

These are the exact command blocks for Step 5 evaluation on:

- `../test_songs/0101 - Heir of Grief.flac`

## Manual Baseline Matrix (fixed settings)

### Run 0 - Baseline

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_songs/v5/test_v5_baseline.bsm \
  --ensemble-classification \
  --multilabel-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --ensemble-demucs-model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --ensemble-demucs-thresholds runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --sensitivity 80 \
  --quantization thirtysecond \
  --no-readability-filter \
  --force-time-signature 4/4 \
  --no-genre-detection \
  --no-pattern-repair
```

### Run 1 - Baseline + Adaptive Thresholds

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_songs/v5/test_v5_baseline_with_adaptive_thresholds.bsm \
  --ensemble-classification \
  --multilabel-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --ensemble-demucs-model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --ensemble-demucs-thresholds runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --sensitivity 80 \
  --quantization thirtysecond \
  --no-readability-filter \
  --adaptive-thresholds \
  --force-time-signature 4/4 \
  --no-genre-detection \
  --no-pattern-repair
```

### Run 2 - Multi-pass

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_songs/v5/test_v5_multipass.bsm \
  --ensemble-classification \
  --multilabel-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --ensemble-demucs-model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --ensemble-demucs-thresholds runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --sensitivity 80 \
  --quantization thirtysecond \
  --no-readability-filter \
  --adaptive-thresholds \
  --force-time-signature 4/4 \
  --no-genre-detection \
  --no-pattern-repair \
  --multi-pass
```

### Run 3 - Global TTA

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_songs/v5/test_v5_tta.bsm \
  --ensemble-classification \
  --multilabel-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --ensemble-demucs-model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --ensemble-demucs-thresholds runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --sensitivity 80 \
  --quantization thirtysecond \
  --no-readability-filter \
  --adaptive-thresholds \
  --force-time-signature 4/4 \
  --no-genre-detection \
  --no-pattern-repair \
  --tta --tta-augmentations 7
```

### Run 4 - Multi-window

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_songs/v5/test_v5_multiwindow.bsm \
  --ensemble-classification \
  --multilabel-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --ensemble-demucs-model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --ensemble-demucs-thresholds runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --sensitivity 80 \
  --quantization thirtysecond \
  --no-readability-filter \
  --adaptive-thresholds \
  --force-time-signature 4/4 \
  --no-genre-detection \
  --no-pattern-repair \
  --multi-window
```

### Run 5 - Checkpoint Ensemble

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_songs/v5/test_v5_checkpoint_ensemble.bsm \
  --ensemble-classification \
  --multilabel-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --ensemble-demucs-model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --ensemble-demucs-thresholds runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --sensitivity 80 \
  --quantization thirtysecond \
  --no-readability-filter \
  --adaptive-thresholds \
  --force-time-signature 4/4 \
  --no-genre-detection \
  --no-pattern-repair \
  --checkpoint-ensemble \
    runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
    runs/v5_multilabel_final_v3_continued/checkpoint_epoch_0010.pt \
    runs/v5_multilabel_final_v3_continued/checkpoint_epoch_0009.pt \
    runs/v5_multilabel_final_v3_continued/checkpoint_epoch_0008.pt
```

## Production-Candidate Matrix (auto-tuned transcription mode)

Candidate baseline flags:

- `--mode transcription`
- `--auto-sensitivity`
- `--auto-quantization`

Removed vs manual matrix:

- `--force-time-signature`
- `--no-genre-detection`
- `--no-pattern-repair`

### Run 0 - Baseline

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_songs/v5/prod/test_v5_baseline_prod.bsm \
  --ensemble-classification \
  --multilabel-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --ensemble-demucs-model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --ensemble-demucs-thresholds runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --mode transcription \
  --auto-sensitivity \
  --auto-quantization
```

### Run 1 - Baseline + Adaptive Thresholds

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_songs/v5/prod/test_v5_baseline_with_adaptive_thresholds_prod.bsm \
  --ensemble-classification \
  --multilabel-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --ensemble-demucs-model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --ensemble-demucs-thresholds runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --mode transcription \
  --auto-sensitivity \
  --auto-quantization \
  --adaptive-thresholds
```

### Run 2 - Multi-pass

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_songs/v5/prod/test_v5_multipass_prod.bsm \
  --ensemble-classification \
  --multilabel-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --ensemble-demucs-model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --ensemble-demucs-thresholds runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --mode transcription \
  --auto-sensitivity \
  --auto-quantization \
  --adaptive-thresholds \
  --multi-pass
```

### Run 3 - Global TTA

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_songs/v5/prod/test_v5_tta_prod.bsm \
  --ensemble-classification \
  --multilabel-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --ensemble-demucs-model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --ensemble-demucs-thresholds runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --mode transcription \
  --auto-sensitivity \
  --auto-quantization \
  --adaptive-thresholds \
  --tta --tta-augmentations 7
```

### Run 4 - Multi-window

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_songs/v5/prod/test_v5_multiwindow_prod.bsm \
  --ensemble-classification \
  --multilabel-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --ensemble-demucs-model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --ensemble-demucs-thresholds runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --mode transcription \
  --auto-sensitivity \
  --auto-quantization \
  --adaptive-thresholds \
  --multi-window
```

### Run 5 - Checkpoint Ensemble

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python -m pipeline.process \
  --input "../test_songs/0101 - Heir of Grief.flac" \
  --output ../test_songs/v5/prod/test_v5_checkpoint_ensemble_prod.bsm \
  --ensemble-classification \
  --multilabel-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
  --multilabel-thresholds runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json \
  --ensemble-demucs-model runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt \
  --ensemble-demucs-thresholds runs/v5_demucs_cymbal_boost/thresholds_demucs_only.json \
  --mode transcription \
  --auto-sensitivity \
  --auto-quantization \
  --adaptive-thresholds \
  --checkpoint-ensemble \
    runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
    runs/v5_multilabel_final_v3_continued/checkpoint_epoch_0029.pt \
    runs/v5_multilabel_final_v3_continued/checkpoint_epoch_0028.pt \
    runs/v5_multilabel_final_v3_continued/checkpoint_epoch_0027.pt
```
