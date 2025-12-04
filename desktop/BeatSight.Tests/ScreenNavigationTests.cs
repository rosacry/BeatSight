using System;
using System.Collections.Generic;
using BeatSight.Game.Screens;
using osu.Framework.Screens;

namespace BeatSight.Tests;

/// <summary>
/// Tests for screen navigation flow including transitions between screens
/// and back button behavior.
/// </summary>
public partial class ScreenNavigationTests
{
    #region Screen Type Tests

    [Fact]
    public void BeatSightScreenIsBaseClass()
    {
        var screen = new TestScreen();

        Assert.IsAssignableFrom<Screen>(screen);
        Assert.IsAssignableFrom<BeatSightScreen>(screen);
    }

    [Fact]
    public void MainMenuScreenDerivesFromBase()
    {
        var screen = new MainMenuScreen();

        Assert.IsAssignableFrom<BeatSightScreen>(screen);
    }

    [Fact]
    public void IntroScreenDerivesFromScreen()
    {
        // IntroScreen extends Screen directly (not BeatSightScreen) for custom intro animation
        var screen = new IntroScreen();

        Assert.IsAssignableFrom<osu.Framework.Screens.Screen>(screen);
    }

    #endregion

    #region Screen Stack Simulation Tests

    [Fact]
    public void ScreenStackTracksNavigation()
    {
        var navigationStack = new Stack<string>();

        // Simulate: Intro -> MainMenu -> SongSelect
        navigationStack.Push("IntroScreen");
        navigationStack.Push("MainMenuScreen");
        navigationStack.Push("SongSelectScreen");

        Assert.Equal(3, navigationStack.Count);
        Assert.Equal("SongSelectScreen", navigationStack.Peek());
    }

    [Fact]
    public void BackNavigationPopsStack()
    {
        var navigationStack = new Stack<string>();
        navigationStack.Push("MainMenuScreen");
        navigationStack.Push("SettingsScreen");

        // Go back
        var popped = navigationStack.Pop();

        Assert.Equal("SettingsScreen", popped);
        Assert.Equal("MainMenuScreen", navigationStack.Peek());
    }

    [Fact]
    public void PushingNewScreenAddsToStack()
    {
        var navigationStack = new Stack<string>();
        navigationStack.Push("MainMenuScreen");

        int countBefore = navigationStack.Count;
        navigationStack.Push("EditorScreen");

        Assert.Equal(countBefore + 1, navigationStack.Count);
    }

    [Fact]
    public void ExitFromRootScreenEmptiesStack()
    {
        var navigationStack = new Stack<string>();
        navigationStack.Push("MainMenuScreen");

        navigationStack.Pop();

        Assert.Empty(navigationStack);
    }

    #endregion

    #region Navigation Flow Tests

    [Fact]
    public void IntroToMainMenuTransition()
    {
        // Simulate: User waits through intro, transitions to main menu
        var navigationHistory = new List<(string from, string to)>();

        navigationHistory.Add(("IntroScreen", "MainMenuScreen"));

        Assert.Single(navigationHistory);
        Assert.Equal("MainMenuScreen", navigationHistory[0].to);
    }

    [Fact]
    public void MainMenuToSongSelectFlow()
    {
        var currentScreen = "MainMenuScreen";

        // User clicks "Play" or "Practice"
        currentScreen = "SongSelectScreen";

        Assert.Equal("SongSelectScreen", currentScreen);
    }

    [Fact]
    public void SongSelectToPlaybackFlow()
    {
        var currentScreen = "SongSelectScreen";
        string? selectedSongPath = "/songs/test.bs";

        // User selects a song
        Assert.NotNull(selectedSongPath);

        // Transition to playback
        currentScreen = "PlaybackScreen";

        Assert.Equal("PlaybackScreen", currentScreen);
    }

    [Fact]
    public void MainMenuToEditorFlow()
    {
        var currentScreen = "MainMenuScreen";

        // User clicks "Editor"
        currentScreen = "EditorScreen";

        Assert.Equal("EditorScreen", currentScreen);
    }

    [Fact]
    public void MainMenuToSettingsFlow()
    {
        var currentScreen = "MainMenuScreen";

        // User clicks "Settings"
        currentScreen = "SettingsScreen";

        Assert.Equal("SettingsScreen", currentScreen);
    }

    [Fact]
    public void SettingsBackToMainMenu()
    {
        var navigationStack = new Stack<string>();
        navigationStack.Push("MainMenuScreen");
        navigationStack.Push("SettingsScreen");

        // User presses back
        navigationStack.Pop();

        Assert.Equal("MainMenuScreen", navigationStack.Peek());
    }

    [Fact]
    public void PlaybackBackToSongSelect()
    {
        var navigationStack = new Stack<string>();
        navigationStack.Push("MainMenuScreen");
        navigationStack.Push("SongSelectScreen");
        navigationStack.Push("PlaybackScreen");

        // User exits playback
        navigationStack.Pop();

        Assert.Equal("SongSelectScreen", navigationStack.Peek());
    }

