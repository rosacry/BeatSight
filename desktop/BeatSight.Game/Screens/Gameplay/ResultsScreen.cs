using System;
using BeatSight.Game.Beatmaps;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Gameplay
{
    public partial class ResultsScreen : Screen
    {
        private readonly GameplayResult result;

        public ResultsScreen(GameplayResult result)
        {
            this.result = result;
        }

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(12, 14, 24, 255)
                },
                new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Vertical,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Spacing = new Vector2(0, 30),
                    Children = new Drawable[]
                    {
                        new SpriteText
                        {
                            Text = "Results",
                            Font = new FontUsage(size: 56, weight: "Bold"),
                            Colour = Color4.White,
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre
                        },
                        new SpriteText
                        {
                            Text = $"{result.BeatmapTitle}",
                            Font = new FontUsage(size: 32),
                            Colour = new Color4(200, 205, 220, 255),
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre
                        },
                        new Container
                        {
                            AutoSizeAxes = Axes.Both,
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            Child = createGradeDisplay()
                        },
                        new GridContainer
                        {
                            Width = 600,
                            AutoSizeAxes = Axes.Y,
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            RowDimensions = new[]
                            {
                                new Dimension(GridSizeMode.AutoSize),
                                new Dimension(GridSizeMode.AutoSize),
                                new Dimension(GridSizeMode.AutoSize),
                                new Dimension(GridSizeMode.AutoSize),
                            },
                            Content = new[]
                            {
                                createStatRow("Score", result.TotalScore.ToString("N0")),
                                createStatRow("Accuracy", $"{result.Accuracy:F2}%"),
                                createStatRow("Max Combo", $"{result.MaxCombo}x"),
                                createStatRow("Judgements", $"{result.Perfect}/{result.Great}/{result.Good}/{result.Meh}/{result.Miss}")
                            }
                        },
                        new Container { Height = 20 },
                        new FillFlowContainer
                        {
                            AutoSizeAxes = Axes.Both,
                            Direction = FillDirection.Horizontal,
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            Spacing = new Vector2(20, 0),
                            Children = new Drawable[]
                            {
                                new ResultButton("Retry", new Color4(76, 175, 80, 255))
                                {
                                    Action = () =>
                                    {
                                        this.Exit();
                                        this.Push(new GameplayScreen(result.BeatmapPath));
                                    }
                                },
                                new ResultButton("Back to Menu", new Color4(33, 150, 243, 255))
                                {
                                    Action = () =>
                                    {
                                        this.Exit();
                                        this.Exit(); // Exit twice to get back to song select
                                    }
                                }
                            }
                        }
                    }
                }
            };
        }

        private Drawable createGradeDisplay()
        {
            string grade = calculateGrade(result.Accuracy);
            Color4 gradeColour = grade switch
            {
                "S" or "SS" => new Color4(255, 215, 0, 255),
                "A" => new Color4(76, 175, 80, 255),
                "B" => new Color4(33, 150, 243, 255),
                "C" => new Color4(255, 152, 0, 255),
                "D" => new Color4(244, 67, 54, 255),
                _ => Color4.Gray
            };

            return new CircularContainer
            {
                Size = new Vector2(140, 140),
                Masking = true,
                BorderThickness = 5,
                BorderColour = gradeColour,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4((byte)(gradeColour.R * 0.2f), (byte)(gradeColour.G * 0.2f), (byte)(gradeColour.B * 0.2f), 255)
                    },
                    new SpriteText
                    {
                        Text = grade,
                        Font = new FontUsage(size: 72, weight: "Bold"),
                        Colour = gradeColour,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre
                    }
                }
            };
        }

        private Drawable[] createStatRow(string label, string value)
        {
            return new Drawable[]
            {
                new SpriteText
                {
                    Text = label,
                    Font = new FontUsage(size: 26),
                    Colour = new Color4(180, 185, 200, 255),
                    Anchor = Anchor.CentreLeft,
                    Origin = Anchor.CentreLeft
                },
                new SpriteText
                {
                    Text = value,
                    Font = new FontUsage(size: 28, weight: "Bold"),
                    Colour = Color4.White,
                    Anchor = Anchor.CentreRight,
                    Origin = Anchor.CentreRight
                }
            };
        }

        private static string calculateGrade(double accuracy)
        {
            if (accuracy >= 95.0) return "SS";
            if (accuracy >= 90.0) return "S";
            if (accuracy >= 80.0) return "A";
            if (accuracy >= 70.0) return "B";
            if (accuracy >= 60.0) return "C";
            return "D";
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == osuTK.Input.Key.Escape)
            {
                this.Exit();
                return true;
            }

            return base.OnKeyDown(e);
        }

        private partial class ResultButton : Button
        {
            private readonly Color4 baseColour;
            private readonly Box background;
            private readonly Container content;

            public ResultButton(string text, Color4 colour)
            {
                AutoSizeAxes = Axes.Both;
                baseColour = colour;

                AddRangeInternal(new Drawable[]
                {
                    content = new Container
                    {
                        Width = 200,
                        Height = 50,
                        Masking = true,
                        CornerRadius = 10,
                        Children = new Drawable[]
                        {
                            background = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = new Color4((byte)(colour.R * 0.7f), (byte)(colour.G * 0.7f), (byte)(colour.B * 0.7f), colour.A)
                            },
                            new SpriteText
                            {
                                Text = text,
                                Font = new FontUsage(size: 22),
                                Colour = Color4.White,
                                Anchor = Anchor.Centre,
                                Origin = Anchor.Centre
                            }
                        }
                    }
                });
            }

            protected override bool OnHover(HoverEvent e)
            {
                background.FadeColour(baseColour, 200, Easing.OutQuint);
                content.ScaleTo(1.05f, 200, Easing.OutQuint);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                base.OnHoverLost(e);
                background.FadeColour(new Color4((byte)(baseColour.R * 0.7f), (byte)(baseColour.G * 0.7f), (byte)(baseColour.B * 0.7f), baseColour.A), 200, Easing.OutQuint);
                content.ScaleTo(1f, 200, Easing.OutQuint);
            }

            protected override bool OnClick(ClickEvent e)
            {
                content.ScaleTo(0.95f, 80, Easing.OutQuad).Then().ScaleTo(1.05f, 120, Easing.OutQuad);
                return base.OnClick(e);
            }
        }
    }

    /// <summary>
    /// Contains the results of a gameplay session
    /// </summary>
    public class GameplayResult
    {
        public string BeatmapTitle { get; set; } = string.Empty;
        public string BeatmapPath { get; set; } = string.Empty;
        public int TotalScore { get; set; }
        public double Accuracy { get; set; }
        public int MaxCombo { get; set; }
        public int Perfect { get; set; }
        public int Great { get; set; }
        public int Good { get; set; }
        public int Meh { get; set; }
        public int Miss { get; set; }
    }
}
