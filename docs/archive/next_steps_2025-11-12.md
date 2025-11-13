# 🎯 BeatSight: Next Steps & Future Plan

**Last Updated**: November 12, 2025  
**Current Phase**: 1.2 - Gameplay Implementation (70% Complete)  
**Status**: ✅ Foundation Strong - Desktop solid, pivoting to web platform

---

## 🆕 Web Pivot Snapshot (Nov 12, 2025)

- Web-first requirements, cost model, and UX flows captured in:
   - `docs/web_pivot_notes.md`
   - `docs/web_mvp_prd.md`
   - `docs/web_compute_costs.md`
   - `docs/web_ux_flows.md`
- Desktop gameplay remains the reference implementation; new workstreams focus on shipping the browser MVP while model training continues in parallel.
- Immediate planning items: backend architecture, ticket breakdown, and infrastructure validation for fingerprinting + GPU queues.

---

## 📊 Current State

### What's Working ✅
- Desktop app with polished gameplay
- Results screen with grading system
- Speed control and audio playback
- Basic editor with timeline
- AI pipeline with ML classifier foundation
- Comprehensive documentation

### What's Missing 🚧
- Real-time microphone input (desktop)
- Practice mode features
- Complete editor tools
- Trained ML model
- Web backend + karma system
- Mobile-friendly web experience

### Data Pipeline Checklist (November 2025)
- [x] Run `ai-pipeline/training/tools/post_ingest_checklist.py` after each dataset ingest to cover dataset health, event loader regression, and sampling weights. _(Prod combined 2025-11-09 outputs → health `reports/health/prod_combined_health_20251109.*`, weights `reports/sampling/prod_combined_weights.json`, log `reports/health/checklist_prod_combined_20251109.log`.)_
- [x] Review merged manifests and `training/configs/sampling_profiles.json`—diff captured in `reports/health/diffs/prod_combined_manifest_diff_cambridge_20251109.json`; weights refreshed (3,891 session groups, total count 1,087,401, crash_dual_label hits 4,200).
- [ ] Export `ai-pipeline/training/datasets/prod_combined_20251109` (slice audio per manifest) so the retrain can source updated clips. Follow `docs/ml_training_runbook.md` for detailed steps.
- [ ] Stage GPU capacity and training configs (experiment YAMLs/notebooks, logging dashboards) ahead of the full retrain.
- [ ] Monitor long-running ingests (tail summary logs, track disk/CPU throughput) to flag anomalies early.
- _Prep notes (Nov 9, 2025): combined manifest refresh complete, sampling profile verified, retrain command stub lives in `CURRENT_STATUS.md`; awaiting dataset export + GPU slot before launching._

---

## 🎯 Immediate Next Steps (Pick One)

### Option 0: Web MVP Kickoff 🌐 **[NEW]**

**Why:** Aligns with pivot; unblocks web intake + verification pipeline and future monetization.

**Focus Areas:**
1. **Backend Architecture Draft**
   - Define service boundaries (fingerprint API, queue workers, web API gateway) referencing `docs/web_backend_architecture.md` (to be created).
   - IAM/auth strategy (JWT scopes tied to karma roles).
2. **Task Breakdown**
   - Convert `docs/web_mvp_prd.md` and `docs/web_ux_flows.md` into engineering tickets/epics.
   - Prioritize fingerprint + AI queue before full editor.
3. **Infrastructure Spike**
   - Benchmark current pipeline runtime (needed for `docs/web_compute_costs.md` accuracy).
   - Evaluate managed GPU providers (Modal, AWS Batch, Azure Batch) and note trade-offs.
4. **Design Alignment**
   - Draft intake/queue UI mockups (Figma or pen sketch) based on flows.
   - Identify shared components with desktop editor for reuse.

**Deliverables:**
- New `docs/web_backend_architecture.md` architecture note.
- Issue tracker entries grouped by milestone (fingerprint, queue, web UI, karma).
- Cost validation report if benchmarks differ >15% from assumptions.

---

### Option A: Practice Mode 🎓 **[RECOMMENDED]**

**Why:** High user value, medium complexity, builds on existing features

**Features to Implement:**
1. **Section Looping**
   - Define loop start/end points
   - Visual markers on timeline
   - Keyboard shortcuts ([ and ] keys)
   - Auto-restart after section

2. **Adjustable Difficulty**
   - Note density slider
   - Remove certain drum components
   - Slower speeds preset buttons
   - Preview difficulty changes

3. **Metronome Overlay**
   - Toggle metronome sound
   - Visual beat indicators
   - Volume control
   - Sync with BPM

4. **Progress Tracking**
   - Track practice sessions
   - Show improvement over time
   - Suggest sections to practice
   - Achievement badges

**Implementation Plan:**
```
Week 1: Section looping + UI
Week 2: Difficulty adjustment + metronome
Week 3: Progress tracking + polish
Week 4: Testing + refinement
```

