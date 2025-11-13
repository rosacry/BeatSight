using System.Collections.Generic;
using System.IO;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Screens.Playback;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.SongSelect
{
    public partial class SongSelectScreen : Screen
    {
        private FillFlowContainer beatmapList = null!;
        private SpriteText statusText = null!;

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(15, 18, 30, 255)
                },
                new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, 20),
                    Padding = new MarginPadding(40),
                    Children = new Drawable[]
                    {
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Direction = FillDirection.Vertical,
                            Spacing = new Vector2(0, 8),
                            Children = new Drawable[]
                            {
                                new SpriteText
                                {
                                    Text = "Select a Beatmap",
                                    Font = new FontUsage(size: 48, weight: "Bold"),
                                    Colour = Color4.White
                                },
                                statusText = new SpriteText
                                {
                                    Font = new FontUsage(size: 20),
                                    Colour = new Color4(200, 205, 220, 255)
                                }
                            }
                        },
                        new Container
                        {
                            RelativeSizeAxes = Axes.Both,
                            Height = 1,
                            Child = new BasicScrollContainer
                            {
                                RelativeSizeAxes = Axes.Both,
                                Child = beatmapList = new FillFlowContainer
                                {
                                    RelativeSizeAxes = Axes.X,
                                    AutoSizeAxes = Axes.Y,
                                    Direction = FillDirection.Vertical,
                                    Spacing = new Vector2(0, 12)
                                }
                            }
                        }
                    }
                }
            };

            populateBeatmaps();
        }

        private void populateBeatmaps()
        {
            beatmapList.Clear();
            IReadOnlyList<BeatmapLibrary.BeatmapEntry> beatmaps = BeatmapLibrary.GetAvailableBeatmaps();

            if (beatmaps.Count == 0)
            {
                statusText.Text = "Drop .bsm beatmaps into shared/formats or BeatSight/Beatmaps to get started.";
                beatmapList.Add(new BeatmapPlaceholder());
                return;
            }

            statusText.Text = "Select a mapping to audition. Toggle full mix vs drums inside playback.";

            foreach (var entry in beatmaps)
                beatmapList.Add(new BeatmapButton(entry)
                {
                    Action = () => this.Push(new MappingPlaybackScreen(entry.Path))
                });
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

        private partial class BeatmapButton : Button
        {
            private readonly BeatmapLibrary.BeatmapEntry entry;
            private readonly Box background;

            public BeatmapButton(BeatmapLibrary.BeatmapEntry entry)
            {
                this.entry = entry;

                RelativeSizeAxes = Axes.X;
                Height = 80;
                Masking = true;
                CornerRadius = 12;

                var metadata = entry.Beatmap.Metadata;

                AddRangeInternal(new Drawable[]
                {
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(30, 40, 70, 255)
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Direction = FillDirection.Vertical,
                        Padding = new MarginPadding { Left = 20, Right = 20, Top = 16, Bottom = 16 },
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = $"{metadata.Title} — {metadata.Artist}",
                                Font = new FontUsage(size: 28, weight: "Medium"),
                                Colour = Color4.White
                            },
                            new SpriteText
                            {
                                Text = $"Mapped by {metadata.Creator} • ★ {metadata.Difficulty:0.0}",
                                Font = new FontUsage(size: 18),
                                Colour = new Color4(190, 195, 210, 255)
                            },
                            new SpriteText
                            {
                                Text = buildAudioSummary(entry),
                                Font = new FontUsage(size: 16),
                                Colour = new Color4(170, 175, 190, 255)
                            }
                        }
                    }
                });
            }

            private string buildAudioSummary(BeatmapLibrary.BeatmapEntry entry)
            {
                var audio = entry.Beatmap.Audio;
                string duration = audio.Duration > 0 ? $"{audio.Duration:0}" : "?";
                string filename = !string.IsNullOrEmpty(audio.Filename) ? Path.GetFileName(audio.Filename) : "no-audio";
                string stem = !string.IsNullOrEmpty(audio.DrumStem) ? Path.GetFileName(audio.DrumStem) : "no stem";

                return $"Audio {duration} ms • File {filename} • Drum Stem {stem}";
            }

            protected override bool OnHover(HoverEvent e)
            {
                background.FadeColour(new Color4(45, 70, 120, 255), 200, Easing.OutQuint);
                this.ScaleTo(1.02f, 200, Easing.OutQuint);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                base.OnHoverLost(e);
                background.FadeColour(new Color4(30, 40, 70, 255), 200, Easing.OutQuint);
                this.ScaleTo(1f, 200, Easing.OutQuint);
            }

            protected override bool OnClick(ClickEvent e)
            {
                this.ScaleTo(0.98f, 80, Easing.OutQuint).Then().ScaleTo(1.02f, 120, Easing.OutQuint);
                return base.OnClick(e);
            }
        }

        private partial class BeatmapPlaceholder : CompositeDrawable
        {
            public BeatmapPlaceholder()
            {
                RelativeSizeAxes = Axes.X;
                Height = 200;

                InternalChildren = new Drawable[]
                {
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        CornerRadius = 12,
                        Masking = true,
                        Child = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(25, 28, 40, 255)
                        }
                    },
                    createPlaceholderMessage()
                };
            }

            private Drawable createPlaceholderMessage()
            {
                var message = new TextFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    TextAnchor = Anchor.Centre,
                    Padding = new MarginPadding(20)
                };

                message.AddText("No beatmaps found. Copy your .bsm files into BeatSight/Beatmaps or shared/formats.",
                    text =>
                    {
                        text.Font = new FontUsage(size: 22);
                        text.Colour = new Color4(200, 205, 220, 255);
                    });

                return message;
            }
        }
    }
}
