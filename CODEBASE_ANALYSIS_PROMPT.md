# BeatSight Comprehensive Codebase Analysis Prompt

## Instructions for Copilot

**Time is not a constraint. Take all the time you need to work on this, and work to the best of your ability.**

---

## Project Vision & Context

### What BeatSight Is
BeatSight is an ambitious, potentially **revolutionary** program designed to transform how drummers learn songs. This is NOT a game—it's a serious educational tool that will fundamentally change drum learning.

**Core Purpose:**
- Drummers learn and follow along to songs through visual representations (2D, 3D, or Manuscript/sheet music mode)
- Users can either manually create beatmaps (not recommended) or use the **AI/ML pipeline** to automatically transcribe drum audio into visual beatmaps
- Eliminates the tedious cycle of listening to songs repeatedly, guessing what the drummer plays at each moment
- As users become familiar with the visualization layouts, they can **sight-read** drum parts on first attempt—similar to how skilled osu! players can sight-read maps

**Current Development State:**
- The AI/ML model for drum transcription is **actively being trained** in parallel with other development
- This is a long-term, high-ambition project with no shortcuts

---

## Your Task

Perform an **exhaustive, systematic analysis** of the entire BeatSight codebase. Generate a comprehensive Markdown document (`IMPLEMENTATION_STATUS.md`) that catalogs:

1. **Unimplemented Features** - Code stubs, TODO comments, placeholder implementations
2. **Incomplete Implementations** - Partially working features, missing edge cases
3. **Missing Integrations** - Components that should connect but don't yet
4. **Technical Debt** - Workarounds, hacks, deprecated patterns needing refactoring
5. **Documentation Gaps** - Missing or outdated docs, undocumented APIs
6. **Test Coverage Gaps** - Untested code paths, missing test cases
7. **Configuration/Setup Issues** - Missing configs, environment setup gaps
8. **UI/UX Incomplete Elements** - Placeholder UI, unfinished user flows
9. **AI/ML Pipeline Status** - Current state of the transcription model, training pipeline, inference integration

---

## Analysis Protocol

### Phase 1: Deep Codebase Scan
Systematically examine every directory and file type:

**Desktop Application (`desktop/`)**
- `BeatSight.Desktop/` - Entry point, platform-specific code
- `BeatSight.Game/` - Core game/application logic, rendering, UI
- `BeatSight.Tests/` - Test coverage analysis

**AI/ML Pipeline (`ai-pipeline/`)**
- `pipeline/` - Core processing pipeline
- `separation/` - Audio stem separation (Demucs)
- `transcription/` - Drum transcription model
- `training/` - Model training infrastructure
- `tools/` - Utility scripts
- `tests/` - ML test coverage

**Backend (`backend/`)**
- API implementation status
- Database schemas
- Service integrations

**Shared Components (`shared/`)**
- Format definitions
- Cross-component utilities

**Documentation (`docs/`)**
- Compare documented features vs implemented features
- Identify documentation gaps

### Phase 2: Pattern Recognition
Search for these indicators across ALL files:

```
Patterns to find:
- TODO, FIXME, HACK, XXX, BUG, OPTIMIZE comments
- NotImplementedException, throw new NotImplementedException
- "not implemented", "not yet implemented", "coming soon"
- pass # (Python empty implementations)
- Empty method/function bodies
- Commented-out code blocks (potential unfinished features)
- Placeholder strings: "Lorem ipsum", "placeholder", "temp", "dummy"
- Magic numbers without explanation
- Hardcoded values that should be configurable
- Disabled features (commented out, feature flags set to false)
- Incomplete switch/match statements (missing cases)
- Empty catch blocks (swallowed exceptions)
- Methods returning null/None as placeholder
- Interfaces/abstract classes with no implementations
- Unused imports (potential unfinished integrations)
- Dead code (unreachable, unused functions)
```

### Phase 3: Architecture Analysis
- Map component dependencies
- Identify missing connections between:
  - AI pipeline → Desktop app
  - Backend → Desktop app
  - Transcription → Beatmap generation
  - Beatmap → Visualization rendering
