using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using osu.Framework.Platform;

namespace BeatSight.Game.Configuration
{
    public class MapPlaybackSettingsManager
    {
        private readonly Storage storage;
        private const string filename = "playback_settings.json";
        private Dictionary<string, MapPlaybackSettings> settings = new();

        public MapPlaybackSettingsManager(Storage storage)
        {
            this.storage = storage;
            load();
        }

        private void load()
        {
            if (storage.Exists(filename))
            {
                using (var stream = storage.GetStream(filename))
                using (var reader = new StreamReader(stream))
                {
                    try
                    {
                        var content = reader.ReadToEnd();
                        settings = JsonConvert.DeserializeObject<Dictionary<string, MapPlaybackSettings>>(content) ?? new();
                    }
                    catch
                    {
                        settings = new();
                    }
                }
            }
        }

        public void Save()
        {
            using (var stream = storage.GetStream(filename, FileAccess.Write, FileMode.Create))
            using (var writer = new StreamWriter(stream))
            {
                writer.Write(JsonConvert.SerializeObject(settings, Formatting.Indented));
            }
        }

        public MapPlaybackSettings Get(string beatmapId)
        {
            if (settings.TryGetValue(beatmapId, out var setting))
                return setting;

            return new MapPlaybackSettings(); // Default
        }

        public void Set(string beatmapId, MapPlaybackSettings setting)
        {
            settings[beatmapId] = setting;
            Save();
        }
    }

    public class MapPlaybackSettings
    {
        public bool AutoZoom { get; set; } = true;
    }
}
