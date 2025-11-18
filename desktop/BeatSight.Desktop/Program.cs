using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using BeatSight.Game;
using Microsoft.Win32.SafeHandles;
using osu.Framework;
using osu.Framework.Logging;
using osu.Framework.Platform;

namespace BeatSight.Desktop
{
    public static class Program
    {
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AttachConsole(int dwProcessId);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AllocConsole();

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateFile(
            string lpFileName,
            uint dwDesiredAccess,
            uint dwShareMode,
            IntPtr lpSecurityAttributes,
            uint dwCreationDisposition,
            uint dwFlagsAndAttributes,
            IntPtr hTemplateFile);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetStdHandle(int nStdHandle, IntPtr hHandle);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr GetStdHandle(int nStdHandle);

        private const int ATTACH_PARENT_PROCESS = -1;
        private const int STD_OUTPUT_HANDLE = -11;
        private const int STD_ERROR_HANDLE = -12;

        private const uint GENERIC_READ = 0x80000000;
        private const uint GENERIC_WRITE = 0x40000000;
        private const uint FILE_SHARE_READ = 0x00000001;
        private const uint FILE_SHARE_WRITE = 0x00000002;
        private const uint OPEN_EXISTING = 3;
        private static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);

        private static TextWriter? attachedStdOutWriter;
        private static TextWriter? attachedStdErrWriter;

        public static void Main(string[] args)
        {
            ensureConsoleAttachment();
            disableFrameworkConsoleEcho();

            var loggingOptions = resolveLoggingOptions(args);

            Logger.Level = loggingOptions.MinimumLevel;

            initialiseGlobalDiagnostics();
            configureLogging(loggingOptions);

            using GameHost host = Host.GetSuitableDesktopHost("BeatSight");
            ensureCookieFile(host);

            using osu.Framework.Game game = new BeatSightGame();

            try
            {
                host.Run(game);
            }
            catch (Exception ex)
            {
                logFatalException(ex);
                throw;
            }
        }

        private static LoggingOptions resolveLoggingOptions(string[] args)
        {
            LogLevel minimumLevel = osu.Framework.Development.DebugUtils.IsDebugBuild ? LogLevel.Debug : LogLevel.Important;
            bool forwardFrameworkNoise = false;
            bool forwardTabletLogs = false;

            for (int i = 0; i < args.Length; i++)
            {
                string argument = args[i];

                if (argument.Equals("--quiet", StringComparison.OrdinalIgnoreCase)
                    || argument.Equals("--no-verbose", StringComparison.OrdinalIgnoreCase)
                    || argument.Equals("--no-verbose-logs", StringComparison.OrdinalIgnoreCase))
                {
                    minimumLevel = LogLevel.Important;
                    forwardFrameworkNoise = false;
                    continue;
                }

                if (argument.Equals("--verbose", StringComparison.OrdinalIgnoreCase)
                    || argument.Equals("--verbose-logs", StringComparison.OrdinalIgnoreCase))
                {
                    minimumLevel = LogLevel.Verbose;
                    forwardFrameworkNoise = true;
                    forwardTabletLogs = true;
                    continue;
                }

                if (argument.Equals("--raw-framework-logs", StringComparison.OrdinalIgnoreCase))
                {
                    forwardFrameworkNoise = true;
                    forwardTabletLogs = true;
                    continue;
                }

                if (argument.Equals("--include-tablet-logs", StringComparison.OrdinalIgnoreCase))
                {
                    forwardTabletLogs = true;
                    continue;
                }

                if (argument.Equals("--suppress-tablet-logs", StringComparison.OrdinalIgnoreCase)
                    || argument.Equals("--no-tablet-logs", StringComparison.OrdinalIgnoreCase))
                {
                    forwardTabletLogs = false;
                    continue;
                }

                if (argument.Equals("--log-level", StringComparison.OrdinalIgnoreCase))
                {
                    if (i + 1 >= args.Length)
                    {
                        writeConsoleLine("WARNING: --log-level expects a value (e.g. --log-level debug). Keeping previous level.", true);
                        continue;
                    }

                    argument = $"--log-level={args[++i]}";
                }

                if (argument.StartsWith("--log-level=", StringComparison.OrdinalIgnoreCase))
                {
                    string candidate = argument.Substring(argument.IndexOf('=') + 1);
                    if (!tryParseLogLevel(candidate, out var parsed))
                    {
                        writeConsoleLine($"WARNING: Unknown log level '{candidate}'. Valid values: {string.Join(", ", Enum.GetNames(typeof(LogLevel)))}", true);
                        continue;
                    }

                    minimumLevel = parsed;

                    if (parsed == LogLevel.Verbose)
                    {
                        forwardFrameworkNoise = true;
                        forwardTabletLogs = true;
                    }

                    continue;
                }
            }

            return new LoggingOptions(minimumLevel, forwardFrameworkNoise, forwardTabletLogs);
        }

