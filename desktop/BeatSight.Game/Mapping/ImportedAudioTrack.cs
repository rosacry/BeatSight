using System;
using System.Globalization;
using System.IO;

namespace BeatSight.Game.Mapping
{
    /// <summary>
    /// Represents an audio asset that has been imported into BeatSight for mapping.
    /// </summary>
    public class ImportedAudioTrack
    {
        public ImportedAudioTrack(string originalPath, string storedPath, string relativeStoragePath, string displayName, long fileSizeBytes, double? durationMilliseconds)
        {
            OriginalPath = originalPath;
            StoredPath = storedPath;
            RelativeStoragePath = relativeStoragePath;
            DisplayName = displayName;
            FileSizeBytes = fileSizeBytes;
            DurationMilliseconds = durationMilliseconds;
            ImportedAt = DateTime.UtcNow;
        }

        public string OriginalPath { get; }
        public string StoredPath { get; }
        public string RelativeStoragePath { get; }
        public string DisplayName { get; }
        public long FileSizeBytes { get; }
        public double? DurationMilliseconds { get; }
        public DateTime ImportedAt { get; }

        public string FormatDuration()
        {
            if (!DurationMilliseconds.HasValue)
                return "Unknown";

            var span = TimeSpan.FromMilliseconds(DurationMilliseconds.Value);
            return span.TotalHours >= 1
                ? span.ToString("hh\\:mm\\:ss", CultureInfo.InvariantCulture)
                : span.ToString("mm\\:ss", CultureInfo.InvariantCulture);
        }

        public string FormatFileSize()
        {
            double size = FileSizeBytes;
            string[] units = { "B", "KB", "MB", "GB" };
            int unitIndex = 0;

            while (size >= 1024 && unitIndex < units.Length - 1)
            {
                size /= 1024;
                unitIndex++;
            }

            return $"{size:0.##} {units[unitIndex]}";
        }

        public override string ToString() => $"{DisplayName} ({FormatDuration()}, {FormatFileSize()})";

        public static string CreateSafeFileName(string originalPath)
        {
            string sanitizedBase = Path.GetFileNameWithoutExtension(originalPath);
            if (string.IsNullOrWhiteSpace(sanitizedBase))
                sanitizedBase = "import";

            foreach (char c in Path.GetInvalidFileNameChars())
                sanitizedBase = sanitizedBase.Replace(c, '_');

            string extension = Path.GetExtension(originalPath);
            string timestamp = DateTime.UtcNow.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture);

            return $"{sanitizedBase}_{timestamp}{extension}";
        }
    }
}
