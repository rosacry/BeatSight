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
- runs the full scene catalog in chunked scene batches,
- splits the heaviest editor/playback cluster into per-scene batches,
- prints heartbeat logs while each batch is running,
- applies a per-batch timeout,
- validates each batch from generated TRX results,
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

CI runs visual regression in `Release`, so prefer `-c Release` when updating baselines.
