param(
    [string]$BaselinePath,
    [string]$CurrentPath,
    [string]$ResultsDirectory = "desktop/BeatSight.Tests/TestResults/visual-chunked",
    [switch]$OutputJson
)

$ErrorActionPreference = "Stop"

$helperScriptPath = Join-Path $PSScriptRoot "visual_regression_rollup_helpers.ps1"
if (-not (Test-Path $helperScriptPath)) {
    throw "Missing helper script: $helperScriptPath"
}
. $helperScriptPath

function Resolve-AbsolutePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }

    return Join-Path (Get-Location).Path $PathValue
}

function Get-LatestRollupArtifacts {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ResultsDirectory,
        [int]$Count = 2
    )

    $resolvedDirectory = Resolve-AbsolutePath -PathValue $ResultsDirectory
    if (-not (Test-Path $resolvedDirectory)) {
        throw "Results directory does not exist: $resolvedDirectory"
    }

    $artifacts = Get-ChildItem -Path $resolvedDirectory -Filter "visual_rollup_*.json" -File |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First $Count

    if ($artifacts.Count -lt $Count) {
        throw "Expected at least $Count visual rollup artifact(s) in $resolvedDirectory, found $($artifacts.Count)."
    }

    return $artifacts
}

function Get-RollupPayload {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ArtifactPath
    )

    $resolvedPath = Resolve-AbsolutePath -PathValue $ArtifactPath
    if (-not (Test-Path $resolvedPath)) {
        throw "Visual rollup artifact not found: $resolvedPath"
    }

    $payload = Get-Content -Path $resolvedPath -Raw | ConvertFrom-Json
    if ($null -eq $payload.Rollup) {
        throw "Visual rollup artifact missing Rollup node: $resolvedPath"
    }

    return [pscustomobject]@{
        Path = $resolvedPath
        Payload = $payload
    }
}

function Format-DeltaSummary {
    param(
        [object]$Metric
    )

    $baseline = if ($null -eq $Metric.Baseline) { "n/a" } else { [Math]::Round([double]$Metric.Baseline, 3) }
    $current = if ($null -eq $Metric.Current) { "n/a" } else { [Math]::Round([double]$Metric.Current, 3) }
    $delta = if ($null -eq $Metric.Delta) { "n/a" } else { "{0:+0.###;-0.###;0}" -f [double]$Metric.Delta }
    $deltaPercent = if ($null -eq $Metric.DeltaPercent) { "n/a" } else { "{0:+0.##;-0.##;0}%" -f [double]$Metric.DeltaPercent }
    return "$($Metric.Name): baseline=$baseline, current=$current, delta=$delta ($deltaPercent)"
}

if ([string]::IsNullOrWhiteSpace($BaselinePath) -and [string]::IsNullOrWhiteSpace($CurrentPath)) {
    $latestArtifacts = Get-LatestRollupArtifacts -ResultsDirectory $ResultsDirectory -Count 2
    $CurrentPath = $latestArtifacts[0].FullName
    $BaselinePath = $latestArtifacts[1].FullName
}
elseif ([string]::IsNullOrWhiteSpace($BaselinePath) -or [string]::IsNullOrWhiteSpace($CurrentPath)) {
    throw "Specify both -BaselinePath and -CurrentPath, or specify neither to auto-select the latest two artifacts."
}

$baseline = Get-RollupPayload -ArtifactPath $BaselinePath
$current = Get-RollupPayload -ArtifactPath $CurrentPath

$comparison = Compare-VisualTimingRollups -BaselineRollup $baseline.Payload.Rollup -CurrentRollup $current.Payload.Rollup

$result = [pscustomobject]@{
    ComparedAtUtc = [DateTimeOffset]::UtcNow.ToString("o")
    BaselinePath = $baseline.Path
    CurrentPath = $current.Path
    BaselineGeneratedAtUtc = $baseline.Payload.GeneratedAtUtc
    CurrentGeneratedAtUtc = $current.Payload.GeneratedAtUtc
    BaselineMetadata = $baseline.Payload.Metadata
    CurrentMetadata = $current.Payload.Metadata
    Comparison = $comparison
}

if ($OutputJson) {
    $result | ConvertTo-Json -Depth 32
}
else {
    Write-Host "[visual-rollup] baseline: $($result.BaselinePath)"
    Write-Host "[visual-rollup] current:  $($result.CurrentPath)"
    Write-Host "[visual-rollup] generated: baseline=$($result.BaselineGeneratedAtUtc), current=$($result.CurrentGeneratedAtUtc)"
    Write-Host "[visual-rollup] batch_count: $($comparison.BatchCountBaseline) -> $($comparison.BatchCountCurrent) (delta $($comparison.BatchCountDelta))"
    Write-Host "[visual-rollup] trx_samples: $($comparison.TrxDurationSampleCountBaseline) -> $($comparison.TrxDurationSampleCountCurrent) (delta $($comparison.TrxDurationSampleCountDelta))"
    Write-Host "[visual-rollup] trx_missing: $($comparison.TrxDurationMissingCountBaseline) -> $($comparison.TrxDurationMissingCountCurrent) (delta $($comparison.TrxDurationMissingCountDelta))"

    foreach ($metric in $comparison.Metrics) {
        Write-Host "[visual-rollup] $(Format-DeltaSummary -Metric $metric)"
    }

    if (-not [string]::IsNullOrWhiteSpace([string]$comparison.SlowestBatchScenesBaseline) -or -not [string]::IsNullOrWhiteSpace([string]$comparison.SlowestBatchScenesCurrent)) {
        $slowDelta = if ($null -eq $comparison.SlowestBatchTotalSecondsDelta) { "n/a" } else { "{0:+0.###;-0.###;0}" -f [double]$comparison.SlowestBatchTotalSecondsDelta }
        Write-Host "[visual-rollup] slowest_batch: '$($comparison.SlowestBatchScenesBaseline)' -> '$($comparison.SlowestBatchScenesCurrent)' (delta ${slowDelta}s)"
    }
}
