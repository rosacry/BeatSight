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
    /// A modern sidebar/navigation panel with animated entries and glow effects.
    /// Inspired by osu!'s navigation design with BeatSight's unique style.
    /// </summary>
    public partial class BeatSightPanel : Container
    {
        private const float panel_width = 280f;
        private const float collapsed_width = 60f;
        private const float animation_duration = 300f;

        private bool isCollapsed;
        private Container panelContent = null!;
        private Container itemsContainer = null!;
        private Box backgroundBox = null!;
        private Box accentStrip = null!;

        public bool IsCollapsed
        {
            get => isCollapsed;
            set
            {
                if (isCollapsed == value) return;
                isCollapsed = value;
                animateCollapse(value);
            }
        }

        public event Action<NavigationItem>? OnItemSelected;

        [BackgroundDependencyLoader]
        private void load()
        {
            Width = panel_width;
            RelativeSizeAxes = Axes.Y;
            Masking = true;

            EdgeEffect = new EdgeEffectParameters
            {
                Type = EdgeEffectType.Shadow,
                Colour = Color4.Black.Opacity(0.4f),
                Radius = 20f,
                Offset = new Vector2(5, 0),
            };

            Children = new Drawable[]
            {
                // Background
                backgroundBox = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(15, 17, 26, 240),
                },

                // Gradient overlay
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = ColourInfo.GradientVertical(
                        new Color4(0, 212, 255, 15),
                        new Color4(255, 50, 150, 10)
                    ),
                },

                // Accent strip on the right edge
                accentStrip = new Box
                {
                    Width = 2,
                    RelativeSizeAxes = Axes.Y,
                    Anchor = Anchor.CentreRight,
                    Origin = Anchor.CentreRight,
                    Colour = ColourInfo.GradientVertical(
                        new Color4(0, 212, 255, 255),
                        new Color4(255, 50, 150, 255)
                    ),
                },

                panelContent = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = new MarginPadding { Top = 20, Bottom = 20 },
                    Children = new Drawable[]
                    {
                        // Logo/Header area
                        new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            Height = 80,
                            Padding = new MarginPadding { Left = 20, Right = 20 },
                            Child = new FillFlowContainer
                            {
                                RelativeSizeAxes = Axes.Both,
                                Direction = FillDirection.Horizontal,
                                Spacing = new Vector2(12, 0),
                                Children = new Drawable[]
                                {
                                    // Logo icon
                                    new Container
                                    {
                                        Size = new Vector2(40),
                                        Anchor = Anchor.CentreLeft,
                                        Origin = Anchor.CentreLeft,
                                        Masking = true,
                                        CornerRadius = 10,
                                        EdgeEffect = new EdgeEffectParameters
                                        {
                                            Type = EdgeEffectType.Glow,
                                            Colour = new Color4(0, 212, 255, 80),
                                            Radius = 10,
                                        },
                                        Children = new Drawable[]
                                        {
                                            new Box
                                            {
                                                RelativeSizeAxes = Axes.Both,
                                                Colour = ColourInfo.GradientHorizontal(
                                                    new Color4(0, 212, 255, 255),
                                                    new Color4(255, 50, 150, 255)
                                                ),
                                            },
                                            new SpriteIcon
                                            {
                                                Anchor = Anchor.Centre,
                                                Origin = Anchor.Centre,
                                                Size = new Vector2(24),
                                                Icon = FontAwesome.Solid.Music,
                                                Colour = Color4.White,
                                            },
                                        },
                                    },

                                    // Title
                                    new SpriteText
                                    {
                                        Text = "BeatSight",
                                        Font = new FontUsage("Torus", 24, "Bold"),
                                        Colour = Color4.White,
                                        Anchor = Anchor.CentreLeft,
                                        Origin = Anchor.CentreLeft,
                                    },
                                },
                            },
                        },

                        // Navigation items container
                        itemsContainer = new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Y = 100,
                            Padding = new MarginPadding { Left = 12, Right = 12 },
                        },
                    },
                },

                // Collapse button
                new CollapseButton
                {
                    Action = () => IsCollapsed = !IsCollapsed,
                },
            };
        }

        /// <summary>
        /// Add a navigation item to the panel.
        /// </summary>
        public void AddItem(NavigationItem item)
        {
            var entry = new NavigationEntry(item)
            {
                Action = () => OnItemSelected?.Invoke(item),
            };

            itemsContainer.Add(entry);
        }

        /// <summary>
        /// Add multiple navigation items at once.
        /// </summary>
        public void AddItems(params NavigationItem[] items)
        {
            float y = 0;
            foreach (var item in items)
            {
                var entry = new NavigationEntry(item)
                {
                    Y = y,
                    Action = () => OnItemSelected?.Invoke(item),
                };
                itemsContainer.Add(entry);
                y += 50; // Item height + spacing
            }
        }

        private void animateCollapse(bool collapse)
        {
            this.ResizeWidthTo(collapse ? collapsed_width : panel_width, animation_duration, Easing.OutQuint);

            foreach (var child in itemsContainer.Children)
            {
                if (child is NavigationEntry entry)
                    entry.SetCollapsedState(collapse, animation_duration);
            }
        }

        /// <summary>
        /// Represents a navigation item with icon, label, and optional notification count.
        /// </summary>
        public class NavigationItem
        {
            public string Label { get; set; } = string.Empty;
            public IconUsage Icon { get; set; } = FontAwesome.Solid.Circle;
            public int NotificationCount { get; set; }
            public string? Route { get; set; }
            public Action? OnActivate { get; set; }
        }

        /// <summary>
        /// A single navigation entry in the panel.
        /// </summary>
        private partial class NavigationEntry : Container
        {
            private const float height = 44f;

            private readonly NavigationItem item;
            private Box hoverBox = null!;
            private Box selectedIndicator = null!;
            private SpriteText labelText = null!;
            private Container notificationBadge = null!;
            private SpriteText notificationText = null!;
            private bool isSelected;

            public Action? Action;

            public bool IsSelected
            {
                get => isSelected;
                set
                {
                    if (isSelected == value) return;
                    isSelected = value;
                    updateSelectedState();
                }
            }

            public NavigationEntry(NavigationItem item)
            {
                this.item = item;
            }

            [BackgroundDependencyLoader]
            private void load()
            {
                RelativeSizeAxes = Axes.X;
                Height = height;
                Masking = true;
                CornerRadius = 10;

                Children = new Drawable[]
                {
                    // Hover background
                    hoverBox = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(255, 255, 255, 0),
                    },

                    // Selected indicator
                    selectedIndicator = new Box
                    {
                        Width = 3,
                        RelativeSizeAxes = Axes.Y,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Colour = new Color4(0, 212, 255, 255),
                        Alpha = 0,
                    },

                    // Content
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(12, 0),
                        Padding = new MarginPadding { Left = 14, Right = 14 },
                        Children = new Drawable[]
                        {
                            // Icon
                            new SpriteIcon
                            {
                                Size = new Vector2(20),
                                Icon = item.Icon,
                                Colour = new Color4(160, 170, 200, 255),
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                            },

                            // Label
                            labelText = new SpriteText
                            {
                                Text = item.Label,
                                Font = new FontUsage("Torus", 14, "SemiBold"),
                                Colour = new Color4(200, 210, 230, 255),
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                            },
                        },
                    },

                    // Notification badge
                    notificationBadge = new CircularContainer
                    {
                        Size = new Vector2(22, 18),
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        X = -10,
                        Masking = true,
                        Alpha = item.NotificationCount > 0 ? 1 : 0,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = new Color4(255, 50, 150, 255),
                            },
                            notificationText = new SpriteText
                            {
                                Text = item.NotificationCount > 99 ? "99+" : item.NotificationCount.ToString(),
                                Font = new FontUsage("Torus", 11, "Bold"),
                                Colour = Color4.White,
                                Anchor = Anchor.Centre,
                                Origin = Anchor.Centre,
                            },
                        },
                    },
                };
            }

            public void SetCollapsedState(bool collapsed, double duration)
            {
                labelText.FadeTo(collapsed ? 0 : 1, duration, Easing.OutQuint);
                notificationBadge.FadeTo(collapsed || item.NotificationCount == 0 ? 0 : 1, duration, Easing.OutQuint);
            }

            public void UpdateNotificationCount(int count)
            {
                notificationText.Text = count > 99 ? "99+" : count.ToString();
                notificationBadge.FadeTo(count > 0 ? 1 : 0, 200, Easing.OutQuint);
            }

            private void updateSelectedState()
            {
                selectedIndicator.FadeTo(isSelected ? 1 : 0, 200, Easing.OutQuint);
                hoverBox.FadeColour(isSelected
                    ? new Color4(0, 212, 255, 20)
                    : new Color4(255, 255, 255, 0), 200, Easing.OutQuint);
            }

            protected override bool OnHover(HoverEvent e)
            {
                if (!isSelected)
                    hoverBox.FadeColour(new Color4(255, 255, 255, 15), 150, Easing.OutQuint);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                if (!isSelected)
                    hoverBox.FadeColour(new Color4(255, 255, 255, 0), 150, Easing.OutQuint);
                base.OnHoverLost(e);
            }

            protected override bool OnClick(ClickEvent e)
            {
                Action?.Invoke();

                // Flash effect on click
                hoverBox.FlashColour(new Color4(0, 212, 255, 40), 300, Easing.OutQuint);

                return base.OnClick(e);
            }
        }

        /// <summary>
        /// Button to collapse/expand the panel.
        /// </summary>
        private partial class CollapseButton : Container
        {
            private Box hoverBox = null!;
            private SpriteIcon icon = null!;
            private bool isCollapsed;

            public Action? Action;

            [BackgroundDependencyLoader]
            private void load()
            {
                Size = new Vector2(24);
                Anchor = Anchor.BottomRight;
                Origin = Anchor.BottomRight;
                Margin = new MarginPadding { Right = 12, Bottom = 12 };
                Masking = true;
                CornerRadius = 6;

                Children = new Drawable[]
                {
                    hoverBox = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(255, 255, 255, 0),
                    },
                    icon = new SpriteIcon
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Size = new Vector2(12),
                        Icon = FontAwesome.Solid.ChevronLeft,
                        Colour = new Color4(160, 170, 200, 255),
                    },
                };
            }

            protected override bool OnHover(HoverEvent e)
            {
                hoverBox.FadeColour(new Color4(255, 255, 255, 20), 150, Easing.OutQuint);
                icon.FadeColour(Color4.White, 150, Easing.OutQuint);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                hoverBox.FadeColour(new Color4(255, 255, 255, 0), 150, Easing.OutQuint);
                icon.FadeColour(new Color4(160, 170, 200, 255), 150, Easing.OutQuint);
                base.OnHoverLost(e);
            }

            protected override bool OnClick(ClickEvent e)
            {
                isCollapsed = !isCollapsed;
                icon.RotateTo(isCollapsed ? 180 : 0, 300, Easing.OutQuint);
                Action?.Invoke();
                return base.OnClick(e);
            }
        }
    }
}
