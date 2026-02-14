# Live Visual Capture Handoff (LLM Playbook)

This document is the operational source of truth for BeatSight's live visual regression pipeline.

Use this when starting a fresh LLM session and you need to run, debug, or extend visual regression without re-discovery.

## Goal

Run deterministic visual QA using **real rendered game screens** (not synthetic layout snapshots), compare against PNG baselines, and fail CI on unintended visual drift.

## What Exists Today

- Scenes covered:
  - `Intro`
  - `MainMenu`
  - `SongSelect`
  - `SongSelectEditor`
  - `Settings`
  - `Recording`
  - `Onboarding`
  - `AudioImportLoading`
  - `MappingChoice`
  - `MetadataChoice`
  - `MappingGeneration`
  - `Editor`
  - `Playback`
  - `EditorManuscript`
  - `PlaybackManuscript`
- Resolutions covered:
  - `1280x720` (`720p`)
  - `1920x1080` (`1080p`)
  - `2560x1440` (`1440p`)
  - `3440x1440` (`ultrawide`)
- Baselines live in:
  - `desktop/BeatSight.Tests/VisualBaselines/*.png`

## 2026-02-14 Stabilization Update

- Visual full-matrix gate currently passes (`60/60`) in compare mode.
- Deterministic user-asset root override is now part of the capture harness:
  - `BEATSIGHT_USER_ASSET_ROOT`
  - wired through `desktop/BeatSight.Game/Configuration/UserAssetDirectories.cs`
- SongSelect/SongSelectEditor fixture seeding is scene-aware in capture:
  - `SongSelect` seeds one deterministic user beatmap (`Heir of Grief`)
  - `SongSelectEditor` seeds two deterministic user beatmaps (`Heir of Grief`, `The Sin and the Sentence`)
- Purpose: keep song-card count/content stable across machines and prevent `%AppData%` drift from breaking visual baselines.

## Core Files and Responsibilities

- `desktop/BeatSight.Tests/VisualRegressionSnapshotTests.cs`
  - Test entrypoint.
  - Enumerates scene/resolution matrix.
  - Handles baseline update mode vs compare mode.
  - Writes diff artifacts to `desktop/BeatSight.Tests/TestResults/visual-diff/`.

- `desktop/BeatSight.Tests/VisualRegression/LiveVisualCaptureRenderer.cs`
  - Boots real `BeatSightGame` host.
  - Pushes target screen from `VisualScene` catalog (main flow + mapping flow + editor/playback).
  - Stabilizes animation/state.
  - Captures screenshot via `host.TakeScreenshotAsync()`.

- `desktop/BeatSight.Tests/VisualRegression/VisualDiffComparer.cs`
  - Pixel diff logic and thresholds.
  - Reports changed ratio + mean delta.

- `desktop/BeatSight.Tests/VisualRegression/VisualSnapshotCatalog.cs`
  - Scene and resolution catalog.

- `desktop/BeatSight.Tests/VisualRegression/VisualRegressionCollection.cs`
  - Disables parallelization for visual tests.

- `.github/workflows/desktop.yml`
  - Runs visual regression on `windows-latest`.
  - Uploads visual diff artifacts.

## Hard Requirements

- Must run on Windows desktop host for live capture.
- Must run in `Release` for CI parity.
- Must set env var `BEATSIGHT_RUN_VISUAL_TESTS=1` to actually execute visual assertions.
- Only set `BEATSIGHT_UPDATE_VISUAL_BASELINES=1` when updating expected visuals intentionally.
- Default behavior runs the full scene x resolution matrix.

## Optional Task-Scoped Filters (for faster local iteration)

Use these to avoid opening the app dozens of times when only one area changed:

- `BEATSIGHT_VISUAL_SCENES`
  - Comma-separated scene names (example: `Editor,Playback`).
- `BEATSIGHT_VISUAL_RESOLUTIONS`
  - Comma-separated names (`720p`, `1080p`, `1440p`, `ultrawide`) or dimensions (`1920x1080`).
- `BEATSIGHT_VISUAL_PROFILE`
  - Built-in subsets: `full`, `smoke`, `mapping`, `editorplayback`, `manuscript`.
  - Used only when explicit scene/resolution filters are not set.

Examples:

```powershell
$env:BEATSIGHT_RUN_VISUAL_TESTS='1'
$env:BEATSIGHT_VISUAL_SCENES='SongSelectEditor,Editor,Playback,EditorManuscript,PlaybackManuscript'
$env:BEATSIGHT_VISUAL_RESOLUTIONS='1080p'
dotnet test desktop/BeatSight.Tests/BeatSight.Tests.csproj -c Release --filter "FullyQualifiedName~VisualRegressionSnapshotTests"
```

```powershell
$env:BEATSIGHT_RUN_VISUAL_TESTS='1'
$env:BEATSIGHT_VISUAL_PROFILE='mapping'
dotnet test desktop/BeatSight.Tests/BeatSight.Tests.csproj -c Release --filter "FullyQualifiedName~VisualRegressionSnapshotTests"
```

Always clear these env vars before the final full-matrix validation pass.

## Fast Commands

### 1. Run visual compare (normal mode)

```powershell
$env:BEATSIGHT_RUN_VISUAL_TESTS='1'
dotnet test desktop/BeatSight.Tests/BeatSight.Tests.csproj -c Release --filter "FullyQualifiedName~VisualRegressionSnapshotTests"
Remove-Item Env:BEATSIGHT_RUN_VISUAL_TESTS -ErrorAction SilentlyContinue
```

### 2. Update baselines intentionally

```powershell
$env:BEATSIGHT_RUN_VISUAL_TESTS='1'
$env:BEATSIGHT_UPDATE_VISUAL_BASELINES='1'
dotnet test desktop/BeatSight.Tests/BeatSight.Tests.csproj -c Release --filter "FullyQualifiedName~VisualRegressionSnapshotTests"
Remove-Item Env:BEATSIGHT_RUN_VISUAL_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:BEATSIGHT_UPDATE_VISUAL_BASELINES -ErrorAction SilentlyContinue
```

### 3. Run all desktop tests

```powershell
dotnet test desktop/BeatSight.Tests/BeatSight.Tests.csproj -c Release
```

## Runtime Flow (How Capture Works)

1. `VisualRegressionSnapshotTests` enumerates all scene/resolution cases.
2. For each case, `LiveVisualCaptureRenderer.Render(...)` starts real game host.
3. It resolves reference beatmap:
   - `shared/formats/simple_beat.bsm`
   - plus reference audio for mapping scenes:
   - `shared/formats/simple_beat.wav`
4. It pushes target screen onto `screenStack`.
5. It applies stabilization:
   - disables dynamic global background (for determinism),
   - waits for pushed scene to be the active `screenStack.CurrentScreen`,
   - waits for drawable size to become valid before capture,
   - waits scene-specific settle time per target screen,
   - freezes playback/editor state via reflected private methods where applicable,
   - applies scene-specific freezes for SongSelect and mapping flows,
   - clears child transforms after final settle to remove looped UI animations,
   - calls `FinishTransforms(true)`.
6. It enforces requested window size (with display clamp fallback).
7. It captures screenshot (`host.TakeScreenshotAsync()`).
8. It retries if frame is near-black.
9. Test compares against baseline via `VisualDiffComparer`.
10. On mismatch, writes:
    - `*.actual.png`
    - `*.diff.png`
11. Test fails with metrics + artifact paths.

## Determinism and Flake Controls

These controls already exist in code and should remain unless replaced with something better:

- Framework RNG reset (best effort).
- Dynamic background alpha forced to zero.
- Scene-specific settle delays.
- Scene-specific freeze hooks:
  - Main menu parallax lock.
  - SongSelect responsive re-apply + carousel/back button transform clear.
  - Audio import loading uses a deterministic test-only screen variant (real layout, no async import transition).
  - Mapping generation heartbeat-scheduler cancel + toast clear.
- Freeze hooks:
  - Editor: stop + seek to fixed time.
  - Playback: stop + seek normalized.
  - Editor/Playback: force lane view mode to `ThreeDimensional` before capture.
  - EditorManuscript/PlaybackManuscript: force lane view mode to `Manuscript` before capture.