- Check for incomplete data flow paths
- Verify all modes work: 2D, 3D, Manuscript

### Phase 4: Feature Completeness Matrix
Cross-reference against these expected features:

**Audio Processing:**
- [ ] Audio file import (multiple formats)
- [ ] Stem separation (drums from full mix)
- [ ] Tempo/BPM detection
- [ ] Time signature detection
- [ ] Metadata extraction

**Drum Transcription (AI/ML):**
- [ ] Onset detection
- [ ] Instrument classification (kick, snare, hi-hat, toms, cymbals, etc.)
- [ ] Velocity estimation
- [ ] Technique detection (ghost notes, flams, rolls, etc.)
- [ ] Model training pipeline
- [ ] Model inference integration
- [ ] Confidence scoring

**Beatmap System:**
- [ ] Beatmap file format (.bs files)
- [ ] Beatmap editor
- [ ] Import from other formats (osu!, etc.)
- [ ] Export capabilities
- [ ] Beatmap validation

**Visualization Modes:**
- [ ] 2D mode (highway/note lane style)
- [ ] 3D mode (spatial representation)
- [ ] Manuscript mode (traditional notation)
- [ ] Mode switching
- [ ] Customizable layouts

**Playback & Learning:**
- [ ] Audio playback synchronized with visualization
- [ ] Speed adjustment (slow down for practice)
- [ ] Loop sections
- [ ] Progress tracking
- [ ] Performance scoring/feedback

**User Experience:**
- [ ] Settings/preferences system
- [ ] Keyboard/input customization
- [ ] Tutorial/onboarding
- [ ] Help documentation in-app

---

## Output Format

Generate `IMPLEMENTATION_STATUS.md` with this structure:

```markdown
# BeatSight Implementation Status Report
*Generated: [Date]*
*Analysis Scope: Full Codebase*

## Executive Summary
- Total items requiring attention: X
- Critical blockers: X
- High priority: X
- Medium priority: X
- Low priority/Nice-to-have: X

## 1. Critical/Blocking Issues
Items that prevent core functionality from working.

### 1.1 [Category]
| File | Line(s) | Issue | Description | Suggested Action |
|------|---------|-------|-------------|------------------|
| path/to/file | 123-125 | Type | Details | Recommendation |

## 2. Incomplete Implementations
Features that exist but aren't finished.

## 3. Missing Features
Features that should exist but have no implementation.

## 4. Integration Gaps
Components that need to be connected.

## 5. AI/ML Pipeline Status
Current state of the drum transcription system.

### 5.1 Training Pipeline
### 5.2 Model Architecture
### 5.3 Inference Integration
### 5.4 Data Pipeline

## 6. Technical Debt
Code quality issues to address.

## 7. Test Coverage Gaps
Untested or undertested areas.

## 8. Documentation Needs
Missing or outdated documentation.

## 9. Configuration & Setup
Environment and setup issues.

## 10. UI/UX Incomplete Elements
Unfinished user interface elements.

## Appendix A: All TODO/FIXME Comments
Complete list with locations.

## Appendix B: Feature Completion Matrix
Checklist of all expected features with status.

## Appendix C: File-by-File Analysis
Detailed breakdown by component.

## Appendix D: Recommended Priority Order
Suggested sequence for addressing items.
```

---

## Important Notes

1. **Be thorough** - This is a serious project with high ambitions. Missing something could delay important work.

2. **Understand the vision** - Every finding should be contextualized against the goal of creating a revolutionary drum learning tool.

3. **AI/ML is in progress** - The model training is happening concurrently. Note the current state but understand it's actively being developed.

4. **Quality over speed** - Take the time needed to do this right. Read files completely. Follow references. Understand context.

5. **Actionable output** - Every item should have clear next steps or recommendations.

6. **Preserve my momentum** - The output should help me understand exactly where to focus next to make maximum progress.

---

## Begin Analysis

Start by exploring the codebase structure, then systematically work through each component. Use all available tools to read files, search for patterns, and understand the architecture.

**Remember: This project aims to be revolutionary. Analyze it with the rigor it deserves.**