        private static void initialiseGlobalDiagnostics()
        {
            AppDomain.CurrentDomain.UnhandledException += (_, e) =>
            {
                if (e.ExceptionObject is Exception ex)
                    logFatalException(ex);
                else
                    logFatalException(new Exception($"Unhandled exception: {e.ExceptionObject}"));
            };

            TaskScheduler.UnobservedTaskException += (_, e) =>
            {
                logFatalException(e.Exception);
                e.SetObserved();
            };
        }

        private static void ensureConsoleAttachment()
        {
            bool attached = AttachConsole(ATTACH_PARENT_PROCESS);

            if (attached)
            {
                configureConsoleWriters();
                return;
            }

            if (Console.IsOutputRedirected || Console.IsErrorRedirected)
            {
                configureConsoleWriters();
                return;
            }

            if (AllocConsole())
                configureConsoleWriters();
        }

        private static void configureConsoleWriters()
        {
            try
            {
                attachedStdOutWriter = redirectStream(STD_OUTPUT_HANDLE);
                attachedStdErrWriter = redirectStream(STD_ERROR_HANDLE);

                if (attachedStdOutWriter != null)
                    Console.SetOut(attachedStdOutWriter);
                if (attachedStdErrWriter != null)
                    Console.SetError(attachedStdErrWriter);

                writeConsoleLine("[bootstrap] Console attached for BeatSight.Desktop diagnostics.");

                Console.SetOut(TextWriter.Null);
                Console.SetError(TextWriter.Null);
            }
            catch
            {
                // If this fails we fall back to whatever defaults are available.
            }
        }

        private static void disableFrameworkConsoleEcho()
        {
            try
            {
                var field = typeof(osu.Framework.Development.DebugUtils).GetField("is_debug_build", BindingFlags.NonPublic | BindingFlags.Static);

                if (field == null)
                    return;

                var forcedFalse = new Lazy<bool>(() => false);
                field.SetValue(null, forcedFalse);
            }
            catch
            {
                // If reflection fails, fall back to the framework's default behaviour.
            }
        }

        private static TextWriter? redirectStream(int stdHandle)
        {
            IntPtr handle = GetStdHandle(stdHandle);

            if (handle == IntPtr.Zero || handle == INVALID_HANDLE_VALUE)
            {
                handle = CreateFile("CONOUT$", GENERIC_WRITE | GENERIC_READ, FILE_SHARE_WRITE | FILE_SHARE_READ, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);

                if (handle == IntPtr.Zero || handle == INVALID_HANDLE_VALUE)
                    return null;

                SetStdHandle(stdHandle, handle);
            }

            var safeHandle = new SafeFileHandle(handle, ownsHandle: false);
            var stream = new FileStream(safeHandle, FileAccess.Write);
            return new StreamWriter(stream) { AutoFlush = true };
        }

        private static void configureLogging(LoggingOptions options)
        {
            foreach (LoggingTarget target in Enum.GetValues(typeof(LoggingTarget)))
            {
                try
                {
                    Logger.GetLogger(target).OutputToListeners = true;
                }
                catch
                {
                    // Some logging targets may not be initialised yet; ignore failures.
                }
            }

            var throttler = options.ForwardFrameworkNoise ? null : LogMessageThrottler.CreateDefault();

            Logger.NewEntry += entry =>
            {
                if (entry == null)
                    return;

                if (!options.ForwardFrameworkNoise && shouldFilterFrameworkNoise(entry, options))
                    return;

                LogThrottleSummary? summary = null;

                if (throttler != null && !throttler.ShouldForward(entry, out summary))
                    return;

                if (summary.HasValue)
                    emitSuppressionSummary(entry, summary.Value);

                forwardLogToConsole(entry);
            };

            Logger.Log(buildLoggingBanner(options), LoggingTarget.Runtime, LogLevel.Important);
        }

        private static string buildLoggingBanner(LoggingOptions options)
        {
            string levelText = options.MinimumLevel.ToString();
            string frameworkStatus = options.ForwardFrameworkNoise
                ? "Raw framework noise enabled; expect renderer/input spam."
                : "Framework noise filtered; pass --raw-framework-logs to inspect renderer spam.";
            string tabletStatus = options.ForwardFrameworkNoise || options.ForwardTabletLogs
                ? "Tablet input logs forwarded."
                : "Tablet input spam filtered (use --include-tablet-logs to inspect).";

            return $"Logging initialised at level {levelText}. {frameworkStatus} {tabletStatus} Override via --log-level=<level>.";
        }

