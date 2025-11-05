using BeatSight.Game.Screens.Mapping;

namespace BeatSight.Tests;

public class GenerationUiStateGuardTests
{
    [Fact]
    public void ReadyStateShowsStartOnly()
    {
        var state = GenerationUiStateGuard.Compute(
            isRunning: false,
            isReady: true,
            isCompleted: false,
            hasRunBefore: false,
            hasPendingChanges: false,
            hasDraft: false);

        Assert.True(state.StartVisible);
        Assert.True(state.StartEnabled);
        Assert.False(state.CancelVisible);
        Assert.False(state.ApplyVisible);
        Assert.False(state.OpenEditorVisible);
    }

    [Fact]
    public void RunningStateLocksControls()
    {
        var state = GenerationUiStateGuard.Compute(
            isRunning: true,
            isReady: false,
            isCompleted: false,
            hasRunBefore: true,
            hasPendingChanges: true,
            hasDraft: true);

        Assert.False(state.StartVisible);
        Assert.True(state.CancelVisible);
        Assert.True(state.CancelEnabled);
        Assert.False(state.ApplyVisible);
        Assert.False(state.OpenEditorVisible);
    }

    [Fact]
    public void CompletedRunWithChangesEnablesApply()
    {
        var state = GenerationUiStateGuard.Compute(
            isRunning: false,
            isReady: false,
            isCompleted: true,
            hasRunBefore: true,
            hasPendingChanges: true,
            hasDraft: true);

        Assert.True(state.ApplyVisible);
        Assert.True(state.ApplyEnabled);
        Assert.True(state.OpenEditorVisible);
        Assert.True(state.OpenEditorEnabled);
    }

    [Fact]
    public void CompletedRunWithoutChangesDisablesApply()
    {
        var state = GenerationUiStateGuard.Compute(
            isRunning: false,
            isReady: false,
            isCompleted: true,
            hasRunBefore: true,
            hasPendingChanges: false,
            hasDraft: true);

        Assert.False(state.ApplyVisible);
        Assert.False(state.ApplyEnabled);
        Assert.True(state.OpenEditorVisible);
        Assert.True(state.OpenEditorEnabled);
    }

    [Fact]
    public void PendingChangesIgnoredWhileRunning()
    {
        var state = GenerationUiStateGuard.Compute(
            isRunning: true,
            isReady: false,
            isCompleted: false,
            hasRunBefore: true,
            hasPendingChanges: true,
            hasDraft: false);

        Assert.False(state.ApplyVisible);
        Assert.False(state.ApplyEnabled);
        Assert.True(state.CancelVisible);
        Assert.True(state.CancelEnabled);
    }
}
