using System.Reflection;
using BeatSight.Game.Screens.Playback.Playfield;
using osu.Framework.Graphics.Shapes;
using Xunit;

namespace BeatSight.Tests;

public class DrawableManuscriptRestTests
{
    [Fact]
    public void QuarterRestUsesStrokeClusterAndHidesStem()
    {
        var rest = new DrawableManuscriptRest();
        rest.SetGlyphLevel(0);

        var stem = getPrivateField<Box>(rest, "stem");
        var quarterStrokeA = getPrivateField<Box>(rest, "quarterStrokeA");
        var quarterStrokeD = getPrivateField<Box>(rest, "quarterStrokeD");
        Assert.True(stem.Alpha < 0.01f);
        Assert.True(quarterStrokeA.Alpha > 0.5f);
        Assert.True(quarterStrokeD.Alpha > 0.5f);
    }

    [Fact]
    public void SixteenthRestShowsTwoHooks()
    {
        var rest = new DrawableManuscriptRest();
        rest.SetGlyphLevel(2);

        var flagPrimary = getPrivateField<Box>(rest, "flagPrimary");
        var flagSecondary = getPrivateField<Box>(rest, "flagSecondary");
        var flagTertiary = getPrivateField<Box>(rest, "flagTertiary");
        Assert.True(flagPrimary.Alpha > 0.5f);
        Assert.True(flagSecondary.Alpha > 0.5f);
        Assert.True(flagTertiary.Alpha < 0.01f);
    }

    [Fact]
    public void LowerVoiceFlipsHookDirection()
    {
        var rest = new DrawableManuscriptRest();
        rest.SetGlyphLevel(1);
        rest.SetVoice(DrawableManuscriptRest.RestVoice.Upper);
        var flagPrimary = getPrivateField<Box>(rest, "flagPrimary");
        float upperRotation = flagPrimary.Rotation;

        rest.SetVoice(DrawableManuscriptRest.RestVoice.Lower);
        float lowerRotation = flagPrimary.Rotation;

        Assert.True(upperRotation > 0);
        Assert.True(lowerRotation < 0);
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
