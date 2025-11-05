using System;
using System.Linq;
using BeatSight.Game.Beatmaps;

if (args.Length == 0)
{
    Console.WriteLine("Usage: TempInspector <beatmap.osu>");
    return;
}

string path = args[0];

try
{
    var beatmap = BeatmapLoader.LoadFromFile(path);
    Console.WriteLine($"Loaded {path}");
    Console.WriteLine($"HitObjects: {beatmap.HitObjects.Count}");
    foreach (var grouping in beatmap.HitObjects.GroupBy(h => h.Component).OrderByDescending(g => g.Count()))
    {
        Console.WriteLine($"  {grouping.Key}: {grouping.Count()}");
    }
}
catch (Exception ex)
{
    Console.WriteLine($"Failed to load beatmap: {ex.Message}");
}
