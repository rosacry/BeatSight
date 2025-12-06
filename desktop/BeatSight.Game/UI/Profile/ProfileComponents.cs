using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.Textures;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics.Effects;
using System;

namespace BeatSight.Game.UI.Profile
{
    /// <summary>
    /// User profile avatar with online status indicator.
    /// </summary>
    public partial class ProfileAvatar : CompositeDrawable
    {
        private readonly float avatarSize;
        private readonly bool showStatus;
        private readonly bool isOnline;
        private Container avatarContainer = null!;
        private Container statusIndicator = null!;

        private static readonly Color4 OnlineColor = new Color4(52, 211, 153, 255); // emerald-400
        private static readonly Color4 OfflineColor = new Color4(100, 116, 139, 255); // slate-500
        private static readonly Color4 CyanAccent = new Color4(6, 182, 212, 255);
        private static readonly Color4 PurpleAccent = new Color4(168, 85, 247, 255);

        public ProfileAvatar(float size = 80, bool showStatus = true, bool isOnline = false)
        {
            this.avatarSize = size;
            this.showStatus = showStatus;
            this.isOnline = isOnline;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            Size = new Vector2(avatarSize);
            Anchor = Anchor.Centre;
            Origin = Anchor.Centre;

            InternalChildren = new Drawable[]
            {
                // Gradient border
                new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = avatarSize / 2,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = CyanAccent,
                        },
                        // Gradient overlay using positioned boxes
                        new Container
                        {
                            RelativeSizeAxes = Axes.Both,
                            Anchor = Anchor.TopRight,
                            Origin = Anchor.TopRight,
                            Width = 0.5f,
                            Child = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = PurpleAccent,
                            },
                        },
                    },
                },
                // Inner avatar container
                avatarContainer = new Container
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Size = new Vector2(avatarSize - 4),
                    Masking = true,
                    CornerRadius = (avatarSize - 4) / 2,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(30, 41, 59, 255), // slate-800
                        },
                        // Placeholder initial
                        new SpriteText
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Text = "U",
                            Font = new FontUsage("Inter", avatarSize * 0.4f, "Bold"),
                            Colour = Color4.White,
                        },
                    },
                },
                // Status indicator
                statusIndicator = new Container
                {
                    Anchor = Anchor.BottomRight,
                    Origin = Anchor.Centre,
                    Size = new Vector2(avatarSize * 0.25f),
                    X = -avatarSize * 0.1f,
                    Y = -avatarSize * 0.1f,
                    Masking = true,
                    CornerRadius = avatarSize * 0.125f,
                    BorderColour = new Color4(15, 23, 42, 255),
                    BorderThickness = 2,
                    Alpha = showStatus ? 1 : 0,
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = isOnline ? OnlineColor : OfflineColor,
                    },
                },
            };
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();
            if (isOnline && showStatus)
            {
                statusIndicator.Loop(c =>
                    c.ScaleTo(1.1f, 1000, Easing.InOutSine)
                     .Then()
                     .ScaleTo(1f, 1000, Easing.InOutSine)
                );
            }
        }
    }

    /// <summary>
    /// User profile header card with avatar, name, and stats.
    /// </summary>
    public partial class ProfileHeader : CompositeDrawable
    {
        private readonly string username;
        private readonly string? subtitle;
        private readonly (string Label, string Value)[] stats;

        private static readonly Color4 BackgroundColor = new Color4(15, 23, 42, 255);
        private static readonly Color4 SurfaceColor = new Color4(30, 41, 59, 255);
        private static readonly Color4 BorderColor = new Color4(51, 65, 85, 200);
        private static readonly Color4 TextPrimary = Color4.White;
        private static readonly Color4 TextSecondary = new Color4(148, 163, 184, 255);

        public ProfileHeader(string username, string? subtitle = null, params (string, string)[] stats)
        {
            this.username = username;
            this.subtitle = subtitle;
            this.stats = stats;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.X;
            AutoSizeAxes = Axes.Y;

            InternalChild = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 20,
                BorderColour = BorderColor,
                BorderThickness = 1,
                Children = new Drawable[]
                {
                    // Background with gradient
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = SurfaceColor,
                    },
                    // Top gradient accent
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 100,
                        Masking = true,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = new Color4(6, 182, 212, 50), // cyan with low alpha
                            },
                        },
                    },
                    // Content
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Padding = new MarginPadding(24),
                        Spacing = new Vector2(0, 16),
                        Children = new Drawable[]
                        {
                            // Avatar and name row
                            new FillFlowContainer
                            {
                                RelativeSizeAxes = Axes.X,
                                AutoSizeAxes = Axes.Y,
                                Direction = FillDirection.Horizontal,
                                Spacing = new Vector2(16, 0),
                                Children = new Drawable[]
                                {
                                    new ProfileAvatar(80, true, true),
                                    new FillFlowContainer
                                    {
                                        Anchor = Anchor.CentreLeft,
                                        Origin = Anchor.CentreLeft,
                                        AutoSizeAxes = Axes.Both,
                                        Direction = FillDirection.Vertical,
                                        Spacing = new Vector2(0, 4),
                                        Children = new Drawable[]
                                        {
                                            new SpriteText
                                            {
                                                Text = username,
                                                Font = new FontUsage("Inter", 24, "Bold"),
                                                Colour = TextPrimary,
                                            },
                                            subtitle != null
                                                ? new SpriteText
                                                {
                                                    Text = subtitle,
                                                    Font = new FontUsage("Inter", 14),
                                                    Colour = TextSecondary,
                                                }
                                                : Empty(),
                                        },
                                    },
                                },
                            },
                            // Stats row
                            stats.Length > 0
                                ? new GridContainer
                                {
                                    RelativeSizeAxes = Axes.X,
                                    Height = 60,
                                    ColumnDimensions = CreateStatColumns(),
                                    Content = new[]
                                    {
                                        CreateStatCells(),
                                    },
                                }
                                : Empty(),
                        },
                    },
                },
            };
        }

        private Dimension[] CreateStatColumns()
        {
            var dims = new Dimension[stats.Length];
            for (int i = 0; i < stats.Length; i++)
                dims[i] = new Dimension(GridSizeMode.Distributed);
            return dims;
        }

        private Drawable[] CreateStatCells()
        {
            var cells = new Drawable[stats.Length];
            for (int i = 0; i < stats.Length; i++)
            {
                cells[i] = new ProfileStatCell(stats[i].Label, stats[i].Value);
            }
            return cells;
        }
    }

    /// <summary>
    /// Individual stat cell for profile display.
    /// </summary>
    public partial class ProfileStatCell : CompositeDrawable
    {
        private readonly string label;
        private readonly string value;

        private static readonly Color4 TextPrimary = Color4.White;
        private static readonly Color4 TextSecondary = new Color4(148, 163, 184, 255);
        private static readonly Color4 CyanAccent = new Color4(6, 182, 212, 255);

        public ProfileStatCell(string label, string value)
        {
            this.label = label;
            this.value = value;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChild = new FillFlowContainer
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 4),
                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Text = value,
                        Font = new FontUsage("Inter", 20, "Bold"),
                        Colour = TextPrimary,
                    },
                    new SpriteText
                    {
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Text = label,
                        Font = new FontUsage("Inter", 12),
                        Colour = TextSecondary,
                    },
                },
            };
        }
    }

    /// <summary>
    /// Achievement badge with icon and unlock status.
    /// </summary>
    public partial class AchievementBadge : CompositeDrawable
    {
        private readonly string name;
        private readonly string description;
        private readonly bool isUnlocked;
        private readonly float badgeSize;

        private static readonly Color4 LockedColor = new Color4(51, 65, 85, 255);
        private static readonly Color4 UnlockedGold = new Color4(250, 204, 21, 255);
        private static readonly Color4 TextPrimary = Color4.White;
        private static readonly Color4 TextSecondary = new Color4(148, 163, 184, 255);

        public AchievementBadge(string name, string description, bool isUnlocked = false, float size = 64)
        {
            this.name = name;
            this.description = description;
            this.isUnlocked = isUnlocked;
            this.badgeSize = size;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            Size = new Vector2(badgeSize + 40, badgeSize + 60);
            Anchor = Anchor.Centre;
            Origin = Anchor.Centre;

            InternalChild = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 8),
                Children = new Drawable[]
                {
                    // Badge icon
                    new Container
                    {
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Size = new Vector2(badgeSize),
                        Masking = true,
                        CornerRadius = 12,
                        EdgeEffect = isUnlocked
                            ? new EdgeEffectParameters
                            {
                                Type = EdgeEffectType.Glow,
                                Colour = UnlockedGold.Opacity(0.4f),
                                Radius = 10,
                            }
                            : new EdgeEffectParameters(),
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = isUnlocked ? UnlockedGold.Opacity(0.2f) : LockedColor,
                            },
                            new SpriteIcon
                            {
                                Anchor = Anchor.Centre,
                                Origin = Anchor.Centre,
                                Size = new Vector2(badgeSize * 0.5f),
                                Icon = isUnlocked ? FontAwesome.Solid.Trophy : FontAwesome.Solid.Lock,
                                Colour = isUnlocked ? UnlockedGold : TextSecondary,
                            },
                        },
                    },
                    // Badge name
                    new SpriteText
                    {
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Text = name,
                        Font = new FontUsage("Inter", 12, "SemiBold"),
                        Colour = isUnlocked ? TextPrimary : TextSecondary,
                    },
                },
            };
        }

        protected override bool OnHover(HoverEvent e)
        {
            this.ScaleTo(1.05f, 100, Easing.OutQuint);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            this.ScaleTo(1f, 100, Easing.OutQuint);
            base.OnHoverLost(e);
        }
    }

    /// <summary>
    /// Recent activity item for profile feed.
    /// </summary>
    public partial class ActivityItem : CompositeDrawable
    {
        private readonly string activityType;
        private readonly string description;
        private readonly string timeAgo;

        private static readonly Color4 SurfaceColor = new Color4(30, 41, 59, 255);
        private static readonly Color4 BorderColor = new Color4(51, 65, 85, 200);
        private static readonly Color4 TextPrimary = Color4.White;
        private static readonly Color4 TextSecondary = new Color4(148, 163, 184, 255);
        private static readonly Color4 CyanAccent = new Color4(6, 182, 212, 255);
        private static readonly Color4 PurpleAccent = new Color4(168, 85, 247, 255);
        private static readonly Color4 AmberAccent = new Color4(245, 158, 11, 255);

        public ActivityItem(string activityType, string description, string timeAgo)
        {
            this.activityType = activityType;
            this.description = description;
            this.timeAgo = timeAgo;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.X;
            Height = 60;

            var iconColor = activityType switch
            {
                "play" => CyanAccent,
                "achievement" => AmberAccent,
                "level_up" => PurpleAccent,
                _ => TextSecondary,
            };

            var icon = activityType switch
            {
                "play" => FontAwesome.Solid.Play,
                "achievement" => FontAwesome.Solid.Trophy,
                "level_up" => FontAwesome.Solid.ArrowUp,
                _ => FontAwesome.Solid.Circle,
            };

            InternalChild = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 12,
                BorderColour = BorderColor,
                BorderThickness = 1,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = SurfaceColor.Opacity(0.5f),
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 16 },
                        Children = new Drawable[]
                        {
                            // Icon
                            new Container
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Size = new Vector2(36),
                                Masking = true,
                                CornerRadius = 8,
                                Child = new Box
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Colour = iconColor.Opacity(0.2f),
                                },
                            },
                            new SpriteIcon
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.Centre,
                                X = 18,
                                Size = new Vector2(16),
                                Icon = icon,
                                Colour = iconColor,
                            },
                            // Description
                            new FillFlowContainer
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                X = 52,
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Vertical,
                                Spacing = new Vector2(0, 2),
                                Children = new Drawable[]
                                {
                                    new SpriteText
                                    {
                                        Text = description,
                                        Font = new FontUsage("Inter", 14),
                                        Colour = TextPrimary,
                                    },
                                    new SpriteText
                                    {
                                        Text = timeAgo,
                                        Font = new FontUsage("Inter", 12),
                                        Colour = TextSecondary,
                                    },
                                },
                            },
                        },
                    },
                },
            };
        }

        protected override bool OnHover(HoverEvent e)
        {
            this.FadeColour(Color4.White.Opacity(0.9f), 100);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            this.FadeColour(Color4.White, 100);
            base.OnHoverLost(e);
        }
    }

    /// <summary>
    /// Level progress bar with XP display.
    /// </summary>
    public partial class LevelProgressBar : CompositeDrawable
    {
        private readonly int currentLevel;
        private readonly int currentXP;
        private readonly int requiredXP;
        private Container progressFill = null!;

        private static readonly Color4 SurfaceColor = new Color4(30, 41, 59, 255);
        private static readonly Color4 TextPrimary = Color4.White;
        private static readonly Color4 TextSecondary = new Color4(148, 163, 184, 255);
        private static readonly Color4 CyanAccent = new Color4(6, 182, 212, 255);
        private static readonly Color4 PurpleAccent = new Color4(168, 85, 247, 255);

        public LevelProgressBar(int level, int currentXP, int requiredXP)
        {
            this.currentLevel = level;
            this.currentXP = currentXP;
            this.requiredXP = requiredXP;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.X;
            Height = 80;

            float progress = (float)currentXP / requiredXP;

            InternalChild = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 8),
                Children = new Drawable[]
                {
                    // Level and XP labels
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 24,
                        Children = new Drawable[]
                        {
                            new FillFlowContainer
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Horizontal,
                                Spacing = new Vector2(8, 0),
                                Children = new Drawable[]
                                {
                                    new SpriteText
                                    {
                                        Text = $"Level {currentLevel}",
                                        Font = new FontUsage("Inter", 16, "Bold"),
                                        Colour = TextPrimary,
                                    },
                                },
                            },
                            new SpriteText
                            {
                                Anchor = Anchor.CentreRight,
                                Origin = Anchor.CentreRight,
                                Text = $"{currentXP:N0} / {requiredXP:N0} XP",
                                Font = new FontUsage("Inter", 14),
                                Colour = TextSecondary,
                            },
                        },
                    },
                    // Progress bar
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 12,
                        Masking = true,
                        CornerRadius = 6,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = SurfaceColor,
                            },
                            progressFill = new Container
                            {
                                RelativeSizeAxes = Axes.Y,
                                Width = 0, // Will animate
                                Masking = true,
                                CornerRadius = 6,
                                Children = new Drawable[]
                                {
                                    new Box
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Colour = CyanAccent,
                                    },
                                    // Gradient overlay
                                    new Container
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Anchor = Anchor.TopRight,
                                        Origin = Anchor.TopRight,
                                        Width = 0.3f,
                                        Child = new Box
                                        {
                                            RelativeSizeAxes = Axes.Both,
                                            Colour = PurpleAccent,
                                        },
                                    },
                                },
                            },
                        },
                    },
                    // Next level label
                    new SpriteText
                    {
                        Text = $"Level {currentLevel + 1}",
                        Font = new FontUsage("Inter", 12),
                        Colour = TextSecondary.Opacity(0.6f),
                        Anchor = Anchor.TopRight,
                        Origin = Anchor.TopRight,
                    },
                },
            };
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Animate progress bar
            float targetWidth = DrawWidth * ((float)currentXP / requiredXP);
            progressFill.ResizeWidthTo(targetWidth, 800, Easing.OutExpo);
        }
    }
}
