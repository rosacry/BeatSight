using System;
using System.Collections.Generic;
using System.Linq;
using osu.Framework.Bindables;
using osuTK.Input;

namespace BeatSight.Game.Configuration
{
    /// <summary>
    /// Provides utilities for managing lane key bindings.
    /// </summary>
    public static class KeyBindingHelper
    {
        /// <summary>
        /// Default key layouts for each lane count.
        /// </summary>
        public static readonly IReadOnlyDictionary<int, Key[]> DefaultLayouts = new Dictionary<int, Key[]>
        {
            { 4, new[] { Key.D, Key.F, Key.J, Key.K } },
            { 5, new[] { Key.S, Key.D, Key.Space, Key.J, Key.K } },
            { 6, new[] { Key.S, Key.D, Key.F, Key.J, Key.K, Key.L } },
            { 7, new[] { Key.S, Key.D, Key.F, Key.Space, Key.J, Key.K, Key.L } },
            { 8, new[] { Key.A, Key.S, Key.D, Key.F, Key.J, Key.K, Key.L, Key.Semicolon } }
        };

        /// <summary>
        /// Maps lane count to the corresponding BeatSightSetting.
        /// </summary>
        public static readonly IReadOnlyDictionary<int, BeatSightSetting> LaneCountToSetting = new Dictionary<int, BeatSightSetting>
        {
            { 4, BeatSightSetting.LaneKeys4 },
            { 5, BeatSightSetting.LaneKeys5 },
            { 6, BeatSightSetting.LaneKeys6 },
            { 7, BeatSightSetting.LaneKeys7 },
            { 8, BeatSightSetting.LaneKeys8 }
        };

        /// <summary>
        /// Parses a comma-separated string of key names into an array of Keys.
        /// </summary>
        /// <param name="serialized">Comma-separated key names (e.g., "S,D,F,Space,J,K,L")</param>
        /// <returns>Array of parsed keys, or null if parsing fails.</returns>
        public static Key[]? ParseKeys(string serialized)
        {
            if (string.IsNullOrWhiteSpace(serialized))
                return null;

            var parts = serialized.Split(',', StringSplitOptions.RemoveEmptyEntries);
            var keys = new List<Key>();

            foreach (var part in parts)
            {
                if (Enum.TryParse<Key>(part.Trim(), ignoreCase: true, out var key))
                {
                    keys.Add(key);
                }
                else
                {
                    // Fallback parsing for special cases
                    key = ParseSpecialKey(part.Trim());
                    if (key != Key.Unknown)
                        keys.Add(key);
                }
            }

            return keys.Count > 0 ? keys.ToArray() : null;
        }

        /// <summary>
        /// Serializes an array of keys to a comma-separated string.
        /// </summary>
        public static string SerializeKeys(Key[] keys)
        {
            return string.Join(",", keys.Select(k => k.ToString()));
        }

        /// <summary>
        /// Gets the key binding for a specific lane count from config.
        /// </summary>
        public static Key[] GetLaneKeys(BeatSightConfigManager config, int laneCount)
        {
            if (!LaneCountToSetting.TryGetValue(laneCount, out var setting))
            {
                // Fall back to defaults for unsupported lane counts
                return GetDefaultKeys(laneCount);
            }

            var serialized = config.Get<string>(setting);
            var parsed = ParseKeys(serialized);

            if (parsed == null || parsed.Length != laneCount)
            {
                // Config invalid, return defaults
                return GetDefaultKeys(laneCount);
            }

            return parsed;
        }

        /// <summary>
        /// Sets the key binding for a specific lane count in config.
        /// </summary>
        public static void SetLaneKeys(BeatSightConfigManager config, int laneCount, Key[] keys)
        {
            if (!LaneCountToSetting.TryGetValue(laneCount, out var setting))
                return;

            if (keys.Length != laneCount)
                throw new ArgumentException($"Expected {laneCount} keys, got {keys.Length}");

            var serialized = SerializeKeys(keys);
            config.GetBindable<string>(setting).Value = serialized;
        }

