@echo off
REM ============================================================================
REM IMPROVED MULTI-LABEL TRAINING - Targeting F1 = 0.90
REM ============================================================================
REM 
REM This script restarts training with improvements to address low-recall classes:
REM - recall_boost loss with per-class gamma (higher for hihat_pedal, cross_stick)
REM - recall_boost_weight = 2.0 to penalize false negatives more
REM - Continued training from best checkpoint with new loss
REM
REM Usage:
REM   train_improved.bat [resume]
REM
REM ============================================================================

cd /d C:\github\BeatSight\ai-pipeline

REM Configuration
set CHECKPOINT=runs/v5_multilabel/best_checkpoint.pt
set OUTPUT_DIR=runs/v5_multilabel_improved
set EPOCHS=60
set BATCH_SIZE=128
set LR=2e-5

REM Create output directory
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo ==============================================
echo IMPROVED MULTI-LABEL TRAINING
echo ==============================================
echo Output: %OUTPUT_DIR%
echo Loss: recall_boost with per-class gamma
echo Recall boost weight: 2.0
echo ==============================================

REM Check if resume mode
set RESUME_ARG=
if "%1"=="resume" (
    set RESUME_ARG=--resume %CHECKPOINT%
    echo Resuming from: %CHECKPOINT%
) else (
    echo Fresh start with pretrained weights
)

REM Main training command
python training/multilabel/train_multilabel.py ^
    --train-dir "F:/datasets/prod_v5_multilabel/train" ^
    --val-dir "F:/datasets/prod_v5_multilabel/val" ^
    --source-dataset "F:/datasets/prod_v5_final" ^
    --feature-cache-dir "F:/feature_cache" ^
    --model-version v5 ^
    --v5-size large ^
    --num-classes 12 ^
    --loss-type recall_boost ^
    --use-per-class-gamma ^
    --recall-boost-weight 2.0 ^
    --gamma 2.0 ^
    --label-smoothing 0.05 ^
    --epochs %EPOCHS% ^
    --batch-size %BATCH_SIZE% ^
    --grad-accum-steps 5 ^
    --lr %LR% ^
    --weight-decay 0.0001 ^
    --scheduler cosine ^
    --warmup-epochs 2 ^
    --use-ema --ema-decay 0.999 ^
    --use-swa --swa-start 0.6 ^
    --specaugment drum ^
    --gradient-checkpointing ^
    --channels-last ^
    --num-workers 4 ^
    --checkpoint-every 1 ^
    --checkpoint-every-batches 5000 ^
    --output-dir %OUTPUT_DIR% ^
    %RESUME_ARG%

echo.
echo Training complete! Check %OUTPUT_DIR% for checkpoints.
pause