- Window size clamp to physical display bounds.
- Screenshot resize to requested resolution if host was clamped.
- Screenshot alpha normalised to fully opaque (`A=255`) for deterministic diffing.
- Near-black screenshot retry loop.
- Visual tests run serially (collection-level parallel disabled).
- User asset root isolation for visual runs (`BEATSIGHT_USER_ASSET_ROOT`) to avoid local song library variance.

## Diff Thresholds (Current)

From `VisualDiffComparer`:

- Max changed pixel ratio: `0.005`
- Max mean delta: `0.001`
- Per-channel noise floor: `3`
- Changed pixel threshold (sum RGBA): `8`

If tests become too strict or too loose, tune here first:
- `desktop/BeatSight.Tests/VisualRegression/VisualDiffComparer.cs`

## How to Add New Visual Coverage

### Add a new scene

1. Add enum entry in:
   - `desktop/BeatSight.Tests/VisualRegression/VisualSnapshotCatalog.cs`
2. Add construction/push logic in:
   - `desktop/BeatSight.Tests/VisualRegression/LiveVisualCaptureRenderer.cs`
3. Add scene stabilization/freeze logic if needed.
4. Generate new baseline PNGs (update mode).
5. Run compare mode and ensure pass.

### Add a new resolution

1. Add `VisualResolution` entry in:
   - `desktop/BeatSight.Tests/VisualRegression/VisualSnapshotCatalog.cs`
2. Generate baselines.
3. Validate compare mode and CI runtime impact.

## CI Behavior

Workflow file:
- `.github/workflows/desktop.yml`

Behavior:
- Regular tests run on Linux/Windows/macOS.
- Live visual regression runs on Windows only.
- Diff artifacts upload always (if files exist):
  - `desktop/BeatSight.Tests/TestResults/visual-diff/**`

## Troubleshooting

### Visual tests do not run

- Cause: `BEATSIGHT_RUN_VISUAL_TESTS` not set.
- Fix: set `BEATSIGHT_RUN_VISUAL_TESTS=1`.

### Missing baseline error

- Cause: baseline PNG absent for a case.
- Fix: run update mode and commit the generated PNG.

### SongSelect/SongSelectEditor card-count mismatch

- Cause: local `%AppData%/BeatSight/Songs` drift being picked up by discovery.
- Existing mitigation:
  - live visual capture sets `BEATSIGHT_USER_ASSET_ROOT` to a temp deterministic root.
  - harness seeds deterministic SongSelect fixture beatmaps by scene.
- If this regresses:
  1. verify `UserAssetDirectories.RootPath` still honors `BEATSIGHT_USER_ASSET_ROOT`,
  2. verify `prepareDeterministicUserAssetRoot(VisualScene scene)` still seeds expected fixtures.

### Near-black capture / blank frame

- Cause: frame not fully ready or host timing jitter.
- Fix order:
  1. increase settle delay slightly,
  2. increase retry attempts,
  3. verify freeze method names still match screen internals.

### Dimension mismatch

- Cause: host window cannot match request exactly.
- Existing mitigation: clamp + post-capture resize.
- If still failing often, inspect display mode / DPI scaling in runner.

## Fresh Session Protocol (Copy This First)

When a new LLM session starts, execute in this exact order:

1. Read:
   - `desktop/BeatSight.Tests/VisualBaselines/LIVE_VISUAL_CAPTURE_HANDOFF.md`
   - `desktop/BeatSight.Tests/VisualRegressionSnapshotTests.cs`
   - `desktop/BeatSight.Tests/VisualRegression/LiveVisualCaptureRenderer.cs`
   - `desktop/BeatSight.Tests/VisualRegression/VisualDiffComparer.cs`
   - `desktop/BeatSight.Tests/VisualRegression/VisualSnapshotCatalog.cs`
2. Run compare mode once (`BEATSIGHT_RUN_VISUAL_TESTS=1`) to establish current state.
3. If failures occur, inspect generated diff artifacts first.
4. Fix root cause in game UI/layout or capture stabilizer.
5. Re-run compare mode.
6. Only update baselines if visual change is intentional.
7. Re-run full desktop test suite.

## Definition of Done for Visual Regression Work

- Visual compare suite passes in Release.
- Full desktop tests pass in Release.
- Any intentional visual updates include new baselines.
- CI workflow still runs live visual regression and artifact upload.
- This handoff doc remains accurate after code changes.
