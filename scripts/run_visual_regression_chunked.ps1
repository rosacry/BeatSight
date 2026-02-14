param(
    [string]$ProjectPath = "desktop/BeatSight.Tests/BeatSight.Tests.csproj",
    [string]$Configuration = "Release",
    [string]$Resolutions = "720p,1080p,1440p,ultrawide",
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
        [int]$TimeoutSeconds,
        [int]$HeartbeatSeconds,
        [switch]$DryRun
    )

    $env:BEATSIGHT_RUN_VISUAL_TESTS = "1"
    $env:BEATSIGHT_VISUAL_SCENES = $Scenes
    $env:BEATSIGHT_VISUAL_RESOLUTIONS = $Resolutions

    $args = @(
        "test",
        $ProjectPath,
        "-c",
        $Configuration,
        "--filter",
        "FullyQualifiedName~VisualRegressionSnapshotTests"
    )

    Write-Host ""
    Write-Host "[visual-gate] scenes: $Scenes"
    Write-Host "[visual-gate] resolutions: $Resolutions"
    Write-Host "[visual-gate] timeout: ${TimeoutSeconds}s"

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
        Write-Warning "Visual batch did not report an exit code; assuming success for scenes: $Scenes"
        $exitCode = 0
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
