using System;
using System.IO;
using System.Text.Json;
using osu.Framework.Logging;
using osu.Framework.Platform;

namespace BeatSight.Game.Calibration
{
    /// <summary>
    /// Manages persistence of microphone calibration profiles.
    /// </summary>
    public class MicCalibrationManager
    {
        private const string calibrationDirectory = "Calibration";
        private const string calibrationFilename = "mic_calibration.json";

        private readonly Storage storage;
        private readonly JsonSerializerOptions serializerOptions = new()
        {
            WriteIndented = true
        };

        public MicCalibrationManager(Storage storage)
        {
            if (storage == null)
                throw new ArgumentNullException(nameof(storage));

            this.storage = storage.GetStorageForDirectory(calibrationDirectory);
        }

        public bool HasProfile()
        {
            return storage.Exists(calibrationFilename);
        }

        public MicCalibrationProfile? Load()
        {
            try
            {
                if (!HasProfile())
                    return null;

                string path = storage.GetFullPath(calibrationFilename);
                using var stream = File.OpenRead(path);
                return JsonSerializer.Deserialize<MicCalibrationProfile>(stream, serializerOptions);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to load mic calibration profile: {ex.Message}", level: LogLevel.Error);
                return null;
            }
        }

        public void Save(MicCalibrationProfile profile)
        {
            try
            {
                string path = storage.GetFullPath(calibrationFilename);
                Directory.CreateDirectory(Path.GetDirectoryName(path)!);
                using var stream = File.Create(path);
                JsonSerializer.Serialize(stream, profile, serializerOptions);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to save mic calibration profile: {ex.Message}", level: LogLevel.Error);
            }
        }

        public void Clear()
        {
            try
            {
                if (HasProfile())
                    storage.Delete(calibrationFilename);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to clear mic calibration profile: {ex.Message}", level: LogLevel.Error);
            }
        }

        public string GetProfilePath()
        {
            return storage.GetFullPath(calibrationFilename);
        }
    }
}