        private static bool shouldFilterFrameworkNoise(LogEntry entry, LoggingOptions options)
        {
            if (!options.ForwardTabletLogs && isTabletLog(entry))
                return true;

            return false;
        }

        private static bool isTabletLog(LogEntry entry)
        {
            bool isInputLog = entry.Target == LoggingTarget.Input
                               || (entry.Target == null && string.Equals(entry.LoggerName, "input", StringComparison.OrdinalIgnoreCase));

            if (!isInputLog)
                return false;

            var message = entry.Message?.ToString();
            return !string.IsNullOrEmpty(message) && message.Contains("[Tablet]", StringComparison.OrdinalIgnoreCase);
        }

        private static void emitSuppressionSummary(LogEntry entry, LogThrottleSummary summary)
        {
            string channel = entry.Target?.ToString() ?? entry.LoggerName ?? "log";
            string level = LogLevel.Debug.ToString().ToLowerInvariant();
            string timestamp = DateTime.UtcNow.ToString("yyyy-MM-dd HH:mm:ss");
            double durationSeconds = summary.DurationSeconds;
            string message = $"Suppressed {summary.SuppressedCount} '{summary.RuleName}' logs over {durationSeconds:0.###}s.";

            writeConsoleLine($"[{channel}] {timestamp} [{level}]: {message}");
        }

        private static bool tryParseLogLevel(string? candidate, out LogLevel level)
        {
            level = LogLevel.Debug;

            if (string.IsNullOrWhiteSpace(candidate))
                return false;

            candidate = candidate.Trim();

            if (candidate.Equals("trace", StringComparison.OrdinalIgnoreCase)
                || candidate.Equals("info", StringComparison.OrdinalIgnoreCase)
                || candidate.Equals("information", StringComparison.OrdinalIgnoreCase))
            {
                level = LogLevel.Verbose;
                return true;
            }

            if (candidate.Equals("warn", StringComparison.OrdinalIgnoreCase)
                || candidate.Equals("warning", StringComparison.OrdinalIgnoreCase))
            {
                level = LogLevel.Important;
                return true;
            }

            if (candidate.Equals("fatal", StringComparison.OrdinalIgnoreCase)
                || candidate.Equals("critical", StringComparison.OrdinalIgnoreCase))
            {
                level = LogLevel.Error;
                return true;
            }

            return Enum.TryParse(candidate, true, out level);
        }

        private static void ensureCookieFile(GameHost host)
        {
            try
            {
                const string cookieFileName = "cookie";

                createCookieIfMissing(host.Storage, cookieFileName);

                if (host.Storage is NativeStorage native)
                {
                    var frameworkStorage = native.GetStorageForDirectory("framework");
                    createCookieIfMissing(frameworkStorage, cookieFileName);
                }
            }
            catch
            {
                // Non-fatal; the framework will emit warnings if creation fails.
            }
        }

        private static void createCookieIfMissing(Storage storage, string cookieFileName)
        {
            using var stream = storage.GetStream(cookieFileName, FileAccess.ReadWrite, FileMode.OpenOrCreate);

            if (stream.Length > 0)
                return;

            using var writer = new StreamWriter(stream);
            writer.WriteLine("# BeatSight cookie store");
        }

        private static void logFatalException(Exception exception)
        {
            try
            {
                string logPath = Path.Combine(AppContext.BaseDirectory, "BeatSight-crash.log");
                using (var writer = new StreamWriter(logPath, append: true))
                {
                    writer.WriteLine("============================================================");
                    writer.WriteLine($"Timestamp: {DateTime.UtcNow:O}");
                    writer.WriteLine("Fatal crash captured by BeatSight.Desktop");
                    writer.WriteLine(exception);
                    writer.WriteLine();
                }

                writeConsoleLine(string.Empty, true);
                writeConsoleLine("========================================", true);
                writeConsoleLine("BeatSight encountered a fatal error.", true);
                writeConsoleLine($"Details written to: {logPath}", true);
                writeConsoleLine(exception.ToString(), true);
                writeConsoleLine("========================================", true);
                writeConsoleLine(string.Empty, true);
            }
            catch
            {
                // If logging fails we still rethrow the original exception.
            }
        }

