using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Screens.Playback.Playfield.Notation;
using Xunit;

namespace BeatSight.Tests;

/// <summary>
/// The 2026-10-24 manuscript rebuild: standard drum-key positions on a five-line staff and the engraver that
/// turns detected hits into beamed measures.
/// </summary>
public class DrumStaffNotationTests
{
    [Theory]
    [InlineData("kick", -3, DrumNotehead.Normal, DrumVoice.Feet)]
    [InlineData("hihat_pedal", -5, DrumNotehead.Cross, DrumVoice.Feet)]
    [InlineData("tom_low", -1, DrumNotehead.Normal, DrumVoice.Hands)]
    [InlineData("snare", 1, DrumNotehead.Normal, DrumVoice.Hands)]
    [InlineData("tom_mid", 2, DrumNotehead.Normal, DrumVoice.Hands)]
    [InlineData("tom_high", 3, DrumNotehead.Normal, DrumVoice.Hands)]
    [InlineData("ride", 4, DrumNotehead.Cross, DrumVoice.Hands)]
    [InlineData("ride_bell", 4, DrumNotehead.Diamond, DrumVoice.Hands)]
    [InlineData("hihat_closed", 5, DrumNotehead.Cross, DrumVoice.Hands)]
    [InlineData("crash_2", 6, DrumNotehead.Cross, DrumVoice.Hands)]
    [InlineData("china", 7, DrumNotehead.Cross, DrumVoice.Hands)]
    [InlineData("cross_stick", 1, DrumNotehead.CircledCross, DrumVoice.Hands)]
    public void ComponentsUseTheStandardDrumKey(string component, int staffStep, DrumNotehead head, DrumVoice voice)
    {
        var symbol = DrumNotation.Resolve(component);

        Assert.Equal(staffStep, symbol.StaffStep);
        Assert.Equal(head, symbol.Head);
        Assert.Equal(voice, symbol.Voice);
    }

    [Fact]
    public void OpenHiHatCarriesTheOpenMark()
    {
        Assert.True(DrumNotation.Resolve("hihat_open").OpenMark);
        Assert.False(DrumNotation.Resolve("hihat_closed").OpenMark);
    }

    [Theory]
    [InlineData("tom_1", "tom_mid")]
    [InlineData("floor_tom", "tom_low")]
    [InlineData("Hi-Hat Open", "hihat_open")]
    [InlineData("bass_drum", "kick")]
    [InlineData("splash_1", "splash")]
    [InlineData("other", "percussion")]
    public void ComponentNamesNormalise(string component, string key)
    {
        Assert.Equal(key, DrumNotation.NormalizeComponentKey(component));
    }

    [Fact]
    public void AdjacentFollowsWrittenStaffOrder()
    {
        Assert.Equal("tom_mid", DrumNotation.Adjacent("snare", 1));
        Assert.Equal("tom_low", DrumNotation.Adjacent("snare", -1));
        Assert.Equal("hihat", DrumNotation.Adjacent("ride", 1));
        Assert.Equal("china", DrumNotation.Adjacent("crash", 1));
        Assert.Equal("china", DrumNotation.Adjacent("china", 1));
        Assert.Equal("hihat_pedal", DrumNotation.Adjacent("hihat_pedal", -1));

        var steps = DrumNotation.BottomToTop.Select(c => DrumNotation.Resolve(c).StaffStep).ToArray();
        Assert.Equal(steps.OrderBy(x => x), steps);
    }

    [Fact]
    public void TempoMapPlacesMeasuresFromTheOffset()
    {
        var map = new DrumTempoMap(new TimingInfo { Bpm = 120, Offset = 100, TimeSignature = "4/4" });

        var measure = map.MeasureAt(2150);
        Assert.Equal(1, measure.Index);
        Assert.Equal(2100, measure.StartTime, 3);
        Assert.Equal(4100, measure.EndTime, 3);
        Assert.Equal(4, measure.Beats);
        Assert.Equal(500, measure.BeatMs, 3);
        Assert.Equal(2, map.NextMeasure(measure).Index);
    }

    [Fact]
    public void TempoMapFollowsTimingPoints()
    {
        var map = new DrumTempoMap(new TimingInfo
        {
            Bpm = 120,
            TimingPoints = new List<TimingPoint>
            {
                new TimingPoint { Time = 0, Bpm = 120, TimeSignature = "4/4" },
                new TimingPoint { Time = 4000, Bpm = 60, TimeSignature = "3/4" }
            }
        });

        var measure = map.MeasureAt(4500);
        Assert.Equal(2, measure.Index);
        Assert.Equal(3, measure.Beats);
        Assert.Equal(1000, measure.BeatMs, 3);
    }

    private static EngravedMeasure engraveFirstMeasure(params (double Time, string Component)[] hits)
    {
        var map = new DrumTempoMap(new TimingInfo { Bpm = 120, Offset = 0 });
        var notes = hits.Select(h => new DrumStaffInputNote(h.Time, h.Component, 0.8)).OrderBy(n => n.Time).ToList();
        return DrumStaffEngraver.Engrave(map.MeasureAt(0), notes);
    }

