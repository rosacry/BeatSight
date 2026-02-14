param(
    [string]$RollupPath,
    [string]$ResultsDirectory = "desktop/BeatSight.Tests/TestResults/visual-chunked",
    [double]$MaxTotalP95Seconds = 0,
    [double]$MaxStartupP95Seconds = 0,
    [double]$MaxTrxMissingRatio = 0,
    [switch]$FailOnThresholdBreach,
    [string]$SummaryPath = "",
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

function Resolve-RollupPath {
    param(
        [string]$RollupPath,
        [string]$ResultsDirectory
    )

    if (-not [string]::IsNullOrWhiteSpace($RollupPath)) {
        $resolvedPath = Resolve-AbsolutePath -PathValue $RollupPath
        if (-not (Test-Path $resolvedPath)) {
            throw "Visual rollup artifact not found: $resolvedPath"
        }

        return $resolvedPath
    }

    $resolvedDirectory = Resolve-AbsolutePath -PathValue $ResultsDirectory
    if (-not (Test-Path $resolvedDirectory)) {
        throw "Visual rollup directory not found: $resolvedDirectory"
    }

    $latest = Get-ChildItem -Path $resolvedDirectory -Filter "visual_rollup_*.json" -File |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1

    if ($null -eq $latest) {
        throw "No visual rollup artifacts found in: $resolvedDirectory"
    }

    return $latest.FullName
}

function Format-Seconds {
    param([object]$Value)
    if ($null -eq $Value) { return "n/a" }
    return "$([Math]::Round([double]$Value, 2))s"
}

$resolvedRollupPath = Resolve-RollupPath -RollupPath $RollupPath -ResultsDirectory $ResultsDirectory
$payload = Get-Content -Path $resolvedRollupPath -Raw | ConvertFrom-Json
if ($null -eq $payload.Rollup) {
    throw "Rollup payload missing Rollup node: $resolvedRollupPath"
}

$rollup = $payload.Rollup
$thresholdEvaluation = Test-VisualTimingRollupThresholds `
    -Rollup $rollup `
    -MaxTotalP95Seconds $MaxTotalP95Seconds `
    -MaxStartupP95Seconds $MaxStartupP95Seconds `
    -MaxTrxMissingRatio $MaxTrxMissingRatio

$missingRatio = if ($null -eq $rollup.BatchCount -or [int]$rollup.BatchCount -le 0) {
    $null
}
else {
    [double]$rollup.TrxDurationMissingCount / [double]$rollup.BatchCount
}

$result = [pscustomobject]@{
    RollupPath = $resolvedRollupPath
    GeneratedAtUtc = $payload.GeneratedAtUtc
    Metadata = $payload.Metadata
    Rollup = $rollup
    Thresholds = [pscustomobject]@{
        MaxTotalP95Seconds = $MaxTotalP95Seconds
        MaxStartupP95Seconds = $MaxStartupP95Seconds
        MaxTrxMissingRatio = $MaxTrxMissingRatio
    }
    Metrics = [pscustomobject]@{
        BatchCount = $rollup.BatchCount
        StartupMeanSeconds = $rollup.StartupMeanSeconds
        StartupP95Seconds = $rollup.StartupP95Seconds
        TotalMeanSeconds = $rollup.TotalMeanSeconds
        TotalP95Seconds = $rollup.TotalP95Seconds
        TrxMeanSeconds = $rollup.TrxMeanSeconds
        TrxP95Seconds = $rollup.TrxP95Seconds
        TrxDurationSampleCount = $rollup.TrxDurationSampleCount
        TrxDurationMissingCount = $rollup.TrxDurationMissingCount
        TrxDurationMissingRatio = $missingRatio
        SlowestBatchScenes = $rollup.SlowestBatchScenes
        SlowestBatchTotalSeconds = $rollup.SlowestBatchTotalSeconds
    }
    ThresholdEvaluation = $thresholdEvaluation
}

$status = if ($thresholdEvaluation.Passed) { "PASS" } else { "FAIL" }
Write-Host "[visual-rollup-gate] status: $status"
Write-Host "[visual-rollup-gate] artifact: $resolvedRollupPath"
Write-Host "[visual-rollup-gate] startup_mean=$(Format-Seconds $rollup.StartupMeanSeconds), startup_p95=$(Format-Seconds $rollup.StartupP95Seconds), total_mean=$(Format-Seconds $rollup.TotalMeanSeconds), total_p95=$(Format-Seconds $rollup.TotalP95Seconds), trx_mean=$(Format-Seconds $rollup.TrxMeanSeconds), trx_p95=$(Format-Seconds $rollup.TrxP95Seconds)"

if (-not $thresholdEvaluation.Passed) {
    foreach ($failure in $thresholdEvaluation.Failures) {
        Write-Host "[visual-rollup-gate][fail] $failure"
    }
}

$resolvedSummaryPath = $SummaryPath
if ([string]::IsNullOrWhiteSpace($resolvedSummaryPath)) {
    $resolvedSummaryPath = $env:GITHUB_STEP_SUMMARY
}

if (-not [string]::IsNullOrWhiteSpace($resolvedSummaryPath)) {
    $summaryLines = @()
    $summaryLines += "## Visual Rollup Gate ($status)"
    $summaryLines += ""
    $summaryLines += "- Artifact: ``$resolvedRollupPath``"
    $summaryLines += "- Generated (UTC): $($payload.GeneratedAtUtc)"
    $summaryLines += "- Batch count: $($rollup.BatchCount)"
    $summaryLines += "- Startup mean/p95: $(Format-Seconds $rollup.StartupMeanSeconds) / $(Format-Seconds $rollup.StartupP95Seconds)"
    $summaryLines += "- Total mean/p95: $(Format-Seconds $rollup.TotalMeanSeconds) / $(Format-Seconds $rollup.TotalP95Seconds)"
    $summaryLines += "- TRX mean/p95: $(Format-Seconds $rollup.TrxMeanSeconds) / $(Format-Seconds $rollup.TrxP95Seconds)"
    if ($null -ne $missingRatio) {
        $summaryLines += "- TRX missing ratio: $([Math]::Round($missingRatio * 100, 2))% ($($rollup.TrxDurationMissingCount)/$($rollup.BatchCount))"
    }
    $summaryLines += "- Slowest batch: '$($rollup.SlowestBatchScenes)' at $(Format-Seconds $rollup.SlowestBatchTotalSeconds)"
    if (-not $thresholdEvaluation.Passed) {
        $summaryLines += ""
        $summaryLines += "### Threshold Failures"
        foreach ($failure in $thresholdEvaluation.Failures) {
            $summaryLines += "- $failure"
        }
    }

    Add-Content -Path $resolvedSummaryPath -Value ($summaryLines -join [Environment]::NewLine)
}

if ($OutputJson) {
    $result | ConvertTo-Json -Depth 32
}

if ($FailOnThresholdBreach -and -not $thresholdEvaluation.Passed) {
    throw "Visual rollup threshold gate failed."
}
