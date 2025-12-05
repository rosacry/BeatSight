#!/bin/bash
# =============================================================================
# BeatSight Legacy Training Modes (ARCHIVED)
# =============================================================================
# This file contains legacy and experimental training modes that have been
# superseded by the V5 pipeline. These modes are preserved for reference
# and research purposes but are NOT recommended for production use.
#
# For production training, use: auto_train.sh
#
# Legacy Mode Categories:
#   - v1/v2/v4 architectures (superseded by V5)
#   - Experimental research (Mamba, AST, Wav2Vec2)
#   - Ensemble training (rarely used)
#   - SSL pretraining (incomplete)
#
# =============================================================================

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         BeatSight Legacy Training Modes (ARCHIVED)               ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "⚠️  These modes are ARCHIVED and NOT recommended for production."
echo "   Use ./auto_train.sh for the current V5 pipeline."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "ARCHIVED MODES (for reference only):"
echo ""
echo "  📦 V1 Baseline (4-layer CNN):"
echo "     warmup (5a), quick (5b), long (5c)"
echo ""
echo "  📦 V2 Cutting-Edge (SE-Attention + Mixup):"
echo "     cutting-edge-warmup (7a), cutting-edge-quick (7b), cutting-edge-long (7c)"
echo ""
echo "  📦 V4 Enhanced (Coordinate Attention):"
echo "     enhanced-warmup (12a), enhanced-quick (12b), enhanced-long (12c)"
echo ""
echo "  🔬 RESEARCH (Novel/Experimental):"
echo ""
echo "  📦 Ensemble Training (5 models):"
echo "     ensemble-warmup (9a), ensemble-quick (9b), ensemble-long (9c)"
echo ""
echo "  📦 Audio Spectrogram Transformer:"
echo "     ast-warmup (10a), ast-quick (10b), ast-long (10c)"
echo ""
echo "  📦 Knowledge Distillation (old):"
echo "     distill-quick (11a), distill-long (11b)"
echo ""
echo "  📦 Self-Supervised Pretraining:"
echo "     ssl-pretrain-warmup (13a), ssl-pretrain-full (13b)"
echo ""
echo "  📦 Temporal Mamba (State-Space Models):"
echo "     temporal-warmup (15a), temporal-quick (15b),"
echo "     temporal-long (15c), temporal-full (15d)"
echo ""
echo "  📦 Ultimate Fusion (Wav2Vec2 + Mamba + Beat Encoding):"
echo "     ultimate-warmup (16a), ultimate-quick (16b),"
echo "     ultimate-long (16c), ultimate-full (16d)"
echo ""
echo "  📦 Microsoft BEATs (Audio Foundation Model):"
echo "     beats-warmup (18a), beats-quick (18b), beats-long (18c)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To run a legacy mode, use the original auto_train.sh:"
echo "   bash ai-pipeline/training/tools/auto_train.sh <mode>"
echo ""
echo "Example:"
echo "   bash ai-pipeline/training/tools/auto_train.sh temporal-warmup"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📖 RECOMMENDED: Use auto_train.sh for production training"
echo "   Path: label-audit → v5-warmup → v5-local-balanced → v5-distill → multilabel"
echo ""
