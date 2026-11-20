// Thin adapter over a separately pinned YARG.Core checkout. Never edits charts.
// Times exclude song.ini delay and .chart Offset; the Python importer records
// and applies those explicitly. Pro Drums is selected even without an ini hint.
using System.Text.Json;
using YARG.Core;
using YARG.Core.Chart;

if (args.Length != 1) throw new ArgumentException("Expected an explicit notes.mid or notes.chart path");
string path = Path.GetFullPath(args[0]);
string ext = Path.GetExtension(path).ToLowerInvariant();
if (ext is not (".mid" or ".chart")) throw new ArgumentException("Unsupported chart extension");
var settings = ext == ".mid" ? ParseSettings.Default_Midi : ParseSettings.Default_Chart;
settings.DrumsType = DrumsType.FourLane; // Caller must reject five-lane sources.
var chart = SongChart.FromFile(settings, path);
var tracks = new List<object>();
foreach (var difficulty in new[] { Difficulty.Expert, Difficulty.ExpertPlus })
{
    if (!chart.ProDrums.TryGetDifficulty(difficulty, out var part) || part.Notes.Count == 0) continue;
    var notes = part.Notes.SelectMany(n => new[] { n }.Concat(n.ChildNotes)).Select(n => new
    {
        tick = n.Tick, time_seconds = n.Time,
        pad = ((FourLaneDrumPad)n.Pad).ToString(),
        double_kick = n.IsDoubleKick, dynamics = n.Type.ToString(),
        flags = n.Flags.ToString(), drum_flags = n.DrumFlags.ToString()
    }).OrderBy(n => n.tick).ThenBy(n => n.pad).ToArray();
    tracks.Add(new { difficulty = difficulty.ToString(), notes });
}
if (tracks.Count == 0) throw new InvalidDataException("No Expert Pro Drums notes");
Console.WriteLine(JsonSerializer.Serialize(new
{
    format = ext, resolution = chart.Resolution,
    tempos = chart.SyncTrack.Tempos.Select(t => new { tick = t.Tick, time_seconds = t.Time, bpm = t.BeatsPerMinute }),
    time_signatures = chart.SyncTrack.TimeSignatures.Select(t => new { tick = t.Tick, numerator = t.Numerator, denominator = t.Denominator }),
    sections = chart.Sections.Select(s => new { tick = s.Tick, time_seconds = s.Time, name = s.Name }),
    tracks
}, new JsonSerializerOptions { WriteIndented = true }));
