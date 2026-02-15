using System;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Globalization;
using BeatSight.Game.Screens.Editor;
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
            string editorDir = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Editor");
            Assert.True(Directory.Exists(editorDir), $"Expected directory missing: {editorDir}");

            string[] editorPartials = Directory.GetFiles(editorDir, "EditorScreen*.cs", SearchOption.TopDirectoryOnly);
            Assert.NotEmpty(editorPartials);
            string source = string.Join("\n", editorPartials.Select(File.ReadAllText));

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
        public void EditorCompactDensityPreservesActionHierarchyAt720p()
        {
            string root = resolveRepositoryRoot();
            string responsiveDensityPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Editor", "EditorScreen.ResponsiveDensity.cs");
            Assert.True(File.Exists(responsiveDensityPath), $"Expected file missing: {responsiveDensityPath}");

            string source = File.ReadAllText(responsiveDensityPath);

            (_, float playCompact) = readBlendPair(source, "playButtonWidth");
            (_, float saveCompact) = readBlendPair(source, "saveButtonWidth");
            (_, float undoCompact) = readBlendPair(source, "undoButtonWidth");
            (_, float redoCompact) = readBlendPair(source, "redoButtonWidth");
            (_, float previewCompact) = readBlendPair(source, "previewButtonWidth");

            Assert.True(playCompact >= 100f, $"Play button compact width too small for 720p density: {playCompact:0.##}");
            Assert.True(saveCompact >= 100f, $"Save button compact width too small for 720p density: {saveCompact:0.##}");
            Assert.True(undoCompact >= 88f, $"Undo button compact width too small for 720p density: {undoCompact:0.##}");
            Assert.True(redoCompact >= 88f, $"Redo button compact width too small for 720p density: {redoCompact:0.##}");
            Assert.True(previewCompact >= 120f, $"Preview button compact width too small for 720p density: {previewCompact:0.##}");

            // Primary actions should remain more prominent than secondary undo/redo actions.
            Assert.True(playCompact >= undoCompact + 10f, $"Play action hierarchy regressed: play={playCompact:0.##}, undo={undoCompact:0.##}");
            Assert.True(saveCompact >= redoCompact + 10f, $"Save action hierarchy regressed: save={saveCompact:0.##}, redo={redoCompact:0.##}");
            Assert.True(previewCompact > playCompact, $"Preview prominence regressed: preview={previewCompact:0.##}, play={playCompact:0.##}");
        }

        [Fact]
        public void EditorStackedInspectorActionRowsUseBoundedWidthsAt720p()
        {
            const float viewportWidth = 1280f;
            const float compactBlend = 1f;

            float singleColumn = EditorResponsiveLayout.ResolveInspectorActionRowWidthFraction(viewportWidth, stackedLayout: true, columnCount: 1, compactBlend);
            float dualColumn = EditorResponsiveLayout.ResolveInspectorActionRowWidthFraction(viewportWidth, stackedLayout: true, columnCount: 2, compactBlend);
            float tripleColumn = EditorResponsiveLayout.ResolveInspectorActionRowWidthFraction(viewportWidth, stackedLayout: true, columnCount: 3, compactBlend);
            float unstacked = EditorResponsiveLayout.ResolveInspectorActionRowWidthFraction(viewportWidth, stackedLayout: false, columnCount: 2, compactBlend);

            Assert.InRange(singleColumn, 0.17f, 0.33f);
            Assert.InRange(dualColumn, 0.34f, 0.63f);
            Assert.InRange(tripleColumn, 0.50f, 0.90f);
            Assert.True(singleColumn < dualColumn, $"Expected 1-column row to be narrower than 2-column row ({singleColumn:0.###} vs {dualColumn:0.###}).");
            Assert.True(dualColumn < tripleColumn, $"Expected 2-column row to be narrower than 3-column row ({dualColumn:0.###} vs {tripleColumn:0.###}).");
            Assert.True(Math.Abs(unstacked - 1f) < 0.001f, $"Expected unstacked action rows to stay full width, got {unstacked:0.###}.");
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
        public void PlaybackStageControlsIncludeThreeDProfileToggle()
        {
            string root = resolveRepositoryRoot();
            string playbackPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Playback", "PlaybackScreen.cs");
            Assert.True(File.Exists(playbackPath), $"Expected file missing: {playbackPath}");

            string source = File.ReadAllText(playbackPath);
            Assert.Contains("toggleThreeDStageProfile", source);
            Assert.Contains("3D Profile:", source);
            Assert.Contains("FormatThreeDStageProfileLabel", source);
        }

        [Fact]
        public void PlaybackSettingsExposeManuscriptCountInGuideModeControl()
        {
            string root = resolveRepositoryRoot();
            string playbackSettingsPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Settings", "PlaybackSettingsSection.cs");
            string configPath = Path.Combine(root, "desktop", "BeatSight.Game", "Configuration", "BeatSightConfigManager.cs");

            Assert.True(File.Exists(playbackSettingsPath), $"Expected file missing: {playbackSettingsPath}");
            Assert.True(File.Exists(configPath), $"Expected file missing: {configPath}");

            string settingsSource = File.ReadAllText(playbackSettingsPath);
            string configSource = File.ReadAllText(configPath);

            Assert.Contains("Sheet Count-in Guides", settingsSource);
            Assert.Contains("BeatSightSetting.ManuscriptCountInGuideMode", settingsSource);
            Assert.Contains("formatManuscriptCountInGuideMode", settingsSource);
            Assert.Contains("setDefault(BeatSightSetting.ManuscriptCountInGuideMode, ManuscriptCountInGuideMode.Full)", configSource);
        }

        [Fact]
        public void PlaybackAndEditorZoomDefaultsStayReadabilityBiased()
        {
            string root = resolveRepositoryRoot();
            string configPath = Path.Combine(root, "desktop", "BeatSight.Game", "Configuration", "BeatSightConfigManager.cs");
            string editorBeatmapLoadPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Editor", "EditorScreen.BeatmapAudioLoad.cs");

            Assert.True(File.Exists(configPath), $"Expected file missing: {configPath}");
            Assert.True(File.Exists(editorBeatmapLoadPath), $"Expected file missing: {editorBeatmapLoadPath}");

            string configSource = File.ReadAllText(configPath);
            string editorSource = File.ReadAllText(editorBeatmapLoadPath);

            Assert.Contains("setDefault(BeatSightSetting.PlaybackZoomLevel, 1.36)", configSource);
            Assert.Contains("setDefault(BeatSightSetting.EditorTimelineZoomDefault, 1.15)", configSource);
            Assert.Contains("TimelineZoom = editorTimelineZoomDefault?.Value ?? 1.15", editorSource);
        }

        [Fact]
        public void EditorPreviewBindsThreeDProfileSettingToPlaybackPlayfield()
        {
            string root = resolveRepositoryRoot();
            string previewPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Editor", "PlaybackPreview.cs");
            Assert.True(File.Exists(previewPath), $"Expected file missing: {previewPath}");

            string source = File.ReadAllText(previewPath);
            Assert.Contains("BeatSightSetting.ThreeDStageProfile", source);
            Assert.Contains("playfield.StageProfile.BindTo(threeDStageProfileSetting)", source);
        }

        [Fact]
        public void ThreeDHighwayBackgroundIncludesLaneReceptorGuides()
        {
            string root = resolveRepositoryRoot();
            string highwayPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Playback", "Playfield", "ThreeDHighwayBackground.cs");
            Assert.True(File.Exists(highwayPath), $"Expected file missing: {highwayPath}");

            string source = File.ReadAllText(highwayPath);
            Assert.Contains("buildLaneReceptors", source);
            Assert.Contains("layoutLaneReceptors", source);
            Assert.Contains("receptorRail", source);
            Assert.Contains("laneReceptorGlows", source);
            Assert.Contains("strikeZoneGlow", source);
            Assert.Contains("ResolveThreeDStrikeZonePresentation", source);
        }

        [Fact]
        public void ManuscriptBackgroundIncludesTimelineMeasureLabels()
        {
            string root = resolveRepositoryRoot();
            string manuscriptPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Playback", "Playfield", "Views", "ManuscriptViewEnhanced.cs");
            Assert.True(File.Exists(manuscriptPath), $"Expected file missing: {manuscriptPath}");

            string source = File.ReadAllText(manuscriptPath);
            Assert.Contains("timelineMeasureLabelLayer", source);
            Assert.Contains("updateTimelineMeasureLabels", source);
            Assert.Contains("getTimelineMeasureLabel", source);
            Assert.Contains("timelinePlayheadLabel", source);
            Assert.Contains("updateTimelinePlayheadLabel", source);
            Assert.Contains("timelinePlayheadCountInLayer", source);
            Assert.Contains("updateTimelinePlayheadCountInGuides", source);
            Assert.Contains("FormatManuscriptCountInLabel", source);
            Assert.Contains("ResolveManuscriptCountInLookAroundTicks", source);
            Assert.Contains("ShouldRenderManuscriptCountInLabel", source);
            Assert.Contains("timelineTupletLabelLayer", source);
            Assert.Contains("updateTimelineTupletLabels", source);
            Assert.Contains("FormatManuscriptTupletHintLabel", source);
            Assert.Contains("ResolveManuscriptTupletGroupingTicks", source);
            Assert.Contains("ShouldRenderManuscriptTupletHint", source);
            Assert.Contains("ResolveManuscriptTupletBracketEmphasis", source);
            Assert.Contains("UsesDiamondNoteheadForComponent", source);
            Assert.Contains("timelineTupletBracketRails", source);
            Assert.Contains("getTimelineTupletBracketRail", source);
            Assert.Contains("getTimelineTupletBracketLeftHook", source);
            Assert.Contains("getTimelineTupletBracketRightHook", source);
            Assert.Contains("label.Text = $\"M{measureIndex + 1}\"", source);
        }

        [Fact]
        public void ManuscriptPlaybackHighlighterUsesBoundedCursorTrailContracts()
        {
            string root = resolveRepositoryRoot();
            string highlighterPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Playback", "Playfield", "Views", "ManuscriptPlaybackHighlighter.cs");
            Assert.True(File.Exists(highlighterPath), $"Expected file missing: {highlighterPath}");

            string source = File.ReadAllText(highlighterPath);
            Assert.Contains("ResolvePlaybackCursorTrailWidth", source);
            Assert.Contains("previewOverlay", source);
            Assert.Contains("topTick", source);
            Assert.Contains("bottomTick", source);
        }

        [Fact]
        public void ManuscriptPlayfieldIncludesDurationCueContracts()
        {
            string root = resolveRepositoryRoot();
            string playfieldPath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Playback", "Playfield", "PlaybackPlayfield.cs");
            string drawableNotePath = Path.Combine(root, "desktop", "BeatSight.Game", "Screens", "Playback", "Playfield", "DrawableNote.cs");
            Assert.True(File.Exists(playfieldPath), $"Expected file missing: {playfieldPath}");
            Assert.True(File.Exists(drawableNotePath), $"Expected file missing: {drawableNotePath}");

            string playfieldSource = File.ReadAllText(playfieldPath);
            string noteSource = File.ReadAllText(drawableNotePath);

            Assert.Contains("manuscriptDurationLayer", playfieldSource);
            Assert.Contains("addManuscriptTieSegment", playfieldSource);
            Assert.Contains("ShouldRenderManuscriptDottedCue", playfieldSource);
            Assert.Contains("manuscriptRestSpanLayer", playfieldSource);
            Assert.Contains("ResolveManuscriptRestSpanEmphasisLevel", playfieldSource);
            Assert.Contains("buildManuscriptHorizontalClusters", playfieldSource);
            Assert.Contains("ResolveManuscriptChordHorizontalOffset", playfieldSource);
            Assert.Contains("ResolveManuscriptSimultaneousTimeKey", playfieldSource);
            Assert.Contains("renderManuscriptTieCues", playfieldSource);
            Assert.Contains("ResolveManuscriptTieArchLiftMagnitude", playfieldSource);
            Assert.Contains("ResolveManuscriptParserFollowAlpha", playfieldSource);
            Assert.Contains("SetCountInGuideMode", playfieldSource);
            Assert.Contains("SetManuscriptDurationDot", noteSource);
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

        private static (float Normal, float Compact) readBlendPair(string source, string variableName)
        {
            var pattern = new Regex(
                $@"float\s+{Regex.Escape(variableName)}\s*=\s*blend\(\s*([0-9.]+)f\s*,\s*([0-9.]+)f\s*,\s*compactBlend\)",
                RegexOptions.Compiled);

            Match match = pattern.Match(source);
            Assert.True(match.Success, $"Could not parse blend pair for '{variableName}'.");

            float normal = float.Parse(match.Groups[1].Value, CultureInfo.InvariantCulture);
            float compact = float.Parse(match.Groups[2].Value, CultureInfo.InvariantCulture);
            return (normal, compact);
        }
    }
}
