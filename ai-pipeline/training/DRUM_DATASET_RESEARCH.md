# Drum/Percussion Audio Datasets Research Report

**Last Updated:** January 6, 2026

## Research Objective
Find datasets with commercial-use licenses containing:
- **China cymbal** ✅ **TARGET EXCEEDED: 90,984 samples** (44x increase from 2,081)
- **Splash cymbal** ✅ **TARGET EXCEEDED: 101,885 samples** (16x increase from 6,550)

### Current 12-Class Structure (Training Data - After Full Lakh Integration)
| Idx | Class | Samples | % of Dataset |
|-----|-------|---------|--------------|
| 0 | china | **90,984** | 0.60% |
| 1 | crash | 182,909 | 1.20% |
| 2 | cross_stick | 347,845 | 2.28% |
| 3 | hihat_closed | 2,709,972 | 17.74% |
| 4 | hihat_open | 432,110 | 2.83% |
| 5 | hihat_pedal | 1,489,807 | 9.75% |
| 6 | kick | 3,099,875 | 20.30% |
| 7 | ride_bell | 217,413 | 1.42% |
| 8 | ride_bow | 1,436,759 | 9.41% |
| 9 | snare | 4,110,099 | 26.91% |
| 10 | splash | **101,885** | 0.67% |
| 11 | tom | 1,053,689 | 6.90% |
| **Total** | | **15,273,347** | |

> **Note:** metadata.json is stale - shows original counts before Lakh integration.
> Actual training data contains synthesized samples (verified via train_labels_*.npy).

> **Class Evolution Note:** `rimshot` was merged into `snare` (13→12 classes) on January 1, 2026.
> Rimshots ARE snare hits (stick hits head+rim simultaneously). The acoustic difference
> is subtle and better handled via post-processing acoustic analysis.

---

## 🎯 TIER 1: HIGH-PRIORITY DATASETS (Likely contain rare classes, commercial-friendly)

### 1. STAR Drums Dataset (NEW - June 2025)
- **URL**: https://zenodo.org/records/15690078
- **License**: BSD 3-Clause + Various CC licenses (check individual files)
- **Size**: ~181 GB
- **Classes**: **18 drum classes** including specialized cymbals
- **Rare Class Content**: 
  - Likely includes china cymbal, splash cymbal, rimshot given the 18-class coverage
  - High temporal accuracy annotations
- **Download**: Split into 30GB chunks on Zenodo
- **Notes**: 
  - Academic dataset from TISMIR 2025 paper
  - Contains MIDI annotations with velocity
  - Mixed with real melodic instruments/vocals
  - **VERIFY LICENSE FOR EACH AUDIO FILE** - some may have restrictions
- **Commercial Use**: ⚠️ Check individual file licenses in LICENSE folder

### 2. Freesound One-Shot Percussive Sounds
- **URL**: https://zenodo.org/record/3665275
- **License**: Mixed CC licenses (Attribution, CC0, some NC)
- **Size**: 10,254 one-shot percussive sounds
- **Rare Class Content**: 
  - Contains cymbal hits including specialty types
  - Filter by tags: "china", "splash", "rimshot", "snare sidestick"
- **Download**: Direct from Zenodo
- **Notes**: Already curated for neural network training
- **Commercial Use**: ⚠️ Filter for CC0 and CC-BY only (exclude NC/SA)

### 3. Freesound Direct (API Scraping)
- **URL**: https://freesound.org/
- **License**: Mixed - filter for CC0 and CC-BY
- **Size**: 
  - **China cymbal**: ~719 sounds (CC0: 176, CC-BY: 506)
  - **Splash cymbal**: ~963 sounds (CC0: 127, CC-BY: 781)
  - **Rimshot**: Estimated 500-1000+ sounds
