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
    [switch]$SkipInitialBuild,
    [switch]$SkipStaleProcessCleanup,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Resolve-ProjectPath {
    param(
        [string]$ProjectPath
    )

    if ([System.IO.Path]::IsPathRooted($ProjectPath)) {
        return $ProjectPath
    }

    return Join-Path (Get-Location).Path $ProjectPath
}

function Stop-StaleBeatSightTestProcesses {
    param(
        [string]$ProjectPath
    )

    $isWindows = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)
    if (-not $isWindows) {
        return
    }

    $projectToken = [System.IO.Path]::GetFileName($ProjectPath)
    $candidates = Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -ieq "testhost.exe" -or $_.Name -ieq "dotnet.exe") -and
        $_.CommandLine -like "*$projectToken*"
    }

    if (-not $candidates) {
        Write-Host "[visual-gate] no stale BeatSight testhost processes detected."
        return
    }

    $stopped = 0
    foreach ($candidate in $candidates) {
        try {
            Stop-Process -Id $candidate.ProcessId -Force -ErrorAction Stop
            $stopped++
        }
        catch {
            Write-Host "[visual-gate][warn] failed to stop stale process id=$($candidate.ProcessId): $($_.Exception.Message)"
        }
    }

    Write-Host "[visual-gate] stopped $stopped stale BeatSight test process(es) before run."
}

function Invoke-InitialBuild {
    param(
        [string]$ProjectPath,
        [string]$Configuration,
        [switch]$DryRun
    )

    Write-Host "[visual-gate] running initial build (once) for $ProjectPath..."
    if ($DryRun) {
        Write-Host "[visual-gate][dry-run] dotnet build $ProjectPath -c $Configuration"
        return
    }

    dotnet build $ProjectPath -c $Configuration
    if ($LASTEXITCODE -ne 0) {
        throw "Initial build failed (exit code $LASTEXITCODE)."
    }
}

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
        "--no-build",
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
    $resolvedProjectPath = Resolve-ProjectPath -ProjectPath $ProjectPath
    Write-Host "[visual-gate] starting chunked visual regression run..."
    Write-Host "[visual-gate] project: $resolvedProjectPath"
    Write-Host "[visual-gate] batches: $($SceneBatches.Count)"

    if (-not $SkipStaleProcessCleanup) {
        Stop-StaleBeatSightTestProcesses -ProjectPath $resolvedProjectPath
    }

    if (-not $SkipInitialBuild) {
        Invoke-InitialBuild -ProjectPath $resolvedProjectPath -Configuration $Configuration -DryRun:$DryRun
    }

    for ($index = 0; $index -lt $SceneBatches.Count; $index++) {
        $batch = $SceneBatches[$index]
        Write-Host ""
        Write-Host "[visual-gate] batch $($index + 1)/$($SceneBatches.Count)"
        [void](Invoke-VisualBatch `
            -Scenes $batch `
            -Resolutions $Resolutions `
            -ProjectPath $resolvedProjectPath `
            -Configuration $Configuration `
            -ResultsDirectory $ResultsDirectory `
            -TimeoutSeconds $BatchTimeoutSeconds `
            -HeartbeatSeconds $HeartbeatSeconds `
            -DryRun:$DryRun)
    }

    if ($RunFullDesktopSuite) {
        Write-Host ""
        Write-Host "[visual-gate] visual batches passed. Running full desktop suite..."
        Remove-Item Env:BEATSIGHT_RUN_VISUAL_TESTS -ErrorAction SilentlyContinue
        Remove-Item Env:BEATSIGHT_VISUAL_SCENES -ErrorAction SilentlyContinue
        Remove-Item Env:BEATSIGHT_VISUAL_RESOLUTIONS -ErrorAction SilentlyContinue
        if ($DryRun) {
            Write-Host "[visual-gate][dry-run] dotnet test $resolvedProjectPath -c $Configuration --no-build"
        }
        else {
            dotnet test $resolvedProjectPath -c $Configuration --no-build
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
