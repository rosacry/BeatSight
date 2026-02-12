using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Progress;
using BeatSight.Game.Screens.Editor;
using BeatSight.Game.Screens.Playback;
using BeatSight.Game.UI.Components;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;
using osu.Framework.Audio;
using osu.Framework.Audio.Track;
using osu.Framework.Input;
using osu.Framework.Graphics.Rendering;
using osu.Framework.Graphics.Textures;
using BeatSight.Game.Screens;
using osu.Framework.Bindables;
using osu.Framework.Logging;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Overlays;

namespace BeatSight.Game.Screens.SongSelect
{
    public partial class SongSelectScreen : BeatSightScreen
    {
        // Note: As per the pivot to a learning tool, this screen serves as the hub for 
        // selecting verified maps or creating new ones via AI/Manual entry.
        // Future integration: Show "Verified" status on BeatmapPanels.

        [Resolved]
        private AudioManager audio { get; set; } = null!;

        [Resolved]
        private IRenderer renderer { get; set; } = null!;

        [Resolved]
        private BeatSightGame game { get; set; } = null!;

        [Resolved]
        private UserProgressManager progressManager { get; set; } = null!;

        [Resolved]
        private Collections.CollectionManager collectionManager { get; set; } = null!;

        private readonly bool editorMode;
        private readonly bool previewMode;
        private BeatmapCarousel carousel = null!;
        private Container leftContent = null!;
        private BeatmapLibrary.BeatmapEntry? selectedBeatmap;
        private SearchTextBox searchBox = null!;
        private BeatSight.Game.UI.Components.Dropdown<BeatmapCarousel.SortMode> sortDropdown = null!;
        private BeatSight.Game.UI.Components.Dropdown<string> genreDropdown = null!;
        private BeatSightCheckbox confidenceFilter = null!;
        private BeatSightCheckbox favoritesFilter = null!;
        private Box backgroundDim = null!;
        private Sprite backgroundSprite = null!;
        private GridContainer mainLayoutGrid = null!;
        private Container headerContainer = null!;
        private Container headerContentContainer = null!;
        private FillFlowContainer headerControlsFlow = null!;
        private FillFlowContainer headerFilterToggleRow = null!;
        private Container rightContentContainer = null!;
        private BeatSightButton randomButton = null!;
        private BackButton backButton = null!;
        private LoadingOverlay loadingOverlay = null!;

        private Bindable<bool> showGlobalBackground = null!;
        private Bindable<double> globalBackgroundOpacity = null!;
        private Box rightAreaBackground = null!;
        private float lastLeftColumnWidth = -1;
        private float lastHeaderHeight = -1;

        public SongSelectScreen(bool editorMode = false, bool previewMode = false)
        {
            this.editorMode = editorMode;
            this.previewMode = previewMode;
        }

