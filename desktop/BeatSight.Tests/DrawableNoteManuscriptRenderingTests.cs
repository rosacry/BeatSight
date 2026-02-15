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
    public void ManuscriptCrossStickUsesXHeadWithoutFilledOval()
    {
        var note = createNote("cross_stick", velocity: 0.9);
        note.Width = 20;
        note.Height = 10;

        note.SetViewMode(LaneViewMode.Manuscript);

        var mainBox = getPrivateField<Box>(note, "mainBox");
        var lineA = getPrivateField<Box>(note, "manuscriptCrossLineA");
        var lineB = getPrivateField<Box>(note, "manuscriptCrossLineB");

        Assert.True(mainBox.Alpha < 0.01f);
        Assert.True(lineA.Alpha > 0.5f);
        Assert.True(lineB.Alpha > 0.5f);
    }

    [Fact]
    public void ManuscriptRideBellUsesDiamondNoteheadWithoutCrossLines()
    {
        var note = createNote("ride_bell", velocity: 0.9);
        note.Width = 20;
        note.Height = 10;

        note.SetViewMode(LaneViewMode.Manuscript);

        var noteheadContainer = getPrivateField<Container>(note, "noteheadContainer");
        var mainBox = getPrivateField<Box>(note, "mainBox");
        var lineA = getPrivateField<Box>(note, "manuscriptCrossLineA");
        var lineB = getPrivateField<Box>(note, "manuscriptCrossLineB");

        Assert.True(noteheadContainer.Rotation > 30f);
        Assert.True(mainBox.Alpha > 0.5f);
        Assert.True(lineA.Alpha < 0.01f);
        Assert.True(lineB.Alpha < 0.01f);
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
        var closedCap = getPrivateField<Box>(note, "manuscriptHiHatClosedCap");
        var slashSecondary = getPrivateField<Box>(note, "manuscriptHiHatHalfOpenSlashSecondary");

        Assert.True(openRing.Alpha > 0.5f);
        Assert.True(closedHorizontal.Alpha < 0.01f);
        Assert.True(closedVertical.Alpha < 0.01f);
        Assert.True(closedCap.Alpha < 0.01f);
        Assert.True(slashSecondary.Alpha < 0.01f);
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
        var closedCap = getPrivateField<Box>(note, "manuscriptHiHatClosedCap");
        var slashSecondary = getPrivateField<Box>(note, "manuscriptHiHatHalfOpenSlashSecondary");

        Assert.True(openRing.Alpha < 0.01f);
        Assert.True(closedHorizontal.Alpha > 0.5f);
        Assert.True(closedVertical.Alpha > 0.5f);
        Assert.True(closedCap.Alpha > 0.4f);
        Assert.True(slashSecondary.Alpha < 0.01f);
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
        var slashSecondary = getPrivateField<Box>(note, "manuscriptHiHatHalfOpenSlashSecondary");
        var closedHorizontal = getPrivateField<Box>(note, "manuscriptHiHatClosedHorizontal");
        var closedCap = getPrivateField<Box>(note, "manuscriptHiHatClosedCap");

        Assert.True(openRing.Alpha > 0.5f);
        Assert.True(slash.Alpha > 0.5f);
        Assert.True(slashSecondary.Alpha > 0.3f);
        Assert.True(closedHorizontal.Alpha < 0.01f);
        Assert.True(closedCap.Alpha < 0.01f);
    }

    [Fact]
    public void ManuscriptHiHatArticulationLiftsAboveDenseStandaloneFlags()
    {
        var note = createNote("hihat_open", velocity: 0.9);
        note.Width = 20;
        note.Height = 10;
        note.SetViewMode(LaneViewMode.Manuscript);

        var openRing = getPrivateField<Circle>(note, "manuscriptHiHatOpenIndicator");
        float baselineY = openRing.Y;

        note.SetManuscriptFlagCount(3);

        Assert.True(openRing.Y < baselineY - 8f, $"Expected articulation to move higher for dense flags. baseline={baselineY:0.##}, current={openRing.Y:0.##}");
    }

    [Fact]
    public void ManuscriptHiHatArticulationOffsetHelperTracksFlagDensityAndStemDirection()
    {
        float stemUpNoFlags = DrawableNote.ResolveManuscriptHiHatArticulationOffsetY(10f, 0, stemDown: false);
        float stemUpDense = DrawableNote.ResolveManuscriptHiHatArticulationOffsetY(10f, 3, stemDown: false);
        float stemDownDense = DrawableNote.ResolveManuscriptHiHatArticulationOffsetY(10f, 3, stemDown: true);

        Assert.True(stemUpNoFlags < 0f);
        Assert.True(stemUpDense < stemUpNoFlags - 8f, $"Expected dense flags to increase upward clearance. noFlags={stemUpNoFlags:0.##}, dense={stemUpDense:0.##}");
        Assert.True(stemDownDense > 0f);
    }

    [Fact]
    public void ManuscriptHiHatAuxiliaryArticulationOffsetHelpersScaleWithGlyphSize()
    {
        float smallSlashOffset = DrawableNote.ResolveManuscriptHalfOpenSlashOffset(4.6f);
        float largeSlashOffset = DrawableNote.ResolveManuscriptHalfOpenSlashOffset(8.2f);
        float smallCapOffset = DrawableNote.ResolveManuscriptClosedCapOffset(4.8f);
        float largeCapOffset = DrawableNote.ResolveManuscriptClosedCapOffset(8.0f);

        Assert.True(smallSlashOffset > 0.5f);
        Assert.True(largeSlashOffset > smallSlashOffset, $"Expected larger articulation ring to increase half-open slash offset. small={smallSlashOffset:0.##}, large={largeSlashOffset:0.##}");
        Assert.True(smallCapOffset > 0f);
        Assert.True(largeCapOffset > smallCapOffset, $"Expected larger closed marker to increase cap offset. small={smallCapOffset:0.##}, large={largeCapOffset:0.##}");
    }

    [Fact]
    public void ManuscriptGhostNotesRenderParentheses()
    {
        var ghost = createNote("snare", velocity: 0.2);
        ghost.Width = 20;
        ghost.Height = 10;

        ghost.SetViewMode(LaneViewMode.Manuscript);

        var left = getPrivateField<Box>(ghost, "manuscriptGhostParenLeft");
        var right = getPrivateField<Box>(ghost, "manuscriptGhostParenRight");
        Assert.True(left.Alpha > 0.3f);
        Assert.True(right.Alpha > 0.3f);

        var normal = createNote("snare", velocity: 0.9);
        normal.Width = 20;
        normal.Height = 10;
        normal.SetViewMode(LaneViewMode.Manuscript);
        var normalLeft = getPrivateField<Box>(normal, "manuscriptGhostParenLeft");
        var normalRight = getPrivateField<Box>(normal, "manuscriptGhostParenRight");
        Assert.True(normalLeft.Alpha < 0.01f);
        Assert.True(normalRight.Alpha < 0.01f);
    }

    [Fact]
    public void ManuscriptGhostParenthesisHelpersScaleWithNoteSize()
    {
        float narrowOffset = DrawableNote.ResolveManuscriptGhostParenthesisOffsetX(10f);
        float wideOffset = DrawableNote.ResolveManuscriptGhostParenthesisOffsetX(22f);
        float shortHeight = DrawableNote.ResolveManuscriptGhostParenthesisHeight(7f);
        float tallHeight = DrawableNote.ResolveManuscriptGhostParenthesisHeight(16f);

        Assert.True(wideOffset > narrowOffset);
        Assert.True(tallHeight > shortHeight);
        Assert.InRange(narrowOffset, 5.4f, 12.5f);
        Assert.InRange(shortHeight, 8.2f, 18f);
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
