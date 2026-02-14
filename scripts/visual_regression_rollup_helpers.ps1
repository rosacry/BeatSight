function Get-VisualTrxDurationSeconds {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TrxPath
    )

    if (-not (Test-Path $TrxPath)) {
        return $null
    }

    [xml]$trx = Get-Content -Path $TrxPath -Raw
    $times = $trx.TestRun.Times
    if ($null -eq $times) {
        return $null
    }

    $startRaw = [string]$times.start
    $finishRaw = [string]$times.finish
    if ([string]::IsNullOrWhiteSpace($startRaw) -or [string]::IsNullOrWhiteSpace($finishRaw)) {
        return $null
    }

    [DateTimeOffset]$start = [DateTimeOffset]::MinValue
    [DateTimeOffset]$finish = [DateTimeOffset]::MinValue
    if (-not [DateTimeOffset]::TryParse($startRaw, [ref]$start)) {
        return $null
    }
    if (-not [DateTimeOffset]::TryParse($finishRaw, [ref]$finish)) {
        return $null
    }

    $durationSeconds = ($finish - $start).TotalSeconds
    if ($durationSeconds -lt 0) {
        return $null
    }

    return [Math]::Round([double]$durationSeconds, 3)
}

function Get-VisualPercentileValue {
    param(
        [double[]]$Values,
        [double]$Percentile
    )

    if (-not $Values -or $Values.Count -eq 0) {
        return $null
    }

    $sorted = $Values | Sort-Object
    $rank = [Math]::Ceiling(($Percentile / 100.0) * $sorted.Count)
    $index = [Math]::Min([Math]::Max([int]$rank - 1, 0), $sorted.Count - 1)
    return [double]$sorted[$index]
}

function Get-VisualTimingRollup {
    param(
        [object[]]$BatchResults
    )

    if (-not $BatchResults -or $BatchResults.Count -eq 0) {
        return $null
    }

    $totalDurations = @($BatchResults | ForEach-Object { [double]$_.TotalSeconds })
    $startupDurations = @($BatchResults | Where-Object { $null -ne $_.StartupSeconds } | ForEach-Object { [double]$_.StartupSeconds })
    $trxDurations = @($BatchResults | Where-Object { $null -ne $_.TrxDurationSeconds } | ForEach-Object { [double]$_.TrxDurationSeconds })
    $trxSampleCount = $trxDurations.Count
    $trxMissingCount = [Math]::Max(0, $BatchResults.Count - $trxSampleCount)

    $totalMean = [double]($totalDurations | Measure-Object -Average).Average
    $totalP95 = Get-VisualPercentileValue -Values $totalDurations -Percentile 95
    $startupMean = if ($startupDurations.Count -gt 0) { [double]($startupDurations | Measure-Object -Average).Average } else { $null }
    $startupP95 = if ($startupDurations.Count -gt 0) { Get-VisualPercentileValue -Values $startupDurations -Percentile 95 } else { $null }
    $trxMean = if ($trxDurations.Count -gt 0) { [double]($trxDurations | Measure-Object -Average).Average } else { $null }
    $trxP95 = if ($trxDurations.Count -gt 0) { Get-VisualPercentileValue -Values $trxDurations -Percentile 95 } else { $null }

    $slowest = $BatchResults | Sort-Object TotalSeconds -Descending | Select-Object -First 1

    return [pscustomobject]@{
        BatchCount = $BatchResults.Count
        StartupMeanSeconds = $startupMean
        StartupP95Seconds = $startupP95
        TotalMeanSeconds = $totalMean
        TotalP95Seconds = $totalP95
        TrxMeanSeconds = $trxMean
        TrxP95Seconds = $trxP95
        TrxDurationSampleCount = $trxSampleCount
        TrxDurationMissingCount = $trxMissingCount
        SlowestBatchScenes = if ($null -eq $slowest) { $null } else { [string]$slowest.Scenes }
        SlowestBatchTotalSeconds = if ($null -eq $slowest) { $null } else { [double]$slowest.TotalSeconds }
    }
}

function Save-VisualTimingRollupArtifact {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ResultsDirectory,
        [Parameter(Mandatory = $true)]
        [object[]]$BatchResults,
        [Parameter(Mandatory = $true)]
        [object]$Rollup,
        [object]$RunMetadata = $null
    )

    if ([string]::IsNullOrWhiteSpace($ResultsDirectory)) {
        return $null
    }

    New-Item -ItemType Directory -Path $ResultsDirectory -Force | Out-Null

    $artifactFileName = "visual_rollup_$(Get-Date -Format 'yyyyMMdd_HHmmss_fff').json"
    $artifactPath = Join-Path $ResultsDirectory $artifactFileName

    $payload = [pscustomobject]@{
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString("o")
        Metadata = $RunMetadata
        Rollup = $Rollup
        Batches = $BatchResults
    }

    $payload | ConvertTo-Json -Depth 8 | Set-Content -Path $artifactPath -Encoding UTF8
    return $artifactPath
}

