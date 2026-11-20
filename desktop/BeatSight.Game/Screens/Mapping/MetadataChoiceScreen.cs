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
                FlowCardLayout.Page(
                    FlowCardLayout.Header("Song not identified", "The file's tags did not name the song. Use what was found, or enter it yourself."),
                    FlowCardLayout.SummaryCard(new[]
                    {
                        ("File", importedTrack.DisplayName),
                        ("Detected title", detectedMetadata?.Title ?? "Unknown"),
                        ("Detected artist", detectedMetadata?.Artist ?? "Unknown"),
                        ("Source", detectedMetadata?.Source ?? "None")
                    }),
                    createActions())
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
                var extractButton = FlowCardLayout.Button("Use detected title and artist", FlowButtonStyle.Primary);
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

            bool hasDetected = buttons.Count > 0;
            var manualButton = FlowCardLayout.Button("Enter it myself", hasDetected ? FlowButtonStyle.Secondary : FlowButtonStyle.Primary);
            manualButton.Action = () =>
            {
                this.Push(new MappingChoiceScreen(importedTrack));
            };
            buttons.Add(manualButton);

            var cancelButton = FlowCardLayout.Button("Cancel", FlowButtonStyle.Quiet, () => this.Exit());
            buttons.Add(cancelButton);

            return buttons;
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