**Files to Modify:**
- `GameplayScreen.cs` - Add practice controls
- Create `PracticeMode.cs` - Practice-specific logic
- `Beatmap.cs` - Add practice metadata

---

### Option B: Real-Time Input 🎤

**Why:** Core feature, high impact, prepares for scoring mode

**Features to Implement:**
1. **Microphone Capture**
   - Select input device
   - Low-latency audio capture
   - Level meter visualization
   - Noise gate

2. **Real-Time Onset Detection**
   - Fast onset detection (<10ms latency)
   - Adaptive threshold
   - Multiple detection algorithms
   - Confidence scoring

3. **Hit Matching**
   - Match detected hits to beatmap
   - Timing window verification
   - Component classification
   - Feedback display

4. **Live Scoring**
   - Real-time accuracy display
   - Combo tracking
   - Miss detection
   - Results at end

**Implementation Plan:**
```
Week 1: Microphone capture + UI
Week 2: Real-time onset detection
Week 3: Hit matching algorithm
Week 4: Live scoring + polish
Week 5: Testing + calibration
```

**Files to Create:**
- `Microphone/MicrophoneCapture.cs`
- `Microphone/RealtimeOnsetDetector.cs`
- `Gameplay/LiveInputMode.cs`

**Challenges:**
- Low latency requirements
- False positive handling
- Component classification accuracy
- Device compatibility

---

### Option C: Complete Editor ✏️

**Why:** Enables community beatmap creation

**Features to Implement:**
1. **Waveform Display**
   - Load and render audio waveform
   - Zoom and pan controls
   - Time ruler
   - Beat grid overlay

2. **Note Placement**
   - Click to place notes
   - Drag to move
   - Delete selected notes
   - Copy/paste regions

3. **Beat Snap Divisor**
   - 1/1, 1/2, 1/4, 1/8, 1/16 snap
   - Visual grid lines
   - Keyboard shortcuts
   - Metronome during editing

4. **Metadata Editor**
   - Song info form
   - Difficulty calculator
   - Tag management
   - Preview time selector

**Implementation Plan:**
```
Week 1: Waveform rendering
Week 2: Note placement tools
Week 3: Beat snap + grid
Week 4: Metadata editor
Week 5: Save/export + testing
```

**Files to Modify:**
- `EditorScreen.cs` - Add editing tools
- `TimelineView.cs` - Waveform rendering
- Create `NotePlacementTool.cs`
- Create `MetadataEditor.cs`

**Libraries Needed:**
- NAudio or similar for waveform
- Custom rendering for beatmap overlay

---

## 🚀 Medium-Term Goals (1-3 Months)

### 1. AI Model Training
- Collect 500+ samples per drum component
- Train DrumClassifierCNN
- Achieve >85% accuracy
- Deploy model in pipeline

### 2. Advanced Gameplay
- Multiple difficulty modes
- Leaderboards (local)
- Replay system
- Customizable key bindings

### 3. Editor Completion
- All editing tools working
- AI-assisted correction
- Playback preview
- Export functionality

### 4. Community Features (Phase 2 Prep)
- Local beatmap library
- Import/export system
- Rating system (offline)
- Beatmap metadata standards

---

## 📅 Long-Term Roadmap (3-12 Months)

### Phase 2: Community Features (Months 4-6)
- Backend API deployment
- User accounts
- Cloud beatmap storage
- Remote AI processing
- Web beatmap browser

### Phase 3: Mobile Apps (Months 7-9)
- Flutter app development
- Touch controls
- Cross-platform sync
- Mobile-optimized UI

### Phase 4: Advanced Features (Months 10-12)
- Multi-instrument support
- VR mode (experimental)
- MIDI device input
- Distributed training
- Sample extraction tool

---

## 💡 Feature Ideas (Backlog)

### Gameplay Enhancements
- [ ] Skin system (customizable visuals)
- [ ] Particle effect customization
- [ ] Background videos
- [ ] Storyboard support
- [ ] Multiplayer (local)

### Practice Tools
- [ ] Slow-mo practice mode
- [ ] Hand separation (left/right)
- [ ] Pattern trainer
- [ ] Sight-reading challenges
- [ ] Daily challenges

### Editor Features
- [ ] Auto-mapper improvements
- [ ] Pattern library
- [ ] Collaboration tools
- [ ] Version control integration
- [ ] Difficulty calculator

### AI Improvements
- [ ] Multi-model ensemble
- [ ] Style transfer
- [ ] Difficulty prediction
- [ ] Auto-correction
- [ ] Pattern generation

### Social Features
- [ ] Friend system
- [ ] Score sharing
- [ ] Beatmap comments
- [ ] Creator profiles
- [ ] Competitions

---

## 🔧 Technical Debt & Maintenance

### High Priority
- [ ] Implement audio loading in EditorScreen (warning fix)
- [ ] Add unit tests for core logic
- [ ] Performance profiling
- [ ] Memory leak detection
- [ ] Error handling improvements

### Medium Priority
- [ ] Refactor beatmap loading
- [ ] Optimize particle systems
- [ ] Cache management
- [ ] Settings persistence
- [ ] Logging system

