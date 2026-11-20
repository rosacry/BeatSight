using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Theming;
using Xunit;

namespace BeatSight.Tests;

public class LaneIdentityResolverTests
{
    private static readonly List<string> phaseTwoComponents = new()
    {
        "hihat_open", "tom_high", "crash", "kick", "snare", "splash", "ride", "ride_bell",
        "tom_mid", "tom_low", "hihat_closed", "hihat_pedal", "china", "percussion"
    };

    [Fact]
    public void ChinaLaneIsNotLabelledAsCrashWhenSecondaryCrashesShareIt()
    {
        // The dynamic builder maps crashes to both the crash lane and the china lane; the china lane must still
        // read "CH" (the 3D view used to print "CR" there).
        var layout = LaneLayoutFactory.CreateFromComponents(phaseTwoComponents, minimumLaneCount: 7);
        string[] shortNames = Enumerable.Range(0, layout.LaneCount)
            .Select(lane => LaneIdentityResolver.Resolve(layout, lane).ShortName)
            .ToArray();

        // Phase 2 writes three tom voices, so each gets its own lane (T1 high, T2 mid, T3 floor).
        Assert.Equal(new[] { "CR", "HH", "SN", "K", "T1", "T2", "T3", "RD", "CH", "SP", "PC" }, shortNames);
    }

    [Fact]
    public void KitsWithSeveralTomVoicesGetOneLanePerTomHighToLow()
    {
        // Human Clone Hero chart (Oblivion, Ziggy): three toms, no china/splash/percussion.
        var cloneHeroKit = new List<string> { "crash", "kick", "snare", "hihat_open", "hihat_closed", "ride", "tom_high", "tom_mid", "tom_low" };
        var layout = LaneLayoutFactory.CreateFromComponents(cloneHeroKit, minimumLaneCount: 7);
        var identities = Enumerable.Range(0, layout.LaneCount).Select(lane => LaneIdentityResolver.Resolve(layout, lane)).ToList();

        Assert.Equal(new[] { "CR", "HH", "SN", "K", "T1", "T2", "T3", "RD" }, identities.Select(identity => identity.ShortName).ToArray());
        Assert.Equal(new[] { "High tom", "Mid tom", "Floor tom" }, identities.Skip(4).Take(3).Select(identity => identity.Name).ToArray());

        int high = DrumLaneHeuristics.ResolveLane("tom_high", layout);
        int mid = DrumLaneHeuristics.ResolveLane("tom_mid", layout);
        int low = DrumLaneHeuristics.ResolveLane("tom_low", layout);
        Assert.True(high < mid && mid < low, $"tom lanes {high}/{mid}/{low}");
    }

    [Fact]
    public void ASingleTomVoiceKeepsOneSharedTomsLane()
    {
        // ADTOF writes every tom as tom_mid.
        var adtofKit = new List<string> { "kick", "snare", "tom_mid", "hihat_closed", "crash" };
        var layout = LaneLayoutFactory.CreateFromComponents(adtofKit, minimumLaneCount: 7);

        int tomLane = DrumLaneHeuristics.ResolveLane("tom_mid", layout);
        Assert.Equal("Toms", LaneIdentityResolver.Resolve(layout, tomLane).Name);
        Assert.Equal(tomLane, DrumLaneHeuristics.ResolveLane("tom_high", layout));
        Assert.Equal(tomLane, DrumLaneHeuristics.ResolveLane("tom_low", layout));
    }

    [Fact]
    public void AMissingMidTomFallsBackToATomLaneNotTheSnare()
    {
        var layout = LaneLayoutFactory.CreateFromComponents(new List<string> { "kick", "snare", "hihat_closed", "tom_high", "tom_low" }, minimumLaneCount: 7);

        int mid = DrumLaneHeuristics.ResolveLane("tom_mid", layout);
        Assert.NotEqual(layout.SnareLane, mid);
        Assert.Contains(mid, new[] { DrumLaneHeuristics.ResolveLane("tom_high", layout), DrumLaneHeuristics.ResolveLane("tom_low", layout) });
        Assert.Equal("High tom", LaneIdentityResolver.Resolve(layout, DrumLaneHeuristics.ResolveLane("tom_high", layout)).Name);
    }

    [Fact]
    public void LabelsFollowLaneContentNotLanePosition()
    {
        // The nine-lane preset puts open hi-hat in lane 2 and kick in lane 4.
        var layout = LaneLayoutFactory.Create(LanePreset.DrumNineLane);

        Assert.Equal("Kick", LaneIdentityResolver.Resolve(layout, layout.KickLane).Name);
        Assert.Equal("Snare", LaneIdentityResolver.Resolve(layout, layout.SnareLane).Name);
        Assert.Equal("OH", LaneIdentityResolver.Resolve(layout, layout.GetLanesFor(DrumComponentCategory.HiHatOpen)[0]).ShortName);
    }

