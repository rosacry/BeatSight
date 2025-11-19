using System;
using System.Collections.Generic;

namespace BeatSight.Game.Beatmaps
{
    /// <summary>
    /// Represents a BeatSight beatmap (.bsm file)
    /// </summary>
    public class Beatmap
    {
        public string Version { get; set; } = "1.0.0";
        public BeatmapMetadata Metadata { get; set; } = new();
        public AudioInfo Audio { get; set; } = new();
        public TimingInfo Timing { get; set; } = new();
        public DrumKitInfo DrumKit { get; set; } = new();
        public List<HitObject> HitObjects { get; set; } = new();
        public EditorInfo? Editor { get; set; }
    }

    public class BeatmapMetadata
    {
        public string Title { get; set; } = "";
        public string Artist { get; set; } = "";
        public string Creator { get; set; } = "";
        public string? Source { get; set; }
        public List<string> Tags { get; set; } = new();
        public double Difficulty { get; set; }
        public int? PreviewTime { get; set; }
        public string BeatmapId { get; set; } = Guid.NewGuid().ToString();
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        public DateTime ModifiedAt { get; set; } = DateTime.UtcNow;
        public string? Description { get; set; }
        public string? BackgroundFile { get; set; }
    }

    public class AudioInfo
    {
        public string Filename { get; set; } = "";
        public string Hash { get; set; } = "";
        public int Duration { get; set; }
        public int SampleRate { get; set; } = 44100;
        public string? DrumStem { get; set; }
        public string? DrumStemHash { get; set; }
    }

    public class TimingInfo
    {
        public double Bpm { get; set; } = 120.0;
        public int Offset { get; set; } = 0;
        public string TimeSignature { get; set; } = "4/4";
        public List<TimingPoint>? TimingPoints { get; set; }
    }

    public class TimingPoint
    {
        public int Time { get; set; }
        public double Bpm { get; set; }
        public string? TimeSignature { get; set; }
    }

    public class DrumKitInfo
    {
        public List<string> Components { get; set; } = new();
        public string? Layout { get; set; }
        public Dictionary<string, string>? CustomSamples { get; set; }
    }

    public class HitObject
    {
        public int Time { get; set; }
        public string Component { get; set; } = "";
        public double Velocity { get; set; } = 0.8;
        public int? Lane { get; set; }
        public int? Duration { get; set; }
    }

    public class EditorInfo
    {
        public int? SnapDivisor { get; set; }
        public int? VisualLanes { get; set; }
        public List<int>? Bookmarks { get; set; }
        public AIGenerationMetadata? AiGenerationMetadata { get; set; }
        public double? TimelineZoom { get; set; }
        public double? WaveformScale { get; set; }
        public bool? BeatGridVisible { get; set; }
    }

    public class AIGenerationMetadata
    {
        public string? ModelVersion { get; set; }
        public double? Confidence { get; set; }
        public DateTime? ProcessedAt { get; set; }
        public bool? ManualEdits { get; set; }
        public string? MetadataProvider { get; set; }
        public double? MetadataConfidence { get; set; }
    }
}
