using System;
using System.IO;
using System.Runtime.InteropServices;
using osu.Framework;
using osu.Framework.Logging;
using System.Threading.Tasks;
using osu.Framework.Platform;
using BeatSight.Game;
using System.Linq;
using Microsoft.Win32.SafeHandles;

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

        public static void Main(string[] args)
        {
            bool verboseLogsRequested = true;

            foreach (string argument in args)
            {
                if (argument.Equals("--verbose-logs", StringComparison.OrdinalIgnoreCase)
                    || argument.Equals("--verbose", StringComparison.OrdinalIgnoreCase))
                {
                    verboseLogsRequested = true;
                }

                if (argument.Equals("--quiet", StringComparison.OrdinalIgnoreCase)
                    || argument.Equals("--no-verbose", StringComparison.OrdinalIgnoreCase)
                    || argument.Equals("--no-verbose-logs", StringComparison.OrdinalIgnoreCase))
                {
                    verboseLogsRequested = false;
                    break;
                }
            }

            ensureConsoleAttachment();

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

        private static void ensureConsoleAttachment()
        {
            bool attached = AttachConsole(ATTACH_PARENT_PROCESS);

            if (attached)
            {
                configureConsoleWriters();
                return;
            }

            // If stdout/stderr are already redirected (e.g. running from Mintty/Git Bash),
            // avoid allocating a second console window but make sure the writers flush.
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
                redirectStream(STD_OUTPUT_HANDLE, writer => Console.SetOut(writer));
                redirectStream(STD_ERROR_HANDLE, writer => Console.SetError(writer));

                // Fire a bootstrap log so the user can quickly confirm attachment succeeded.
                Console.WriteLine("[bootstrap] Console attached for BeatSight.Desktop diagnostics.");
            }
            catch
            {
                // If this fails we fall back to whatever defaults are available.
            }
        }

        private static void redirectStream(int stdHandle, Action<TextWriter> applyWriter)
        {
            IntPtr handle = GetStdHandle(stdHandle);

            if (handle == IntPtr.Zero || handle == INVALID_HANDLE_VALUE)
            {
                handle = CreateFile("CONOUT$", GENERIC_WRITE | GENERIC_READ, FILE_SHARE_WRITE | FILE_SHARE_READ, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);

                if (handle == IntPtr.Zero || handle == INVALID_HANDLE_VALUE)
                    return;

                SetStdHandle(stdHandle, handle);
            }

            var safeHandle = new SafeFileHandle(handle, ownsHandle: false);
            var stream = new FileStream(safeHandle, FileAccess.Write);
            var writer = new StreamWriter(stream) { AutoFlush = true };

            applyWriter(writer);
        }

        private static void configureLogging(bool includeRawFrameworkLogs)
        {
            var inputLogger = Logger.GetLogger(LoggingTarget.Input);
            inputLogger.OutputToListeners = true;

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
                : "Verbose framework logging suppressed (tablet spam hidden). Use --quiet/--no-verbose to skip framework spam.",
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