        private static void forwardLogToConsole(LogEntry entry)
        {
            if (entry == null)
                return;

            string channel = entry.Target?.ToString() ?? entry.LoggerName ?? "log";
            string level = entry.Level.ToString().ToLowerInvariant();
            string timestamp = DateTime.UtcNow.ToString("yyyy-MM-dd HH:mm:ss");

            var message = entry.Message?.ToString();
            if (!string.IsNullOrEmpty(message))
            {
                foreach (var line in message.Replace("\r\n", "\n").Split('\n'))
                {
                    var trimmed = line.Trim();
                    if (trimmed.Length == 0)
                        continue;

                    writeConsoleLine($"[{channel}] {timestamp} [{level}]: {trimmed}", entry.Level >= LogLevel.Error);
                }
            }

            if (entry.Exception != null)
            {
                foreach (var line in entry.Exception.ToString().Replace("\r\n", "\n").Split('\n'))
                {
                    var trimmed = line.Trim();
                    if (trimmed.Length == 0)
                        continue;

                    writeConsoleLine($"[{channel}] {timestamp} [{level}]: {trimmed}", true);
                }
            }
        }

        private static void writeConsoleLine(string message, bool isError = false)
        {
            var targetWriter = isError ? attachedStdErrWriter ?? attachedStdOutWriter : attachedStdOutWriter ?? attachedStdErrWriter;

            if (targetWriter != null)
            {
                targetWriter.WriteLine(message);
                return;
            }

            if (isError)
                Console.Error.WriteLine(message);
            else
                Console.Out.WriteLine(message);
        }

        private readonly record struct LoggingOptions(LogLevel MinimumLevel, bool ForwardFrameworkNoise, bool ForwardTabletLogs);

        private sealed class LogMessageThrottler
        {
            private readonly IReadOnlyList<LogThrottleRule> rules;
            private readonly Dictionary<string, ThrottleState> states = new Dictionary<string, ThrottleState>();

            private LogMessageThrottler(IReadOnlyList<LogThrottleRule> rules)
            {
                this.rules = rules;
            }

            public static LogMessageThrottler CreateDefault() => new LogMessageThrottler(new[]
            {
                new LogThrottleRule(
                    "texture-upload-queue",
                    new Regex("Texture.+upload queue is large", RegexOptions.Compiled | RegexOptions.CultureInvariant | RegexOptions.IgnoreCase),
                    LogLevel.Verbose,
                    TimeSpan.FromSeconds(1))
            });

            public bool ShouldForward(LogEntry entry, out LogThrottleSummary? summary)
            {
                summary = null;

                string? message = entry.Message?.ToString();
                if (string.IsNullOrEmpty(message))
                    return true;

                foreach (var rule in rules)
                {
                    if (entry.Level < rule.MinimumLevel)
                        continue;

                    if (!rule.Pattern.IsMatch(message))
                        continue;

                    var now = DateTime.UtcNow;

                    lock (states)
                    {
                        if (!states.TryGetValue(rule.Name, out var current))
                            current = new ThrottleState();

                        if (current.LastEmissionUtc != default && now - current.LastEmissionUtc < rule.RestPeriod)
                        {
                            current.SuppressedCount++;

                            if (current.SuppressedCount == 1)
                                current.FirstSuppressedUtc = now;

                            current.LastSuppressedUtc = now;
                            states[rule.Name] = current;
                            return false;
                        }

                        if (current.SuppressedCount > 0 && current.FirstSuppressedUtc != default)
                            summary = new LogThrottleSummary(rule.Name, current.SuppressedCount, current.FirstSuppressedUtc, current.LastSuppressedUtc);

                        current.LastEmissionUtc = now;
                        current.SuppressedCount = 0;
                        current.FirstSuppressedUtc = default;
                        current.LastSuppressedUtc = default;
                        states[rule.Name] = current;
                    }

                    return true;
                }

                return true;
            }
        }

        private readonly record struct LogThrottleRule(string Name, Regex Pattern, LogLevel MinimumLevel, TimeSpan RestPeriod);

        private readonly record struct LogThrottleSummary(string RuleName, int SuppressedCount, DateTime FirstSuppressedUtc, DateTime LastSuppressedUtc)
        {
            public double DurationSeconds => FirstSuppressedUtc == default || LastSuppressedUtc == default
                ? 0
                : Math.Max(0, (LastSuppressedUtc - FirstSuppressedUtc).TotalSeconds);
        }

        private struct ThrottleState
        {
            public DateTime LastEmissionUtc;
            public int SuppressedCount;
            public DateTime FirstSuppressedUtc;
            public DateTime LastSuppressedUtc;
        }
    }
}
