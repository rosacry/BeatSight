# Visual Baselines

This folder stores PNG baselines used by `VisualRegressionSnapshotTests`.

Snapshots are captured from the live running `BeatSightGame` screen graph (`host.TakeScreenshotAsync()`), not synthetic model renders.

For Task 1 validation coverage:
- `Editor` and `Playback` snapshots are captured with lane view mode forced to `3D`.
- `EditorManuscript` and `PlaybackManuscript` snapshots are captured with lane view mode forced to `Manuscript`.

For full operational details (fresh-session protocol, architecture, troubleshooting, extension flow), see:
- `desktop/BeatSight.Tests/VisualBaselines/LIVE_VISUAL_CAPTURE_HANDOFF.md`

## Covered snapshots
- `Intro` at `720p`, `1080p`, `1440p`, `ultrawide`
- `MainMenu` at `720p`, `1080p`, `1440p`, `ultrawide`
- `SongSelect` at `720p`, `1080p`, `1440p`, `ultrawide`
- `SongSelectEditor` at `720p`, `1080p`, `1440p`, `ultrawide`
- `Settings` at `720p`, `1080p`, `1440p`, `ultrawide`
- `Recording` at `720p`, `1080p`, `1440p`, `ultrawide`
- `Onboarding` at `720p`, `1080p`, `1440p`, `ultrawide`
- `AudioImportLoading` at `720p`, `1080p`, `1440p`, `ultrawide`
- `MappingChoice` at `720p`, `1080p`, `1440p`, `ultrawide`
- `MetadataChoice` at `720p`, `1080p`, `1440p`, `ultrawide`
- `MappingGeneration` at `720p`, `1080p`, `1440p`, `ultrawide`
- `Editor` at `720p`, `1080p`, `1440p`, `ultrawide`
- `Playback` at `720p`, `1080p`, `1440p`, `ultrawide`
- `EditorManuscript` at `720p`, `1080p`, `1440p`, `ultrawide`
- `PlaybackManuscript` at `720p`, `1080p`, `1440p`, `ultrawide`

## Updating baselines
Run (Windows desktop host):

```powershell
$env:BEATSIGHT_RUN_VISUAL_TESTS='1'
$env:BEATSIGHT_UPDATE_VISUAL_BASELINES='1'
dotnet test desktop/BeatSight.Tests/BeatSight.Tests.csproj -c Release --filter "FullyQualifiedName~VisualRegressionSnapshotTests"
Remove-Item Env:BEATSIGHT_RUN_VISUAL_TESTS
Remove-Item Env:BEATSIGHT_UPDATE_VISUAL_BASELINES
```

Only update baselines when a visual change is intentional.

To run visual assertions without updating baselines:

```powershell
$env:BEATSIGHT_RUN_VISUAL_TESTS='1'
dotnet test desktop/BeatSight.Tests/BeatSight.Tests.csproj -c Release --filter "FullyQualifiedName~VisualRegressionSnapshotTests"
Remove-Item Env:BEATSIGHT_RUN_VISUAL_TESTS
```

## Task-focused subsets (fast local loop)
You do not need to run all scenes/resolutions while iterating.

Scene subset + resolution subset:

```powershell
$env:BEATSIGHT_RUN_VISUAL_TESTS='1'
$env:BEATSIGHT_VISUAL_SCENES='SongSelectEditor,Editor,Playback'
$env:BEATSIGHT_VISUAL_RESOLUTIONS='1080p'
dotnet test desktop/BeatSight.Tests/BeatSight.Tests.csproj -c Release --filter "FullyQualifiedName~VisualRegressionSnapshotTests"
Remove-Item Env:BEATSIGHT_RUN_VISUAL_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:BEATSIGHT_VISUAL_SCENES -ErrorAction SilentlyContinue
Remove-Item Env:BEATSIGHT_VISUAL_RESOLUTIONS -ErrorAction SilentlyContinue
```

Built-in profile subsets:

```powershell
$env:BEATSIGHT_RUN_VISUAL_TESTS='1'
$env:BEATSIGHT_VISUAL_PROFILE='mapping' # full | smoke | mapping | editorplayback | manuscript
dotnet test desktop/BeatSight.Tests/BeatSight.Tests.csproj -c Release --filter "FullyQualifiedName~VisualRegressionSnapshotTests"
Remove-Item Env:BEATSIGHT_RUN_VISUAL_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:BEATSIGHT_VISUAL_PROFILE -ErrorAction SilentlyContinue
```

