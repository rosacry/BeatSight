using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Newtonsoft.Json;
using osuTK.Graphics;

namespace BeatSight.Game.Beatmaps
{
    public enum LaneEditScope
    {
        Editor,
        Settings,
        Playback
    }

    public enum LaneEditOperation
    {
        Add,
        Remove,
        Rename,
        Recolor,
        Reorder
    }

    public static class LaneManagement
    {
        public const int MinLaneCount = 1;
        public const int MaxLaneCount = 9;

        private static readonly string[] defaultLaneNames =
        {
            "Crash",
            "HiHat",
            "Snare",
            "Kick",
            "Tom",
            "Ride",
            "China",
            "Splash",
            "Perc"
        };

        private static readonly string[] defaultLaneShortNames =
        {
            "CR",
            "HH",
            "SN",
            "K",
            "TM",
            "RD",
            "CH",
            "SP",
            "PC"
        };

        private static readonly Color4[] defaultLanePalette =
        {
            new Color4(250, 181, 66, 255),
            new Color4(242, 164, 42, 255),
            new Color4(255, 66, 86, 255),
            new Color4(117, 68, 249, 255),
            new Color4(68, 145, 255, 255),
            new Color4(245, 113, 44, 255),
            new Color4(255, 82, 178, 255),
            new Color4(92, 212, 208, 255),
            new Color4(120, 185, 255, 255)
        };

        public static IReadOnlyList<Color4> DefaultPalette => defaultLanePalette;

        public static bool IsLaneEditAllowed(LaneEditScope scope, LaneEditOperation operation)
        {
            return scope switch
            {
                LaneEditScope.Editor => true,
                LaneEditScope.Settings => operation == LaneEditOperation.Recolor || operation == LaneEditOperation.Reorder,
                LaneEditScope.Playback => operation == LaneEditOperation.Recolor || operation == LaneEditOperation.Reorder,
                _ => false
            };
        }

        public static int ResolveLaneCount(Beatmap? beatmap, int fallbackLaneCount = 7)
        {
            int fallback = Math.Clamp(fallbackLaneCount, MinLaneCount, MaxLaneCount);
            if (beatmap == null)
                return fallback;

            int fromLayout = 0;
            var lanes = beatmap.DrumKit?.LaneLayout?.Lanes;
            if (lanes != null && lanes.Count > 0)
                fromLayout = lanes.Max(l => l.Index) + 1;

            int fromHitObjects = beatmap.HitObjects
                .Where(h => h.Lane.HasValue)
                .Select(h => h.Lane!.Value)
                .DefaultIfEmpty(-1)
                .Max() + 1;

            int fromEditor = beatmap.Editor?.VisualLanes ?? 0;
            int resolved = Math.Max(fallback, Math.Max(fromLayout, Math.Max(fromHitObjects, fromEditor)));
            return Math.Clamp(resolved, MinLaneCount, MaxLaneCount);
        }

        public static List<LaneInfo> EnsureLaneLayout(Beatmap beatmap, int fallbackLaneCount = 7)
        {
            beatmap.DrumKit ??= new DrumKitInfo();
            beatmap.DrumKit.LaneLayout ??= new LaneLayoutInfo();
            beatmap.DrumKit.LaneLayout.Lanes ??= new List<LaneInfo>();

            int targetCount = ResolveLaneCount(beatmap, fallbackLaneCount);
            var existingByIndex = beatmap.DrumKit.LaneLayout.Lanes
                .GroupBy(l => l.Index)
                .ToDictionary(g => g.Key, g => g.First());

            var normalized = new List<LaneInfo>(targetCount);
            for (int index = 0; index < targetCount; index++)
            {
                LaneInfo lane = existingByIndex.TryGetValue(index, out var existing)
                    ? existing
                    : new LaneInfo();

                lane.Index = index;
                lane.Name = sanitizeName(lane.Name, index);
                lane.ShortName = sanitizeShortName(lane.ShortName, lane.Name, index);
                lane.ColorHex = normalizeColorHex(lane.ColorHex, index);
                normalized.Add(lane);
            }

            beatmap.DrumKit.LaneLayout.Lanes = normalized;
            ensureEditorVisualLaneCount(beatmap, targetCount);
            return normalized;
        }

        public static bool TryGetLaneInfo(Beatmap? beatmap, int laneIndex, out LaneInfo laneInfo)
        {
            laneInfo = null!;
            if (beatmap?.DrumKit?.LaneLayout?.Lanes == null)
                return false;

            laneInfo = beatmap.DrumKit.LaneLayout.Lanes.FirstOrDefault(l => l.Index == laneIndex)!;
            return laneInfo != null;
        }