- **Download**: API or bulk download scripts
- **Notes**: 
  - Use Freesound API with license filtering
  - Pack: "HiHats-18x20inchChinaHats-multisampled" (274 files)
  - Pack: "Special Cymbals" (64 files with china/splash)
  - User "quartertone" has extensive multisampled cymbals
  - User "Logicogonist" has large china cymbal collection
- **Commercial Use**: ✅ Yes, when filtered for CC0/CC-BY

### 4. Philharmonia Orchestra Sound Samples
- **URL**: https://philharmonia.co.uk/explore/sound_samples/percussion
- **License**: Free for commercial use (cannot sell as samples)
- **Size**: Thousands of orchestral percussion samples
- **Rare Class Content**:
  - Professional cymbal recordings
  - Multiple velocity layers
  - Various playing techniques
- **Download**: Bulk ZIP download available
- **Notes**: Recorded by professional orchestra members in studio
- **Commercial Use**: ✅ Yes, explicit commercial permission

### 5. FSD50K (Freesound Dataset 50K)
- **URL**: https://zenodo.org/record/4060432
- **License**: CC-BY 4.0
- **Size**: 51,197 clips, 200 classes from AudioSet ontology
- **Rare Class Content**:
  - "Cymbal" class (~4,688 clips in AudioSet)
  - "Rimshot" class (~4,528 clips in AudioSet)
  - Individual drum classes labeled
- **Download**: Zenodo (large download)
- **Notes**: Human-verified labels, subset of Freesound
- **Commercial Use**: ✅ Yes (CC-BY 4.0)

---

## 🎯 TIER 2: GOOD DATASETS (Drum loops/kits, commercial-friendly)

### 6. WaivOps POP-ROK Dataset
- **URL**: https://zenodo.org/record/14038284
- **License**: CC-BY 4.0 ✅
- **Size**: 5,378 audio loops (~24 hours)
- **Rare Class Content**:
  - Acoustic drum kit sounds
  - Pop/rock style drumming
  - May contain rimshots in context
- **Download**: Zenodo
- **Notes**: MIDI-rendered, various drum kits (~30 acoustic kits)
- **Commercial Use**: ✅ Yes

### 7. WaivOps EDM-TR9 Dataset
- **URL**: https://zenodo.org/record/10278066
- **License**: CC-BY 4.0 ✅
- **Size**: 3,780 audio loops (~8 hours)
- **Rare Class Content**: Electronic drum sounds, limited for rare acoustic classes
- **Download**: Zenodo
- **Commercial Use**: ✅ Yes

### 8. WaivOps EDM-HSE Dataset
- **URL**: https://zenodo.org/record/13769544
- **License**: CC-BY 4.0 ✅
- **Size**: 8,000 audio loops (~17 hours)
- **Rare Class Content**: EDM drum patterns with JSON labels
- **Download**: Zenodo
- **Commercial Use**: ✅ Yes

### 9. WaivOps EDM-TR8 Dataset
- **URL**: https://zenodo.org/record/13257814
- **License**: CC-BY 4.0 ✅
- **Size**: 3,790 audio loops (~9 hours)
- **Rare Class Content**: TR-808 style drums
- **Download**: Zenodo
- **Commercial Use**: ✅ Yes

### 10. WaivOps HH-LFBB Dataset
- **URL**: https://zenodo.org/record/7523435
- **License**: CC-BY 4.0 ✅
- **Size**: 3,332 audio loops (~19 hours)
- **Rare Class Content**: Lo-fi hip-hop drums with swings
- **Download**: Zenodo
- **Commercial Use**: ✅ Yes

---

## 🎯 TIER 3: REFERENCE DATASETS (Academic, may have license restrictions)

### 11. Google AudioSet
- **URL**: https://research.google.com/audioset/
- **License**: YouTube ToS applies - ⚠️ NOT FOR COMMERCIAL MODEL TRAINING
- **Size**: 2M+ YouTube videos, 527 classes
- **Rare Class Content**:
  - **Cymbal**: 4,688 videos (90% quality estimate)
  - **Rimshot**: 4,528 videos (40% quality estimate)
  - Hi-hat: 3,900 videos
  - Snare drum: 6,842 videos
  - Crash cymbal: Available as sub-class
