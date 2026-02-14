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
