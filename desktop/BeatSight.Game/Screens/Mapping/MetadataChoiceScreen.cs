using BeatSight.Game.Mapping;
using BeatSight.Game.Services.Metadata;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;

namespace BeatSight.Game.Screens.Mapping
{
    public partial class MetadataChoiceScreen : BeatSightScreen
    {
        private readonly ImportedAudioTrack importedTrack;
        private readonly DetectedMetadata? detectedMetadata;

        public MetadataChoiceScreen(ImportedAudioTrack importedTrack, DetectedMetadata? detectedMetadata)
        {
            this.importedTrack = importedTrack;
            this.detectedMetadata = detectedMetadata;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(18, 18, 28, 255)
                },
                new ScreenEdgeContainer
                {
                    EdgePadding = new MarginPadding { Horizontal = 60, Vertical = 40 },
                    Content = new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 20),
                        Children = new Drawable[]
                        {
                            createHeader(),
                            createSummaryPanel(),
                            createActions()
                        }
                    }
                }
            };
        }

        private Drawable createHeader()
        {
            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 6),
                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Text = "Song Not Identified",
                        Font = BeatSightFont.Title(36f),
                        Colour = Color4.White
                    },
                    new SpriteText
                    {
                        Text = "We couldn't automatically identify this song.",
                        Font = BeatSightFont.Section(20f),
                        Colour = new Color4(190, 195, 210, 255)
                    }
                }
            };
        }

        private Drawable createSummaryPanel()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 12,
                Child = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Padding = new MarginPadding(24),
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(24, 27, 40, 255)
                        },
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Direction = FillDirection.Vertical,
                            Spacing = new Vector2(0, 10),
                            Children = new Drawable[]
                            {
                                createInfoRow("File", importedTrack.DisplayName),
                                createInfoRow("Detected Title", detectedMetadata?.Title ?? "Unknown"),
                                createInfoRow("Detected Artist", detectedMetadata?.Artist ?? "Unknown"),
                                createInfoRow("Source", detectedMetadata?.Source ?? "None")
                            }
                        }
                    }
                }
            };
        }

        private Drawable createActions()
        {
            var buttons = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 14)
            };

            if (detectedMetadata != null && (!string.IsNullOrEmpty(detectedMetadata.Title) || !string.IsNullOrEmpty(detectedMetadata.Artist)))
            {
                var extractButton = createPrimaryButton("Use Extracted Metadata", new Color4(120, 200, 255, 255));
                extractButton.Action = () =>
                {
                    importedTrack.Title = detectedMetadata.Title;
                    importedTrack.Artist = detectedMetadata.Artist;
                    if (!string.IsNullOrEmpty(detectedMetadata.Title))
                        importedTrack.DisplayName = detectedMetadata.Title;

                    this.Push(new MappingChoiceScreen(importedTrack));
                };
                buttons.Add(extractButton);
            }

            var manualButton = createPrimaryButton("Input Manually", new Color4(180, 130, 255, 255));
            manualButton.Action = () =>
            {
                this.Push(new MappingChoiceScreen(importedTrack));
            };
            buttons.Add(manualButton);

            var cancelButton = createSecondaryButton("Cancel", () => this.Exit());
            buttons.Add(cancelButton);

            return buttons;
        }

        private Drawable createInfoRow(string label, string value)
        {
            return new FillFlowContainer
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
                        Font = BeatSightFont.Section(16f),
                        Colour = new Color4(160, 170, 190, 255)
                    },
                    new SpriteText
                    {
                        Text = value,
                        Font = BeatSightFont.Section(22f),
                        Colour = Color4.White
                    }
                }
            };
        }

        private BasicButton createPrimaryButton(string text, Color4 colour)
        {
            return new BasicButton
            {
                Text = text,
                RelativeSizeAxes = Axes.X,
                Height = 52,
                BackgroundColour = colour,
                CornerRadius = 10,
                Masking = true,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre
            };
        }

        private BasicButton createSecondaryButton(string text, System.Action action)
        {
            var button = new BasicButton
            {
                Text = text,
                RelativeSizeAxes = Axes.X,
                Height = 46,
                BackgroundColour = new Color4(60, 65, 85, 255),
                CornerRadius = 10,
                Masking = true,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre
            };

            button.Action = action;
            return button;
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
    }
}