- **Download**: Download scripts available, requires YouTube extraction
- **Notes**: 
  - Excellent for understanding class distributions
  - Contains weak labels (not isolated hits)
  - Source YouTube IDs can be used to find similar content
- **Commercial Use**: ❌ NO (YouTube ToS)

### 12. IDMT-SMT-Drums Dataset
- **URL**: https://zenodo.org/records/7544164 / https://www.idmt.fraunhofer.de/en/publications/datasets/drums.html
- **License**: Non-commercial research only ⚠️
- **Size**: 608 WAV files (~2.1 hours)
- **Classes**: Kick, snare, hi-hat only (3 classes)
- **Notes**: Already in your collection, limited to basic classes
- **Commercial Use**: ❌ Research only

### 13. MTG-Jamendo Dataset
- **URL**: https://github.com/MTG/mtg-jamendo-dataset
- **License**: ⚠️ Non-commercial (requires Jamendo permission for commercial)
- **Size**: 55,000+ full tracks with instrument tags
- **Rare Class Content**: Full tracks, not isolated hits
- **Notes**: Would need source separation to extract drum hits
- **Commercial Use**: ❌ NO (contact hello@jamendo.com for commercial license)

### 14. NSynth Dataset (Google Magenta)
- **URL**: https://magenta.tensorflow.org/datasets/nsynth
- **License**: CC-BY 4.0 ✅
- **Size**: 305,979 musical notes
- **Rare Class Content**: 
  - Focuses on pitched instruments
  - Limited percussion content
  - No specific cymbal types
- **Commercial Use**: ✅ Yes, but limited percussion

---

## 🎯 TIER 4: SAMPLE PACK SOURCES (Require manual curation)

### 15. SampleFocus Community Samples
- **URL**: https://samplefocus.com/tag/cymbal (187 samples)
- **License**: Check individual samples
- **Tags Available**: "china", "splash", "rimshot", "crashes"
- **Notes**: Community uploaded, verify each license
- **Commercial Use**: ⚠️ Varies by sample

### 16. Internet Archive Drum Samples
- **URL**: https://archive.org/search?query=drum+samples+free
- **License**: Various (check each)
- **Size**: 494+ results for drum samples
- **Notes**: Mixed quality, requires manual filtering
- **Commercial Use**: ⚠️ Verify each item

### 17. BBC Sound Effects
- **URL**: https://sound-effects.bbcrewind.co.uk/
- **License**: RemArc License (personal/educational only) ⚠️
- **Size**: Large sound effects library
- **Notes**: High quality but restricted license
- **Commercial Use**: ❌ NO for commercial ML training

---

## 📊 SAMPLE COUNT ESTIMATES FOR RARE CLASSES

### Achievable from Free Sources:

| Source | China Cymbal | Splash Cymbal |
|--------|-------------|---------------|
| Freesound CC0/BY | ~400-500 | ~600-800 |
| FSD50K | ~500-1000 | ~500-1000 |
| STAR Drums | TBD (check 18 classes) | TBD |
| Philharmonia | ~50-100 | ~50-100 |
| WaivOps (all) | ~100 (from loops) | ~100 |
| SampleFocus | ~50-100 | ~50-100 |
| **Subtotal Free** | ~1,100-1,800 | ~1,300-2,100 |

### Gap Analysis (Updated January 6, 2026):
| Class | Original | After Lakh | Target | Status |
|-------|----------|------------|--------|--------|
| China Cymbal | 2,081 | **90,984** | 50,000+ | ✅ **182% of target** |
| Splash Cymbal | 6,550 | **101,885** | 50,000+ | ✅ **204% of target** |

> **Note:** Rimshot was merged into snare class. Detection now via post-processing.
> 
> **Class imbalance improved from 2,189:1 to 45:1 (snare:china)**