    [Fact]
    public void EighthNoteGrooveIsBeamedInPairsWithQuarterNoteKicks()
    {
        var hits = new List<(double, string)>();
        for (int i = 0; i < 8; i++)
            hits.Add((i * 250, "hihat_closed"));
        hits.Add((0, "kick"));
        hits.Add((1000, "kick"));
        hits.Add((500, "snare"));
        hits.Add((1500, "snare"));

        var measure = engraveFirstMeasure(hits.ToArray());
        var hands = measure.Chords.Where(c => c.Voice == DrumVoice.Hands).ToList();
        var feet = measure.Chords.Where(c => c.Voice == DrumVoice.Feet).ToList();

        Assert.Equal(8, hands.Count);
        Assert.All(hands, c => Assert.Equal(1, c.BeamLevels));
        Assert.Equal(4, hands.Select(c => c.BeamGroup).Distinct().Count());
        Assert.Equal(2, hands.Count(c => c.Notes.Any(n => n.Symbol.Key == "snare")));

        Assert.Equal(2, feet.Count);
        Assert.All(feet, c => Assert.False(c.IsBeamed));
        Assert.All(feet, c => Assert.Equal(0, c.BeamLevels));
        Assert.Empty(measure.Rests);
    }

    [Fact]
    public void JitteredSixteenthsQuantiseToTheSixteenthGrid()
    {
        double[] jitter = { 0, 9, -12, 7 };
        var hits = Enumerable.Range(0, 16).Select(i => (i * 125.0 + jitter[i % 4], "hihat_closed")).ToArray();

        var measure = engraveFirstMeasure(hits);

        Assert.Equal(16, measure.Chords.Count);
        Assert.All(measure.Chords, c => Assert.Equal(4, c.Grid));
        Assert.All(measure.Chords, c => Assert.Equal(2, c.BeamLevels));
        Assert.Equal(new[] { 0, 1, 2, 3 }, measure.Chords.Take(4).Select(c => c.Slot));
    }

    [Fact]
    public void EvenThreesBecomeEighthNoteTriplets()
    {
        var measure = engraveFirstMeasure((0, "snare"), (166.7, "snare"), (333.3, "snare"));

        var triplet = measure.Chords.Where(c => c.Beat == 0).ToList();
        Assert.Equal(3, triplet.Count);
        Assert.All(triplet, c => Assert.Equal(3, c.Grid));
        Assert.All(triplet, c => Assert.Equal(1, c.BeamLevels));
        Assert.Single(measure.Tuplets);
        Assert.Equal(3, measure.Tuplets[0].Number);
    }

    [Fact]
    public void EmptyMeasureGetsAWholeMeasureRest()
    {
        var measure = engraveFirstMeasure();

        Assert.Empty(measure.Chords);
        Assert.Single(measure.Rests);
        Assert.Equal(-1, measure.Rests[0].Level);
    }

    [Fact]
    public void OffbeatEighthGetsALeadingRestAndAFlag()
    {
        var measure = engraveFirstMeasure((250, "snare"));

        var chord = Assert.Single(measure.Chords);
        Assert.False(chord.IsBeamed);
        Assert.Equal(1, chord.BeamLevels);
        Assert.Contains(measure.Rests, r => r.Level == 1 && r.Time == 0);
        Assert.Equal(3, measure.Rests.Count(r => r.Level == 0)); // beats 2-4 are empty
    }

    [Fact]
    public void DottedEighthAndSixteenth()
    {
        var measure = engraveFirstMeasure((0, "snare"), (375, "snare"));

        var chords = measure.Chords.Where(c => c.Beat == 0).ToList();
        Assert.Equal(2, chords.Count);
        Assert.True(chords[0].Dotted);
        Assert.Equal(1, chords[0].BeamLevels);
        Assert.Equal(2, chords[1].BeamLevels);
        Assert.Equal(chords[0].BeamGroup, chords[1].BeamGroup);
    }

    [Fact]
    public void SlightlyEarlyDownbeatBelongsToTheNextMeasure()
    {
        var map = new DrumTempoMap(new TimingInfo { Bpm = 120 });
        var notes = new List<DrumStaffInputNote> { new DrumStaffInputNote(1990, "crash", 0.8) };

        var first = DrumStaffEngraver.Engrave(map.MeasureAt(0), notes);
        var second = DrumStaffEngraver.Engrave(map.MeasureAt(2000), notes);

        Assert.Empty(first.Chords);
        var chord = Assert.Single(second.Chords);
        Assert.Equal(2000, chord.Time, 3);
    }

    [Fact]
    public void SimultaneousHitsShareOneChordPerVoice()
    {
        var measure = engraveFirstMeasure((0, "crash"), (8, "snare"), (3, "kick"), (5, "hihat_pedal"));

        var hands = Assert.Single(measure.Chords, c => c.Voice == DrumVoice.Hands);
        var feet = Assert.Single(measure.Chords, c => c.Voice == DrumVoice.Feet);
        Assert.Equal(new[] { 1, 6 }, hands.Notes.Select(n => n.Symbol.StaffStep));
        Assert.Equal(new[] { -5, -3 }, feet.Notes.Select(n => n.Symbol.StaffStep));
    }
}
