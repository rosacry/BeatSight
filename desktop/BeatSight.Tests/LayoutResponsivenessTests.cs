using System.IO;
using System.Text.RegularExpressions;
using Xunit;

namespace BeatSight.Tests
{
    public class LayoutResponsivenessTests
    {
        [Fact]
        public void CoreScreensAvoidHardCodedAbsoluteGridDimensions()
        {
            string root = resolveRepositoryRoot();
            string[] coreScreens =
            {
                Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Editor", "EditorScreen.cs"),
                Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "SongSelect", "SongSelectScreen.cs"),
                Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Settings", "SettingsScreen.cs"),
                Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Playback", "PlaybackScreen.cs"),
                Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "MainMenuScreen.cs")
            };

            var hardcodedAbsolutePattern = new Regex(@"new\s+Dimension\s*\(\s*GridSizeMode\.Absolute\s*,\s*[0-9]", RegexOptions.Compiled);

            foreach (string file in coreScreens)
            {
                Assert.True(File.Exists(file), $"Expected file missing: {file}");
                string source = File.ReadAllText(file);
                Assert.DoesNotMatch(hardcodedAbsolutePattern, source);
            }
        }

        [Fact]
        public void ResponsiveLayoutUtilityExists()
        {
            string root = resolveRepositoryRoot();
            string responsiveLayoutPath = Path.Combine(root, "desktop", "BeatSight.Game", "UI", "Theming", "ResponsiveLayout.cs");

            Assert.True(File.Exists(responsiveLayoutPath), $"Expected responsive layout utility missing: {responsiveLayoutPath}");
        }

        [Fact]
        public void SongSelectResponsiveLayoutUtilityExists()
        {
            string root = resolveRepositoryRoot();
            string responsiveLayoutPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "SongSelect", "SongSelectResponsiveLayout.cs");

            Assert.True(File.Exists(responsiveLayoutPath), $"Expected song-select responsive layout utility missing: {responsiveLayoutPath}");
        }

        [Fact]
        public void PlaybackResponsiveLayoutUtilityExists()
        {
            string root = resolveRepositoryRoot();
            string responsiveLayoutPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Playback", "PlaybackResponsiveLayout.cs");

            Assert.True(File.Exists(responsiveLayoutPath), $"Expected playback responsive layout utility missing: {responsiveLayoutPath}");
        }

        [Fact]
        public void MainMenuResponsiveLayoutUtilityExists()
        {
            string root = resolveRepositoryRoot();
            string responsiveLayoutPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "MainMenuResponsiveLayout.cs");

            Assert.True(File.Exists(responsiveLayoutPath), $"Expected menu responsive layout utility missing: {responsiveLayoutPath}");
        }

        [Fact]
        public void SettingsResponsiveDropdownSizingAvoidsManualHeightAssignment()
        {
            string root = resolveRepositoryRoot();
            string settingsScreenPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Settings", "SettingsScreen.cs");
            Assert.True(File.Exists(settingsScreenPath), $"Expected file missing: {settingsScreenPath}");

            string source = File.ReadAllText(settingsScreenPath);
            var problematicPattern = new Regex(@"\b(?:directDropdown|mappedDropdown)\.Height\s*=", RegexOptions.Compiled);
            Assert.DoesNotMatch(problematicPattern, source);
        }

        [Fact]
        public void EditorHeaderDefinesCoreActionButtons()
        {
            string root = resolveRepositoryRoot();
            string editorPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Editor", "EditorScreen.cs");
            Assert.True(File.Exists(editorPath), $"Expected file missing: {editorPath}");

            string source = File.ReadAllText(editorPath);

            Assert.Contains("new EditorButton(\"Play\"", source);
            Assert.Contains("new EditorButton(\"Save\"", source);
            Assert.Contains("new EditorButton(\"Undo\"", source);
            Assert.Contains("new EditorButton(\"Redo\"", source);
            Assert.Contains("new PreviewToggleButton", source);

            var headerFlowPattern = new Regex(
                @"Children\s*=\s*new\s+Drawable\[\]\s*\{\s*playPauseButton\s*,\s*saveButton\s*,\s*undoButton\s*,\s*redoButton\s*,\s*previewToggle\s*\}",
                RegexOptions.Compiled | RegexOptions.Singleline);
            Assert.Matches(headerFlowPattern, source);
        }

        [Fact]
        public void SongSelectHeaderUsesHorizontalScrollContainerForOverflowSafety()
        {
            string root = resolveRepositoryRoot();
            string songSelectPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "SongSelect", "SongSelectScreen.cs");
            Assert.True(File.Exists(songSelectPath), $"Expected file missing: {songSelectPath}");

            string source = File.ReadAllText(songSelectPath);

            Assert.Contains("new BeatSightScrollContainer(Direction.Horizontal)", source);
            Assert.Contains("headerControlsFlow = controlsFlow;", source);
            Assert.Contains("resolveHeaderPadding", source);
        }

        [Fact]
        public void SettingsScreenClearsDropdownOverlayBeforeSectionSwap()
        {
            string root = resolveRepositoryRoot();
            string settingsScreenPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Settings", "SettingsScreen.cs");
            Assert.True(File.Exists(settingsScreenPath), $"Expected file missing: {settingsScreenPath}");

            string source = File.ReadAllText(settingsScreenPath);
            Assert.Contains("dropdownOverlay.Clear(disposeChildren: true);", source);
        }

        private static string resolveRepositoryRoot()
        {
            string current = AppContext.BaseDirectory;
            for (int i = 0; i < 8; i++)
            {
                string candidate = Path.GetFullPath(Path.Combine(current, ".."));
                if (File.Exists(Path.Combine(candidate, "BeatSight.sln")))
                    return candidate;

                current = candidate;
            }

            throw new DirectoryNotFoundException("Could not locate repository root from test output directory.");
        }
    }
}