**Lakh MIDI Synthesis Status (Completed Jan 6, 2026):**
- ✅ Feature cache: 49,747 china .pt files, 49,971 splash .pt files
- ✅ Full integration completed via direct cache scan
- ✅ **Final counts: 90,984 china, 101,885 splash**

---

## 🔧 RECOMMENDED DATA AUGMENTATION STRATEGIES

Since free sources cannot provide 50K+ samples per rare class, consider:

### 1. **Pitch Shifting**
- Shift each sample ±2-3 semitones
- Creates 5-7x more samples per original

### 2. **Time Stretching**
- Stretch/compress by ±5-15%
- Creates 3-4x more samples

### 3. **Room Simulation**
- Apply various impulse responses
- Creates 5-10x more samples

### 4. **EQ Variations**
- Apply subtle EQ curves
- Creates 3-5x more samples

### 5. **Velocity Scaling**
- Adjust amplitude + dynamics
- Creates 3-5x more samples

### 6. **Noise Addition**
- Add subtle background noise
- Creates 2-3x more samples

### Combined Multiplier: **100-500x per original sample**

With 1,500 original china cymbal samples + augmentation → **150K-750K synthetic samples**

---

## 🛒 COMMERCIAL SAMPLE LIBRARIES (Paid Options)

If budget allows, these provide high-quality, commercially-licensed content:

### 1. **Splice Sounds**
- URL: https://splice.com/sounds
- License: Royalty-free for productions
- Content: Extensive drum one-shots and loops
- Cost: Subscription model (~$10-20/month)
- **Note**: Check ToS for ML training specifically

### 2. **Cymatics.fm**
- URL: https://cymatics.fm/pages/free-download-vault
- License: Royalty-free (check specific terms for ML)
- Content: Free packs available, premium options
- Cost: Free tiers + paid packs

### 3. **Native Instruments (Kontakt Libraries)**
- URL: https://www.native-instruments.com/
- License: Personal/commercial production use
- **Note**: Usually prohibits redistribution/ML training

---

## 📋 ACTION PLAN

### Phase 1: Collect Free Commercial-Use Samples
1. ✅ Download Philharmonia percussion pack
2. ✅ Use Freesound API to bulk download CC0/CC-BY cymbal samples
3. ⚠️ FSD50K - ZIP corrupted, only 186 valid samples extracted
4. ✅ Download STAR Drums - Added samples to dataset
5. ✅ Download all WaivOps datasets from Zenodo
6. ✅ **Lakh MIDI synthesis - COMPLETED** (50K china + 50K splash manifests)
7. ✅ **Integration into training data - COMPLETED** (41K china + 52K splash verified)

### Phase 2: Process and Extract Hits
1. Source separate drum stems from loop datasets
2. Onset detect and segment individual hits
3. Manually verify and label rare class samples
4. Create consistent file naming and metadata

### Phase 3: Data Augmentation Pipeline
1. Implement pitch shifting augmentation
2. Implement room simulation augmentation
3. Implement time stretching augmentation
4. Generate 100x+ augmented versions
5. Apply quality filtering to remove artifacts

### Phase 4: Synthesis Generation
1. Use drum synthesis models to generate novel samples
2. Train class-conditional generative models
3. Human verification of synthetic quality

---

## 📚 REFERENCES

1. Weber, P., et al. (2025). "STAR Drums: A Dataset for Automatic Drum Transcription", TISMIR.
2. Fonseca, E., et al. (2020). "FSD50K: an Open Dataset of Human-Labeled Sound Events", IEEE/ACM TASLP.
3. Gemmeke, J., et al. (2017). "Audio Set: An ontology and human-labeled dataset for audio events", ICASSP.
4. Cartwright, M., et al. (2015). "Freesound Technical Demo", ACM Multimedia.

---

*Report generated: December 2025, updated January 6, 2026*
*For BeatSight AI Pipeline - Drum Classification Model Training*