        /// <summary>
        /// Gets a bindable for the key configuration string.
        /// </summary>
        public static Bindable<string> GetLaneKeysBindable(BeatSightConfigManager config, int laneCount)
        {
            if (!LaneCountToSetting.TryGetValue(laneCount, out var setting))
                return new Bindable<string>(SerializeKeys(GetDefaultKeys(laneCount)));

            return config.GetBindable<string>(setting);
        }

        /// <summary>
        /// Gets default keys for a lane count.
        /// </summary>
        public static Key[] GetDefaultKeys(int laneCount)
        {
            if (DefaultLayouts.TryGetValue(laneCount, out var keys))
                return keys;

            // For unsupported lane counts, generate from fallback order
            return GenerateFallbackKeys(laneCount);
        }

        /// <summary>
        /// Resets key bindings for a specific lane count to defaults.
        /// </summary>
        public static void ResetToDefaults(BeatSightConfigManager config, int laneCount)
        {
            var defaults = GetDefaultKeys(laneCount);
            SetLaneKeys(config, laneCount, defaults);
        }

        /// <summary>
        /// Builds a reverse lookup dictionary from key to lane index.
        /// </summary>
        public static Dictionary<Key, int> BuildKeyToLaneMap(Key[] laneKeys)
        {
            var map = new Dictionary<Key, int>();
            for (int i = 0; i < laneKeys.Length; i++)
            {
                map[laneKeys[i]] = i;
            }
            return map;
        }

        /// <summary>
        /// Gets a friendly display name for a key.
        /// </summary>
        public static string GetKeyDisplayName(Key key)
        {
            return key switch
            {
                Key.Space => "Space",
                Key.Semicolon => ";",
                Key.Quote => "'",
                Key.BracketLeft => "[",
                Key.BracketRight => "]",
                Key.BackSlash => "\\",
                Key.Slash => "/",
                Key.Period => ".",
                Key.Comma => ",",
                Key.Minus => "-",
                Key.Plus => "+",
                Key.LShift => "L-Shift",
                Key.RShift => "R-Shift",
                Key.LControl => "L-Ctrl",
                Key.RControl => "R-Ctrl",
                Key.LAlt => "L-Alt",
                Key.RAlt => "R-Alt",
                _ => key.ToString()
            };
        }

        private static Key ParseSpecialKey(string name)
        {
            return name.ToLowerInvariant() switch
            {
                ";" => Key.Semicolon,
                "'" => Key.Quote,
                "[" => Key.BracketLeft,
                "]" => Key.BracketRight,
                "\\" => Key.BackSlash,
                "/" => Key.Slash,
                "." => Key.Period,
                "," => Key.Comma,
                "-" => Key.Minus,
                "+" => Key.Plus,
                "space" => Key.Space,
                "lshift" or "l-shift" or "leftshift" => Key.LShift,
                "rshift" or "r-shift" or "rightshift" => Key.RShift,
                "lctrl" or "l-ctrl" or "leftctrl" => Key.LControl,
                "rctrl" or "r-ctrl" or "rightctrl" => Key.RControl,
                "lalt" or "l-alt" or "leftalt" => Key.LAlt,
                "ralt" or "r-alt" or "rightalt" => Key.RAlt,
                _ => Key.Unknown
            };
        }

        private static Key[] GenerateFallbackKeys(int count)
        {
            // Default key order for generating fallback layouts
            var fallbackOrder = new[]
            {
                Key.S, Key.D, Key.F, Key.Space,
                Key.J, Key.K, Key.L, Key.Semicolon,
                Key.A, Key.LControl
            };

            var keys = new Key[count];
            for (int i = 0; i < count && i < fallbackOrder.Length; i++)
            {
                keys[i] = fallbackOrder[i];
            }

            // Fill remaining with numbered keys if needed
            for (int i = fallbackOrder.Length; i < count; i++)
            {
                keys[i] = (Key)((int)Key.Number0 + (i - fallbackOrder.Length) % 10);
            }

            return keys;
        }
    }
}
