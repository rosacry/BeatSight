// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.Textures;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// Difficulty rating display for beatmaps.
    /// </summary>
    public enum DifficultyRating
    {
        Easy,
        Normal,
        Hard,
        Insane,
        Expert,
        ExpertPlus
    }

    /// <summary>
    /// A modern, visually polished card for displaying beatmap/song information.
    /// Features hover effects, difficulty indicators, and smooth animations.
    /// </summary>
    public partial class BeatmapCard : CompositeDrawable
    {
        private const float card_height = 100;
        private const float cover_width = 100;
        private const float corner_radius = 12;
        private const double hover_duration = 200;

        #region Properties

        /// <summary>
        /// Title of the beatmap/song.
        /// </summary>
        public string Title { get; init; } = "Unknown Title";

        /// <summary>
        /// Artist name.
        /// </summary>
        public string Artist { get; init; } = "Unknown Artist";

        /// <summary>
        /// Mapper/Creator name.
        /// </summary>
        public string Creator { get; init; } = "";

        /// <summary>
        /// Duration of the song in seconds.
        /// </summary>
        public double Duration { get; init; }

        /// <summary>
        /// BPM of the song.
        /// </summary>
        public double Bpm { get; init; }

        /// <summary>
        /// Difficulty rating value (0-10 scale).
        /// </summary>
        public double StarRating { get; init; }

        /// <summary>
        /// Difficulty category.
        /// </summary>
        public DifficultyRating Difficulty { get; init; } = DifficultyRating.Normal;

        /// <summary>
        /// Number of times this beatmap has been played.
        /// </summary>
        public int PlayCount { get; init; }

        /// <summary>
        /// Whether the beatmap is locally downloaded.
        /// </summary>
        public bool IsDownloaded { get; init; } = true;

        /// <summary>
        /// Whether the user has a score on this beatmap.
        /// </summary>
        public bool HasScore { get; init; }

        /// <summary>
        /// The best score percentage (0-100).
        /// </summary>
        public double BestScore { get; init; }

        /// <summary>
        /// Path or URL to the cover image.
        /// </summary>
        public string? CoverPath { get; init; }

        /// <summary>
        /// Action when the card is clicked.
        /// </summary>
        public Action? OnSelect { get; init; }

        /// <summary>
        /// Action when play button is clicked.
        /// </summary>
        public Action? OnPlay { get; init; }

        #endregion

        private Container cardContainer = null!;
        private Box backgroundBox = null!;
        private Box hoverOverlay = null!;
        private Container coverContainer = null!;
        private Box coverPlaceholder = null!;
        private Sprite coverSprite = null!;
        private Box difficultyStripe = null!;
        private Container playButtonContainer = null!;
        private CircularContainer difficultyBadge = null!;
        private Container downloadIndicator = null!;
        private Box scoreIndicator = null!;

        [BackgroundDependencyLoader]
        private void load(TextureStore textures)
        {
            RelativeSizeAxes = Axes.X;
            Height = card_height;

            InternalChild = cardContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = corner_radius,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Shadow,
                    Colour = Color4.Black.Opacity(0.3f),
                    Radius = 8,
                    Offset = new Vector2(0, 2)
                },
                Children = new Drawable[]
                {
                    // Background
                    backgroundBox = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4Extensions.FromHex("1a1a2e")
                    },

                    // Hover overlay
                    hoverOverlay = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4.White.Opacity(0),
                    },

                    // Difficulty stripe on the left
                    difficultyStripe = new Box
                    {
                        Width = 4,
                        RelativeSizeAxes = Axes.Y,
                        Colour = GetDifficultyColour(Difficulty)
                    },

                    // Cover art container
                    coverContainer = new Container
                    {
                        Size = new Vector2(cover_width, card_height),
                        X = 4,
                        Masking = true,
                        CornerRadius = 8,
                        Children = new Drawable[]
                        {
                            coverPlaceholder = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = GetDifficultyColour(Difficulty).Opacity(0.3f)
                            },
                            coverSprite = new Sprite
                            {
                                RelativeSizeAxes = Axes.Both,
                                FillMode = FillMode.Fill,
                                Alpha = 0
                            },
                            // Gradient overlay on cover
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = ColourInfo.GradientHorizontal(
                                    Color4.Black.Opacity(0),
                                    Color4.Black.Opacity(0.5f))
                            },
                            // Difficulty badge on cover
                            difficultyBadge = new CircularContainer
                            {
                                Anchor = Anchor.BottomRight,
                                Origin = Anchor.BottomRight,
                                Size = new Vector2(28),
                                Margin = new MarginPadding(6),
                                Masking = true,
                                Children = new Drawable[]
                                {
                                    new Box
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Colour = GetDifficultyColour(Difficulty)
                                    },
                                    new SpriteText
                                    {
                                        Anchor = Anchor.Centre,
                                        Origin = Anchor.Centre,
                                        Text = StarRating.ToString("F1"),
                                        Font = new FontUsage("Nunito", size: 11, weight: "Bold"),
                                        Colour = Color4.White
                                    }
                                }
                            }
                        }
                    },

                    // Content
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Left = cover_width + 16, Right = 16, Vertical = 12 },
                        Children = new Drawable[]
                        {
                            // Title and artist
                            new FillFlowContainer
                            {
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Vertical,
                                Spacing = new Vector2(0, 4),
                                Children = new Drawable[]
                                {
                                    new SpriteText
                                    {
                                        Text = Title,
                                        Font = new FontUsage("Nunito", size: 18, weight: "Bold"),
                                        Colour = Color4.White,
                                        Truncate = true,
                                        MaxWidth = 350
                                    },
                                    new SpriteText
                                    {
                                        Text = Artist,
                                        Font = new FontUsage("Nunito", size: 14),
                                        Colour = Color4.White.Opacity(0.7f),
                                        Truncate = true,
                                        MaxWidth = 350
                                    },
                                    new FillFlowContainer
                                    {
                                        AutoSizeAxes = Axes.Both,
                                        Direction = FillDirection.Horizontal,
                                        Spacing = new Vector2(12, 0),
                                        Margin = new MarginPadding { Top = 4 },
                                        Children = new Drawable[]
                                        {
                                            CreateInfoChip(FontAwesome.Regular.Clock, FormatDuration(Duration)),
                                            CreateInfoChip(FontAwesome.Solid.Heartbeat, $"{Bpm:F0} BPM"),
                                            CreateInfoChip(FontAwesome.Solid.Play, PlayCount.ToString("N0"))
                                        }
                                    }
                                }
                            },

                            // Right side - score/status
                            new Container
                            {
                                Anchor = Anchor.CentreRight,
                                Origin = Anchor.CentreRight,
                                AutoSizeAxes = Axes.Both,
                                Children = new Drawable[]
                                {
                                    new FillFlowContainer
                                    {
                                        Anchor = Anchor.CentreRight,
                                        Origin = Anchor.CentreRight,
                                        AutoSizeAxes = Axes.Both,
                                        Direction = FillDirection.Vertical,
                                        Spacing = new Vector2(0, 4),
                                        Children = new Drawable[]
                                        {
                                            // Best score display
                                            HasScore ? CreateScoreDisplay() : Empty(),

                                            // Download indicator
                                            downloadIndicator = new Container
                                            {
                                                AutoSizeAxes = Axes.Both,
                                                Alpha = IsDownloaded ? 0 : 1,
                                                Child = CreateInfoChip(FontAwesome.Solid.CloudDownloadAlt, "Download", Color4Extensions.FromHex("00d4ff"))
                                            }
                                        }
                                    },

                                    // Play button (appears on hover)
                                    playButtonContainer = new Container
                                    {
                                        Anchor = Anchor.CentreRight,
                                        Origin = Anchor.CentreRight,
                                        Size = new Vector2(48),
                                        Alpha = 0,
                                        Scale = new Vector2(0.8f),
                                        Child = new PlayButton
                                        {
                                            RelativeSizeAxes = Axes.Both,
                                            Action = () => OnPlay?.Invoke()
                                        }
                                    }
                                }
                            }
                        }
                    },

                    // Score indicator bar at bottom
                    HasScore
                        ? (scoreIndicator = new Box
                        {
                            Anchor = Anchor.BottomLeft,
                            Origin = Anchor.BottomLeft,
                            Height = 3,
                            Width = 0,
                            Colour = GetScoreColour(BestScore)
                        })
                        : Empty()
                }
            };

            // Load cover image if available
            if (!string.IsNullOrEmpty(CoverPath))
            {
                var texture = textures.Get(CoverPath);
                if (texture != null)
                {
                    coverSprite.Texture = texture;
                    coverSprite.FadeIn(300);
                }
            }
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Animate score bar
            if (HasScore && scoreIndicator != null)
            {
                float targetWidth = (float)(BestScore / 100) * DrawWidth;
                scoreIndicator.ResizeWidthTo(targetWidth, 800, Easing.OutQuint);
            }
        }

        protected override bool OnHover(HoverEvent e)
        {
            hoverOverlay.FadeColour(Color4.White.Opacity(0.05f), hover_duration);
            cardContainer.ScaleTo(1.02f, hover_duration, Easing.OutQuint);

            // Lift shadow
            cardContainer.TweenEdgeEffectTo(new EdgeEffectParameters
            {
                Type = EdgeEffectType.Shadow,
                Colour = Color4.Black.Opacity(0.4f),
                Radius = 16,
                Offset = new Vector2(0, 6)
            }, hover_duration, Easing.OutQuint);

            // Show play button
            playButtonContainer.FadeIn(hover_duration);
            playButtonContainer.ScaleTo(1f, hover_duration, Easing.OutBack);

            // Glow on difficulty stripe
            difficultyStripe.FadeColour(GetDifficultyColour(Difficulty).Lighten(0.3f), hover_duration);

            return true;
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            hoverOverlay.FadeColour(Color4.White.Opacity(0), hover_duration);
            cardContainer.ScaleTo(1f, hover_duration, Easing.OutQuint);

            cardContainer.TweenEdgeEffectTo(new EdgeEffectParameters
            {
                Type = EdgeEffectType.Shadow,
                Colour = Color4.Black.Opacity(0.3f),
                Radius = 8,
                Offset = new Vector2(0, 2)
            }, hover_duration, Easing.OutQuint);

            playButtonContainer.FadeOut(hover_duration);
            playButtonContainer.ScaleTo(0.8f, hover_duration, Easing.OutQuint);

            difficultyStripe.FadeColour(GetDifficultyColour(Difficulty), hover_duration);
        }

        protected override bool OnClick(ClickEvent e)
        {
            // Flash effect
            hoverOverlay.FlashColour(Color4.White.Opacity(0.2f), 200);
            OnSelect?.Invoke();
            return true;
        }

        private Drawable CreateInfoChip(IconUsage icon, string text, Color4? colour = null)
        {
            return new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(4, 0),
                Children = new Drawable[]
                {
                    new SpriteIcon
                    {
                        Size = new Vector2(10),
                        Icon = icon,
                        Colour = colour ?? Color4.White.Opacity(0.5f),
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft
                    },
                    new SpriteText
                    {
                        Text = text,
                        Font = new FontUsage("Nunito", size: 11),
                        Colour = colour ?? Color4.White.Opacity(0.5f),
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft
                    }
                }
            };
        }

        private Drawable CreateScoreDisplay()
        {
            return new FillFlowContainer
            {
                Anchor = Anchor.TopRight,
                Origin = Anchor.TopRight,
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(4, 0),
                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Text = $"{BestScore:F1}%",
                        Font = new FontUsage("Nunito", size: 16, weight: "Bold"),
                        Colour = GetScoreColour(BestScore),
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft
                    },
                    new SpriteIcon
                    {
                        Size = new Vector2(12),
                        Icon = GetScoreIcon(BestScore),
                        Colour = GetScoreColour(BestScore),
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft
                    }
                }
            };
        }

        private static string FormatDuration(double seconds)
        {
            var span = TimeSpan.FromSeconds(seconds);
            return span.TotalHours >= 1
                ? $"{(int)span.TotalHours}:{span.Minutes:D2}:{span.Seconds:D2}"
                : $"{(int)span.TotalMinutes}:{span.Seconds:D2}";
        }

        public static Color4 GetDifficultyColour(DifficultyRating difficulty) => difficulty switch
        {
            DifficultyRating.Easy => Color4Extensions.FromHex("88cc00"),
            DifficultyRating.Normal => Color4Extensions.FromHex("00d4ff"),
            DifficultyRating.Hard => Color4Extensions.FromHex("ffcc00"),
            DifficultyRating.Insane => Color4Extensions.FromHex("ff66aa"),
            DifficultyRating.Expert => Color4Extensions.FromHex("aa66ff"),
            DifficultyRating.ExpertPlus => Color4Extensions.FromHex("1a1a2e"),
            _ => Color4.White
        };

        private static Color4 GetScoreColour(double score) => score switch
        {
            >= 100 => Color4Extensions.FromHex("ffcc00"), // SS
            >= 95 => Color4Extensions.FromHex("00ff88"),  // S
            >= 90 => Color4Extensions.FromHex("00d4ff"),  // A
            >= 80 => Color4Extensions.FromHex("88cc00"),  // B
            >= 70 => Color4Extensions.FromHex("ffcc00"),  // C
            _ => Color4Extensions.FromHex("ff4466")       // D
        };

        private static IconUsage GetScoreIcon(double score) => score switch
        {
            >= 100 => FontAwesome.Solid.Crown,
            >= 95 => FontAwesome.Solid.Star,
            >= 80 => FontAwesome.Solid.CheckCircle,
            _ => FontAwesome.Regular.CheckCircle
        };

        /// <summary>
        /// Animated play button for the card.
        /// </summary>
        private partial class PlayButton : CompositeDrawable
        {
            public Action? Action { get; set; }

            private CircularContainer circle = null!;
            private Box background = null!;
            private SpriteIcon icon = null!;

            [BackgroundDependencyLoader]
            private void load()
            {
                InternalChild = circle = new CircularContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    EdgeEffect = new EdgeEffectParameters
                    {
                        Type = EdgeEffectType.Glow,
                        Colour = Color4Extensions.FromHex("00d4ff").Opacity(0.4f),
                        Radius = 10
                    },
                    Children = new Drawable[]
                    {
                        background = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = Color4Extensions.FromHex("00d4ff")
                        },
                        icon = new SpriteIcon
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Size = new Vector2(20),
                            Icon = FontAwesome.Solid.Play,
                            Colour = Color4.White,
                            X = 2 // Optical centering
                        }
                    }
                };
            }

            protected override bool OnHover(HoverEvent e)
            {
                circle.ScaleTo(1.1f, 200, Easing.OutQuint);
                background.FadeColour(Color4Extensions.FromHex("00d4ff").Lighten(0.2f), 200);
                return true;
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                circle.ScaleTo(1f, 200, Easing.OutQuint);
                background.FadeColour(Color4Extensions.FromHex("00d4ff"), 200);
            }

            protected override bool OnClick(ClickEvent e)
            {
                circle.ScaleTo(0.9f, 50, Easing.OutQuint)
                    .Then()
                    .ScaleTo(1.1f, 200, Easing.OutQuint);

                background.FlashColour(Color4.White, 200);
                Action?.Invoke();
                return true;
            }
        }
    }
}
