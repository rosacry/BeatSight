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
}
