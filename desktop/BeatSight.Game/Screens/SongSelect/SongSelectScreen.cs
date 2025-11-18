using System.Collections.Generic;
using System.IO;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Screens.Gameplay;
using BeatSight.Game.Screens.Playback;
using BeatSight.Game.UI.Components;
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
    public enum SongSelectDestination
    {
        Gameplay,
        Playback
    }

    public partial class SongSelectScreen : Screen
    {
        private readonly SongSelectDestination destination;
        private FillFlowContainer beatmapList = null!;
        private SpriteText titleText = null!;
        private BackButton backButton = null!;

        public SongSelectScreen(SongSelectDestination destination = SongSelectDestination.Playback)
        {
            backButton = new BackButton { Margin = BackButton.DefaultMargin };
            this.destination = destination;
        }

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Background
                },
                new ScreenEdgeContainer(scrollable: false)
                {
                    Content = new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 24),
                        Children = new Drawable[]
                        {
                            createHeader(),
                            createBeatmapScroll()
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

            backButton.Action = () => this.Exit();
            populateBeatmaps();
        }

        private Drawable createHeader()
        {
            titleText = new SpriteText
            {
                Font = BeatSightFont.Title(50f),
                Colour = UITheme.TextPrimary,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre
            };

            titleText.Text = destination == SongSelectDestination.Gameplay ? "Song Selection" : "Playback Library";

            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Padding = new MarginPadding { Top = 8, Bottom = 8 },
                Child = titleText
            };
        }

        private Drawable createBeatmapScroll()
        {
            return new Container
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
            };
        }

        private void populateBeatmaps()
        {
            beatmapList.Clear();
            IReadOnlyList<BeatmapLibrary.BeatmapEntry> beatmaps = BeatmapLibrary.GetAvailableBeatmaps();

            if (beatmaps.Count == 0)
            {
                beatmapList.Add(new BeatmapPlaceholder());
                return;
            }

            foreach (var entry in beatmaps)
            {
                beatmapList.Add(new BeatmapButton(entry, destination)
                {
                    Action = () => launchEntry(entry)
                });
            }
        }

        private void launchEntry(BeatmapLibrary.BeatmapEntry entry)
        {
            switch (destination)
            {
                case SongSelectDestination.Gameplay:
                    this.Push(new GameplayScreen(entry.Path));
                    break;

                case SongSelectDestination.Playback:
                default:
                    this.Push(new MappingPlaybackScreen(entry.Path));
                    break;
            }
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
            private const float corner_radius = 16f;
            private const float hover_scale = 1.015f;
            private const float edge_padding = 16f;
            private const float masking_smoothness = 2f;

            private readonly BeatmapLibrary.BeatmapEntry entry;
            private readonly SongSelectDestination destination;
            private readonly Box background;
            private readonly Container buttonBody;

            public BeatmapButton(BeatmapLibrary.BeatmapEntry entry, SongSelectDestination destination)
            {
                this.entry = entry;
                this.destination = destination;

                RelativeSizeAxes = Axes.X;
                AutoSizeAxes = Axes.Y;
                Padding = new MarginPadding { Horizontal = edge_padding };

                InternalChild = buttonBody = new Container
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Masking = true,
                    CornerRadius = corner_radius,
                    MaskingSmoothness = masking_smoothness
                };

                var metadata = entry.Beatmap.Metadata;
                var accentColour = destination == SongSelectDestination.Gameplay
                    ? UITheme.AccentPrimary
                    : UITheme.AccentSecondary;

                buttonBody.AddRange(new Drawable[]
                {
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = 6,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Colour = accentColour
                    },
                    createContent(metadata, accentColour, entry)
                });
            }

            private Drawable createContent(BeatmapMetadata metadata, Color4 accentColour, BeatmapLibrary.BeatmapEntry entry)
            {
                var title = new SpriteText
                {
                    Text = buildDisplayTitle(metadata),
                    Font = BeatSightFont.Title(32f),
                    Colour = UITheme.TextPrimary,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    AllowMultiline = true,
                    MaxWidth = 760,
                    Truncate = false
                };
                disableShadow(title);

                var mapper = new SpriteText
                {
                    Text = buildMapperLabel(metadata),
                    Font = BeatSightFont.Label(18f),
                    Colour = UITheme.TextSecondary,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    MaxWidth = 720,
                    AllowMultiline = false,
                    Truncate = true
                };
                disableShadow(mapper);

                var audioSummary = new SpriteText
                {
                    Text = buildAudioSummary(entry),
                    Font = BeatSightFont.Body(17f),
                    Colour = UITheme.TextSecondary,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    MaxWidth = 520,
                    AllowMultiline = true,
                    Truncate = false
                };
                disableShadow(audioSummary);

                var actionLabel = new SpriteText
                {
                    Text = destination == SongSelectDestination.Gameplay ? "Play" : "Preview",
                    Font = BeatSightFont.Button(17f),
                    Colour = UITheme.Emphasise(accentColour, 1.05f),
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre
                };
                disableShadow(actionLabel);

                var summaryRow = new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Direction = FillDirection.Horizontal,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    Spacing = new Vector2(16, 0),
                    Children = new Drawable[]
                    {
                        audioSummary,
                        actionLabel
                    }
                };

                return new Container
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Padding = new MarginPadding { Horizontal = 30, Vertical = 18 },
                    Child = new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Spacing = new Vector2(6, 8),
                        Children = new Drawable[]
                        {
                            title,
                            mapper,
                            summaryRow
                        }
                    }
                };
            }

            private static string buildDisplayTitle(BeatmapMetadata metadata)
            {
                string title = firstNonEmpty(metadata.Title, fallback: "Untitled");
                string artist = firstNonEmpty(metadata.Artist, fallback: "Unknown Artist");
                return $"{title} — {artist}";
            }

            private static string buildMapperLabel(BeatmapMetadata metadata)
            {
                string creator = firstNonEmpty(metadata.Creator, fallback: "Unknown Mapper");
                string difficulty = metadata.Difficulty > 0 ? $"★ {metadata.Difficulty:0.0}" : "unrated";
                return $"Mapped by {creator} • {difficulty}";
            }

            private static string buildAudioSummary(BeatmapLibrary.BeatmapEntry entry)
            {
                var audio = entry.Beatmap.Audio;
                string duration = audio.Duration > 0 ? $"{audio.Duration:0}" : "?";
                string filename = !string.IsNullOrEmpty(audio.Filename) ? Path.GetFileName(audio.Filename) : "no-audio";
                string stem = !string.IsNullOrEmpty(audio.DrumStem) ? Path.GetFileName(audio.DrumStem) : "no stem";

                return $"Audio {duration} ms • File {filename} • Drum Stem {stem}";
            }

            private static string firstNonEmpty(string? primary, string? secondary = null, string fallback = "")
            {
                if (!string.IsNullOrWhiteSpace(primary))
                    return primary;

                if (!string.IsNullOrWhiteSpace(secondary))
                    return secondary;

                return fallback;
            }

            private static void disableShadow(SpriteText text)
            {
                text.Shadow = false;
                text.ShadowColour = Color4.Transparent;
                text.ShadowOffset = Vector2.Zero;
            }

            protected override bool OnHover(HoverEvent e)
            {
                background.FadeColour(UITheme.Emphasise(UITheme.Surface, 1.07f), 200, Easing.OutQuint);
                buttonBody.ScaleTo(hover_scale, 200, Easing.OutQuint);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                base.OnHoverLost(e);
                background.FadeColour(UITheme.Surface, 200, Easing.OutQuint);
                buttonBody.ScaleTo(1f, 200, Easing.OutQuint);
            }

            protected override bool OnClick(ClickEvent e)
            {
                buttonBody.ScaleTo(0.98f, 80, Easing.OutQuint)
                          .Then()
                          .ScaleTo(hover_scale, 120, Easing.OutQuint)
                          .Then()
                          .ScaleTo(1f, 120, Easing.OutQuint);
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
                            Colour = UITheme.Surface
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
                        text.Font = BeatSightFont.Section(22f);
                        text.Colour = new Color4(200, 205, 220, 255);
                    });

                return message;
            }
        }
    }
}