        public static string ResolveLaneLabel(Beatmap? beatmap, int laneIndex, string fallbackLabel)
        {
            if (TryGetLaneInfo(beatmap, laneIndex, out var laneInfo))
            {
                if (!string.IsNullOrWhiteSpace(laneInfo.ShortName))
                    return laneInfo.ShortName!;

                if (!string.IsNullOrWhiteSpace(laneInfo.Name))
                    return laneInfo.Name!;
            }

            return fallbackLabel;
        }

        public static bool TryGetLaneColor(Beatmap? beatmap, int laneIndex, out Color4 color)
        {
            color = default;
            if (!TryGetLaneInfo(beatmap, laneIndex, out var laneInfo))
                return false;

            return TryParseColorHex(laneInfo.ColorHex, out color);
        }

        public static bool AddLane(Beatmap beatmap, out int addedLaneIndex)
        {
            var lanes = EnsureLaneLayout(beatmap);
            if (lanes.Count >= MaxLaneCount)
            {
                addedLaneIndex = lanes.Count - 1;
                return false;
            }

            addedLaneIndex = lanes.Count;
            lanes.Add(new LaneInfo
            {
                Index = addedLaneIndex,
                Name = sanitizeName(null, addedLaneIndex),
                ShortName = sanitizeShortName(null, null, addedLaneIndex),
                ColorHex = normalizeColorHex(null, addedLaneIndex)
            });

            beatmap.DrumKit.LaneLayout!.Lanes = lanes;
            ensureEditorVisualLaneCount(beatmap, lanes.Count);
            return true;
        }

        public static bool RemoveLane(Beatmap beatmap, int laneIndex)
        {
            var lanes = EnsureLaneLayout(beatmap);
            if (lanes.Count <= MinLaneCount || laneIndex < 0 || laneIndex >= lanes.Count)
                return false;

            lanes.RemoveAt(laneIndex);

            for (int i = 0; i < lanes.Count; i++)
                lanes[i].Index = i;

            foreach (var hit in beatmap.HitObjects)
            {
                if (!hit.Lane.HasValue)
                    continue;

                int lane = hit.Lane.Value;
                if (lane == laneIndex)
                    hit.Lane = Math.Clamp(laneIndex - 1, 0, lanes.Count - 1);
                else if (lane > laneIndex)
                    hit.Lane = lane - 1;
            }

            beatmap.DrumKit.LaneLayout!.Lanes = lanes;
            ensureEditorVisualLaneCount(beatmap, lanes.Count);
            return true;
        }

        public static bool MoveLane(Beatmap beatmap, int fromIndex, int toIndex)
        {
            var lanes = EnsureLaneLayout(beatmap);
            if (fromIndex < 0 || fromIndex >= lanes.Count || toIndex < 0 || toIndex >= lanes.Count || fromIndex == toIndex)
                return false;

            var moving = lanes[fromIndex];
            lanes.RemoveAt(fromIndex);
            lanes.Insert(toIndex, moving);

            var laneIndexMap = new Dictionary<int, int>(lanes.Count);
            for (int i = 0; i < lanes.Count; i++)
            {
                int oldIndex = lanes[i].Index;
                laneIndexMap[oldIndex] = i;
            }

            for (int i = 0; i < lanes.Count; i++)
                lanes[i].Index = i;

            foreach (var hit in beatmap.HitObjects)
            {
                if (!hit.Lane.HasValue)
                    continue;

                int lane = hit.Lane.Value;
                if (laneIndexMap.TryGetValue(lane, out int mapped))
                    hit.Lane = mapped;
            }

            beatmap.DrumKit.LaneLayout!.Lanes = lanes;
            ensureEditorVisualLaneCount(beatmap, lanes.Count);
            return true;
        }

        public static bool RenameLane(Beatmap beatmap, int laneIndex, string? name, string? shortName)
        {
            var lanes = EnsureLaneLayout(beatmap);
            if (laneIndex < 0 || laneIndex >= lanes.Count)
                return false;

            lanes[laneIndex].Name = sanitizeName(name, laneIndex);
            lanes[laneIndex].ShortName = sanitizeShortName(shortName, lanes[laneIndex].Name, laneIndex);
            beatmap.DrumKit.LaneLayout!.Lanes = lanes;
            return true;
        }

        public static bool RecolorLane(Beatmap beatmap, int laneIndex, Color4 color)
        {
            var lanes = EnsureLaneLayout(beatmap);
            if (laneIndex < 0 || laneIndex >= lanes.Count)
                return false;

            lanes[laneIndex].ColorHex = ToColorHex(color);
            beatmap.DrumKit.LaneLayout!.Lanes = lanes;
            return true;
        }

