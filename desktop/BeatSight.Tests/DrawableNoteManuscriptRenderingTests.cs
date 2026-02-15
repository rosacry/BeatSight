using System.Reflection;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Screens.Playback.Playfield;
using osu.Framework.Bindables;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using Xunit;

namespace BeatSight.Tests;

public class DrawableNoteManuscriptRenderingTests
{
    [Fact]
    public void ManuscriptModeDisablesParentMaskingSoStemsCanRenderOutsideNotehead()
    {
        var note = createNote("snare", velocity: 0.85);
        note.Width = 18;
        note.Height = 10;

        note.SetViewMode(LaneViewMode.Manuscript);

        Assert.False(note.Masking);

        var stem = getPrivateField<Box>(note, "stem");
        Assert.True(stem.Alpha > 0.5f);
        Assert.True(stem.Height > note.Height);
    }

    [Fact]
    public void ManuscriptCymbalNotesUseCrossNoteheadLines()
    {
        var note = createNote("hihat_closed", velocity: 0.9);
        note.Width = 20;
        note.Height = 10;

        note.SetViewMode(LaneViewMode.Manuscript);

        var lineA = getPrivateField<Box>(note, "manuscriptCrossLineA");
        var lineB = getPrivateField<Box>(note, "manuscriptCrossLineB");
        Assert.True(lineA.Alpha > 0.5f);
        Assert.True(lineB.Alpha > 0.5f);
    }

    [Fact]
    public void ManuscriptStandaloneFlagsFollowAssignedFlagCount()
    {
        var note = createNote("snare", velocity: 0.9);
        note.Width = 20;
        note.Height = 10;
        note.SetViewMode(LaneViewMode.Manuscript);

        note.SetManuscriptFlagCount(2);

        var primary = getPrivateField<Box>(note, "manuscriptFlagPrimary");
        var secondary = getPrivateField<Box>(note, "manuscriptFlagSecondary");
        var tertiary = getPrivateField<Box>(note, "manuscriptFlagTertiary");
        Assert.True(primary.Alpha > 0.5f);
        Assert.True(secondary.Alpha > 0.5f);
        Assert.True(tertiary.Alpha < 0.01f);

        note.SetManuscriptFlagCount(0);
        Assert.True(primary.Alpha < 0.01f);
        Assert.True(secondary.Alpha < 0.01f);
        Assert.True(tertiary.Alpha < 0.01f);
    }

    [Fact]
    public void ManuscriptModeTiltsStandardNoteheadsAndResetsOutsideManuscript()
    {
        var note = createNote("snare", velocity: 0.9);
        note.Width = 20;
        note.Height = 10;

        note.SetViewMode(LaneViewMode.Manuscript);
        var noteheadContainer = getPrivateField<Container>(note, "noteheadContainer");
        Assert.True(noteheadContainer.Rotation < -10f);

        note.SetViewMode(LaneViewMode.TwoDimensional);
        Assert.Equal(0f, noteheadContainer.Rotation);
    }

    [Fact]
    public void ManuscriptOpenHiHatShowsOpenArticulationRing()
    {
        var note = createNote("hihat_open", velocity: 0.9);
        note.Width = 20;
        note.Height = 10;

        note.SetViewMode(LaneViewMode.Manuscript);

        var openRing = getPrivateField<Circle>(note, "manuscriptHiHatOpenIndicator");
        var closedHorizontal = getPrivateField<Box>(note, "manuscriptHiHatClosedHorizontal");
        var closedVertical = getPrivateField<Box>(note, "manuscriptHiHatClosedVertical");

        Assert.True(openRing.Alpha > 0.5f);
        Assert.True(closedHorizontal.Alpha < 0.01f);
        Assert.True(closedVertical.Alpha < 0.01f);
    }

    [Fact]
    public void ManuscriptClosedHiHatShowsClosedArticulationMarker()
    {
        var note = createNote("hihat_closed", velocity: 0.9);
        note.Width = 20;
        note.Height = 10;

        note.SetViewMode(LaneViewMode.Manuscript);

        var openRing = getPrivateField<Circle>(note, "manuscriptHiHatOpenIndicator");
        var closedHorizontal = getPrivateField<Box>(note, "manuscriptHiHatClosedHorizontal");
        var closedVertical = getPrivateField<Box>(note, "manuscriptHiHatClosedVertical");

        Assert.True(openRing.Alpha < 0.01f);
        Assert.True(closedHorizontal.Alpha > 0.5f);
        Assert.True(closedVertical.Alpha > 0.5f);
    }

    [Fact]
    public void ManuscriptHalfOpenHiHatShowsRingWithSlashMarker()
    {
        var note = createNote("hihat_half_open", velocity: 0.9);
        note.Width = 20;
        note.Height = 10;

        note.SetViewMode(LaneViewMode.Manuscript);

        var openRing = getPrivateField<Circle>(note, "manuscriptHiHatOpenIndicator");
        var slash = getPrivateField<Box>(note, "manuscriptHiHatHalfOpenSlash");
        var closedHorizontal = getPrivateField<Box>(note, "manuscriptHiHatClosedHorizontal");

        Assert.True(openRing.Alpha > 0.5f);
        Assert.True(slash.Alpha > 0.5f);
        Assert.True(closedHorizontal.Alpha < 0.01f);
    }

    [Fact]
    public void ManuscriptDurationDotFollowsAssignedCueState()
    {
        var note = createNote("snare", velocity: 0.9);
        note.Width = 20;
        note.Height = 10;
        note.SetViewMode(LaneViewMode.Manuscript);

        note.SetManuscriptDurationDot(true);

        var dot = getPrivateField<Circle>(note, "manuscriptDurationDot");
        Assert.True(dot.Alpha > 0.5f);

        note.SetManuscriptDurationDot(false);
        Assert.True(dot.Alpha < 0.01f);
    }

    private static DrawableNote createNote(string component, double velocity)
    {
        return new DrawableNote(
            new HitObject
            {
                Time = 1000,
                Component = component,
                Velocity = velocity
            },
            lane: 0,
            showGlow: new Bindable<bool>(true),
            showParticles: new Bindable<bool>(true));
    }

    private static T getPrivateField<T>(object target, string fieldName)
        where T : class
    {
        FieldInfo? field = target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
        Assert.NotNull(field);

        object? value = field!.GetValue(target);
        Assert.IsType<T>(value);
        return (T)value!;
    }
}
