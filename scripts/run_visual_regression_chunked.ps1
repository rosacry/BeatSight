param(
    [string]$ProjectPath = "desktop/BeatSight.Tests/BeatSight.Tests.csproj",
    [string]$Configuration = "Release",
    [string]$Resolutions = "720p,1080p,1440p,ultrawide",
    [string]$ResultsDirectory = "desktop/BeatSight.Tests/TestResults/visual-chunked",
    [string[]]$SceneBatches = @(
        "Intro,MainMenu,SongSelect,SongSelectEditor,Settings",
        "Recording,Onboarding,AudioImportLoading,MappingChoice,MetadataChoice",
        "MappingGeneration",
        "Editor",
        "Playback",
        "EditorManuscript",
        "PlaybackManuscript"
    ),
    [int]$BatchTimeoutSeconds = 900,
    [int]$HeartbeatSeconds = 20,
    [switch]$RunFullDesktopSuite,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Invoke-VisualBatch {
    param(
        [string]$Scenes,
        [string]$Resolutions,
        [string]$ProjectPath,
        [string]$Configuration,
        [string]$ResultsDirectory,
        [int]$TimeoutSeconds,
        [int]$HeartbeatSeconds,
        [switch]$DryRun
    )

    $env:BEATSIGHT_RUN_VISUAL_TESTS = "1"
    $env:BEATSIGHT_VISUAL_SCENES = $Scenes
    $env:BEATSIGHT_VISUAL_RESOLUTIONS = $Resolutions

    $resolvedResultsDirectory = if ([System.IO.Path]::IsPathRooted($ResultsDirectory)) {
        $ResultsDirectory
    }
    else {
        Join-Path (Get-Location).Path $ResultsDirectory
    }
    New-Item -ItemType Directory -Path $resolvedResultsDirectory -Force | Out-Null
    $sceneSlug = ($Scenes -replace '[^A-Za-z0-9]+', '_').Trim('_')
    if ([string]::IsNullOrWhiteSpace($sceneSlug)) {
        $sceneSlug = "batch"
    }
    $trxFileName = "visual_batch_${sceneSlug}_$(Get-Date -Format 'yyyyMMdd_HHmmss_fff').trx"
    $trxPath = Join-Path $resolvedResultsDirectory $trxFileName

    $args = @(
        "test",
        $ProjectPath,
        "-c",
        $Configuration,
        "--filter",
        "FullyQualifiedName~VisualRegressionSnapshotTests",
        "--logger",
        "trx;LogFileName=$trxFileName",
        "--results-directory",
        $resolvedResultsDirectory
    )

    Write-Host ""
    Write-Host "[visual-gate] scenes: $Scenes"
    Write-Host "[visual-gate] resolutions: $Resolutions"
    Write-Host "[visual-gate] timeout: ${TimeoutSeconds}s"
    Write-Host "[visual-gate] trx: $trxPath"
    Write-Host "[visual-gate] note: each batch can take 60-120s+ depending on scene/resolution complexity."

    if ($DryRun) {
        Write-Host "[visual-gate][dry-run] dotnet $($args -join ' ')"
        return 0
    }

    $process = Start-Process -FilePath "dotnet" -ArgumentList $args -NoNewWindow -PassThru
    $elapsed = 0

    while (-not $process.HasExited) {
        Start-Sleep -Seconds $HeartbeatSeconds
        $elapsed += $HeartbeatSeconds
        if (-not $process.HasExited) {
            Write-Host "[visual-gate] batch still running (${elapsed}s elapsed)..."
        }

        if ($elapsed -ge $TimeoutSeconds -and -not $process.HasExited) {
            try {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
            finally {
                throw "Visual batch timed out after ${TimeoutSeconds}s for scenes: $Scenes"
            }
        }
    }

    $process.WaitForExit()
    $process.Refresh()
    $exitCode = $process.ExitCode
    if ($null -eq $exitCode) {
        Write-Host "[visual-gate][info] batch did not report an exit code for scenes: $Scenes; verifying via TRX outcome."
        $exitCode = 0
    }

    if (-not (Test-Path $trxPath)) {
        throw "Visual batch did not produce TRX results: $trxPath"
    }

    [xml]$trx = Get-Content -Path $trxPath -Raw
    $summary = $trx.TestRun.ResultSummary
    $counters = $summary.Counters
    $outcome = [string]$summary.outcome
    $total = [int]$counters.total
    $passed = [int]$counters.passed
    $failed = [int]$counters.failed
    Write-Host "[visual-gate] trx outcome: $outcome ($passed/$total passed, $failed failed)"

    if ($failed -gt 0 -or ($outcome -ne "Passed" -and $outcome -ne "Completed")) {
        throw "Visual batch failed by TRX outcome ($outcome, failed=$failed) for scenes: $Scenes"
    }

    if ($exitCode -ne 0) {
        throw "Visual batch failed (exit code $exitCode) for scenes: $Scenes"
    }

    Write-Host "[visual-gate] batch passed for scenes: $Scenes"
    return 0
}

try {
    Write-Host "[visual-gate] starting chunked visual regression run..."
    Write-Host "[visual-gate] project: $ProjectPath"
    Write-Host "[visual-gate] batches: $($SceneBatches.Count)"

    for ($index = 0; $index -lt $SceneBatches.Count; $index++) {
        $batch = $SceneBatches[$index]
        Write-Host ""
        Write-Host "[visual-gate] batch $($index + 1)/$($SceneBatches.Count)"
        [void](Invoke-VisualBatch `
            -Scenes $batch `
            -Resolutions $Resolutions `
            -ProjectPath $ProjectPath `
            -Configuration $Configuration `
            -ResultsDirectory $ResultsDirectory `
            -TimeoutSeconds $BatchTimeoutSeconds `
            -HeartbeatSeconds $HeartbeatSeconds `
            -DryRun:$DryRun)
    }

    if ($RunFullDesktopSuite) {
        Write-Host ""
        Write-Host "[visual-gate] visual batches passed. Running full desktop suite..."
        if ($DryRun) {
            Write-Host "[visual-gate][dry-run] dotnet test $ProjectPath -c $Configuration"
        }
        else {
            dotnet test $ProjectPath -c $Configuration
            if ($LASTEXITCODE -ne 0) {
                throw "Full desktop suite failed (exit code $LASTEXITCODE)."
            }
        }
    }

    Write-Host ""
    Write-Host "[visual-gate] completed successfully."
}
finally {
    Remove-Item Env:BEATSIGHT_RUN_VISUAL_TESTS -ErrorAction SilentlyContinue
    Remove-Item Env:BEATSIGHT_VISUAL_SCENES -ErrorAction SilentlyContinue
    Remove-Item Env:BEATSIGHT_VISUAL_RESOLUTIONS -ErrorAction SilentlyContinue
}
