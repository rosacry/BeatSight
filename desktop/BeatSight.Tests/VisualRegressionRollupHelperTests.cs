using System.Diagnostics;
using System.Text.Json;
using BeatSight.Tests.VisualRegression;
using Xunit;

namespace BeatSight.Tests;

public class VisualRegressionRollupHelperTests
{
    [Fact]
    public void RollupHelperParsesSyntheticTrxDuration()
    {
        if (!OperatingSystem.IsWindows())
            return;

        string repoRoot = TestPathResolver.ResolveRepositoryRoot();
        string helperPath = Path.Combine(repoRoot, "scripts", "visual_regression_rollup_helpers.ps1");
        Assert.True(File.Exists(helperPath), $"Expected helper script missing: {helperPath}");

        string tempRoot = Path.Combine(Path.GetTempPath(), "BeatSight.RollupHelperTests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempRoot);
        string trxPath = Path.Combine(tempRoot, "sample.trx");

        try
        {
            File.WriteAllText(trxPath, """
<?xml version="1.0" encoding="utf-8"?>
<TestRun id="test" name="sample">
  <Times creation="2026-02-14T16:00:00.0000000+00:00" queuing="2026-02-14T16:00:01.0000000+00:00" start="2026-02-14T16:00:05.0000000+00:00" finish="2026-02-14T16:01:35.5000000+00:00" />
  <ResultSummary outcome="Completed">
    <Counters total="1" executed="1" passed="1" failed="0" />
  </ResultSummary>
</TestRun>
""");

            string payload = runHelperAndGetJson(
                helperPath,
                $"[pscustomobject]@{{ duration = Get-VisualTrxDurationSeconds -TrxPath '{toSingleQuotedLiteral(trxPath)}' }}");

            using JsonDocument document = JsonDocument.Parse(payload);
            double duration = document.RootElement.GetProperty("duration").GetDouble();
            Assert.InRange(duration, 90.49, 90.51);
        }
        finally
        {
            try
            {
                Directory.Delete(tempRoot, recursive: true);
            }
            catch
            {
                // Best effort cleanup.
            }
        }
    }

    [Fact]
    public void RollupHelperReturnsNullForMalformedTrxTimes()
    {
        if (!OperatingSystem.IsWindows())
            return;

        string repoRoot = TestPathResolver.ResolveRepositoryRoot();
        string helperPath = Path.Combine(repoRoot, "scripts", "visual_regression_rollup_helpers.ps1");
        Assert.True(File.Exists(helperPath), $"Expected helper script missing: {helperPath}");

        string tempRoot = Path.Combine(Path.GetTempPath(), "BeatSight.RollupHelperTests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempRoot);
        string trxPath = Path.Combine(tempRoot, "malformed.trx");

        try
        {
            File.WriteAllText(trxPath, """
<?xml version="1.0" encoding="utf-8"?>
<TestRun id="test" name="malformed">
  <ResultSummary outcome="Completed">
    <Counters total="1" executed="1" passed="1" failed="0" />
  </ResultSummary>
</TestRun>
""");

            string payload = runHelperAndGetJson(
                helperPath,
                $"[pscustomobject]@{{ duration = Get-VisualTrxDurationSeconds -TrxPath '{toSingleQuotedLiteral(trxPath)}' }}");

            using JsonDocument document = JsonDocument.Parse(payload);
            JsonElement duration = document.RootElement.GetProperty("duration");
            Assert.Equal(JsonValueKind.Null, duration.ValueKind);
        }
        finally
        {
            try
            {
                Directory.Delete(tempRoot, recursive: true);
            }
            catch
            {
                // Best effort cleanup.
            }
        }
    }

    [Fact]
    public void RollupHelperComputesExpectedMeanAndP95()
    {
        if (!OperatingSystem.IsWindows())
            return;

        string repoRoot = TestPathResolver.ResolveRepositoryRoot();
        string helperPath = Path.Combine(repoRoot, "scripts", "visual_regression_rollup_helpers.ps1");
        Assert.True(File.Exists(helperPath), $"Expected helper script missing: {helperPath}");

        string payload = runHelperAndGetJson(
            helperPath,
            """
            $results = @(
              [pscustomobject]@{ Scenes='A'; StartupSeconds=2; TotalSeconds=10; TrxDurationSeconds=9 },
              [pscustomobject]@{ Scenes='B'; StartupSeconds=4; TotalSeconds=20; TrxDurationSeconds=19 },
              [pscustomobject]@{ Scenes='C'; StartupSeconds=6; TotalSeconds=30; TrxDurationSeconds=29 },
              [pscustomobject]@{ Scenes='D'; StartupSeconds=8; TotalSeconds=40; TrxDurationSeconds=39 }
            )
            Get-VisualTimingRollup -BatchResults $results
            """);

        using JsonDocument document = JsonDocument.Parse(payload);
        JsonElement root = document.RootElement;

        Assert.Equal(4, root.GetProperty("BatchCount").GetInt32());
        Assert.Equal("D", root.GetProperty("SlowestBatchScenes").GetString());
        Assert.InRange(root.GetProperty("SlowestBatchTotalSeconds").GetDouble(), 39.99, 40.01);

        Assert.InRange(root.GetProperty("StartupMeanSeconds").GetDouble(), 4.99, 5.01);
        Assert.InRange(root.GetProperty("StartupP95Seconds").GetDouble(), 7.99, 8.01);
        Assert.InRange(root.GetProperty("TotalMeanSeconds").GetDouble(), 24.99, 25.01);
        Assert.InRange(root.GetProperty("TotalP95Seconds").GetDouble(), 39.99, 40.01);
        Assert.InRange(root.GetProperty("TrxMeanSeconds").GetDouble(), 23.99, 24.01);
        Assert.InRange(root.GetProperty("TrxP95Seconds").GetDouble(), 38.99, 39.01);
        Assert.Equal(4, root.GetProperty("TrxDurationSampleCount").GetInt32());
        Assert.Equal(0, root.GetProperty("TrxDurationMissingCount").GetInt32());
    }

    [Fact]
    public void RollupHelperTracksMissingTrxDurationSamples()
    {
        if (!OperatingSystem.IsWindows())
            return;

        string repoRoot = TestPathResolver.ResolveRepositoryRoot();
        string helperPath = Path.Combine(repoRoot, "scripts", "visual_regression_rollup_helpers.ps1");
        Assert.True(File.Exists(helperPath), $"Expected helper script missing: {helperPath}");

        string payload = runHelperAndGetJson(
            helperPath,
            """
            $results = @(
              [pscustomobject]@{ Scenes='A'; StartupSeconds=2; TotalSeconds=10; TrxDurationSeconds=$null },
              [pscustomobject]@{ Scenes='B'; StartupSeconds=4; TotalSeconds=20; TrxDurationSeconds=19 },
              [pscustomobject]@{ Scenes='C'; StartupSeconds=6; TotalSeconds=30; TrxDurationSeconds=$null }
            )
            Get-VisualTimingRollup -BatchResults $results
            """);

        using JsonDocument document = JsonDocument.Parse(payload);
        JsonElement root = document.RootElement;

        Assert.Equal(1, root.GetProperty("TrxDurationSampleCount").GetInt32());
        Assert.Equal(2, root.GetProperty("TrxDurationMissingCount").GetInt32());
        Assert.InRange(root.GetProperty("TrxMeanSeconds").GetDouble(), 18.99, 19.01);
        Assert.InRange(root.GetProperty("TrxP95Seconds").GetDouble(), 18.99, 19.01);
    }

    [Fact]
    public void RollupHelperWritesTimingArtifactJson()
    {
        if (!OperatingSystem.IsWindows())
            return;

        string repoRoot = TestPathResolver.ResolveRepositoryRoot();
        string helperPath = Path.Combine(repoRoot, "scripts", "visual_regression_rollup_helpers.ps1");
        Assert.True(File.Exists(helperPath), $"Expected helper script missing: {helperPath}");

        string tempRoot = Path.Combine(Path.GetTempPath(), "BeatSight.RollupHelperTests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempRoot);

        try
        {
            string payload = runHelperAndGetJson(
                helperPath,
                $$"""
                $results = @(
                  [pscustomobject]@{ Scenes='Settings'; StartupSeconds=1.2; TotalSeconds=12.3; TrxDurationSeconds=10.9; TrxPath='settings.trx'; Passed=1; Total=1 },
                  [pscustomobject]@{ Scenes='Editor'; StartupSeconds=2.5; TotalSeconds=22.2; TrxDurationSeconds=20.1; TrxPath='editor.trx'; Passed=1; Total=1 }
                )
                $rollup = Get-VisualTimingRollup -BatchResults $results
                $metadata = [pscustomobject]@{ Profile='smoke'; BatchCount=2; DryRun=$false }
                $path = Save-VisualTimingRollupArtifact -ResultsDirectory '{{toSingleQuotedLiteral(tempRoot)}}' -BatchResults $results -Rollup $rollup -RunMetadata $metadata
                [pscustomobject]@{
                  path = $path
                  exists = (Test-Path $path)
                }
                """);

            using JsonDocument result = JsonDocument.Parse(payload);
            JsonElement resultRoot = result.RootElement;

            Assert.True(resultRoot.GetProperty("exists").GetBoolean());

            string? artifactPath = resultRoot.GetProperty("path").GetString();
            Assert.False(string.IsNullOrWhiteSpace(artifactPath));
            Assert.True(File.Exists(artifactPath), $"Expected artifact file missing: {artifactPath}");
            Assert.StartsWith("visual_rollup_", Path.GetFileName(artifactPath), StringComparison.OrdinalIgnoreCase);

            using JsonDocument artifact = JsonDocument.Parse(File.ReadAllText(artifactPath));
            JsonElement artifactRoot = artifact.RootElement;

            Assert.False(string.IsNullOrWhiteSpace(artifactRoot.GetProperty("GeneratedAtUtc").GetString()));
            Assert.Equal("smoke", artifactRoot.GetProperty("Metadata").GetProperty("Profile").GetString());
            Assert.Equal(2, artifactRoot.GetProperty("Rollup").GetProperty("BatchCount").GetInt32());
            Assert.Equal("Editor", artifactRoot.GetProperty("Rollup").GetProperty("SlowestBatchScenes").GetString());

            JsonElement batches = artifactRoot.GetProperty("Batches");
            Assert.Equal(2, batches.GetArrayLength());
            Assert.Equal("Settings", batches[0].GetProperty("Scenes").GetString());
            Assert.Equal("Editor", batches[1].GetProperty("Scenes").GetString());
        }
        finally
        {
            try
            {
                Directory.Delete(tempRoot, recursive: true);
            }
            catch
            {
                // Best effort cleanup.
            }
        }
    }

    [Fact]
    public void RollupHelperComparesTimingRollups()
    {
        if (!OperatingSystem.IsWindows())
            return;

        string repoRoot = TestPathResolver.ResolveRepositoryRoot();
        string helperPath = Path.Combine(repoRoot, "scripts", "visual_regression_rollup_helpers.ps1");
        Assert.True(File.Exists(helperPath), $"Expected helper script missing: {helperPath}");

        string payload = runHelperAndGetJson(
            helperPath,
            """
            $baseline = [pscustomobject]@{
              BatchCount=2
              StartupMeanSeconds=0
              StartupP95Seconds=3
              TotalMeanSeconds=20
              TotalP95Seconds=25
              TrxMeanSeconds=18
              TrxP95Seconds=24
              TrxDurationSampleCount=2
              TrxDurationMissingCount=1
              SlowestBatchScenes='Editor'
              SlowestBatchTotalSeconds=30
            }
            $current = [pscustomobject]@{
              BatchCount=2
              StartupMeanSeconds=2
              StartupP95Seconds=4
              TotalMeanSeconds=24
              TotalP95Seconds=29
              TrxMeanSeconds=20
              TrxP95Seconds=27
              TrxDurationSampleCount=2
              TrxDurationMissingCount=0
              SlowestBatchScenes='Playback'
              SlowestBatchTotalSeconds=34
            }
            Compare-VisualTimingRollups -BaselineRollup $baseline -CurrentRollup $current
            """);

        using JsonDocument document = JsonDocument.Parse(payload);
        JsonElement root = document.RootElement;

        Assert.Equal(2, root.GetProperty("BatchCountBaseline").GetInt32());
        Assert.Equal(2, root.GetProperty("BatchCountCurrent").GetInt32());
        Assert.Equal(0, root.GetProperty("BatchCountDelta").GetInt32());
        Assert.Equal(1, root.GetProperty("TrxDurationMissingCountBaseline").GetInt32());
        Assert.Equal(0, root.GetProperty("TrxDurationMissingCountCurrent").GetInt32());
        Assert.Equal(-1, root.GetProperty("TrxDurationMissingCountDelta").GetInt32());
        Assert.Equal("Editor", root.GetProperty("SlowestBatchScenesBaseline").GetString());
        Assert.Equal("Playback", root.GetProperty("SlowestBatchScenesCurrent").GetString());
        Assert.InRange(root.GetProperty("SlowestBatchTotalSecondsDelta").GetDouble(), 3.99, 4.01);

        JsonElement metrics = root.GetProperty("Metrics");
        Assert.Equal(6, metrics.GetArrayLength());

        JsonElement startupMean = metrics[0];
        Assert.Equal("StartupMeanSeconds", startupMean.GetProperty("Name").GetString());
        Assert.InRange(startupMean.GetProperty("Delta").GetDouble(), 1.99, 2.01);
        Assert.Equal(JsonValueKind.Null, startupMean.GetProperty("DeltaPercent").ValueKind);

        JsonElement totalMean = metrics[2];
        Assert.Equal("TotalMeanSeconds", totalMean.GetProperty("Name").GetString());
        Assert.InRange(totalMean.GetProperty("Delta").GetDouble(), 3.99, 4.01);
        Assert.InRange(totalMean.GetProperty("DeltaPercent").GetDouble(), 19.99, 20.01);
    }

    [Fact]
    public void CompareVisualRollupsScriptProducesExpectedJson()
    {
        if (!OperatingSystem.IsWindows())
            return;

        string repoRoot = TestPathResolver.ResolveRepositoryRoot();
        string scriptPath = Path.Combine(repoRoot, "scripts", "compare_visual_rollups.ps1");
        Assert.True(File.Exists(scriptPath), $"Expected compare script missing: {scriptPath}");

        string tempRoot = Path.Combine(Path.GetTempPath(), "BeatSight.RollupCompareTests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempRoot);
        string baselinePath = Path.Combine(tempRoot, "visual_rollup_baseline.json");
        string currentPath = Path.Combine(tempRoot, "visual_rollup_current.json");

        try
        {
            File.WriteAllText(
                baselinePath,
                """
{
  "GeneratedAtUtc": "2026-02-14T16:00:00.0000000+00:00",
  "Metadata": { "Label": "baseline" },
  "Rollup": {
    "BatchCount": 2,
    "StartupMeanSeconds": 0,
    "StartupP95Seconds": 3,
    "TotalMeanSeconds": 20,
    "TotalP95Seconds": 25,
    "TrxMeanSeconds": 18,
    "TrxP95Seconds": 24,
    "TrxDurationSampleCount": 2,
    "TrxDurationMissingCount": 1,
    "SlowestBatchScenes": "Editor",
    "SlowestBatchTotalSeconds": 30
  },
  "Batches": []
}
""");

            File.WriteAllText(
                currentPath,
                """
{
  "GeneratedAtUtc": "2026-02-14T16:05:00.0000000+00:00",
  "Metadata": { "Label": "current" },
  "Rollup": {
    "BatchCount": 2,
    "StartupMeanSeconds": 2,
    "StartupP95Seconds": 4,
    "TotalMeanSeconds": 24,
    "TotalP95Seconds": 29,
    "TrxMeanSeconds": 20,
    "TrxP95Seconds": 27,
    "TrxDurationSampleCount": 2,
    "TrxDurationMissingCount": 0,
    "SlowestBatchScenes": "Playback",
    "SlowestBatchTotalSeconds": 34
  },
  "Batches": []
}
""");

            string payload = runPowerShellFileAndGetOutput(
                scriptPath,
                "-BaselinePath",
                baselinePath,
                "-CurrentPath",
                currentPath,
                "-OutputJson");

            using JsonDocument document = JsonDocument.Parse(payload);
            JsonElement root = document.RootElement;

            Assert.Equal("baseline", root.GetProperty("BaselineMetadata").GetProperty("Label").GetString());
            Assert.Equal("current", root.GetProperty("CurrentMetadata").GetProperty("Label").GetString());

            JsonElement comparison = root.GetProperty("Comparison");
            Assert.Equal(0, comparison.GetProperty("BatchCountDelta").GetInt32());
            Assert.Equal(-1, comparison.GetProperty("TrxDurationMissingCountDelta").GetInt32());
            Assert.Equal("Editor", comparison.GetProperty("SlowestBatchScenesBaseline").GetString());
            Assert.Equal("Playback", comparison.GetProperty("SlowestBatchScenesCurrent").GetString());

            JsonElement metrics = comparison.GetProperty("Metrics");
            JsonElement startupMean = findMetric(metrics, "StartupMeanSeconds");
            Assert.InRange(startupMean.GetProperty("Delta").GetDouble(), 1.99, 2.01);
            Assert.Equal(JsonValueKind.Null, startupMean.GetProperty("DeltaPercent").ValueKind);

            JsonElement totalMean = findMetric(metrics, "TotalMeanSeconds");
            Assert.InRange(totalMean.GetProperty("Delta").GetDouble(), 3.99, 4.01);
            Assert.InRange(totalMean.GetProperty("DeltaPercent").GetDouble(), 19.99, 20.01);
        }
        finally
        {
            try
            {
                Directory.Delete(tempRoot, recursive: true);
            }
            catch
            {
                // Best effort cleanup.
            }
        }
    }

    [Fact]
    public void RollupThresholdEvaluationPassesWhenWithinLimits()
    {
        if (!OperatingSystem.IsWindows())
            return;

        string repoRoot = TestPathResolver.ResolveRepositoryRoot();
        string helperPath = Path.Combine(repoRoot, "scripts", "visual_regression_rollup_helpers.ps1");
        Assert.True(File.Exists(helperPath), $"Expected helper script missing: {helperPath}");

        string payload = runHelperAndGetJson(
            helperPath,
            """
            $rollup = [pscustomobject]@{
              BatchCount=4
              StartupP95Seconds=72
              TotalP95Seconds=122
              TrxDurationMissingCount=1
            }
            Test-VisualTimingRollupThresholds -Rollup $rollup -MaxStartupP95Seconds 120 -MaxTotalP95Seconds 180 -MaxTrxMissingRatio 0.4
            """);

        using JsonDocument document = JsonDocument.Parse(payload);
        JsonElement root = document.RootElement;
        Assert.True(root.GetProperty("Passed").GetBoolean());
        Assert.Equal(0, root.GetProperty("FailureCount").GetInt32());
        Assert.Equal(0, root.GetProperty("Failures").GetArrayLength());
    }

    [Fact]
    public void RollupThresholdEvaluationReportsExpectedFailures()
    {
        if (!OperatingSystem.IsWindows())
            return;

        string repoRoot = TestPathResolver.ResolveRepositoryRoot();
        string helperPath = Path.Combine(repoRoot, "scripts", "visual_regression_rollup_helpers.ps1");
        Assert.True(File.Exists(helperPath), $"Expected helper script missing: {helperPath}");

        string payload = runHelperAndGetJson(
            helperPath,
            """
            $rollup = [pscustomobject]@{
              BatchCount=3
              StartupP95Seconds=190
              TotalP95Seconds=340
              TrxDurationMissingCount=2
            }
            Test-VisualTimingRollupThresholds -Rollup $rollup -MaxStartupP95Seconds 180 -MaxTotalP95Seconds 300 -MaxTrxMissingRatio 0.3
            """);

        using JsonDocument document = JsonDocument.Parse(payload);
        JsonElement root = document.RootElement;
        Assert.False(root.GetProperty("Passed").GetBoolean());
        Assert.Equal(3, root.GetProperty("FailureCount").GetInt32());
        JsonElement failures = root.GetProperty("Failures");
        Assert.Equal(3, failures.GetArrayLength());
    }

    private static string runHelperAndGetJson(string helperPath, string scriptBody)
    {
        string command = "$ErrorActionPreference='Stop'; . '" +
                         toSingleQuotedLiteral(helperPath) +
                         "'; " +
                         scriptBody +
                         " | ConvertTo-Json -Compress";

        var processStart = new ProcessStartInfo
        {
            FileName = resolvePowerShellExecutable(),
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        processStart.ArgumentList.Add("-NoProfile");
        processStart.ArgumentList.Add("-NonInteractive");
        processStart.ArgumentList.Add("-ExecutionPolicy");
        processStart.ArgumentList.Add("Bypass");
        processStart.ArgumentList.Add("-Command");
        processStart.ArgumentList.Add(command);

        using var process = Process.Start(processStart);
        Assert.NotNull(process);

        string stdout = process!.StandardOutput.ReadToEnd();
        string stderr = process.StandardError.ReadToEnd();
        process.WaitForExit();

        Assert.True(
            process.ExitCode == 0,
            $"PowerShell helper command failed with exit code {process.ExitCode}.{Environment.NewLine}STDERR:{Environment.NewLine}{stderr}{Environment.NewLine}STDOUT:{Environment.NewLine}{stdout}");

        return stdout.Trim();
    }

    private static string runPowerShellFileAndGetOutput(string scriptPath, params string[] arguments)
    {
        var processStart = new ProcessStartInfo
        {
            FileName = resolvePowerShellExecutable(),
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        processStart.ArgumentList.Add("-NoProfile");
        processStart.ArgumentList.Add("-NonInteractive");
        processStart.ArgumentList.Add("-ExecutionPolicy");
        processStart.ArgumentList.Add("Bypass");
        processStart.ArgumentList.Add("-File");
        processStart.ArgumentList.Add(scriptPath);

        foreach (string argument in arguments)
            processStart.ArgumentList.Add(argument);

        using var process = Process.Start(processStart);
        Assert.NotNull(process);

        string stdout = process!.StandardOutput.ReadToEnd();
        string stderr = process.StandardError.ReadToEnd();
        process.WaitForExit();

        Assert.True(
            process.ExitCode == 0,
            $"PowerShell script failed with exit code {process.ExitCode}.{Environment.NewLine}STDERR:{Environment.NewLine}{stderr}{Environment.NewLine}STDOUT:{Environment.NewLine}{stdout}");

        return stdout.Trim();
    }

    private static string resolvePowerShellExecutable()
    {
        if (OperatingSystem.IsWindows())
        {
            string windowsPowerShell = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.System),
                "WindowsPowerShell",
                "v1.0",
                "powershell.exe");

            if (File.Exists(windowsPowerShell))
                return windowsPowerShell;
        }

        return "pwsh";
    }

    private static string toSingleQuotedLiteral(string value)
        => value.Replace("'", "''");

    private static JsonElement findMetric(JsonElement metrics, string metricName)
    {
        foreach (JsonElement metric in metrics.EnumerateArray())
        {
            if (string.Equals(metric.GetProperty("Name").GetString(), metricName, StringComparison.Ordinal))
                return metric;
        }

        throw new InvalidOperationException($"Metric not found: {metricName}");
    }
}
