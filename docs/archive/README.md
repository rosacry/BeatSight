# Archived Training Paths

This folder contains documentation for training paths that are **not the recommended default** but are preserved for:
- Research/publication purposes
- Novel IP/patents
- Comparison benchmarks

---

## Current Recommended Path: V5 Ultimate (Path G)

**See `docs/CUTTING_EDGE_TRAINING_FEATURES.md` for the current production training guide.**

```bash
./auto_train.sh label-audit      # 14  - Find bad labels (~30min)
./auto_train.sh v5-warmup        # 17a - Validate system (~2hr)
./auto_train.sh v5-full          # 17d - Full training (~24hr)
./auto_train.sh v5-self-distill  # 17e - Born-Again boost (~24hr) [optional]
```

---

## Archived Documentation

| File | Description |
|------|-------------|
| `CUTTING_EDGE_TRAINING_FEATURES_FULL.md` | Complete list of all training paths (A-H) with detailed explanations |
| `TEMPORAL_MAMBA_IMPLEMENTATION.md` | Path E: Temporal Mamba model (novel research) |
| `TEMPORAL_MODELING_EXPLAINED.md` | Explanation of temporal context modeling |
| `ULTIMATE_TRAINING_ROADMAP.md` | Path F: Ultimate model combining all innovations |
| `PATENT_AND_MONETIZATION_STRATEGY.md` | IP strategy for Path E/F innovations |

---

## When to Use Archived Paths

### Path E (Temporal Mamba) - `15a-15d`
- **Use when:** You want to publish a paper or file patents
- **Novel contributions:** First Mamba/S6 for drums, beat-aware encoding, pattern priors
- **Training time:** ~45 hours

### Path F (Ultimate) - `16a-16d`
- **Use when:** Maximum novel IP required
- **Novel contributions:** All of Path E plus Wav2Vec2 fusion
- **Training time:** ~75+ hours

### Path H (BEATs) - `18a-18c`
- **Use when:** Experimenting with Microsoft's audio foundation model
- **Training time:** ~1-12 hours

### Legacy Paths (Ensemble, Transformer, etc.)
- **Use when:** Comparing architectures or need ensemble for specific use cases
- Access via `legacy` option in `post_export_commands.sh`

---

*Archived: November 26, 2025*