### Low Priority
- [ ] Code cleanup
- [ ] Documentation updates
- [ ] Example beatmaps
- [ ] Tutorial system
- [ ] Accessibility features

---

## 📚 Learning Resources

### For Next Features

**Practice Mode:**
- [Audio timing in games](https://www.gamasutra.com/view/feature/131393/programming_responsiveness_with_.php)
- [Loop implementation patterns](https://github.com/ppy/osu-framework/wiki)

**Real-Time Input:**
- [Low-latency audio in C#](https://github.com/naudio/NAudio)
- [Onset detection algorithms](https://librosa.org/doc/latest/onset.html)

**Editor:**
- [Waveform rendering](https://github.com/naudio/NAudio#waveform-rendering)
- [Timeline UI patterns](https://github.com/ppy/osu-framework/wiki)

**ML Training:**
- [PyTorch tutorials](https://pytorch.org/tutorials/)
- [Audio classification](https://pytorch.org/audio/stable/tutorials/audio_classification_tutorial.html)

---

## 🎯 Success Metrics

### Short-Term (1 Month)
- [ ] Practice mode fully functional
- [ ] 10+ playable beatmaps
- [ ] <10ms audio latency
- [ ] 60+ FPS gameplay

### Medium-Term (3 Months)
- [ ] 100+ training samples collected
- [ ] ML model achieving >80% accuracy
- [ ] Editor supports full workflow
- [ ] Local beatmap library working

### Long-Term (6 Months)
- [ ] Backend API deployed
- [ ] 50+ community beatmaps
- [ ] Mobile app beta
- [ ] 100+ active users

---

## 🤝 Community Involvement

### How to Contribute

**Code:**
- Pick a feature from backlog
- Create pull request
- Follow contribution guidelines

**Data:**
- Create beatmaps
- Label drum samples
- Test ML models

**Documentation:**
- Write tutorials
- Improve docs
- Create video guides

**Testing:**
- Run desktop app daily
- Log issues with reproduction steps
- Provide feedback on UX
- Benchmark performance

---

## 🧭 Decision Log (Recent)
- 2025-11-12: Pivot focus towards browser MVP while retaining desktop as reference implementation.
- 2025-11-09: Cambridge dataset relabel completed; retrain blocked on export + GPU scheduling.
- 2025-11-01: Practice mode promoted to Phase 1.3 priority due to early tester demand.

---

## 📎 Related Documents
- `CURRENT_STATUS.md`
- `ROADMAP.md`
- `FEATURE_LIST.md`
- `docs/ARCHITECTURE.md`
- `docs/LIVE_INPUT_REGRESSION_CHECKLIST.md`
- `docs/ml_training_runbook.md`
- `docs/web_mvp_prd.md`
- `docs/web_backend_architecture.md`
- `docs/web_backend_schema.md`
- `docs/web_compute_costs.md`
- `docs/web_ux_flows.md`

---

## 📈 Metrics Dashboard (Manual Update)
- Desktop build success rate: 100%
- AI pipeline regression tests: ⚠️ Pending smoke run after Cambridge export
- Dataset size (events): 3,010,770
- Crash label coverage: `crash` 26,421 / `crash2` 16,258
- GPU training backlog: 1 job (prod_combined retrain)

---

## ✅ Completed Action Items (Nov 2025)
- [x] Dual-crash relabel + health gates green
- [x] Sampling weights updated for prod combined
- [x] Cambridge dataset restore validated via presence check
- [x] Web pivot documentation drafted (PRD, schema, flows, cost)
- [x] Backend FastAPI skeleton pushed

---

## 🧰 Tooling Reminder
- `ai-pipeline/training/tools/build_training_dataset.py`
- `ai-pipeline/training/tools/dataset_health.py`
- `ai-pipeline/training/tools/post_ingest_checklist.py`
- `ai-pipeline/training/tools/check_cambridge_presence.py`
- `ai-pipeline/training/tools/hard_negative_miner.py`
- `backend/app/main.py` (FastAPI entry)

---

## ⚠️ Risks & Mitigations
- **Risk:** GPU queue backlog once web intake scales.
  - **Mitigation:** Prototype Modal/AWS Batch integration now; enforce quotas.
- **Risk:** Dataset export downtime could block web MVP.
  - **Mitigation:** Automate dataset readiness scripts; schedule exports during low-traffic windows.
- **Risk:** Documentation sprawl causing context loss.
  - **Mitigation:** Maintain summary docs (this file) with pointers to deep dives; archive stale notes.
- **Risk:** Practice mode delay frustrates early adopters.
  - **Mitigation:** Reserve weekly sprint capacity to ship practice features incrementally.

---

## 🗂️ Archive Notes
- Historical session logs live under `SESSION_SUMMARY_*` files.
- Older bugfix logs are in `BUGFIX_SESSION.md` and `EDITOR_FIXES_*.md`.
- Keep this document focused on actionable next steps; archive older sections as milestones close.