    [Fact]
    public void LaneColoursMatchTheirInstrumentAndAreDistinctWithinALayout()
    {
        var layout = LaneLayoutFactory.CreateFromComponents(phaseTwoComponents, minimumLaneCount: 7);
        var identities = Enumerable.Range(0, layout.LaneCount).Select(lane => LaneIdentityResolver.Resolve(layout, lane)).ToList();

        Assert.Equal(DrumPalette.Kick, identities[layout.KickLane].Colour);
        Assert.Equal(DrumPalette.Snare, identities[layout.SnareLane].Colour);
        Assert.Equal(identities.Count, identities.Select(identity => identity.Colour).Distinct().Count());
    }

    [Fact]
    public void ComponentColoursUseTheSharedPalette()
    {
        Assert.Equal(DrumPalette.Crash, DrumPalette.ForComponent("crash_2"));
        Assert.Equal(DrumPalette.China, DrumPalette.ForComponent("china"));
        Assert.Equal(DrumPalette.HiHatOpen, DrumPalette.ForComponent("hihat_open"));
        Assert.Equal(DrumPalette.TomLow, DrumPalette.ForComponent("tom_low"));
        Assert.Equal(DrumPalette.RideBell, DrumPalette.ForComponent("ride_bell"));
        Assert.Equal(DrumPalette.Kick, DesignSystem.GetComponentColor("kick"));
    }

    [Fact]
    public void LegacyDefaultLaneColoursAreNotTreatedAsCustomisations()
    {
        var beatmap = new Beatmap();
        beatmap.DrumKit = new DrumKitInfo
        {
            LaneLayout = new LaneLayoutInfo
            {
                Lanes = new List<LaneInfo>
                {
                    new LaneInfo { Index = 0, Name = "Crash", ColorHex = "#FAB542" },
                    new LaneInfo { Index = 1, Name = "HiHat", ColorHex = "#123456" },
                }
            }
        };

        Assert.False(LaneManagement.TryGetLaneColor(beatmap, 0, out _));
        Assert.True(LaneManagement.TryGetLaneColor(beatmap, 1, out var custom));
        Assert.Equal("#123456", LaneManagement.ToColorHex(custom));

        var profile = LaneManagement.DeserializeLaneProfile("[{\"Index\":0,\"Name\":\"Crash\",\"ColorHex\":\"#FAB542\"}]");
        Assert.Equal(LaneManagement.ToColorHex(DrumPalette.Crash), profile[0].ColorHex);
    }

    [Fact]
    public void PositionalDefaultLaneColoursAreNotTreatedAsCustomisations()
    {
        // The editor writes Crash, HiHat, Snare, ... colours by lane index; with another layout lane 1 may hold the snare.
        var beatmap = new Beatmap();
        beatmap.DrumKit = new DrumKitInfo
        {
            LaneLayout = new LaneLayoutInfo
            {
                Lanes = new List<LaneInfo>
                {
                    new LaneInfo { Index = 0, Name = "Crash", ColorHex = LaneManagement.ToColorHex(DrumPalette.Crash) },
                    new LaneInfo { Index = 1, Name = "HiHat", ColorHex = LaneManagement.ToColorHex(DrumPalette.HiHat) },
                    new LaneInfo { Index = 2, Name = "Snare", ColorHex = LaneManagement.ToColorHex(DrumPalette.Kick) },
                }
            }
        };

        Assert.False(LaneManagement.TryGetLaneColor(beatmap, 0, out _));
        Assert.False(LaneManagement.TryGetLaneColor(beatmap, 1, out _));
        Assert.True(LaneManagement.TryGetLaneColor(beatmap, 2, out var custom));
        Assert.Equal(LaneManagement.ToColorHex(DrumPalette.Kick), LaneManagement.ToColorHex(custom));
    }

    [Fact]
    public void ComponentKeyNamesTheLanesOwnInstrument()
    {
        var layout = LaneLayoutFactory.Create(LanePreset.DrumNineLane);

        Assert.Equal("kick", LaneIdentityResolver.ComponentKey(layout, layout.KickLane));
        Assert.Equal("snare", LaneIdentityResolver.ComponentKey(layout, layout.SnareLane));
        Assert.Equal("hihat_closed", LaneIdentityResolver.ComponentKey(layout, layout.HiHatLane));
        Assert.Equal("ride", LaneIdentityResolver.ComponentKey(layout, layout.RideLane));
    }

    [Theory]
    [InlineData(1.0, 2.97)]
    [InlineData(0.45, 2.24)]
    [InlineData(0.2, 1.40)]
    public void LegacyPlaybackZoomMigrationPreservesTheLookAhead(double stored, double expectedFactor)
    {
        Assert.InRange(BeatSightConfigManager.LegacyPlaybackZoomFactor(stored), expectedFactor - 0.01, expectedFactor + 0.01);
    }
}
