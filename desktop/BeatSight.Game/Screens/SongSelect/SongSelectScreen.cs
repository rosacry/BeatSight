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
        private BeatmapCarousel carousel = null!;
        private Container leftContent = null!;
        private BeatmapLibrary.BeatmapEntry? selectedBeatmap;
        private BeatSightTextBox searchBox = null!;
        private BeatSight.Game.UI.Components.Dropdown<BeatmapCarousel.SortMode> sortDropdown = null!;
        private Box backgroundDim = null!;
        private Sprite backgroundSprite = null!;
        private BackButton backButton = null!;

        public SongSelectScreen(bool editorMode = false)
        {
            this.editorMode = editorMode;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            backButton = new BackButton
            {
                Action = this.Exit,
                Margin = BackButton.DefaultMargin
            };

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Background
                },
                backgroundSprite = new Sprite
                {
                    RelativeSizeAxes = Axes.Both,
                    FillMode = FillMode.Fill,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Alpha = 0.5f
                },
                backgroundDim = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Black,
                    Alpha = 0.6f // Darker dim for better readability
                },
                new SafeAreaContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Child = new GridContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        RowDimensions = new[]
                        {
                            new Dimension(GridSizeMode.Distributed), // Main content
                            new Dimension(GridSizeMode.Absolute, 60) // Footer
                        },
                        Content = new[]
                        {
                            new Drawable[]
                            {
                                new GridContainer
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    ColumnDimensions = new[]
                                    {
                                        new Dimension(GridSizeMode.Relative, 0.4f), // Left side (Details / Drop)
                                        new Dimension(GridSizeMode.Relative, 0.6f)  // Right side (Carousel)
                                    },
                                    Content = new[]
                                    {
                                        new Drawable[]
                                        {
                                            createLeftArea(),
                                            createRightArea()
                                        }
                                    }
                                }
                            },
                            new Drawable[]
                            {
                                createFooter()
                            }
                        }
                    }
                },
                new SafeAreaContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = BackButton.DefaultMargin,
                    Child = backButton
                }
            };

            populateBeatmaps();
        }

        private Drawable createFooter()
        {
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
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(10),
                        Padding = new MarginPadding { Horizontal = 20 },
                        Children = new Drawable[]
                        {
                            new BeatSightButton
                            {
                                Text = "Random (F2)",
                                Width = 150,
                                Height = 40,
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Action = selectRandom
                            },
                            new BeatSightButton
                            {
                                Text = "Options",
                                Width = 120,
                                Height = 40,
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Action = () => { /* TODO: Options overlay */ }
                            }
                        }
                    }
                }
            };
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
        }

        public override void OnSuspending(ScreenTransitionEvent e)
        {
            base.OnSuspending(e);
            // currentTrack?.Stop();
        }

        public override void OnResuming(ScreenTransitionEvent e)
        {
            base.OnResuming(e);
            if (selectedBeatmap != null)
                selectBeatmap(selectedBeatmap);
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            switch (e.Key)
            {
                case osuTK.Input.Key.Escape:
                    this.Exit();
                    return true;
                case osuTK.Input.Key.F2:
                    selectRandom();
                    return true;
            }
            return base.OnKeyDown(e);
        }

        private void selectRandom()
        {
            carousel.SelectRandom();
        }

        public void StartPlayback()
        {
            if (selectedBeatmap != null)
            {
                this.Push(new PlaybackScreen(selectedBeatmap.Path));
            }
        }

        private partial class BeatmapDetailsPanel : CompositeDrawable
        {
            public Action? CreateNewAction;

            private readonly bool editorMode;
            private FillFlowContainer contentFlow = null!;

            // Details view
            private Container detailsContainer = null!;
            private SpriteText title = null!;
            private SpriteText artist = null!;
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
                                title = new SpriteText
                                {
                                    Font = BeatSightFont.Title(40f),
                                    Colour = UITheme.TextPrimary,
                                    AllowMultiline = true,
                                    RelativeSizeAxes = Axes.X,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
                                },
                                artist = new SpriteText
                                {
                                    Font = BeatSightFont.Section(24f),
                                    Colour = UITheme.TextSecondary,
                                    AllowMultiline = true,
                                    RelativeSizeAxes = Axes.X,
                                    Anchor = Anchor.TopCentre,
                                    Origin = Anchor.TopCentre,
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
                Padding = new MarginPadding { Top = 80, Left = 40, Right = 20, Bottom = 40 }
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
                        Colour = UITheme.Surface.Opacity(0.95f)
                    },
                    leftContent
                }
            };
        }

        private Drawable createRightArea()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    new Box
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
                    },
                    createHeader()
                }
            };
        }

        private Drawable createHeader()
        {
            searchBox = new BeatSightTextBox
            {
                Height = 40,
                Width = 300,
                PlaceholderText = "Search...",
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Margin = new MarginPadding { Right = 20 }
            };

            searchBox.OnCommit += (sender, newText) => carousel.Filter(searchBox.Text);
            searchBox.Current.BindValueChanged(e => carousel.Filter(e.NewValue));

            sortDropdown = new BeatSight.Game.UI.Components.Dropdown<BeatmapCarousel.SortMode>
            {
                Width = 150,
                Items = Enum.GetValues(typeof(BeatmapCarousel.SortMode)).Cast<BeatmapCarousel.SortMode>(),
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Margin = new MarginPadding { Right = 20 }
            };

            sortDropdown.Current.BindValueChanged(e => carousel.Sort(e.NewValue));

            return new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 100,
                Padding = new MarginPadding { Horizontal = 40, Vertical = 20 },
                Children = new Drawable[]
                {
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        Spacing = new Vector2(20, 0),
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = editorMode ? "Editor Selection" : "Song Selection",
                                Font = BeatSightFont.Title(32f),
                                Colour = UITheme.TextPrimary,
                                Anchor = Anchor.CentreRight,
                                Origin = Anchor.CentreRight
                            },
                            sortDropdown,
                            searchBox
                        }
                    }
                }
            };
        }
    }
}