function Compare-VisualTimingRollups {
    param(
        [Parameter(Mandatory = $true)]
        [object]$BaselineRollup,
        [Parameter(Mandatory = $true)]
        [object]$CurrentRollup
    )

    $metricNames = @(
        "StartupMeanSeconds",
        "StartupP95Seconds",
        "TotalMeanSeconds",
        "TotalP95Seconds",
        "TrxMeanSeconds",
        "TrxP95Seconds"
    )

    $metricDiffs = @()
    foreach ($metricName in $metricNames) {
        $baselineRaw = $BaselineRollup.$metricName
        $currentRaw = $CurrentRollup.$metricName
        $baseline = if ($null -eq $baselineRaw) { $null } else { [double]$baselineRaw }
        $current = if ($null -eq $currentRaw) { $null } else { [double]$currentRaw }
        $delta = if ($null -eq $baseline -or $null -eq $current) { $null } else { [double]($current - $baseline) }
        $deltaPercent = if ($null -eq $delta -or $null -eq $baseline -or [Math]::Abs([double]$baseline) -lt 0.000001) {
            $null
        }
        else {
            [double](($delta / [Math]::Abs([double]$baseline)) * 100.0)
        }

        $metricDiffs += [pscustomobject]@{
            Name = $metricName
            Baseline = $baseline
            Current = $current
            Delta = $delta
            DeltaPercent = $deltaPercent
        }
    }

    $baselineBatchCount = if ($null -eq $BaselineRollup.BatchCount) { $null } else { [int]$BaselineRollup.BatchCount }
    $currentBatchCount = if ($null -eq $CurrentRollup.BatchCount) { $null } else { [int]$CurrentRollup.BatchCount }
    $baselineTrxSamples = if ($null -eq $BaselineRollup.TrxDurationSampleCount) { $null } else { [int]$BaselineRollup.TrxDurationSampleCount }
    $currentTrxSamples = if ($null -eq $CurrentRollup.TrxDurationSampleCount) { $null } else { [int]$CurrentRollup.TrxDurationSampleCount }
    $baselineTrxMissing = if ($null -eq $BaselineRollup.TrxDurationMissingCount) { $null } else { [int]$BaselineRollup.TrxDurationMissingCount }
    $currentTrxMissing = if ($null -eq $CurrentRollup.TrxDurationMissingCount) { $null } else { [int]$CurrentRollup.TrxDurationMissingCount }

    return [pscustomobject]@{
        BatchCountBaseline = $baselineBatchCount
        BatchCountCurrent = $currentBatchCount
        BatchCountDelta = if ($null -eq $baselineBatchCount -or $null -eq $currentBatchCount) { $null } else { [int]($currentBatchCount - $baselineBatchCount) }
        TrxDurationSampleCountBaseline = $baselineTrxSamples
        TrxDurationSampleCountCurrent = $currentTrxSamples
        TrxDurationSampleCountDelta = if ($null -eq $baselineTrxSamples -or $null -eq $currentTrxSamples) { $null } else { [int]($currentTrxSamples - $baselineTrxSamples) }
        TrxDurationMissingCountBaseline = $baselineTrxMissing
        TrxDurationMissingCountCurrent = $currentTrxMissing
        TrxDurationMissingCountDelta = if ($null -eq $baselineTrxMissing -or $null -eq $currentTrxMissing) { $null } else { [int]($currentTrxMissing - $baselineTrxMissing) }
        SlowestBatchScenesBaseline = if ($null -eq $BaselineRollup.SlowestBatchScenes) { $null } else { [string]$BaselineRollup.SlowestBatchScenes }
        SlowestBatchScenesCurrent = if ($null -eq $CurrentRollup.SlowestBatchScenes) { $null } else { [string]$CurrentRollup.SlowestBatchScenes }
        SlowestBatchTotalSecondsBaseline = if ($null -eq $BaselineRollup.SlowestBatchTotalSeconds) { $null } else { [double]$BaselineRollup.SlowestBatchTotalSeconds }
        SlowestBatchTotalSecondsCurrent = if ($null -eq $CurrentRollup.SlowestBatchTotalSeconds) { $null } else { [double]$CurrentRollup.SlowestBatchTotalSeconds }
        SlowestBatchTotalSecondsDelta = if ($null -eq $BaselineRollup.SlowestBatchTotalSeconds -or $null -eq $CurrentRollup.SlowestBatchTotalSeconds) { $null } else { [double]$CurrentRollup.SlowestBatchTotalSeconds - [double]$BaselineRollup.SlowestBatchTotalSeconds }
        Metrics = $metricDiffs
    }
}

function Test-VisualTimingRollupThresholds {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Rollup,
        [double]$MaxTotalP95Seconds = 0,
        [double]$MaxStartupP95Seconds = 0,
        [double]$MaxTrxMissingRatio = 0
    )

    $failures = @()

    if ($null -ne $Rollup.TotalP95Seconds -and $MaxTotalP95Seconds -gt 0 -and [double]$Rollup.TotalP95Seconds -gt $MaxTotalP95Seconds) {
        $failures += "total_p95=$([Math]::Round([double]$Rollup.TotalP95Seconds, 3))s exceeds limit ${MaxTotalP95Seconds}s"
    }

    if ($null -ne $Rollup.StartupP95Seconds -and $MaxStartupP95Seconds -gt 0 -and [double]$Rollup.StartupP95Seconds -gt $MaxStartupP95Seconds) {
        $failures += "startup_p95=$([Math]::Round([double]$Rollup.StartupP95Seconds, 3))s exceeds limit ${MaxStartupP95Seconds}s"
    }

    if ($MaxTrxMissingRatio -gt 0 -and $null -ne $Rollup.BatchCount -and [int]$Rollup.BatchCount -gt 0) {
        $missingCount = if ($null -eq $Rollup.TrxDurationMissingCount) { 0 } else { [double]$Rollup.TrxDurationMissingCount }
        $batchCount = [double]$Rollup.BatchCount
        $missingRatio = $missingCount / $batchCount

        if ($missingRatio -gt $MaxTrxMissingRatio) {
            $failures += "trx_missing_ratio=$([Math]::Round($missingRatio, 4)) exceeds limit $([Math]::Round($MaxTrxMissingRatio, 4))"
        }
    }

    return [pscustomobject]@{
        Passed = $failures.Count -eq 0
        FailureCount = $failures.Count
        Failures = $failures
    }
}