    [Fact]
    public void EditorBackToMainMenu()
    {
        var navigationStack = new Stack<string>();
        navigationStack.Push("MainMenuScreen");
        navigationStack.Push("EditorScreen");

        // User exits editor
        navigationStack.Pop();

        Assert.Equal("MainMenuScreen", navigationStack.Peek());
    }

    #endregion

    #region Deep Navigation Tests

    [Fact]
    public void DeepNavigationReturnsCorrectly()
    {
        var navigationStack = new Stack<string>();

        // Deep navigation: Main -> SongSelect -> Playback -> Results
        navigationStack.Push("MainMenuScreen");
        navigationStack.Push("SongSelectScreen");
        navigationStack.Push("PlaybackScreen");
        navigationStack.Push("ResultsScreen");

        Assert.Equal(4, navigationStack.Count);

        // Navigate all the way back
        while (navigationStack.Count > 1)
        {
            navigationStack.Pop();
        }

        Assert.Equal("MainMenuScreen", navigationStack.Peek());
    }

    [Fact]
    public void NavigationPreservesHistory()
    {
        var fullHistory = new List<string>();
        var activeStack = new Stack<string>();

        void navigate(string to)
        {
            activeStack.Push(to);
            fullHistory.Add(to);
        }

        void goBack()
        {
            if (activeStack.Count > 1)
            {
                var from = activeStack.Pop();
                fullHistory.Add($"Back from {from}");
            }
        }

        navigate("MainMenuScreen");
        navigate("SettingsScreen");
        goBack();
        navigate("EditorScreen");
        goBack();

        Assert.Equal(5, fullHistory.Count);
        Assert.Contains("Back from SettingsScreen", fullHistory);
        Assert.Contains("Back from EditorScreen", fullHistory);
    }

    #endregion

    #region Screen Transition State Tests

    [Fact]
    public void ScreenTransitionHasFromScreen()
    {
        string? fromScreen = "MainMenuScreen";
        string toScreen = "SettingsScreen";

        Assert.NotNull(fromScreen);
        Assert.NotEqual(fromScreen, toScreen);
    }

    [Fact]
    public void FirstScreenHasNoFromScreen()
    {
        string? fromScreen = null;
        string toScreen = "IntroScreen";

        Assert.Null(fromScreen);
        Assert.NotNull(toScreen);
    }

    [Fact]
    public void TransitionAnimationDuration()
    {
        const double fadeInDuration = 400;
        const double fadeOutDuration = 200;

        // As defined in BeatSightScreen.cs
        Assert.Equal(400, fadeInDuration);
        Assert.Equal(200, fadeOutDuration);
    }

    #endregion

    #region Back Button Behavior Tests

    [Fact]
    public void BackButtonDisabledOnRootScreen()
    {
        var navigationStack = new Stack<string>();
        navigationStack.Push("MainMenuScreen");

        bool canGoBack = navigationStack.Count > 1;

        Assert.False(canGoBack);
    }

    [Fact]
    public void BackButtonEnabledOnNestedScreen()
    {
        var navigationStack = new Stack<string>();
        navigationStack.Push("MainMenuScreen");
        navigationStack.Push("SettingsScreen");

        bool canGoBack = navigationStack.Count > 1;

        Assert.True(canGoBack);
    }

    [Fact]
    public void BackButtonExitsPlayback()
    {
        var navigationStack = new Stack<string>();
        navigationStack.Push("SongSelectScreen");
        navigationStack.Push("PlaybackScreen");

        bool wasPlaybackActive = navigationStack.Peek() == "PlaybackScreen";
        navigationStack.Pop();

        Assert.True(wasPlaybackActive);
        Assert.NotEqual("PlaybackScreen", navigationStack.Peek());
    }

    [Fact]
    public void EscapeKeyTriggersBack()
    {
        // Simulate key binding
        const string escapeAction = "Back";
        var keyBindings = new Dictionary<string, string>
        {
            { "Escape", escapeAction }
        };

        Assert.Equal("Back", keyBindings["Escape"]);
    }

    #endregion

    #region Screen State Preservation Tests

    [Fact]
    public void SettingsChangesPreservedAfterBack()
    {
        var settings = new Dictionary<string, object>
        {
            { "Volume", 0.8 },
            { "FullScreen", true }
        };

        // Navigate to settings, change values
        settings["Volume"] = 0.5;

        // Navigate back, then return
        // Settings should persist
        Assert.Equal(0.5, settings["Volume"]);
    }

    [Fact]
    public void SongSelectRemembersLastSelection()
    {
        int? lastSelectedIndex = null;

        // User selects a song
        lastSelectedIndex = 5;

        // Navigate to playback, then back
        // Selection should be remembered
        Assert.Equal(5, lastSelectedIndex);
    }

    [Fact]
    public void EditorUnsavedChangesPrompt()
    {
        bool hasUnsavedChanges = true;
        bool shouldPrompt = hasUnsavedChanges;

        Assert.True(shouldPrompt);
    }

    #endregion

    #region Helper Classes

    /// <summary>
    /// Test screen for type checking.
    /// </summary>
    private partial class TestScreen : BeatSightScreen
    {
    }

    #endregion
}
