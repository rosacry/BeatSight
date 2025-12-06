// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using osu.Framework.Allocation;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Cursor;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Input.Events;
using osu.Framework.Localisation;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// A modern tooltip with smooth animations and customizable appearance.
    /// </summary>
    public partial class BeatSightTooltip : VisibilityContainer, ITooltip
    {
        private const float max_width = 300;
        private const float corner_radius = 8;
        private const double appear_duration = 200;
        private const double disappear_duration = 150;

        private Container content = null!;
        private Box background = null!;
        private SpriteText titleText = null!;
        private TextFlowContainer descriptionText = null!;

        protected override Container<Drawable> Content => content;

        [BackgroundDependencyLoader]
        private void load()
        {
            AutoSizeAxes = Axes.Both;

            InternalChild = content = new Container
            {
                AutoSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = corner_radius,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Shadow,
                    Colour = Color4.Black.Opacity(0.5f),
                    Radius = 10,
                    Offset = new Vector2(0, 2)
                },
                Children = new Drawable[]
                {
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4Extensions.FromHex("1a1a2e").Opacity(0.95f)
                    },
                    new Container
                    {
                        AutoSizeAxes = Axes.Both,
                        Padding = new MarginPadding(12),
                        Children = new Drawable[]
                        {
                            new FillFlowContainer
                            {
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Vertical,
                                Spacing = new Vector2(0, 4),
                                Children = new Drawable[]
                                {
                                    titleText = new SpriteText
                                    {
                                        Font = new FontUsage("Nunito", size: 14, weight: "Bold"),
                                        Colour = Color4.White,
                                        MaxWidth = max_width
                                    },
                                    descriptionText = new TextFlowContainer
                                    {
                                        AutoSizeAxes = Axes.Y,
                                        Width = max_width,
                                        TextAnchor = Anchor.TopLeft
                                    }
                                }
                            }
                        }
                    }
                }
            };

            descriptionText.AddText(string.Empty, t =>
        {
            t.Font = new FontUsage("Nunito", size: 12);
            t.Colour = Color4.White.Opacity(0.7f);
        });
        }

        public void SetContent(object content)
        {
            if (content is LocalisableString localisableContent)
                SetContentInternal(localisableContent);
            else if (content is string stringContent)
                SetContentInternal(stringContent);
        }

        private void SetContentInternal(LocalisableString contentString)
        {
            // Check if it contains a pipe for title|description format
            string str = contentString.ToString();
            int pipeIndex = str.IndexOf('|');

            if (pipeIndex > 0)
            {
                titleText.Text = str[..pipeIndex];
                titleText.Alpha = 1;

                descriptionText.Clear();
                descriptionText.AddText(str[(pipeIndex + 1)..], t =>
                {
                    t.Font = new FontUsage("Nunito", size: 12);
                    t.Colour = Color4.White.Opacity(0.7f);
                });
            }
            else
            {
                titleText.Text = str;
                titleText.Alpha = 1;
                descriptionText.Clear();
            }
        }
        public void Move(Vector2 pos)
        {
            Position = pos;
        }

        protected override void PopIn()
        {
            content.ScaleTo(0.9f).ScaleTo(1f, appear_duration, Easing.OutQuint);
            this.FadeIn(appear_duration, Easing.OutQuint);
        }

        protected override void PopOut()
        {
            this.FadeOut(disappear_duration, Easing.InQuint);
        }
    }

    /// <summary>
    /// A tooltip container that can be applied to any drawable.
    /// </summary>
    public partial class BeatSightTooltipContainer : Container, IHasTooltip
    {
        public LocalisableString TooltipText { get; set; }

        public BeatSightTooltipContainer()
        {
            AutoSizeAxes = Axes.Both;
        }
    }

    /// <summary>
    /// Extended tooltip with icon support.
    /// </summary>
    public partial class RichTooltip : VisibilityContainer, ITooltip
    {
        private const float max_width = 350;
        private const float corner_radius = 12;

        private Container content = null!;
        private SpriteIcon icon = null!;
        private SpriteText titleText = null!;
        private TextFlowContainer descriptionText = null!;
        private Container iconContainer = null!;

        protected override Container<Drawable> Content => content;

        public IconUsage Icon
        {
            set => icon.Icon = value;
        }

        public Color4 IconColour
        {
            set => iconContainer.Colour = value;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            AutoSizeAxes = Axes.Both;

            InternalChild = content = new Container
            {
                AutoSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = corner_radius,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Shadow,
                    Colour = Color4.Black.Opacity(0.6f),
                    Radius = 15,
                    Offset = new Vector2(0, 4)
                },
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4Extensions.FromHex("1a1a2e")
                    },
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(12, 0),
                        Padding = new MarginPadding(16),
                        Children = new Drawable[]
                        {
                            iconContainer = new Container
                            {
                                Size = new Vector2(36),
                                Masking = true,
                                CornerRadius = 8,
                                Children = new Drawable[]
                                {
                                    new Box
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Colour = Color4Extensions.FromHex("00d4ff").Opacity(0.15f)
                                    },
                                    icon = new SpriteIcon
                                    {
                                        Anchor = Anchor.Centre,
                                        Origin = Anchor.Centre,
                                        Size = new Vector2(18),
                                        Colour = Color4Extensions.FromHex("00d4ff")
                                    }
                                }
                            },
                            new FillFlowContainer
                            {
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Vertical,
                                Spacing = new Vector2(0, 4),
                                Children = new Drawable[]
                                {
                                    titleText = new SpriteText
                                    {
                                        Font = new FontUsage("Nunito", size: 15, weight: "Bold"),
                                        Colour = Color4.White
                                    },
                                    descriptionText = new TextFlowContainer
                                    {
                                        AutoSizeAxes = Axes.Y,
                                        Width = max_width - 80
                                    }
                                }
                            }
                        }
                    }
                }
            };
        }

        public void SetContent(object content)
        {
            if (content is LocalisableString localisableContent)
                SetContentInternal(localisableContent);
            else if (content is string stringContent)
                SetContentInternal(stringContent);
        }

        private void SetContentInternal(LocalisableString contentString)
        {
            string str = contentString.ToString();
            int pipeIndex = str.IndexOf('|');

            if (pipeIndex > 0)
            {
                titleText.Text = str[..pipeIndex];
                descriptionText.Clear();
                descriptionText.AddText(str[(pipeIndex + 1)..], t =>
                {
                    t.Font = new FontUsage("Nunito", size: 12);
                    t.Colour = Color4.White.Opacity(0.7f);
                });
            }
            else
            {
                titleText.Text = str;
                descriptionText.Clear();
            }
        }

        public void Move(Vector2 pos)
        {
            Position = pos;
        }

        protected override void PopIn()
        {
            content.ScaleTo(0.9f).ScaleTo(1f, 200, Easing.OutQuint);
            this.FadeIn(200, Easing.OutQuint);
        }

        protected override void PopOut()
        {
            this.FadeOut(150, Easing.InQuint);
        }
    }

    /// <summary>
    /// Tooltip that appears as a keyboard shortcut hint.
    /// </summary>
    public partial class KeyboardShortcutTooltip : VisibilityContainer, ITooltip
    {
        private Container content = null!;
        private SpriteText actionText = null!;
        private FillFlowContainer keysContainer = null!;

        protected override Container<Drawable> Content => content;

        [BackgroundDependencyLoader]
        private void load()
        {
            AutoSizeAxes = Axes.Both;

            InternalChild = content = new Container
            {
                AutoSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 6,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Shadow,
                    Colour = Color4.Black.Opacity(0.4f),
                    Radius = 8,
                    Offset = new Vector2(0, 2)
                },
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4Extensions.FromHex("242444")
                    },
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(8, 0),
                        Padding = new MarginPadding { Horizontal = 10, Vertical = 6 },
                        Children = new Drawable[]
                        {
                            actionText = new SpriteText
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Font = new FontUsage("Nunito", size: 12),
                                Colour = Color4.White.Opacity(0.8f)
                            },
                            keysContainer = new FillFlowContainer
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Horizontal,
                                Spacing = new Vector2(4, 0)
                            }
                        }
                    }
                }
            };
        }

        public void SetContent(object content)
        {
            if (content is LocalisableString localisableContent)
                SetContentInternal(localisableContent);
            else if (content is string stringContent)
                SetContentInternal(stringContent);
        }

        private void SetContentInternal(LocalisableString contentString)
        {
            string str = contentString.ToString();
            int pipeIndex = str.IndexOf('|');

            if (pipeIndex > 0)
            {
                actionText.Text = str[..pipeIndex];
                string[] keys = str[(pipeIndex + 1)..].Split('+');

                keysContainer.Clear();
                foreach (string key in keys)
                {
                    keysContainer.Add(CreateKeyBadge(key.Trim()));
                }
            }
            else
            {
                actionText.Text = str;
                keysContainer.Clear();
            }
        }

        private Drawable CreateKeyBadge(string key)
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
                        Colour = Color4Extensions.FromHex("1a1a2e")
                    },
                    new SpriteText
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Text = key.ToUpperInvariant(),
                        Font = new FontUsage("Nunito", size: 10, weight: "Bold"),
                        Colour = Color4Extensions.FromHex("00d4ff"),
                        Padding = new MarginPadding { Horizontal = 6, Vertical = 2 }
                    }
                }
            };
        }

        public void Move(Vector2 pos)
        {
            Position = pos;
        }

        protected override void PopIn()
        {
            content.ScaleTo(0.95f).ScaleTo(1f, 150, Easing.OutQuint);
            this.FadeIn(150, Easing.OutQuint);
        }

        protected override void PopOut()
        {
            this.FadeOut(100, Easing.InQuint);
        }
    }
}
