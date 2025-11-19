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

namespace BeatSight.Game.Screens.SongSelect
{
    public partial class SongSelectScreen : Screen
    {
        private readonly bool editorMode;
        private BeatmapCarousel carousel = null!;
        private Container leftContent = null!;
        private BackButton backButton = null!;
        private BeatmapLibrary.BeatmapEntry? selectedBeatmap;
        private BasicTextBox searchBox = null!;
        private BeatSight.Game.UI.Components.Dropdown<BeatmapCarousel.SortMode> sortDropdown = null!;

        public SongSelectScreen(bool editorMode = false)
        {
            this.editorMode = editorMode;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Background
                },
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
                },
                new SafeAreaContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = BackButton.DefaultMargin,
                    Child = backButton = new BackButton
                    {
                        Action = () => this.Exit()
                    }
                }
            };

            populateBeatmaps();
        }

        private Drawable createLeftArea()
        {
            leftContent = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Top = 80, Left = 40, Right = 20, Bottom = 40 }
            };

            if (editorMode)
            {
                leftContent.Child = new DropZone
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Action = onFileDropped
                };
            }
            else
            {
                // Play mode: Show details of selected beatmap
                leftContent.Child = new BeatmapDetailsPanel();
            }

            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface.Opacity(0.5f)
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
                        Padding = new MarginPadding { Top = 100, Bottom = 0, Right = 0 }, // Top padding for header
                        Child = carousel = new BeatmapCarousel
                        {
                            BeatmapSelected = selectBeatmap
                        }
                    },
                    createHeader() // Overlay header on top right
                }
            };
        }

        private Drawable createHeader()
        {
            searchBox = new BasicTextBox
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

        private void populateBeatmaps()
        {
            var beatmaps = BeatmapLibrary.GetAvailableBeatmaps();
            carousel.SetBeatmaps(beatmaps);
        }

        private void selectBeatmap(BeatmapLibrary.BeatmapEntry entry)
        {
            selectedBeatmap = entry;

            if (!editorMode)
            {
                if (leftContent.Child is BeatmapDetailsPanel details)
                {
                    details.UpdateBeatmap(entry.Beatmap);
                }

                // In a real scenario, we might want to wait for a "Play" button click
                // But for now, let's just update details. 
                // To actually play, maybe double click or a play button in details?
                // Let's add a Play button to the details panel.
            }
            else
            {
                this.Push(new EditorScreen(entry.Path));
            }
        }

        private void onFileDropped(string path)
        {
            this.Push(new EditorScreen(null));
        }

        private partial class BeatmapDetailsPanel : CompositeDrawable
        {
            private SpriteText title = null!;
            private SpriteText artist = null!;
            private SpriteText creator = null!;
            private SpriteText difficulty = null!;
            private SpriteText bpm = null!;
            private SpriteText duration = null!;

            private BeatSightButton playButton = null!;

            public BeatmapDetailsPanel()
            {
                RelativeSizeAxes = Axes.Both;

                InternalChild = new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, 10),
                    Children = new Drawable[]
                    {
                        title = new SpriteText
                        {
                            Font = BeatSightFont.Title(40f),
                            Colour = UITheme.TextPrimary,
                            AllowMultiline = true,
                            RelativeSizeAxes = Axes.X
                        },
                        artist = new SpriteText
                        {
                            Font = BeatSightFont.Section(24f),
                            Colour = UITheme.TextSecondary,
                            AllowMultiline = true,
                            RelativeSizeAxes = Axes.X
                        },
                        new Box { RelativeSizeAxes = Axes.X, Height = 2, Colour = UITheme.Divider, Margin = new MarginPadding { Vertical = 10 } },
                        creator = new SpriteText
                        {
                            Font = BeatSightFont.Body(18f),
                            Colour = UITheme.TextMuted
                        },
                        new FillFlowContainer
                        {
                            AutoSizeAxes = Axes.Both,
                            Direction = FillDirection.Horizontal,
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
                            Colour = UITheme.AccentWarning
                        },
                        new Container { Height = 40 }, // Spacer
                        playButton = new BeatSightButton
                        {
                            Text = "Play Beatmap",
                            Width = 200,
                            Height = 50,
                            BackgroundColour = UITheme.AccentPrimary,
                            Action = () => { /* Logic to start play */ },
                            Alpha = 0 // Hidden until beatmap selected
                        }
                    }
                };
            }

            public void UpdateBeatmap(Beatmap beatmap)
            {
                title.Text = beatmap.Metadata.Title;
                artist.Text = beatmap.Metadata.Artist;
                creator.Text = $"Mapped by {beatmap.Metadata.Creator}";

                // Assuming BPM and Duration are available or calculable
                bpm.Text = $"BPM: {beatmap.Timing.Bpm:F0}";
                duration.Text = $"Length: {TimeSpan.FromMilliseconds(beatmap.Audio.Duration):mm\\:ss}";

                difficulty.Text = $"Difficulty: {beatmap.Metadata.Difficulty:F1} stars";

                playButton.Alpha = 1;
                playButton.Action = () =>
                {
                    // Find parent screen and push playback
                    if (this.FindClosestParent<SongSelectScreen>() is SongSelectScreen screen)
                    {
                        screen.StartPlayback();
                    }
                };
            }
        }

        public void StartPlayback()
        {
            if (selectedBeatmap != null)
            {
                this.Push(new PlaybackScreen(selectedBeatmap.Path));
            }
        }

        private partial class DropZone : Container
        {
            public Action<string>? Action;

            public DropZone()
            {
                Masking = true;
                CornerRadius = 20;
                BorderColour = UITheme.AccentPrimary;
                BorderThickness = 4;

                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface.Opacity(0.2f)
                    },
                    new SpriteText
                    {
                        Text = "Drop Audio File Here\nto create new beatmap",
                        Font = BeatSightFont.Title(24f),
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Colour = UITheme.TextPrimary
                    }
                };
            }
        }
    }
}
