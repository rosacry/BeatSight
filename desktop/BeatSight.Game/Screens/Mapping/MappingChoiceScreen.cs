using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens;
using BeatSight.Game.Screens.Editor;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Mapping
{
    public partial class MappingChoiceScreen : BeatSightScreen
    {
        private readonly ImportedAudioTrack importedTrack;

        private BasicButton manualButton = null!;
        private BasicButton aiButton = null!;
        private BasicButton localAiButton = null!;
        private Container localAiContainer = null!;
        private SpriteText statusText = null!;

        private Bindable<bool> developerModeEnabled = null!;
        private Bindable<bool> useLocalInference = null!;
        private Bindable<bool> showLocalOption = null!;
        private Bindable<string> localModelPath = null!;

        public MappingChoiceScreen(ImportedAudioTrack importedTrack)
        {
            this.importedTrack = importedTrack;
        }

        [BackgroundDependencyLoader]
        private void load(BeatSightConfigManager config)
        {
            developerModeEnabled = config.GetBindable<bool>(BeatSightSetting.DeveloperModeEnabled);
            useLocalInference = config.GetBindable<bool>(BeatSightSetting.UseLocalInference);
            showLocalOption = config.GetBindable<bool>(BeatSightSetting.ShowLocalInferenceOption);
            localModelPath = config.GetBindable<string>(BeatSightSetting.LocalModelPath);

            InternalChildren = new Drawable[]
            {
                FlowCardLayout.Page(
                    FlowCardLayout.Header("Audio imported", "Choose how to build the drum chart for this song."),
                    FlowCardLayout.SummaryCard(new[]
                    {
                        ("Title", importedTrack.DisplayName),
                        ("Length", importedTrack.FormatDuration()),
                        ("File size", importedTrack.FormatFileSize()),
                        ("Source", importedTrack.OriginalPath)
                    }),
                    createActions())
            };
        }

        private Drawable createActions()
        {
            statusText = new SpriteText
            {
                Text = "AI transcription separates the drums and charts every hit; you can correct it in the editor.",
                Font = BeatSightFont.Body(UITheme.TypeBody),
                Colour = UITheme.TextSecondary,
                RelativeSizeAxes = Axes.X,
                Truncate = true
            };

            manualButton = FlowCardLayout.Button("Chart it myself", FlowButtonStyle.Secondary);
            manualButton.Action = () => this.Push(new EditorScreen(null, importedTrack));

            // AI transcription is the recommended path; charting by hand is the alternative.
            aiButton = FlowCardLayout.Button("Transcribe with AI", FlowButtonStyle.Primary);
            aiButton.Action = () => this.Push(new MappingGenerationScreen(importedTrack));

            // Local AI button (Developer Mode only)
            localAiButton = FlowCardLayout.Button("Run AI locally (developer)", FlowButtonStyle.Secondary);
            localAiButton.Action = () => this.Push(new MappingGenerationScreen(importedTrack, useLocalInference: true));

            var hasLocalModel = !string.IsNullOrEmpty(localModelPath.Value) && System.IO.File.Exists(localModelPath.Value);
            var localModelInfo = hasLocalModel
                ? $"Model: {System.IO.Path.GetFileName(localModelPath.Value)}"
                : "No local model configured (Settings → Developer)";

            localAiContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Alpha = (developerModeEnabled.Value && showLocalOption.Value) ? 1 : 0,
                Children = new Drawable[]
                {
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 6),
                        Children = new Drawable[]
                        {
                            localAiButton,
                            new SpriteText
                            {
                                Text = localModelInfo,
                                Font = BeatSightFont.Body(14f),
                                Colour = hasLocalModel ? UITheme.AccentSuccess : UITheme.AccentWarning,
                                Anchor = Anchor.TopCentre,
                                Origin = Anchor.TopCentre
                            }
                        }
                    }
                }
            };

            // Disable button if no model is configured
            if (!hasLocalModel)
            {
                localAiButton.Enabled.Value = false;
                localAiButton.Action = null;
            }

            var cancelButton = FlowCardLayout.Button("Cancel", FlowButtonStyle.Quiet, () => this.Exit());

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 14),
                Children = new Drawable[]
                {
                    statusText,
                    aiButton,
                    manualButton,
                    localAiContainer,
                    cancelButton
                }
            };
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
