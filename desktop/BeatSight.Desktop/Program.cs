using System;
using System.IO;
using System.Runtime.InteropServices;
using osu.Framework;
using osu.Framework.Logging;
using System.Threading.Tasks;
using osu.Framework.Platform;
using BeatSight.Game;
using System.Linq;

namespace BeatSight.Desktop
{
    public static class Program
    {
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AttachConsole(int dwProcessId);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AllocConsole();

        private const int ATTACH_PARENT_PROCESS = -1;

        public static void Main(string[] args)
        {
            bool verboseLogsRequested = args.Any(a =>
                a.Equals("--verbose-logs", StringComparison.OrdinalIgnoreCase)
                || a.Equals("--verbose", StringComparison.OrdinalIgnoreCase));

            // Try to attach to parent console (for terminal output)
            if (!AttachConsole(ATTACH_PARENT_PROCESS))
            {
                // If no parent console, allocate a new one
                AllocConsole();
            }

            // Default to debug-level logging unless verbose logs are explicitly requested.
            Logger.Level = verboseLogsRequested ? LogLevel.Verbose : LogLevel.Debug;

            initialiseGlobalDiagnostics();
            configureLogging(verboseLogsRequested);

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

        private static void configureLogging(bool includeRawFrameworkLogs)
        {
            var inputLogger = Logger.GetLogger(LoggingTarget.Input);
            inputLogger.OutputToListeners = false;

            foreach (LoggingTarget target in Enum.GetValues(typeof(LoggingTarget)))
            {
                try
                {
                    Logger.GetLogger(target).OutputToListeners = false;
                }
                catch
                {
                    // Some logging targets may not be initialised yet; ignore failures.
                }
            }

            Logger.NewEntry += entry =>
            {
                if (!includeRawFrameworkLogs)
                {
                    bool isInputLog = entry.Target == LoggingTarget.Input ||
                                       (entry.Target == null && string.Equals(entry.LoggerName, "input", StringComparison.OrdinalIgnoreCase));

                    if (isInputLog)
                    {
                        var message = entry.Message?.ToString();
                        if (!string.IsNullOrEmpty(message) && message.Contains("[Tablet]", StringComparison.OrdinalIgnoreCase))
                            return;
                    }
                }

                forwardLogToConsole(entry);
            };

            Logger.Log(includeRawFrameworkLogs
                ? "Verbose framework logging enabled."
                : "Verbose framework logging suppressed (tablet spam hidden).",
                LoggingTarget.Runtime,
                LogLevel.Important);
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

                Console.WriteLine();
                Console.WriteLine("========================================");
                Console.WriteLine("BeatSight encountered a fatal error.");
                Console.WriteLine($"Details written to: {logPath}");
                Console.WriteLine(exception);
                Console.WriteLine("========================================");
                Console.WriteLine();
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

                    Console.WriteLine($"[{channel}] {timestamp} [{level}]: {trimmed}");
                }
            }

            if (entry.Exception != null)
            {
                foreach (var line in entry.Exception.ToString().Replace("\r\n", "\n").Split('\n'))
                {
                    var trimmed = line.Trim();
                    if (trimmed.Length == 0)
                        continue;

                    Console.WriteLine($"[{channel}] {timestamp} [{level}]: {trimmed}");
                }
            }
        }
    }
}
