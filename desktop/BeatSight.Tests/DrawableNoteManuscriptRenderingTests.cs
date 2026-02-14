using System.Reflection;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Screens.Playback.Playfield;
using osu.Framework.Bindables;
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
