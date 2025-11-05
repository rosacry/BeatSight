using System;
using System.IO;
using osu.Framework;
using osu.Framework.Logging;
using osu.Framework.Platform;
using BeatSight.Game;

namespace BeatSight.Desktop
{
    public static class Program
    {
        public static void Main(string[] args)
        {
            // Set minimum log level to Debug to skip verbose tablet detection logs
            Logger.Level = LogLevel.Debug;

            suppressTabletDetectionLogs();

            using GameHost host = Host.GetSuitableDesktopHost("BeatSight");
            ensureCookieFile(host);
            using osu.Framework.Game game = new BeatSightGame();
            host.Run(game);
        }

        private static void suppressTabletDetectionLogs()
        {
            var inputLogger = Logger.GetLogger(LoggingTarget.Input);
            inputLogger.OutputToListeners = false;

            Logger.NewEntry += entry =>
            {
                bool isInputLog = entry.Target == LoggingTarget.Input ||
                                   (entry.Target == null && string.Equals(entry.LoggerName, "input", StringComparison.OrdinalIgnoreCase));

                if (!isInputLog)
                    return;

                if (!string.IsNullOrEmpty(entry.Message) && entry.Message.Contains("[Tablet]", StringComparison.OrdinalIgnoreCase))
                    return;

                // Re-emit input logs except tablet detection so other diagnostics remain visible.
                var level = entry.Level.ToString().ToLowerInvariant();
                var timestamp = DateTime.UtcNow.ToString("yyyy-MM-dd HH:mm:ss");
                var message = (entry.Message ?? string.Empty).Replace("\r\n", "\n");

                foreach (var line in message.Split('\n'))
                {
                    var trimmed = line.Trim();
                    if (trimmed.Length == 0)
                        continue;

                    Console.WriteLine($"[input] {timestamp} [{level}]: {trimmed}");
                }

                if (entry.Exception != null)
                {
                    var exceptionText = entry.Exception.ToString().Replace("\r\n", "\n");
                    foreach (var line in exceptionText.Split('\n'))
                    {
                        var trimmed = line.Trim();
                        if (trimmed.Length == 0)
                            continue;

                        Console.WriteLine($"[input] {timestamp} [{level}]: {trimmed}");
                    }
                }
            };
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
    }
}
