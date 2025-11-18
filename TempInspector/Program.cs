using System;
using System.Linq;
using BeatSight.Game.Beatmaps;

if (args.Length == 0)
{
    Console.WriteLine("Usage: TempInspector <beatmap.osu>");
    Console.WriteLine("       TempInspector --inspect-fonts");
    return;
}

if (args.Length == 1 && args[0].Equals("--inspect-fonts", StringComparison.OrdinalIgnoreCase))
{
    InspectEmbeddedFonts();
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

static void InspectEmbeddedFonts()
{
    using var baseResources = new osu.Framework.IO.Stores.ResourceStore<byte[]>();
    baseResources.AddStore(new osu.Framework.IO.Stores.NamespacedResourceStore<byte[]>(new osu.Framework.IO.Stores.DllResourceStore(typeof(osu.Framework.Game).Assembly), "Resources"));
    baseResources.AddStore(new osu.Framework.IO.Stores.NamespacedResourceStore<byte[]>(new osu.Framework.IO.Stores.DllResourceStore(typeof(BeatSight.Game.BeatSightGame).Assembly), "Resources"));

    string[] fonts =
    {
        "Fonts/Exo2/Exo2-Regular",
        "Fonts/Exo2/Exo2-Medium",
        "Fonts/Exo2/Exo2-SemiBold",
        "Fonts/Exo2/Exo2-Bold",
        "Fonts/Nunito/Nunito-Light",
        "Fonts/Nunito/Nunito-Regular",
        "Fonts/Nunito/Nunito-Medium",
        "Fonts/Nunito/Nunito-SemiBold"
    };

    foreach (string font in fonts)
    {
        using var stream = baseResources.GetStream($"{font}.ttf");
        Console.WriteLine(stream == null
            ? $"{font} -> missing"
            : $"{font} -> {stream.Length} bytes");
    }
}
