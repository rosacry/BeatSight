using System;
using System.Collections.Generic;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;

namespace BeatSight.Game.UI.Components
{
    public enum FlowButtonStyle
    {
        /// <summary>The recommended next step: filled accent.</summary>
        Primary,
        /// <summary>An alternative path: neutral surface with a border.</summary>
        Secondary,
        /// <summary>Back out / cancel: text weight only.</summary>
        Quiet
    }

    /// <summary>
    /// Shared layout for the short decision screens of the import flow (audio imported, song identification,
    /// AI generation): a centred, width-limited column with a title, a summary card and stacked actions.
    /// </summary>
    public static class FlowCardLayout
    {
        public const float ColumnWidth = 720f;

        public static Drawable Page(params Drawable[] sections) => new Container
        {
            RelativeSizeAxes = Axes.Both,
            Children = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Background
                },
                new BeatSightScrollContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Child = new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Padding = new MarginPadding { Vertical = 72, Horizontal = 32 },
                        Child = new FillFlowContainer
                        {
                            Width = ColumnWidth,
                            AutoSizeAxes = Axes.Y,
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            Direction = FillDirection.Vertical,
                            Spacing = new Vector2(0, 24),
                            Children = sections
                        }
                    }
                }
            }
        };

        public static Drawable Header(string title, string subtitle) => new FillFlowContainer
        {
            RelativeSizeAxes = Axes.X,
            AutoSizeAxes = Axes.Y,
            Direction = FillDirection.Vertical,
            Spacing = new Vector2(0, 6),
            Children = new Drawable[]
            {
                new SpriteText
                {
                    Text = title,
                    Font = BeatSightFont.Title(UITheme.TypeTitle),
                    Colour = UITheme.TextPrimary
                },
                new SpriteText
                {
                    Text = subtitle,
                    Font = BeatSightFont.Body(UITheme.TypeBody),
                    Colour = UITheme.TextSecondary
                }
            }
        };

        /// <summary>Label/value rows on a surface card. The background sits beside (not around) the auto-sized content.</summary>
        public static Drawable SummaryCard(IEnumerable<(string Label, string Value)> rows)
        {
            var flow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Padding = new MarginPadding(20),
                Spacing = new Vector2(0, 12)
            };

            foreach (var (label, value) in rows)
            {
                flow.Add(new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, 2),
                    Children = new Drawable[]
                    {
                        new SpriteText
                        {
                            Text = label,
                            Font = BeatSightFont.Label(UITheme.TypeLabel),
                            Colour = UITheme.TextMuted
                        },
                        new SpriteText
                        {
                            Text = string.IsNullOrWhiteSpace(value) ? "—" : value,
                            Font = BeatSightFont.Body(UITheme.TypeBody + 1),
                            Colour = UITheme.TextPrimary,
                            RelativeSizeAxes = Axes.X,
                            Truncate = true
                        }
                    }
                });
            }

            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 12,
                BorderThickness = 1,
                BorderColour = UITheme.Border,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface
                    },
                    flow
                }
            };
        }

        /// <summary>Wrapped explanatory text (secondary colour).</summary>
        public static Drawable Note(string text) => new TextFlowContainer(t =>
        {
            t.Font = BeatSightFont.Body(UITheme.TypeBody);
            t.Colour = UITheme.TextSecondary;
        })
        {
            RelativeSizeAxes = Axes.X,
            AutoSizeAxes = Axes.Y,
            Text = text
        };

        public static BeatSightButton Button(string text, FlowButtonStyle style, Action? action = null) => new BeatSightButton
        {
            Text = text,
            RelativeSizeAxes = Axes.X,
            Height = style == FlowButtonStyle.Quiet ? 40 : 50,
            CornerRadius = 10,
            FontSize = style == FlowButtonStyle.Quiet ? 15f : 17f,
            BackgroundColour = style switch
            {
                FlowButtonStyle.Primary => UITheme.AccentPrimary,
                FlowButtonStyle.Secondary => UITheme.SurfaceAlt,
                _ => UITheme.Background
            },
            TextColour = style switch
            {
                FlowButtonStyle.Primary => UITheme.TextOnAccent,
                FlowButtonStyle.Secondary => UITheme.TextPrimary,
                _ => UITheme.TextSecondary
            },
            BorderThickness = style == FlowButtonStyle.Secondary ? 1 : 0,
            BorderColour = UITheme.Border,
            Action = action
        };
    }
}
