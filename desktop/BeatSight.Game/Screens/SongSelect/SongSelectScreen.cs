using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using BeatSight.Game.Beatmaps;
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
using BeatSight.Game.Configuration;

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

        private readonly bool editorMode;
        private readonly bool previewMode;
        private BeatmapCarousel carousel = null!;
        private Container leftContent = null!;
        private BeatmapLibrary.BeatmapEntry? selectedBeatmap;
        private SearchTextBox searchBox = null!;
        private BeatSight.Game.UI.Components.Dropdown<BeatmapCarousel.SortMode> sortDropdown = null!;
        private Box backgroundDim = null!;
        private Sprite backgroundSprite = null!;
        private BackButton backButton = null!;
        private LoadingOverlay loadingOverlay = null!;

        private Bindable<bool> showGlobalBackground = null!;
        private Bindable<double> globalBackgroundOpacity = null!;
        private Box rightAreaBackground = null!;

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
                        new GridContainer
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
                        },
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
        }

        private void selectBeatmap(BeatmapLibrary.BeatmapEntry entry)
        {
            if (selectedBeatmap == entry) return;

            selectedBeatmap = entry;

            if (leftContent.Child is BeatmapDetailsPanel details)
            {
                details.UpdateBeatmap(entry.Beatmap);
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

            private readonly bool editorMode;
            private FillFlowContainer contentFlow = null!;

            // Details view
            private Container detailsContainer = null!;
            private TextFlowContainer title = null!;
            private TextFlowContainer artist = null!;
            private SpriteText creator = null!;
            private SpriteText difficulty = null!;
            private SpriteText bpm = null!;
            private SpriteText duration = null!;
            private BeatSightButton actionButton = null!;

            // Empty view
            private Container emptyContainer = null!;

            public BeatmapDetailsPanel(bool editorMode)
            {
                this.editorMode = editorMode;
                RelativeSizeAxes = Axes.Both;

                InternalChildren = new Drawable[]
                {
                    emptyContainer = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Children = new Drawable[]
                        {
                            new FillFlowContainer
                            {
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Vertical,
                                Anchor = Anchor.Centre,
                                Origin = Anchor.Centre,
                                Spacing = new Vector2(0, 20),
                                Children = new Drawable[]
                                {
                                    new TextFlowContainer(t =>
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
                                    new BeatSightButton
                                    {
                                        Text = "Create New Beatmap",
                                        Width = 250,
                                        Height = 50,
                                        BackgroundColour = UITheme.AccentPrimary,
                                        Action = () => CreateNewAction?.Invoke(),
                                        Alpha = editorMode ? 1 : 0,
                                        Anchor = Anchor.Centre,
                                        Origin = Anchor.Centre
                                    },
                                    new SpriteText
                                    {
                                        Text = "You can also drag & drop audio files",
                                        Font = BeatSightFont.Body(16f),
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
                            Spacing = new Vector2(0, 10),
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
                                    Colour = UITheme.TextMuted,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                new FillFlowContainer
                                {
                                    AutoSizeAxes = Axes.Both,
                                    Direction = FillDirection.Horizontal,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    Spacing = new Vector2(20, 0),
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
                                new Container { Height = 40 }, // Spacer
                                actionButton = new BeatSightButton
                                {
                                    Text = editorMode ? "Edit Beatmap" : "Play Beatmap",
                                    Width = 200,
                                    Height = 50,
                                    BackgroundColour = UITheme.AccentPrimary,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                    Action = () => { /* Logic to start play/edit */ }
                                }
                            }
                        }
                    }
                };
            }

            public void UpdateBeatmap(Beatmap beatmap)
            {
                emptyContainer.FadeOut(200);
                detailsContainer.FadeIn(200);

                title.Text = beatmap.Metadata.Title;
                artist.Text = beatmap.Metadata.Artist;
                creator.Text = $"Mapped by {beatmap.Metadata.Creator}";

                bpm.Text = $"BPM: {beatmap.Timing.Bpm:F0}";
                duration.Text = $"Length: {TimeSpan.FromMilliseconds(beatmap.Audio.Duration):mm\\:ss}";

                difficulty.Text = $"Difficulty: {beatmap.Metadata.Difficulty:F1} stars";

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
            }
        }

        private void startNewProject(string? audioPath)
        {
            this.Push(new EditorScreen(audioPath));
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
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Top = 100, Bottom = 0, Right = 0 },
                        Child = carousel = new BeatmapCarousel
                        {
                            BeatmapSelected = selectBeatmap
                        }
                    }
                }
            };
        }

        private Drawable createHeader()
        {
            searchBox = new SearchTextBox
            {
                Height = 40,
                Width = 300,
                PlaceholderText = "Search...",
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
            };

            searchBox.OnCommit += (sender, newText) => carousel.Filter(searchBox.Text);
            searchBox.Current.BindValueChanged(e => carousel.Filter(e.NewValue));

            sortDropdown = new BeatSight.Game.UI.Components.Dropdown<BeatmapCarousel.SortMode>
            {
                Width = 150,
                Items = Enum.GetValues(typeof(BeatmapCarousel.SortMode)).Cast<BeatmapCarousel.SortMode>(),
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
            };

            sortDropdown.Current.BindValueChanged(e => carousel.Sort(e.NewValue));

            return new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 100,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface,
                        Alpha = 1f
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 40 },
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = editorMode ? "EDITOR" : "PLAYBACK",
                                Font = BeatSightFont.Title(40f),
                                Colour = UITheme.AccentPrimary,
                                Anchor = Anchor.Centre,
                                Origin = Anchor.Centre,
                            },
                            new FillFlowContainer
                            {
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Horizontal,
                                Anchor = Anchor.CentreRight,
                                Origin = Anchor.CentreRight,
                                Spacing = new Vector2(20, 0),
                                Children = new Drawable[]
                                {
                                    sortDropdown,
                                    searchBox
                                }
                            }
                        }
                    }
                }
            };
        }
    }
}