Recommended workflow:
- During development: run targeted subsets.
- Before merge/baseline commit: clear subset env vars and run full matrix once.

## Chunked full-matrix runner (avoids silent long waits)
For long runs where per-batch progress is helpful, use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_visual_regression_chunked.ps1 -RunFullDesktopSuite
```

This helper:
- optionally cleans up stale BeatSight testhost/dotnet test processes before run (`-SkipStaleProcessCleanup` to disable),
- runs one upfront build by default (`-SkipInitialBuild` to disable),
- runs the full scene catalog in chunked scene batches,
- splits the heaviest editor/playback cluster into per-scene batches,
- prints heartbeat logs while each batch is running,
- prints per-batch timing telemetry (`startup` from first TRX appearance + `total` duration),
- prints end-of-run timing rollups (`startup_mean`, `startup_p95`, `total_mean`, `total_p95`, `trx_mean`, `trx_p95`, and slowest batch),
- writes a per-run rollup artifact JSON (`visual_rollup_*.json`) in the chunked results directory with metadata, rollup, and batch rows,
- emits a single warning when TRX duration timestamps are missing for one or more batches (rollup still uses available samples),
- applies a startup watchdog that fails fast if no TRX appears (`-BatchStartupTimeoutSeconds`, default `180`; set `0` to disable),
- applies a per-batch timeout,
- validates each batch from generated TRX results,
- runs each test invocation with `--no-build` after the upfront build,
- clears visual-env filters before `-RunFullDesktopSuite` so full-suite counts are not scope-trimmed,
- and clears visual test environment variables on exit.

## Chunked scoped runner (recommended for editor/settings work)
Use this when you want progress heartbeats without running the full matrix:

```powershell
& ./scripts/run_visual_regression_chunked.ps1 `
  -SceneBatches 'SongSelectEditor,Settings','Editor,Playback','EditorManuscript,PlaybackManuscript' `
  -Resolutions '720p,1080p,1440p,ultrawide' `
  -HeartbeatSeconds 15
```

Notes:
- Prefer direct invocation (`& ./scripts/...`) from the repo root in PowerShell.
- Avoid nested `powershell -Command ...` wrappers for complex array args, since quoting can mis-bind parameters.

## Rollup trend compare helper
To compare two persisted rollup artifacts:

```powershell
& ./scripts/compare_visual_rollups.ps1 `
  -BaselinePath 'desktop/BeatSight.Tests/TestResults/visual-chunked/visual_rollup_20260214_160000_000.json' `
  -CurrentPath 'desktop/BeatSight.Tests/TestResults/visual-chunked/visual_rollup_20260214_170000_000.json'
```

Or auto-compare the latest two rollups in the default results directory:

```powershell
& ./scripts/compare_visual_rollups.ps1
```

For machine-readable output:

```powershell
& ./scripts/compare_visual_rollups.ps1 -OutputJson
```

CI now uploads chunked rollup artifacts from Windows runs as `visual-rollup-windows-latest`.

## Rollup threshold gate helper
To evaluate the latest rollup artifact against timing/coverage thresholds:

```powershell
& ./scripts/evaluate_visual_rollup.ps1 `
  -ResultsDirectory 'desktop/BeatSight.Tests/TestResults/visual-chunked' `
  -MaxTotalP95Seconds 300 `
  -MaxStartupP95Seconds 180 `
  -MaxTrxMissingRatio 0.30 `
  -FailOnThresholdBreach
```

To evaluate a specific artifact:

```powershell
& ./scripts/evaluate_visual_rollup.ps1 `
  -RollupPath 'desktop/BeatSight.Tests/TestResults/visual-chunked/visual_rollup_20260214_171741_596.json' `
  -MaxTotalP95Seconds 300 `
  -MaxStartupP95Seconds 180 `
  -MaxTrxMissingRatio 0.30
```

For machine-readable output:

```powershell
& ./scripts/evaluate_visual_rollup.ps1 -OutputJson
```

The desktop CI workflow now runs this threshold gate after the chunked visual pass on Windows.

CI runs visual regression in `Release`, so prefer `-c Release` when updating baselines.
