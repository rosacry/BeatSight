// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using osu.Framework.Allocation;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// A stylized track preview card with album art, waveform, and playback controls.
    /// </summary>
    public partial class TrackPreviewCard : CompositeDrawable
    {
        /// <summary>
        /// Event fired when play/pause is toggled.
        /// </summary>
        public event Action<bool>? OnPlayPauseToggled;

        /// <summary>
        /// Event fired when the track is selected.
        /// </summary>
        public event Action? OnTrackSelected;

        /// <summary>
        /// Track title.
        /// </summary>
        public string Title { get; set; } = "Unknown Track";

        /// <summary>
        /// Artist name.
        /// </summary>
        public string Artist { get; set; } = "Unknown Artist";

        /// <summary>
        /// Track duration in milliseconds.
        /// </summary>
        public double Duration { get; set; } = 180000;

        /// <summary>
        /// Current playback progress (0-1).
        /// </summary>
        public float Progress
        {
            get => progress;
            set
            {
                progress = Math.Clamp(value, 0f, 1f);
                updateProgress();
            }
        }

        /// <summary>
        /// Whether the track is currently playing.
        /// </summary>
        public bool IsPlaying
        {
            get => isPlaying;
            set
            {
                isPlaying = value;
                updatePlayState();
            }
        }

        /// <summary>
        /// BPM of the track.
        /// </summary>
        public float BPM { get; set; } = 120;

        /// <summary>
        /// Difficulty rating (0-10).
        /// </summary>
        public float Difficulty { get; set; } = 5;

        private float progress;
        private bool isPlaying;
        private bool isHovered;

        private Container albumArtContainer = null!;
        private SpriteText titleText = null!;
        private SpriteText artistText = null!;
        private SpriteText durationText = null!;
        private Container playButton = null!;
        private SpriteIcon playIcon = null!;
        private Box progressBar = null!;
        private FillFlowContainer statsContainer = null!;
        private Container hoverOverlay = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            Size = new Vector2(320, 180);

            InternalChildren = new Drawable[]
            {
                // Card background with glow
                new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 16,
                    EdgeEffect = new EdgeEffectParameters
                    {
                        Type = EdgeEffectType.Shadow,
                        Colour = Color4.Black.Opacity(0.3f),
                        Radius = 12,
                        Offset = new Vector2(0, 4),
                    },
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4Extensions.FromHex("1f2937"),
                    }
                },

                // Content
                new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Direction = FillDirection.Horizontal,
                    Padding = new MarginPadding(12),
                    Spacing = new Vector2(12, 0),
                    Children = new Drawable[]
                    {
                        // Album art
                        albumArtContainer = new Container
                        {
                            Size = new Vector2(156),
                            Masking = true,
                            CornerRadius = 12,
                            Children = new Drawable[]
                            {
                                // Placeholder gradient
                                new Box
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Colour = Color4Extensions.FromHex("374151"),
                                },
                                // Gradient overlay
                                new Box
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Colour = ColourInfo.GradientVertical(
                                        Color4.Transparent,
                                        Color4.Black.Opacity(0.5f)
                                    ),
                                },
                                // Music icon placeholder
                                new SpriteIcon
                                {
                                    Size = new Vector2(48),
                                    Anchor = Anchor.Centre,
                                    Origin = Anchor.Centre,
                                    Icon = FontAwesome.Solid.Music,
                                    Colour = Color4Extensions.FromHex("6b7280"),
                                },
                                // Play button overlay
                                playButton = new Container
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Alpha = 0,
                                    Children = new Drawable[]
                                    {
                                        new Box
                                        {
                                            RelativeSizeAxes = Axes.Both,
                                            Colour = Color4.Black.Opacity(0.5f),
                                        },
                                        new Container
                                        {
                                            Size = new Vector2(56),
                                            Anchor = Anchor.Centre,
                                            Origin = Anchor.Centre,
                                            Masking = true,
                                            CornerRadius = 28,
                                            EdgeEffect = new EdgeEffectParameters
                                            {
                                                Type = EdgeEffectType.Glow,
                                                Colour = Color4Extensions.FromHex("0ea5e980"),
                                                Radius = 16,
                                            },
                                            Children = new Drawable[]
                                            {
                                                new Box
                                                {
                                                    RelativeSizeAxes = Axes.Both,
                                                    Colour = Color4Extensions.FromHex("0ea5e9"),
                                                },
                                                playIcon = new SpriteIcon
                                                {
                                                    Size = new Vector2(24),
                                                    Anchor = Anchor.Centre,
                                                    Origin = Anchor.Centre,
                                                    Icon = FontAwesome.Solid.Play,
                                                    Colour = Color4.White,
                                                    X = 2, // Visual balance for play icon
                                                }
                                            }
                                        }
                                    }
                                },
                                // Progress bar at bottom
                                new Container
                                {
                                    RelativeSizeAxes = Axes.X,
                                    Height = 4,
                                    Anchor = Anchor.BottomLeft,
                                    Origin = Anchor.BottomLeft,
                                    Children = new Drawable[]
                                    {
                                        new Box
                                        {
                                            RelativeSizeAxes = Axes.Both,
                                            Colour = Color4.Black.Opacity(0.5f),
                                        },
                                        progressBar = new Box
                                        {
                                            RelativeSizeAxes = Axes.Y,
                                            Width = 0,
                                            Colour = Color4Extensions.FromHex("0ea5e9"),
                                        }
                                    }
                                }
                            }
                        },

                        // Track info
                        new FillFlowContainer
                        {
                            AutoSizeAxes = Axes.Both,
                            Direction = FillDirection.Vertical,
                            Spacing = new Vector2(0, 4),
                            Children = new Drawable[]
                            {
                                titleText = new SpriteText
                                {
                                    Text = Title,
                                    Font = new FontUsage("Torus", 18, "Bold"),
                                    Colour = Color4.White,
                                    Truncate = true,
                                    MaxWidth = 120,
                                },
                                artistText = new SpriteText
                                {
                                    Text = Artist,
                                    Font = new FontUsage("Torus", 14),
                                    Colour = Color4Extensions.FromHex("9ca3af"),
                                    Truncate = true,
                                    MaxWidth = 120,
                                },
                                durationText = new SpriteText
                                {
                                    Text = formatDuration(Duration),
                                    Font = new FontUsage("Torus", 12),
                                    Colour = Color4Extensions.FromHex("6b7280"),
                                    Padding = new MarginPadding { Top = 4 },
                                },

                                // Stats
                                statsContainer = new FillFlowContainer
                                {
                                    AutoSizeAxes = Axes.Both,
                                    Direction = FillDirection.Horizontal,
                                    Spacing = new Vector2(8, 0),
                                    Padding = new MarginPadding { Top = 12 },
                                    Children = new Drawable[]
                                    {
                                        createStatBadge(FontAwesome.Solid.Heartbeat, $"{BPM:F0}"),
                                        createStatBadge(FontAwesome.Solid.Star, $"{Difficulty:F1}"),
                                    }
                                }
                            }
                        }
                    }
                },

                // Hover overlay
                hoverOverlay = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 16,
                    Alpha = 0,
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4Extensions.FromHex("0ea5e910"),
                    }
                }
            };

            updateProgress();
        }

        private Drawable createStatBadge(IconUsage icon, string value)
        {
            return new Container
            {
                AutoSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 4,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4Extensions.FromHex("374151"),
                    },
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(4, 0),
                        Padding = new MarginPadding { Horizontal = 6, Vertical = 2 },
                        Children = new Drawable[]
                        {
                            new SpriteIcon
                            {
                                Size = new Vector2(10),
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Icon = icon,
                                Colour = Color4Extensions.FromHex("9ca3af"),
                            },
                            new SpriteText
                            {
                                Text = value,
                                Font = new FontUsage("Torus", 11),
                                Colour = Color4Extensions.FromHex("d1d5db"),
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                            }
                        }
                    }
                }
            };
        }

        private string formatDuration(double ms)
        {
            var timeSpan = TimeSpan.FromMilliseconds(ms);
            return timeSpan.Hours > 0
                ? $"{timeSpan:h\\:mm\\:ss}"
                : $"{timeSpan:m\\:ss}";
        }

        private void updateProgress()
        {
            progressBar.ResizeWidthTo(albumArtContainer.DrawWidth * progress, 100, Easing.OutQuad);
        }

        private void updatePlayState()
        {
            playIcon.Icon = isPlaying ? FontAwesome.Solid.Pause : FontAwesome.Solid.Play;
            playIcon.X = isPlaying ? 0 : 2;
        }

        protected override bool OnHover(HoverEvent e)
        {
            isHovered = true;
            playButton.FadeIn(200, Easing.OutQuad);
            hoverOverlay.FadeIn(200, Easing.OutQuad);
            this.ScaleTo(1.02f, 200, Easing.OutQuad);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            isHovered = false;
            if (!isPlaying)
            {
                playButton.FadeOut(200, Easing.OutQuad);
            }
            hoverOverlay.FadeOut(200, Easing.OutQuad);
            this.ScaleTo(1f, 200, Easing.OutQuad);
            base.OnHoverLost(e);
        }

        protected override bool OnClick(ClickEvent e)
        {
            // Check if click is on the album art area (play button)
            if (e.MousePosition.X < albumArtContainer.DrawWidth + 12)
            {
                IsPlaying = !IsPlaying;
                OnPlayPauseToggled?.Invoke(IsPlaying);

                // Visual feedback
                albumArtContainer.ScaleTo(0.95f).ScaleTo(1f, 200, Easing.OutQuad);
            }
            else
            {
                OnTrackSelected?.Invoke();
            }

            return true;
        }

        /// <summary>
        /// Updates the track information display.
        /// </summary>
        public void UpdateTrackInfo(string title, string artist, double duration, float bpm, float difficulty)
        {
            Title = title;
            Artist = artist;
            Duration = duration;
            BPM = bpm;
            Difficulty = difficulty;

            titleText.Text = title;
            artistText.Text = artist;
            durationText.Text = formatDuration(duration);

            // Recreate stats
            statsContainer.Clear();
            statsContainer.Add(createStatBadge(FontAwesome.Solid.Heartbeat, $"{bpm:F0}"));
            statsContainer.Add(createStatBadge(FontAwesome.Solid.Star, $"{difficulty:F1}"));
        }
    }

    /// <summary>
    /// A compact horizontal track item for lists.
    /// </summary>
    public partial class TrackListItem : CompositeDrawable
    {
        /// <summary>
        /// Event fired when play/pause is toggled.
        /// </summary>
        public event Action<bool>? OnPlayPauseToggled;

        /// <summary>
        /// Event fired when the item is clicked.
        /// </summary>
        public event Action? OnSelected;

        /// <summary>
        /// Track title.
        /// </summary>
        public string Title { get; set; } = "Unknown Track";

        /// <summary>
        /// Artist name.
        /// </summary>
        public string Artist { get; set; } = "Unknown Artist";

        /// <summary>
        /// Track duration.
        /// </summary>
        public double Duration { get; set; }

        /// <summary>
        /// Whether currently playing.
        /// </summary>
        public bool IsPlaying
        {
            get => isPlaying;
            set
            {
                isPlaying = value;
                updatePlayState();
            }
        }

        /// <summary>
        /// Whether this item is selected.
        /// </summary>
        public bool Selected
        {
            get => selected;
            set
            {
                selected = value;
                updateSelectedState();
            }
        }

        private bool isPlaying;
        private bool selected;
        private Container playButton = null!;
        private SpriteIcon playIcon = null!;
        private Box selectedBackground = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.X;
            Height = 56;

            InternalChildren = new Drawable[]
            {
                // Background
                selectedBackground = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4Extensions.FromHex("0ea5e920"),
                    Alpha = 0,
                },
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Transparent,
                },
                new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Direction = FillDirection.Horizontal,
                    Padding = new MarginPadding { Horizontal = 12 },
                    Spacing = new Vector2(12, 0),
                    Children = new Drawable[]
                    {
                        // Play button
                        playButton = new Container
                        {
                            Size = new Vector2(40),
                            Anchor = Anchor.CentreLeft,
                            Origin = Anchor.CentreLeft,
                            Masking = true,
                            CornerRadius = 20,
                            Children = new Drawable[]
                            {
                                new Box
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Colour = Color4Extensions.FromHex("374151"),
                                },
                                playIcon = new SpriteIcon
                                {
                                    Size = new Vector2(16),
                                    Anchor = Anchor.Centre,
                                    Origin = Anchor.Centre,
                                    Icon = FontAwesome.Solid.Play,
                                    Colour = Color4.White,
                                    X = 1,
                                }
                            }
                        },

                        // Track info
                        new FillFlowContainer
                        {
                            AutoSizeAxes = Axes.Both,
                            Direction = FillDirection.Vertical,
                            Anchor = Anchor.CentreLeft,
                            Origin = Anchor.CentreLeft,
                            Spacing = new Vector2(0, 2),
                            Children = new Drawable[]
                            {
                                new SpriteText
                                {
                                    Text = Title,
                                    Font = new FontUsage("Torus", 14, "SemiBold"),
                                    Colour = Color4.White,
                                },
                                new SpriteText
                                {
                                    Text = Artist,
                                    Font = new FontUsage("Torus", 12),
                                    Colour = Color4Extensions.FromHex("9ca3af"),
                                }
                            }
                        }
                    }
                },
                
                // Duration on right
                new SpriteText
                {
                    Text = formatDuration(Duration),
                    Font = new FontUsage("Torus", 12),
                    Colour = Color4Extensions.FromHex("6b7280"),
                    Anchor = Anchor.CentreRight,
                    Origin = Anchor.CentreRight,
                    Padding = new MarginPadding { Right = 16 },
                },

                // Hover indicator
                new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 1,
                    Anchor = Anchor.BottomLeft,
                    Origin = Anchor.BottomLeft,
                    Colour = Color4Extensions.FromHex("374151"),
                }
            };
        }

        private string formatDuration(double ms)
        {
            var timeSpan = TimeSpan.FromMilliseconds(ms);
            return $"{timeSpan:m\\:ss}";
        }

        private void updatePlayState()
        {
            playIcon.Icon = isPlaying ? FontAwesome.Solid.Pause : FontAwesome.Solid.Play;
            playIcon.X = isPlaying ? 0 : 1;

            if (isPlaying)
            {
                playButton.Child.FadeColour(Color4Extensions.FromHex("0ea5e9"), 200);
            }
            else
            {
                playButton.Child.FadeColour(Color4Extensions.FromHex("374151"), 200);
            }
        }

        private void updateSelectedState()
        {
            selectedBackground.FadeTo(selected ? 1 : 0, 200);
        }

        protected override bool OnHover(HoverEvent e)
        {
            this.FadeColour(Color4Extensions.FromHex("ffffff10"), 100);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            this.FadeColour(Color4.White, 100);
            base.OnHoverLost(e);
        }

        protected override bool OnClick(ClickEvent e)
        {
            // Check if click is on play button
            if (e.MousePosition.X < 64)
            {
                IsPlaying = !IsPlaying;
                OnPlayPauseToggled?.Invoke(IsPlaying);
            }
            else
            {
                OnSelected?.Invoke();
            }

            return true;
        }
    }

    /// <summary>
    /// A now playing bar typically shown at bottom of screen.
    /// </summary>
    public partial class NowPlayingBar : CompositeDrawable
    {
        /// <summary>
        /// Event fired when play/pause is toggled.
        /// </summary>
        public event Action<bool>? OnPlayPauseToggled;

        /// <summary>
        /// Event fired when next track is requested.
        /// </summary>
        public event Action? OnNextTrack;

        /// <summary>
        /// Event fired when previous track is requested.
        /// </summary>
        public event Action? OnPreviousTrack;

        /// <summary>
        /// Current track title.
        /// </summary>
        public string Title
        {
            get => titleText.Text.ToString();
            set => titleText.Text = value;
        }

        /// <summary>
        /// Current track artist.
        /// </summary>
        public string Artist
        {
            get => artistText.Text.ToString();
            set => artistText.Text = value;
        }

        /// <summary>
        /// Current playback progress (0-1).
        /// </summary>
        public float Progress
        {
            get => progress;
            set
            {
                progress = Math.Clamp(value, 0f, 1f);
                progressBar.ResizeWidthTo(value, 100, Easing.OutQuad);
            }
        }

        /// <summary>
        /// Whether currently playing.
        /// </summary>
        public bool IsPlaying
        {
            get => isPlaying;
            set
            {
                isPlaying = value;
                playIcon.Icon = isPlaying ? FontAwesome.Solid.Pause : FontAwesome.Solid.Play;
                playIcon.X = isPlaying ? 0 : 2;
            }
        }

        private float progress;
        private bool isPlaying;
        private SpriteText titleText = null!;
        private SpriteText artistText = null!;
        private SpriteIcon playIcon = null!;
        private Box progressBar = null!;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.X;
            Height = 72;

            InternalChildren = new Drawable[]
            {
                // Background
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4Extensions.FromHex("111827"),
                },

                // Progress bar at top
                new Container
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 3,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = Color4Extensions.FromHex("374151"),
                        },
                        progressBar = new Box
                        {
                            RelativeSizeAxes = Axes.Y,
                            Width = 0,
                            Colour = Color4Extensions.FromHex("0ea5e9"),
                        }
                    }
                },

                // Content
                new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = new MarginPadding { Horizontal = 16, Top = 3 },
                    Child = new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(16, 0),
                        Children = new Drawable[]
                        {
                            // Album art placeholder
                            new Container
                            {
                                Size = new Vector2(56),
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Masking = true,
                                CornerRadius = 8,
                                Children = new Drawable[]
                                {
                                    new Box
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Colour = Color4Extensions.FromHex("374151"),
                                    },
                                    new SpriteIcon
                                    {
                                        Size = new Vector2(24),
                                        Anchor = Anchor.Centre,
                                        Origin = Anchor.Centre,
                                        Icon = FontAwesome.Solid.Music,
                                        Colour = Color4Extensions.FromHex("6b7280"),
                                    }
                                }
                            },

                            // Track info
                            new FillFlowContainer
                            {
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Vertical,
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Spacing = new Vector2(0, 2),
                                Children = new Drawable[]
                                {
                                    titleText = new SpriteText
                                    {
                                        Text = "Not Playing",
                                        Font = new FontUsage("Torus", 15, "SemiBold"),
                                        Colour = Color4.White,
                                    },
                                    artistText = new SpriteText
                                    {
                                        Text = "Select a track",
                                        Font = new FontUsage("Torus", 13),
                                        Colour = Color4Extensions.FromHex("9ca3af"),
                                    }
                                }
                            }
                        }
                    }
                },

                // Playback controls on right
                new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Horizontal,
                    Anchor = Anchor.CentreRight,
                    Origin = Anchor.CentreRight,
                    Padding = new MarginPadding { Right = 16 },
                    Spacing = new Vector2(8, 0),
                    Children = new Drawable[]
                    {
                        createControlButton(FontAwesome.Solid.StepBackward, () => OnPreviousTrack?.Invoke()),
                        new ClickableContainer
                        {
                            Size = new Vector2(48),
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Masking = true,
                            CornerRadius = 24,
                            Action = () =>
                            {
                                IsPlaying = !IsPlaying;
                                OnPlayPauseToggled?.Invoke(IsPlaying);
                            },
                            Children = new Drawable[]
                            {
                                new Box
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Colour = Color4Extensions.FromHex("0ea5e9"),
                                },
                                playIcon = new SpriteIcon
                                {
                                    Size = new Vector2(20),
                                    Anchor = Anchor.Centre,
                                    Origin = Anchor.Centre,
                                    Icon = FontAwesome.Solid.Play,
                                    Colour = Color4.White,
                                    X = 2,
                                }
                            }
                        },
                        createControlButton(FontAwesome.Solid.StepForward, () => OnNextTrack?.Invoke()),
                    }
                }
            };
        }

        private ClickableContainer createControlButton(IconUsage icon, Action action)
        {
            return new ClickableContainer
            {
                Size = new Vector2(36),
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Action = action,
                Child = new SpriteIcon
                {
                    Size = new Vector2(18),
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Icon = icon,
                    Colour = Color4Extensions.FromHex("9ca3af"),
                }
            };
        }
    }
}