        [BackgroundDependencyLoader]
        private void load(BeatSightConfigManager config)
        {
            showGlobalBackground = config.GetBindable<bool>(BeatSightSetting.ShowGlobalBackground);
            globalBackgroundOpacity = config.GetBindable<double>(BeatSightSetting.GlobalBackgroundOpacity);

            showGlobalBackground.BindValueChanged(_ => updateBackgroundState());
            globalBackgroundOpacity.BindValueChanged(_ => updateBackgroundState(), true);

            backButton = new BackButton
            {
                Action = this.Exit,
                Margin = BackButton.DefaultMargin,
                Depth = -10
            };

            mainLayoutGrid = new GridContainer
            {
                RelativeSizeAxes = Axes.Both,
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Relative, 0.3f), // Left side (Details / Drop)
                    new Dimension(GridSizeMode.Relative, 0.7f)  // Right side (Carousel)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        createLeftArea(),
                        createRightArea()
                    }
                }
            };

            InternalChildren = new Drawable[]
            {
                // Background is now global
                backgroundSprite = new Sprite
                {
                    RelativeSizeAxes = Axes.Both,
                    FillMode = FillMode.Fill,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Alpha = 0.2f // Lower alpha to let dynamic background show through slightly or just be subtle
                },
                backgroundDim = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Black,
                    Alpha = 0.3f // Darker dim for better readability
                },
                new SafeAreaContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Children = new Drawable[]
                    {
                        mainLayoutGrid,
                        createHeader()
                    }
                },
                new SafeAreaContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = BackButton.DefaultMargin,
                    Child = backButton
                },
                loadingOverlay = new LoadingOverlay()
            };

            populateBeatmaps();
            updateBackgroundState();
            applyResponsiveLayout(force: true);

            if (previewMode)
            {
                this.Alpha = 1;
                backButton.Alpha = 0;
            }
        }



        private void populateBeatmaps()
        {
            var beatmaps = BeatmapLibrary.GetAvailableBeatmaps();
            carousel.SetBeatmaps(beatmaps);

            // Populate genre dropdown dynamically
            if (genreDropdown != null)
            {
                var genres = new HashSet<string> { "All" };
                foreach (var b in beatmaps)
                {
                    foreach (var tag in b.Beatmap.Metadata.Tags)
                    {
                        if (!string.IsNullOrWhiteSpace(tag))
                            genres.Add(tag);
                    }
                }
                genreDropdown.Items = genres.OrderBy(g => g == "All" ? "" : g).ToList();
            }
        }

        private void selectBeatmap(BeatmapLibrary.BeatmapEntry entry)
        {
            if (selectedBeatmap == entry) return;

            bool switchingBetweenBeatmaps = selectedBeatmap != null;
            selectedBeatmap = entry;

            if (leftContent.Child is BeatmapDetailsPanel details)
            {
                details.UpdateBeatmap(entry.Beatmap, animateSwap: switchingBetweenBeatmaps);

                // Fetch and display progress data
                var beatmapId = UserProgressManager.GenerateBeatmapId(
                    entry.Path,
                    entry.Beatmap.Metadata.Title,
                    entry.Beatmap.Metadata.Artist);
                var progress = progressManager.GetProgress(beatmapId);
                details.UpdateProgress(progress);

                // Wire up favorite toggle
                details.ToggleFavoriteAction = () =>
                {
                    var newFavorite = progressManager.ToggleFavorite(beatmapId);
                    details.SetFavoriteStatus(newFavorite);
                };
            }

            // Play preview
            // currentTrack?.Stop();

            // Load background
            if (!string.IsNullOrEmpty(entry.Beatmap.Metadata.BackgroundFile))
            {
                string bgPath = Path.Combine(Path.GetDirectoryName(entry.Path)!, entry.Beatmap.Metadata.BackgroundFile);
                if (File.Exists(bgPath))
                {
                    try
                    {
                        using var stream = File.OpenRead(bgPath);
                        var texture = Texture.FromStream(renderer, stream);
                        backgroundSprite.Texture = texture;
                        backgroundSprite.FadeInFromZero(500);
                    }
                    catch
                    {
                        backgroundSprite.FadeOut(500);
                    }
                }
                else
                {
                    backgroundSprite.FadeOut(500);
                }
            }
            else
            {
                backgroundSprite.FadeOut(500);
            }

            // In a real implementation, we would load the track from the beatmap path.
            // For now, we'll just simulate or try to load if possible.
            // Since we don't have a robust track loader here yet, we will skip actual audio playback 
            // to avoid crashes, but the structure is here.
            // To fully implement, we need a TrackStore that can load from files.
            // var trackPath = Path.Combine(Path.GetDirectoryName(entry.Path), entry.Beatmap.Audio.Filename);
            // currentTrack = audio.Tracks.Get(trackPath); // This requires the track to be in the store.
        }

        private void openBeatmapInEditor(BeatmapLibrary.BeatmapEntry entry)
        {
            this.Push(new EditorScreen(entry.Path));
        }

        private void deleteBeatmap(BeatmapLibrary.BeatmapEntry entry)
        {
            // Show confirmation dialog before deleting
            var dialog = new ConfirmationDialog(
                title: "Delete Beatmap",
                message: $"Are you sure you want to delete \"{entry.Beatmap.Metadata.Title}\"?\n\nThis action cannot be undone.",
                confirmText: "Delete",
                cancelText: "Cancel",
                onConfirm: () => performDeleteBeatmap(entry),
                isDangerous: true
            );

            AddInternal(dialog);
            dialog.Show();
        }

        private void performDeleteBeatmap(BeatmapLibrary.BeatmapEntry entry)
        {
            try
            {
                if (File.Exists(entry.Path))
                {
                    File.Delete(entry.Path);
                    Logger.Log($"Deleted beatmap: {entry.Path}", LoggingTarget.Runtime, LogLevel.Important);

                    // Clear selection if the deleted beatmap was selected
                    if (selectedBeatmap == entry)
                    {
                        selectedBeatmap = null;
                    }

                    // Schedule the refresh on the main thread to ensure UI updates properly
                    Schedule(() =>
                    {
                        var beatmaps = BeatmapLibrary.GetAvailableBeatmaps();
                        carousel.SetBeatmaps(beatmaps);
                    });
                }
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to delete beatmap: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
            }
        }

        private void addBeatmapToCollection(BeatmapLibrary.BeatmapEntry entry)
        {
            var beatmapId = UserProgressManager.GenerateBeatmapId(
                entry.Path,
                entry.Beatmap.Metadata.Title,
                entry.Beatmap.Metadata.Artist);

            var collections = collectionManager.Collections;

            if (collections.Count == 0)
            {
                // Create a default collection if none exist
                var defaultCollection = collectionManager.CreateCollection("Favorites");
                collectionManager.AddToCollection(defaultCollection.Id, beatmapId);
                Logger.Log($"Created 'Favorites' collection and added: {entry.Beatmap.Metadata.Title}", LoggingTarget.Runtime, LogLevel.Important);
            }
            else
            {
                // For now, add to the first collection. A proper UI picker will be added later.
                var firstCollection = collections.First();
                collectionManager.AddToCollection(firstCollection.Id, beatmapId);
                Logger.Log($"Added to collection '{firstCollection.Name}': {entry.Beatmap.Metadata.Title}", LoggingTarget.Runtime, LogLevel.Important);
            }
        }

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);

            if (previewMode)
            {
                // Finish any animations from base class (like FadeInFromZero)
                this.FinishTransforms(true);
                this.Alpha = 1;

                // Ensure layout is correct
                leftContent.FinishTransforms(true);
                leftContent.Alpha = 1;
                leftContent.X = 0;

                carousel.FinishTransforms(true);
                carousel.Alpha = 1;
                carousel.X = 0;

                backButton.Alpha = 0;
                loadingOverlay.Hide();
                return;
            }

            // Animate left content (Details/Search)
            leftContent.MoveToX(-100).FadeInFromZero(500).MoveToX(0, 800, Easing.OutQuint);

            // Animate carousel
            carousel.MoveToX(100).FadeInFromZero(500).MoveToX(0, 800, Easing.OutQuint);
        }

        public override void OnSuspending(ScreenTransitionEvent e)
        {
            base.OnSuspending(e);
            // currentTrack?.Stop();
        }

        public override void OnResuming(ScreenTransitionEvent e)
        {
            base.OnResuming(e);
            loadingOverlay.Hide();
            if (selectedBeatmap != null)
                selectBeatmap(selectedBeatmap);
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (searchBox != null)
            {
                if (!searchBox.HasFocus)
                {
                    // Handle backspace when not focused
                    if (e.Key == osuTK.Input.Key.BackSpace && searchBox.Text.Length > 0)
                    {
                        searchBox.SetTextWithoutAnimation(searchBox.Text.Remove(searchBox.Text.Length - 1));
                        GetContainingFocusManager().ChangeFocus(searchBox);
                        return true;
                    }

                    // Handle text input manually since OnTextInput/TextInputEvent is causing issues
                    if (!e.ControlPressed && !e.AltPressed && !e.SuperPressed)
                    {
                        char? c = getCharFromKey(e.Key, e.ShiftPressed);
                        if (c.HasValue)
                        {
                            searchBox.FocusAndAppend(c.Value);
                            return true;
                        }
                    }
                }

                if (e.Key == osuTK.Input.Key.Escape && searchBox.Text.Length > 0)
                {
                    searchBox.Text = string.Empty;
                    return true;
                }
            }

            switch (e.Key)
            {
                case osuTK.Input.Key.Left:
                    if (searchBox == null || !searchBox.HasFocus)
                        return carousel.SelectPrevious();
                    break;

                case osuTK.Input.Key.Right:
                    if (searchBox == null || !searchBox.HasFocus)
                        return carousel.SelectNext();
                    break;

                case osuTK.Input.Key.Escape:
                    this.Exit();
                    return true;
            }
            return base.OnKeyDown(e);
        }

        private char? getCharFromKey(osuTK.Input.Key key, bool shift)
        {
            if (key >= osuTK.Input.Key.A && key <= osuTK.Input.Key.Z)
            {
                char c = (char)('a' + (key - osuTK.Input.Key.A));
                return shift ? char.ToUpper(c) : c;
            }
            if (key >= osuTK.Input.Key.Number0 && key <= osuTK.Input.Key.Number9)
            {
                if (shift)
                {
                    switch (key)
                    {
                        case osuTK.Input.Key.Number1: return '!';
                        case osuTK.Input.Key.Number2: return '@';
                        case osuTK.Input.Key.Number3: return '#';
                        case osuTK.Input.Key.Number4: return '$';
                        case osuTK.Input.Key.Number5: return '%';
                        case osuTK.Input.Key.Number6: return '^';
                        case osuTK.Input.Key.Number7: return '&';
                        case osuTK.Input.Key.Number8: return '*';
                        case osuTK.Input.Key.Number9: return '(';
                        case osuTK.Input.Key.Number0: return ')';
                    }
                }
                return (char)('0' + (key - osuTK.Input.Key.Number0));
            }
            if (key == osuTK.Input.Key.Space) return ' ';
            if (key == osuTK.Input.Key.Minus) return shift ? '_' : '-';
            if (key == osuTK.Input.Key.Period) return shift ? '>' : '.';
            if (key == osuTK.Input.Key.Comma) return shift ? '<' : ',';
            return null;
        }
        public void StartPlayback()
        {
            if (selectedBeatmap != null)
            {
                loadingOverlay.Show();
                Scheduler.AddDelayed(() =>
                {
                    this.Push(new PlaybackScreen(selectedBeatmap.Path));
                    loadingOverlay.Hide();
                }, 2000);
            }
        }

        private partial class BeatmapDetailsPanel : CompositeDrawable
        {
            public Action? CreateNewAction;
            public Action? ImportAudioAction;
            public Action? ToggleFavoriteAction;

            private readonly bool editorMode;
            private FillFlowContainer contentFlow = null!;

            // Details view
            private Container detailsContainer = null!;
            private TextFlowContainer title = null!;
            private TextFlowContainer artist = null!;
            private SpriteText creator = null!;
            private SpriteText difficulty = null!;
            private Container aiBadge = null!;
            private SpriteText confidenceText = null!;
            private SpriteText modelVersionText = null!;
            private SpriteText bpm = null!;
            private SpriteText duration = null!;
            private SpriteText source = null!;
            private SpriteText releaseDate = null!;
            private SpriteText tags = null!;
            private SpriteText provider = null!;
            private BeatSightButton actionButton = null!;

            // Progress tracking display
            private Container progressStatsContainer = null!;
            private SpriteText playCountText = null!;
            private SpriteText practiceTimeText = null!;
            private SpriteText lastPlayedText = null!;
            private SpriteText practiceHistoryTitleText = null!;
            private BeatSightButton favoriteButton = null!;
            private bool isFavorite;
            private FillFlowContainer emptyStateFlow = null!;
            private FillFlowContainer detailsMetaRowFlow = null!;
            private FillFlowContainer progressHistoryFlow = null!;
            private SpriteText aiBadgeText = null!;
            private readonly List<Container> detailsSpacers = new();

            // Empty view
            private Container emptyContainer = null!;
            private TextFlowContainer emptyPromptText = null!;
            private BeatSightButton createBeatmapButton = null!;
            private BeatSightButton importAudioButton = null!;
            private SpriteText emptyHintText = null!;
            private float lastResponsiveWidth = -1f;
            private float lastResponsiveHeight = -1f;

            public BeatmapDetailsPanel(bool editorMode)
            {
                this.editorMode = editorMode;
                RelativeSizeAxes = Axes.Both;
                var metrics = SongSelectResponsiveLayout.ComputeDetails(DrawWidth, DrawHeight);
                FillFlowContainer detailsMetaFlow;
                FillFlowContainer progressFlow;
                SpriteText aiBadgeLabel;

                InternalChildren = new Drawable[]
                {
                    emptyContainer = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Children = new Drawable[]
                        {
                            emptyStateFlow = new FillFlowContainer
                            {
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Vertical,
                                Anchor = Anchor.Centre,
                                Origin = Anchor.Centre,
                                Spacing = new Vector2(0, metrics.ContentSpacing * 1.8f),
                                Children = new Drawable[]
                                {
                                    emptyPromptText = new TextFlowContainer(t =>
                                    {
                                        t.Font = BeatSightFont.Title(24f);
                                        t.Colour = UITheme.TextSecondary;
                                    })
                                    {
                                        AutoSizeAxes = Axes.Both,
                                        Anchor = Anchor.Centre,
                                        Origin = Anchor.Centre,
                                        TextAnchor = Anchor.TopCentre,
                                        Text = editorMode ? "Select a beatmap to edit\nor create a new one" : "Select a song to play"
                                    },
                                    createBeatmapButton = new BeatSightButton
                                    {
                                        Text = "Create New Beatmap",
                                        Width = metrics.PrimaryButtonWidth,
                                        Height = metrics.PrimaryButtonHeight,
                                        FontSize = metrics.PrimaryButtonFontSize,
                                        BackgroundColour = UITheme.AccentPrimary,
                                        Action = () => CreateNewAction?.Invoke(),
                                        Alpha = editorMode ? 1 : 0,
                                        Anchor = Anchor.Centre,
                                        Origin = Anchor.Centre
                                    },
                                    importAudioButton = new BeatSightButton
                                    {
                                        Text = "Generate from Audio",
                                        Width = metrics.PrimaryButtonWidth,
                                        Height = metrics.PrimaryButtonHeight,
                                        FontSize = metrics.PrimaryButtonFontSize,
                                        BackgroundColour = UITheme.AccentSecondary,
                                        Action = () => ImportAudioAction?.Invoke(),
                                        Alpha = editorMode ? 1 : 0,
                                        Anchor = Anchor.Centre,
                                        Origin = Anchor.Centre
                                    },
                                    emptyHintText = new SpriteText
                                    {
                                        Text = "You can also drag & drop audio files",
                                        Font = BeatSightFont.Body(metrics.HintFontSize),
                                        Colour = UITheme.TextMuted,
                                        Anchor = Anchor.Centre,
                                        Origin = Anchor.Centre,
                                        Alpha = editorMode ? 1 : 0
                                    }
                                }
                            }
                        }
                    },
                    detailsContainer = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Alpha = 0, // Hidden initially
                        Child = contentFlow = new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Direction = FillDirection.Vertical,
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Spacing = new Vector2(0, metrics.ContentSpacing),
                            Children = new Drawable[]
                            {
                                title = new TextFlowContainer(t =>
                                {
                                    t.Font = BeatSightFont.Title(40f);
                                    t.Colour = UITheme.TextPrimary;
                                    t.Spacing = new Vector2(0.1f, 0f);
                                    t.UseFullGlyphHeight = true;
                                })
                                {
                                    RelativeSizeAxes = Axes.X,
                                    AutoSizeAxes = Axes.Y,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    TextAnchor = Anchor.TopCentre,
                                },
                                artist = new TextFlowContainer(t =>
                                {
                                    t.Font = BeatSightFont.Section(24f);
                                    t.Colour = UITheme.TextSecondary;
                                    t.Spacing = new Vector2(0.1f, 0f);
                                    t.UseFullGlyphHeight = true;
                                })
                                {
                                    RelativeSizeAxes = Axes.X,
                                    AutoSizeAxes = Axes.Y,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    TextAnchor = Anchor.TopCentre,
                                },
                                new Box { RelativeSizeAxes = Axes.X, Height = 2, Colour = UITheme.Divider, Margin = new MarginPadding { Vertical = 10 } },
                                creator = new SpriteText
                                {
                                    Font = BeatSightFont.Body(18f),
                                    Colour = UITheme.TextSecondary,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                detailsMetaFlow = new FillFlowContainer
                                {
                                    AutoSizeAxes = Axes.Both,
                                    Direction = FillDirection.Horizontal,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    Spacing = new Vector2(metrics.ContentSpacing * 2f, 0),
                                    Children = new Drawable[]
                                    {
                                        bpm = new SpriteText { Font = BeatSightFont.Body(18f), Colour = UITheme.TextPrimary },
                                        duration = new SpriteText { Font = BeatSightFont.Body(18f), Colour = UITheme.TextPrimary }
                                    }
                                },
                                difficulty = new SpriteText
                                {
                                    Font = BeatSightFont.Body(18f),
                                    Colour = UITheme.AccentWarning,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                aiBadge = new Container
                                {
                                    AutoSizeAxes = Axes.Both,
                                    Masking = true,
                                    CornerRadius = 4,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    Alpha = 0,
                                    Children = new Drawable[]
                                    {
                                        new Box { RelativeSizeAxes = Axes.Both, Colour = UITheme.AccentSecondary },
                                        aiBadgeLabel = new SpriteText
                                        {
                                            Text = "AI Generated",
                                            Font = BeatSightFont.Caption(12f),
                                            Colour = Color4.White,
                                            Padding = new MarginPadding { Horizontal = 8, Vertical = 2 }
                                        }
                                    }
                                },
                                confidenceText = new SpriteText
                                {
                                    Font = BeatSightFont.Caption(14f),
                                    Colour = UITheme.TextMuted,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                modelVersionText = new SpriteText
                                {
                                    Font = BeatSightFont.Caption(12f),
                                    Colour = UITheme.TextMuted,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    Alpha = 0.5f
                                },
                                source = new SpriteText
                                {
                                    Font = BeatSightFont.Body(16f),
                                    Colour = UITheme.TextSecondary,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                releaseDate = new SpriteText
                                {
                                    Font = BeatSightFont.Body(16f),
                                    Colour = UITheme.TextSecondary,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                tags = new SpriteText
                                {
                                    Font = BeatSightFont.Body(16f),
                                    Colour = UITheme.TextSecondary,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                provider = new SpriteText
                                {
                                    Font = BeatSightFont.Caption(14f),
                                    Colour = UITheme.TextMuted,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    Alpha = 0.7f
                                },
                                createSpacer(20), // Spacer
                                // Progress stats section
                                progressStatsContainer = new Container
                                {
                                    AutoSizeAxes = Axes.Both,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    Alpha = 0, // Hidden until we have progress data
                                    Child = progressFlow = new FillFlowContainer
                                    {
                                        AutoSizeAxes = Axes.Both,
                                        Direction = FillDirection.Vertical,
                                        Anchor = Anchor.TopCentre,
                                        Origin = Anchor.TopCentre,
                                        Spacing = new Vector2(0, metrics.ContentSpacing * 0.48f),
                                        Children = new Drawable[]
                                        {
                                            new Box { RelativeSizeAxes = Axes.X, Width = 0.6f, Height = 1, Colour = UITheme.Divider, Anchor = Anchor.TopCentre, Origin = Anchor.TopCentre },
                                            practiceHistoryTitleText = new SpriteText
                                            {
                                                Text = "Practice History",
                                                Font = BeatSightFont.Section(14f),
                                                Colour = UITheme.AccentSecondary,
                                                Anchor = Anchor.TopCentre,
                                                Origin = Anchor.TopCentre,
                                                Margin = new MarginPadding { Top = 8 }
                                            },
                                            playCountText = new SpriteText
                                            {
                                                Font = BeatSightFont.Body(14f),
                                                Colour = UITheme.TextSecondary,
                                                Anchor = Anchor.TopCentre,
                                                Origin = Anchor.TopCentre,
                                            },
                                            practiceTimeText = new SpriteText
                                            {
                                                Font = BeatSightFont.Body(14f),
                                                Colour = UITheme.TextSecondary,
                                                Anchor = Anchor.TopCentre,
                                                Origin = Anchor.TopCentre,
                                            },
                                            lastPlayedText = new SpriteText
                                            {
                                                Font = BeatSightFont.Body(14f),
                                                Colour = UITheme.TextMuted,
                                                Anchor = Anchor.TopCentre,
                                                Origin = Anchor.TopCentre,
                                            }
                                        }
                                    }
                                },
                                createSpacer(20), // Spacer
                                // Favorite button
                                favoriteButton = new BeatSightButton
                                {
                                    Text = "Add to Favorites",
                                    Width = metrics.SecondaryButtonWidth,
                                    Height = metrics.SecondaryButtonHeight,
                                    FontSize = metrics.SecondaryButtonFontSize,
                                    BackgroundColour = UITheme.SurfaceAlt,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    Action = () => ToggleFavoriteAction?.Invoke()
                                },
                                createSpacer(20), // Spacer
                                actionButton = new BeatSightButton
                                {
                                    Text = editorMode ? "Edit Beatmap" : "Play Beatmap",
                                    Width = metrics.PrimaryButtonWidth,
                                    Height = metrics.PrimaryButtonHeight,
                                    FontSize = metrics.PrimaryButtonFontSize,
                                    BackgroundColour = UITheme.AccentPrimary,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    Action = () => { /* Logic to start play/edit */ }
                                }
                            }
                        }
                    }
                };

                detailsMetaRowFlow = detailsMetaFlow;
                progressHistoryFlow = progressFlow;
                aiBadgeText = aiBadgeLabel;
            }

            private Container createSpacer(float height)
            {
                var spacer = new Container { Height = height };
                detailsSpacers.Add(spacer);
                return spacer;
            }

            protected override void Update()
            {
                base.Update();
                applyResponsiveLayout();
            }

            private void applyResponsiveLayout(bool force = false)
            {
                var viewport = resolveResponsiveViewport();
                if (viewport.X <= 0 || viewport.Y <= 0)
                    return;

                if (!force
                    && Math.Abs(viewport.X - lastResponsiveWidth) < 0.2f
                    && Math.Abs(viewport.Y - lastResponsiveHeight) < 0.2f)
                {
                    return;
                }

                var metrics = SongSelectResponsiveLayout.ComputeDetails(viewport.X, viewport.Y);

                if (createBeatmapButton != null)
                {
                    createBeatmapButton.Width = metrics.PrimaryButtonWidth;
                    createBeatmapButton.Height = metrics.PrimaryButtonHeight;
                    createBeatmapButton.FontSize = metrics.PrimaryButtonFontSize;
                }

                if (importAudioButton != null)
                {
                    importAudioButton.Width = metrics.PrimaryButtonWidth;
                    importAudioButton.Height = metrics.PrimaryButtonHeight;
                    importAudioButton.FontSize = metrics.PrimaryButtonFontSize;
                }

                if (favoriteButton != null)
                {
                    favoriteButton.Width = metrics.SecondaryButtonWidth;
                    favoriteButton.Height = metrics.SecondaryButtonHeight;
                    favoriteButton.FontSize = metrics.SecondaryButtonFontSize;
                }

                if (actionButton != null)
                {
                    actionButton.Width = metrics.PrimaryButtonWidth;
                    actionButton.Height = metrics.PrimaryButtonHeight;
                    actionButton.FontSize = metrics.PrimaryButtonFontSize;
                }

                if (emptyPromptText != null)
                    emptyPromptText.Scale = new Vector2(metrics.TitleScale);

                if (emptyHintText != null)
                    emptyHintText.Font = BeatSightFont.Body(metrics.HintFontSize);

                if (emptyStateFlow != null)
                    emptyStateFlow.Spacing = new Vector2(0, metrics.ContentSpacing * 1.8f);

                if (title != null)
                    title.Scale = new Vector2(metrics.TitleScale);

                if (artist != null)
                    artist.Scale = new Vector2(metrics.ArtistScale);

                if (contentFlow != null)
                    contentFlow.Spacing = new Vector2(0, metrics.ContentSpacing);

                if (detailsMetaRowFlow != null)
                    detailsMetaRowFlow.Spacing = new Vector2(metrics.ContentSpacing * 2f, 0);

                if (progressHistoryFlow != null)
                    progressHistoryFlow.Spacing = new Vector2(0, System.Math.Max(3f, metrics.ContentSpacing * 0.48f));

                foreach (var spacer in detailsSpacers)
                    spacer.Height = System.Math.Clamp(metrics.ContentSpacing * 1.9f, 14f, 24f);

                if (creator != null)
                    creator.Font = BeatSightFont.Body(metrics.BodyFontSize);

                if (difficulty != null)
                    difficulty.Font = BeatSightFont.Body(metrics.BodyFontSize);

                if (bpm != null)
                    bpm.Font = BeatSightFont.Body(metrics.BodyFontSize);

                if (duration != null)
                    duration.Font = BeatSightFont.Body(metrics.BodyFontSize);

                if (source != null)
                    source.Font = BeatSightFont.Body(metrics.BodyFontSize);

                if (releaseDate != null)
                    releaseDate.Font = BeatSightFont.Body(metrics.BodyFontSize);

                if (tags != null)
                    tags.Font = BeatSightFont.Body(metrics.BodyFontSize);

                if (provider != null)
                    provider.Font = BeatSightFont.Caption(metrics.CaptionFontSize);

                if (confidenceText != null)
                    confidenceText.Font = BeatSightFont.Caption(metrics.CaptionFontSize);

                if (modelVersionText != null)
                    modelVersionText.Font = BeatSightFont.Caption(metrics.CaptionFontSize);

                if (practiceHistoryTitleText != null)
                    practiceHistoryTitleText.Font = BeatSightFont.Section(metrics.CaptionFontSize + 0.8f);

                if (aiBadgeText != null)
                    aiBadgeText.Font = BeatSightFont.Caption(System.Math.Max(11.5f, metrics.CaptionFontSize - 0.2f));

                float historyBodyFont = System.Math.Max(12.4f, metrics.BodyFontSize - 1.2f);
                if (playCountText != null)
                    playCountText.Font = BeatSightFont.Body(historyBodyFont);
                if (practiceTimeText != null)
                    practiceTimeText.Font = BeatSightFont.Body(historyBodyFont);
                if (lastPlayedText != null)
                    lastPlayedText.Font = BeatSightFont.Body(System.Math.Max(12f, historyBodyFont - 0.4f));

                lastResponsiveWidth = viewport.X;
                lastResponsiveHeight = viewport.Y;
            }

            private Vector2 resolveResponsiveViewport()
                => ResponsiveLayout.ResolveViewport(
                    this,
                    DrawWidth > 0 ? DrawWidth : 640f,
                    DrawHeight > 0 ? DrawHeight : 1080f);

            public void UpdateBeatmap(Beatmap beatmap, bool animateSwap = false)
            {
                bool detailsAlreadyVisible = detailsContainer.Alpha > 0.01f && emptyContainer.Alpha < 0.99f;

                emptyContainer.ClearTransforms();
                detailsContainer.ClearTransforms();

                if (!detailsAlreadyVisible)
                {
                    emptyContainer.FadeOut(200);
                    detailsContainer.FadeIn(200);
                }

                title.Text = beatmap.Metadata.Title;
                artist.Text = beatmap.Metadata.Artist;
                creator.Text = $"Mapped by {beatmap.Metadata.Creator}";

                bpm.Text = $"BPM: {beatmap.Timing.Bpm:F0}";
                duration.Text = $"Length: {TimeSpan.FromMilliseconds(beatmap.Audio.Duration):mm\\:ss}";

                difficulty.Text = $"Difficulty: {beatmap.Metadata.Difficulty:F1} stars";

                var aiMeta = beatmap.Editor?.AiGenerationMetadata;
                if (aiMeta != null)
                {
                    aiBadge.Alpha = 1;
                    confidenceText.Text = aiMeta.Confidence.HasValue ? $"Confidence: {aiMeta.Confidence.Value:P0}" : "";
                    modelVersionText.Text = !string.IsNullOrEmpty(aiMeta.ModelVersion) ? $"Model: {aiMeta.ModelVersion}" : "";
                }
                else
                {
                    aiBadge.Alpha = 0;
                    confidenceText.Text = "";
                    modelVersionText.Text = "";
                }

                source.Text = string.IsNullOrEmpty(beatmap.Metadata.Source) ? "" : $"Source: {beatmap.Metadata.Source}";
                releaseDate.Text = string.IsNullOrEmpty(beatmap.Metadata.ReleaseDate) ? "" : $"Released: {beatmap.Metadata.ReleaseDate}";
                tags.Text = beatmap.Metadata.Tags.Count > 0 ? $"Tags: {string.Join(", ", beatmap.Metadata.Tags)}" : "";
                provider.Text = string.IsNullOrEmpty(beatmap.Metadata.Provider) ? "" : $"Provider: {beatmap.Metadata.Provider}";


                actionButton.Action = () =>
                {
                    if (this.FindClosestParent<SongSelectScreen>() is SongSelectScreen screen)
                    {
                        if (editorMode)
                            screen.Push(new EditorScreen(screen.selectedBeatmap?.Path));
                        else
                            screen.StartPlayback();
                    }
                };

                animateContentSwap(animateSwap || !detailsAlreadyVisible);
            }

            /// <summary>
            /// Updates the progress statistics display for the selected beatmap.
            /// </summary>
            public void UpdateProgress(SongProgress? progress)
            {
                if (progress == null || progress.PlayCount == 0)
                {
                    progressStatsContainer.Alpha = 0;
                    isFavorite = false;
                    updateFavoriteButton();
                    return;
                }

                progressStatsContainer.Alpha = 1;
                isFavorite = progress.IsFavorite;
                updateFavoriteButton();

                playCountText.Text = $"Sessions: {progress.PlayCount}";

                var totalTime = TimeSpan.FromMilliseconds(progress.TotalPlayTimeMs);
                if (totalTime.TotalHours >= 1)
                    practiceTimeText.Text = $"Total Practice: {totalTime.Hours}h {totalTime.Minutes}m";
                else if (totalTime.TotalMinutes >= 1)
                    practiceTimeText.Text = $"Total Practice: {totalTime.Minutes}m {totalTime.Seconds}s";
                else
                    practiceTimeText.Text = $"Total Practice: {totalTime.Seconds}s";

                if (progress.LastPlayedAt != default)
                {
                    var elapsed = DateTimeOffset.UtcNow - progress.LastPlayedAt;
                    if (elapsed.TotalDays >= 1)
                        lastPlayedText.Text = $"Last practiced: {(int)elapsed.TotalDays} days ago";
                    else if (elapsed.TotalHours >= 1)
                        lastPlayedText.Text = $"Last practiced: {(int)elapsed.TotalHours} hours ago";
                    else
                        lastPlayedText.Text = "Last practiced: recently";
                }
                else
                {
                    lastPlayedText.Text = "";
                }
            }

            private void updateFavoriteButton()
            {
                if (isFavorite)
                {
                    favoriteButton.Text = "Favorited";
                    favoriteButton.BackgroundColour = UITheme.AccentWarning;
                }
                else
                {
                    favoriteButton.Text = "Add to Favorites";
                    favoriteButton.BackgroundColour = UITheme.SurfaceAlt;
                }
            }

            private void animateContentSwap(bool animate)
            {
                contentFlow.ClearTransforms();

                if (!animate)
                {
                    contentFlow.X = 0;
                    contentFlow.Alpha = 1;
                    return;
                }

                contentFlow.X = -30;
                contentFlow.Alpha = 0;
                contentFlow.FadeIn(260, Easing.OutQuint);
                contentFlow.MoveToX(0, 260, Easing.OutQuint);
            }

            /// <summary>
            /// Called when favorite status changes externally.
            /// </summary>
            public void SetFavoriteStatus(bool favorite)
            {
                isFavorite = favorite;
                updateFavoriteButton();
            }
        }

        private void startNewProject(string? audioPath)
        {
            this.Push(new EditorScreen(audioPath));
        }

        private void importAudioAndGenerate()
        {
            // In a full implementation, this would open a native file picker.
            // For now, we rely on the Drag & Drop workflow which is fully implemented in BeatSightGame.
            // We can show a notification or just log.
            Logger.Log("Use Drag & Drop to import audio files.", LoggingTarget.Runtime, LogLevel.Important);

            // If we had a file path from a picker:
            // game.ImportAudio(path);
        }

        private Drawable createLeftArea()
        {
            leftContent = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Top = 120, Left = 40, Right = 20, Bottom = 40 }
            };

            var details = new BeatmapDetailsPanel(editorMode);
            details.CreateNewAction = () => startNewProject(null);
            details.ImportAudioAction = () => importAudioAndGenerate();
            leftContent.Child = details;

            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.SurfaceAlt
                    },
                    leftContent
                }
            };
        }

        private void updateBackgroundState()
        {
            if (rightAreaBackground == null) return;

            if (showGlobalBackground.Value)
            {
                // Invert opacity: 100% background opacity = 0% overlay opacity
                rightAreaBackground.Alpha = 1.0f - (float)globalBackgroundOpacity.Value;
            }
            else
            {
                rightAreaBackground.Alpha = 1.0f;
            }
        }

        private Drawable createRightArea()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    rightAreaBackground = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.BackgroundLayer
                    },
                    rightContentContainer = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Top = 100, Bottom = 0, Right = 0 },
                        Child = carousel = new BeatmapCarousel
                        {
                            BeatmapSelected = selectBeatmap,
                            OpenInEditorRequested = openBeatmapInEditor,
                            DeleteRequested = deleteBeatmap,
                            AddToCollectionRequested = addBeatmapToCollection
                        }
                    }
                }
            };
        }

        private Drawable createHeader()
        {
            var metrics = SongSelectResponsiveLayout.ComputeScreen(DrawWidth, DrawHeight);

            searchBox = new SearchTextBox
            {
                Height = metrics.HeaderControlHeight,
                Width = metrics.SearchWidth,
                FontSize = System.Math.Clamp(metrics.HeaderControlHeight * 0.45f, 16f, 22f),
                TextSize = System.Math.Clamp(metrics.HeaderControlHeight * 0.45f, 16f, 22f),
                PlaceholderText = "Search...",
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
            };

            searchBox.OnCommit += (sender, newText) => carousel.Filter(searchBox.Text);
            searchBox.Current.BindValueChanged(e => carousel.Filter(e.NewValue));

            sortDropdown = new BeatSight.Game.UI.Components.Dropdown<BeatmapCarousel.SortMode>
            {
                Width = metrics.SortWidth,
                Items = Enum.GetValues(typeof(BeatmapCarousel.SortMode)).Cast<BeatmapCarousel.SortMode>(),
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
            };

            sortDropdown.Current.BindValueChanged(e => carousel.Sort(e.NewValue));

            genreDropdown = new BeatSight.Game.UI.Components.Dropdown<string>
            {
                Width = metrics.GenreWidth,
                Items = new[] { "All", "Pop", "Rock", "Hip-Hop", "Electronic" }, // Example genres
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
            };

            genreDropdown.Current.BindValueChanged(e =>
            {
                string val = e.NewValue == "All" ? "" : e.NewValue;
                carousel.SetGenreFilter(val);
            });

            confidenceFilter = new BeatSightCheckbox
            {
                LabelText = "High Confidence Only",
                LabelFontSize = metrics.HeaderFilterLabelSize,
                Padding = new MarginPadding { Right = 6 },
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Scale = Vector2.One,
            };

            confidenceFilter.Current.BindValueChanged(e => carousel.SetConfidenceFilter(e.NewValue ? 0.8 : 0.0));

            favoritesFilter = new BeatSightCheckbox
            {
                LabelText = "Favorites",
                LabelFontSize = metrics.HeaderFilterLabelSize,
                Padding = new MarginPadding { Right = 6 },
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Scale = Vector2.One,
            };

            favoritesFilter.Current.BindValueChanged(e =>
            {
                if (e.NewValue)
                {
                    carousel.SetCustomFilter(entry =>
                    {
                        var beatmapId = UserProgressManager.GenerateBeatmapId(
                            entry.Path,
                            entry.Beatmap.Metadata.Title,
                            entry.Beatmap.Metadata.Artist);
                        var progress = progressManager.GetProgress(beatmapId);
                        return progress?.IsFavorite == true;
                    });
                }
                else
                {
                    carousel.SetCustomFilter(null);
                }
            });

            randomButton = new BeatSightButton
            {
                Text = "Random",
                Width = metrics.RandomWidth,
                Height = metrics.HeaderControlHeight,
                FontSize = metrics.HeaderButtonFontSize,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Action = () => carousel.SelectRandom()
            };

            var filterToggleRow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Spacing = new Vector2(metrics.HeaderFilterSpacing, 0f),
                Children = new Drawable[]
                {
                    confidenceFilter,
                    favoritesFilter
                }
            };
            headerFilterToggleRow = filterToggleRow;

            var controlsFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Spacing = new Vector2(metrics.HeaderControlSpacing, 0),
                Children = new Drawable[]
                {
                    randomButton,
                    filterToggleRow,
                    genreDropdown,
                    searchBox,
                    sortDropdown
                }
            };

            var controlsScroll = new BeatSightScrollContainer(Direction.Horizontal)
            {
                RelativeSizeAxes = Axes.Both,
                ScrollbarVisible = false,
                Child = new Container
                {
                    RelativeSizeAxes = Axes.Y,
                    AutoSizeAxes = Axes.X,
                    Anchor = Anchor.CentreRight,
                    Origin = Anchor.CentreRight,
                    Child = controlsFlow
                }
            };
            headerControlsFlow = controlsFlow;

            return headerContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = metrics.HeaderHeight,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface,
                        Alpha = 1f
                    },
                    headerContentContainer = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = resolveHeaderPadding(metrics, resolveResponsiveViewport()),
                        Child = controlsScroll
                    }
                }
            };
        }

        protected override void Update()
        {
            base.Update();
            applyResponsiveLayout();
        }

        private void applyResponsiveLayout(bool force = false)
        {
            if (mainLayoutGrid == null || headerContainer == null || leftContent == null || rightContentContainer == null)
                return;

            var viewport = resolveResponsiveViewport();
            if (viewport.X <= 0 || viewport.Y <= 0)
                return;

            var metrics = SongSelectResponsiveLayout.ComputeScreen(viewport.X, viewport.Y);

            if (force || Math.Abs(metrics.LeftColumnWidth - lastLeftColumnWidth) > 0.2f)
            {
                mainLayoutGrid.ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, metrics.LeftColumnWidth),
                    new Dimension()
                };
                lastLeftColumnWidth = metrics.LeftColumnWidth;
            }

            if (force || Math.Abs(metrics.HeaderHeight - lastHeaderHeight) > 0.2f)
            {
                headerContainer.Height = metrics.HeaderHeight;
                lastHeaderHeight = metrics.HeaderHeight;
            }

            leftContent.Padding = new MarginPadding
            {
                Top = metrics.LeftTopPadding,
                Left = metrics.HorizontalInset,
                Right = Math.Max(12f, metrics.HorizontalInset * 0.55f),
                Bottom = metrics.BottomPadding
            };

            rightContentContainer.Padding = new MarginPadding
            {
                Top = metrics.RightTopPadding,
                Bottom = 0,
                Right = 0
            };

            if (searchBox != null)
            {
                searchBox.Height = metrics.HeaderControlHeight;
                searchBox.Width = metrics.SearchWidth;
                float searchFont = Math.Clamp(metrics.HeaderControlHeight * 0.45f, 16f, 22f);
                searchBox.TextSize = searchFont;
            }

            if (sortDropdown != null)
            {
                sortDropdown.Width = metrics.SortWidth;
            }

            if (genreDropdown != null)
            {
                genreDropdown.Width = metrics.GenreWidth;
            }

            if (randomButton != null)
            {
                randomButton.Height = metrics.HeaderControlHeight;
                randomButton.Width = metrics.RandomWidth;
                randomButton.FontSize = metrics.HeaderButtonFontSize;
            }

            if (confidenceFilter != null)
                confidenceFilter.LabelFontSize = metrics.HeaderFilterLabelSize;

            if (favoritesFilter != null)
                favoritesFilter.LabelFontSize = metrics.HeaderFilterLabelSize;

            if (headerFilterToggleRow != null)
                headerFilterToggleRow.Spacing = new Vector2(metrics.HeaderFilterSpacing, 0);

            if (headerControlsFlow != null)
                headerControlsFlow.Spacing = new Vector2(metrics.HeaderControlSpacing, 0);

            if (headerContentContainer != null)
                headerContentContainer.Padding = resolveHeaderPadding(metrics, viewport);
        }

        private MarginPadding resolveHeaderPadding(SongSelectScreenLayoutMetrics metrics, Vector2 viewport)
        {
            float fallbackButtonHeight = ResponsiveLayout.ClampFraction(viewport.Y, 0.05f, 38f, 58f);
            float fallbackButtonWidth = Math.Clamp(fallbackButtonHeight * 2.72f, 106f, 156f);
            // Use layout width instead of draw width to avoid hover/transform jitter shifting header controls.
            float buttonWidth = backButton?.Width > 1f ? backButton.Width : fallbackButtonWidth;
            float leftMargin = backButton?.Margin.Left > 0 ? backButton.Margin.Left : BackButton.DefaultMargin.Left;
            float clearance = ResponsiveLayout.ClampFraction(viewport.X, 0.008f, 10f, 22f);
            float reservedLeft = leftMargin + buttonWidth + clearance;

            return new MarginPadding
            {
                Left = Math.Max(metrics.HeaderContentPadding, reservedLeft),
                Right = metrics.HeaderContentPadding
            };
        }

        private Vector2 resolveResponsiveViewport()
            => ResponsiveLayout.ResolveViewport(
                this,
                DrawWidth > 0 ? DrawWidth : 1920f,
                DrawHeight > 0 ? DrawHeight : 1080f);
    }
}