        public static List<LaneInfo> DeserializeLaneProfile(string? json, int fallbackLaneCount = 7)
        {
            try
            {
                if (!string.IsNullOrWhiteSpace(json))
                {
                    var lanes = JsonConvert.DeserializeObject<List<LaneInfo>>(json);
                    if (lanes != null && lanes.Count > 0)
                    {
                        var ordered = lanes
                            .OrderBy(l => l.Index)
                            .Select((lane, index) => new LaneInfo
                            {
                                Index = index,
                                Name = sanitizeName(lane.Name, index),
                                ShortName = sanitizeShortName(lane.ShortName, lane.Name, index),
                                ColorHex = normalizeColorHex(lane.ColorHex, index)
                            })
                            .Take(MaxLaneCount)
                            .ToList();

                        if (ordered.Count > 0)
                            return ordered;
                    }
                }
            }
            catch
            {
                // Fall through to defaults.
            }

            int count = Math.Clamp(fallbackLaneCount, MinLaneCount, MaxLaneCount);
            var fallback = new List<LaneInfo>(count);
            for (int i = 0; i < count; i++)
            {
                fallback.Add(new LaneInfo
                {
                    Index = i,
                    Name = sanitizeName(null, i),
                    ShortName = sanitizeShortName(null, null, i),
                    ColorHex = normalizeColorHex(null, i)
                });
            }

            return fallback;
        }

        public static string SerializeLaneProfile(IEnumerable<LaneInfo> lanes)
        {
            var normalized = lanes
                .OrderBy(l => l.Index)
                .Select((lane, index) => new LaneInfo
                {
                    Index = index,
                    Name = sanitizeName(lane.Name, index),
                    ShortName = sanitizeShortName(lane.ShortName, lane.Name, index),
                    ColorHex = normalizeColorHex(lane.ColorHex, index)
                })
                .Take(MaxLaneCount)
                .ToList();

            return JsonConvert.SerializeObject(normalized);
        }

        public static bool TryParseColorHex(string? value, out Color4 color)
        {
            color = default;
            if (string.IsNullOrWhiteSpace(value))
                return false;

            string hex = value.Trim();
            if (hex.StartsWith("#", StringComparison.Ordinal))
                hex = hex[1..];

            if (hex.Length != 6 && hex.Length != 8)
                return false;

            if (!byte.TryParse(hex[..2], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out byte r)
                || !byte.TryParse(hex[2..4], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out byte g)
                || !byte.TryParse(hex[4..6], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out byte b))
            {
                return false;
            }

            byte a = 255;
            if (hex.Length == 8
                && !byte.TryParse(hex[6..8], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out a))
            {
                return false;
            }

            color = new Color4(r, g, b, a);
            return true;
        }

        public static string ToColorHex(Color4 color)
        {
            byte r = (byte)Math.Round(Math.Clamp(color.R, 0f, 1f) * 255f);
            byte g = (byte)Math.Round(Math.Clamp(color.G, 0f, 1f) * 255f);
            byte b = (byte)Math.Round(Math.Clamp(color.B, 0f, 1f) * 255f);
            return $"#{r:X2}{g:X2}{b:X2}";
        }

        private static string sanitizeName(string? value, int laneIndex)
        {
            string trimmed = value?.Trim() ?? string.Empty;
            if (!string.IsNullOrWhiteSpace(trimmed))
                return trimmed;

            return laneIndex >= 0 && laneIndex < defaultLaneNames.Length
                ? defaultLaneNames[laneIndex]
                : $"Lane {laneIndex + 1}";
        }

        private static string sanitizeShortName(string? value, string? name, int laneIndex)
        {
            string trimmed = value?.Trim() ?? string.Empty;
            if (!string.IsNullOrWhiteSpace(trimmed))
                return trimmed.Length <= 6 ? trimmed : trimmed[..6];

            if (laneIndex >= 0 && laneIndex < defaultLaneShortNames.Length)
                return defaultLaneShortNames[laneIndex];

            string source = string.IsNullOrWhiteSpace(name) ? $"L{laneIndex + 1}" : name.Trim();
            if (source.Length <= 6)
                return source;

            return source[..6];
        }

        private static string normalizeColorHex(string? value, int laneIndex)
        {
            if (TryParseColorHex(value, out var color))
                return ToColorHex(color);

            var fallback = defaultLanePalette[Math.Abs(laneIndex) % defaultLanePalette.Length];
            return ToColorHex(fallback);
        }

        private static void ensureEditorVisualLaneCount(Beatmap beatmap, int laneCount)
        {
            beatmap.Editor ??= new EditorInfo();
            beatmap.Editor.VisualLanes = Math.Clamp(laneCount, MinLaneCount, MaxLaneCount);
        }
    }
}
