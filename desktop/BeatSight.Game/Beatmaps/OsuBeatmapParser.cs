using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using BeatSight.Game.Mapping;

namespace BeatSight.Game.Beatmaps
{
    /// <summary>
    /// Parses osu! beatmap files (.osu format) and converts them to BeatSight beatmaps
    /// </summary>
    public static class OsuBeatmapParser
    {
        public static Beatmap ParseFromFile(string path)
        {
            if (!File.Exists(path))
                throw new FileNotFoundException($"Osu beatmap file not found: {path}");

            string[] lines = File.ReadAllLines(path);

            var beatmap = new Beatmap
            {
                Metadata = { BeatmapId = Guid.NewGuid().ToString() }
            };

            string currentSection = string.Empty;
            var hitObjects = new List<(int time, int column)>();

            for (int i = 0; i < lines.Length; i++)
            {
                string line = lines[i].Trim();

                // Skip empty lines and comments
                if (string.IsNullOrWhiteSpace(line) || line.StartsWith("//"))
                    continue;

                // Check for section headers
                if (line.StartsWith("[") && line.EndsWith("]"))
                {
                    currentSection = line.Substring(1, line.Length - 2);
                    continue;
                }

                // Parse based on current section
                switch (currentSection)
                {
                    case "General":
                        parseGeneralSection(line, beatmap);
                        break;
                    case "Metadata":
                        parseMetadataSection(line, beatmap);
                        break;
                    case "Difficulty":
                        parseDifficultySection(line, beatmap);
                        break;
                    case "TimingPoints":
                        parseTimingPoint(line, beatmap);
                        break;
                    case "HitObjects":
                        var hitObject = parseHitObject(line);
                        if (hitObject.HasValue)
                            hitObjects.Add(hitObject.Value);
                        break;
                }
            }

            // Convert hit objects to BeatSight format
            convertHitObjects(beatmap, hitObjects);

            // Set default values if missing
            if (beatmap.Timing.Bpm <= 0)
                beatmap.Timing.Bpm = 120;

            if (string.IsNullOrWhiteSpace(beatmap.Metadata.Creator))
                beatmap.Metadata.Creator = "Unknown Mapper";

            beatmap.Metadata.CreatedAt = DateTime.UtcNow;
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;

            return beatmap;
        }

        private static void parseGeneralSection(string line, Beatmap beatmap)
        {
            var parts = line.Split(new[] { ':' }, 2);
            if (parts.Length != 2) return;

            string key = parts[0].Trim();
            string value = parts[1].Trim();

            switch (key)
            {
                case "AudioFilename":
                    beatmap.Audio.Filename = value;
                    break;
                case "PreviewTime":
                    if (int.TryParse(value, out int previewTime))
                        beatmap.Metadata.PreviewTime = previewTime;
                    break;
            }
        }

        private static void parseMetadataSection(string line, Beatmap beatmap)
        {
            var parts = line.Split(new[] { ':' }, 2);
            if (parts.Length != 2) return;

            string key = parts[0].Trim();
            string value = parts[1].Trim();

            switch (key)
            {
                case "Title":
                case "TitleUnicode":
                    if (string.IsNullOrWhiteSpace(beatmap.Metadata.Title))
                        beatmap.Metadata.Title = value;
                    break;
                case "Artist":
                case "ArtistUnicode":
                    if (string.IsNullOrWhiteSpace(beatmap.Metadata.Artist))
                        beatmap.Metadata.Artist = value;
                    break;
                case "Creator":
                    beatmap.Metadata.Creator = value;
                    break;
                case "Version":
                    // Store difficulty name as a tag
                    if (!string.IsNullOrWhiteSpace(value))
                        beatmap.Metadata.Tags.Add($"Difficulty:{value}");
                    break;
                case "Source":
                    beatmap.Metadata.Source = value;
                    break;
                case "Tags":
                    var tags = value.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                    beatmap.Metadata.Tags.AddRange(tags);
                    break;
            }
        }

        private static void parseDifficultySection(string line, Beatmap beatmap)
        {
            var parts = line.Split(new[] { ':' }, 2);
            if (parts.Length != 2) return;

            string key = parts[0].Trim();
            string value = parts[1].Trim();

            switch (key)
            {
                case "OverallDifficulty":
                    if (double.TryParse(value, NumberStyles.Any, CultureInfo.InvariantCulture, out double od))
                        beatmap.Metadata.Difficulty = od;
                    break;
            }
        }

        private static void parseTimingPoint(string line, Beatmap beatmap)
        {
            // TimingPoint format: time,beatLength,meter,sampleSet,sampleIndex,volume,uninherited,effects
            var parts = line.Split(',');
            if (parts.Length < 2) return;

            if (!int.TryParse(parts[0], out int time)) return;
            if (!double.TryParse(parts[1], NumberStyles.Any, CultureInfo.InvariantCulture, out double beatLength)) return;

            // Only process uninherited (red) timing points for BPM calculation
            bool isUninherited = parts.Length >= 7 && parts[6].Trim() == "1";

            if (isUninherited && beatLength > 0)
            {
                // beatLength is milliseconds per beat, convert to BPM
                double bpm = 60000.0 / beatLength;

                // Set the first timing point as the main BPM
                if (beatmap.Timing.Bpm <= 0)
                {
                    beatmap.Timing.Bpm = Math.Round(bpm, 2);
                    beatmap.Timing.Offset = time;
                }
            }
        }

        private static (int time, int column)? parseHitObject(string line)
        {
            // HitObject format: x,y,time,type,hitSound,...
            // For mania (mode 3), x position determines the column
            var parts = line.Split(',');
            if (parts.Length < 3) return null;

            if (!int.TryParse(parts[0], out int x)) return null;
            if (!int.TryParse(parts[2], out int time)) return null;

            // Calculate column from x position (osu mania uses 512 width)
            // We'll map to 7 lanes for BeatSight
            int column = (int)((x / 512.0) * 7);
            column = Math.Clamp(column, 0, 6);

            return (time, column);
        }

        private static void convertHitObjects(Beatmap beatmap, List<(int time, int column)> hitObjects)
        {
            // Sort by time
            hitObjects.Sort((a, b) => a.time.CompareTo(b.time));

            foreach (var (time, column) in hitObjects)
            {
                // Map columns to drum components in a consistent way with gameplay lanes
                string component = mapColumnToComponent(column);
                int lane = resolveLaneForComponent(component);

                beatmap.HitObjects.Add(new HitObject
                {
                    Time = time,
                    Component = component,
                    Lane = lane,
                    Velocity = 0.8 // Default velocity
                });
            }

            // Set audio duration based on last note
            if (beatmap.HitObjects.Count > 0)
            {
                int lastNoteTime = beatmap.HitObjects[^1].Time;
                beatmap.Audio.Duration = lastNoteTime + 5000; // Add 5 seconds buffer
            }
        }

        private static string mapColumnToComponent(int column)
        {
            // Map 7 columns to drum components in a logical way that mirrors the editor lanes
            return column switch
            {
                0 => "crash",          // Far left - crash cymbal
                1 => "hihat_closed",   // Left - hi-hat (closed by default)
                2 => "snare",          // Left centre - snare drum
                3 => "kick",           // Centre - kick drum
                4 => "tom_high",       // Right centre - tom drum
                5 => "ride",           // Right - ride cymbal
                6 => "splash",         // Far right - splash / china cymbal
                _ => "snare"
            };
        }

        private static int resolveLaneForComponent(string component) => DrumLaneHeuristics.ResolveLane(component);
    }
}
