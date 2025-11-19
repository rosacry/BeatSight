using System;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens.Playback;
using BeatSight.Game.Screens.Playback.Playfield;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    public partial class PlaybackPreview : CompositeDrawable
    {
        private readonly Func<double> currentTimeProvider;
        private PreviewStageContainer stageContainer = null!;
        private PlaybackPlayfield playfield = null!;
        private SpriteText placeholderText = null!;
        private Beatmap? beatmap;
        private Bindable<LanePreset> lanePresetSetting = null!;
        private Bindable<KickLaneMode> kickLaneModeSetting = null!;
        private LaneLayout currentLaneLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);
        private bool useGlobalKickLine;

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        public PlaybackPreview(Func<double> currentTimeProvider)
        {
            this.currentTimeProvider = currentTimeProvider;

            RelativeSizeAxes = Axes.Both;
            Masking = true;
            CornerRadius = 20;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            playfield = new PlaybackPlayfield(currentTimeProvider)
            {
                RelativeSizeAxes = Axes.Both
            };
            playfield.SetPreviewMode(true);
            playfield.SetLaneLayout(currentLaneLayout);

            stageContainer = new PreviewStageContainer(playfield)
            {
                RelativeSizeAxes = Axes.Both
            };

            placeholderText = new SpriteText
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Font = BeatSightFont.Section(18f),
                Colour = new Color4(198, 205, 224, 255),
                Text = "Load or create a beatmap to preview playback",
                Alpha = 0
            };

            InternalChildren = new Drawable[]
            {
                stageContainer,
                placeholderText
            };

            lanePresetSetting = config.GetBindable<LanePreset>(BeatSightSetting.LanePreset);
            lanePresetSetting.BindValueChanged(onLanePresetChanged, true);

            kickLaneModeSetting = config.GetBindable<KickLaneMode>(BeatSightSetting.KickLaneMode);
            kickLaneModeSetting.BindValueChanged(onKickLaneModeChanged, true);

            updatePlaceholderState();
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();
            applyBeatmap();
        }

        public void SetBeatmap(Beatmap? beatmap)
        {
            this.beatmap = beatmap;

            if (!IsLoaded)
                return;

            applyBeatmap();
        }

        public void RefreshBeatmap()
        {
            if (!IsLoaded)
                return;

            applyBeatmap();
        }

        private void applyBeatmap()
        {
            if (playfield == null)
                return;

            // Update layout if AutoDynamic
            if (lanePresetSetting.Value == LanePreset.AutoDynamic)
            {
                if (beatmap != null && beatmap.DrumKit.Components.Count > 0)
                {
                    currentLaneLayout = LaneLayoutFactory.CreateFromComponents(beatmap.DrumKit.Components);
                }
                else
                {
                    currentLaneLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);
                }
                playfield.SetLaneLayout(currentLaneLayout);
            }

            if (beatmap != null)
            {
                playfield.LoadBeatmap(beatmap);
            }
            else
            {
                playfield.LoadBeatmap(new Beatmap());
            }

            updatePlaceholderState();
        }

        private void onLanePresetChanged(ValueChangedEvent<LanePreset> preset)
        {
            if (preset.NewValue == LanePreset.AutoDynamic && beatmap != null && beatmap.DrumKit.Components.Count > 0)
            {
                currentLaneLayout = LaneLayoutFactory.CreateFromComponents(beatmap.DrumKit.Components);
            }
            else if (preset.NewValue == LanePreset.AutoDynamic)
            {
                currentLaneLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);
            }
            else
            {
                currentLaneLayout = LaneLayoutFactory.Create(preset.NewValue);
            }

            playfield?.SetLaneLayout(currentLaneLayout);
        }

        private void onKickLaneModeChanged(ValueChangedEvent<KickLaneMode> mode)
        {
            useGlobalKickLine = mode.NewValue == KickLaneMode.GlobalLine;
            playfield?.SetKickLineMode(useGlobalKickLine);
        }

        private void updatePlaceholderState()
        {
            int noteCount = beatmap?.HitObjects.Count ?? 0;
            bool hasContent = noteCount > 0;

            stageContainer?.FadeTo(hasContent ? 1f : 0.35f, 200, Easing.OutQuint);

            if (placeholderText == null)
                return;

            if (hasContent)
            {
                placeholderText.FadeOut(200, Easing.OutQuint);
            }
            else
            {
                placeholderText.Text = beatmap == null
                    ? "Load or create a beatmap to preview playback"
                    : "Add notes to preview playback";
                placeholderText.FadeIn(200, Easing.OutQuint);
            }
        }

        private partial class PreviewStageContainer : CompositeDrawable
        {
            private readonly Container stagePadding;

            public PreviewStageContainer(Drawable playfield)
            {
                RelativeSizeAxes = Axes.Both;

                var stageSurface = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 28,
                    EdgeEffect = new EdgeEffectParameters
                    {
                        Type = EdgeEffectType.Shadow,
                        Colour = new Color4(0, 0, 0, 48),
                        Radius = 32,
                        Roundness = 1f
                    },
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(10, 12, 20, 255)
                        },
                        playfield
                    }
                };

                stagePadding = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Child = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 24, Vertical = 18 },
                        Child = stageSurface
                    }
                };

                InternalChild = stagePadding;
            }

            protected override void Update()
            {
                base.Update();

                if (DrawWidth <= 0 || DrawHeight <= 0)
                    return;

                float horizontal = Math.Clamp(DrawWidth * 0.012f, 12f, 60f);
                float vertical = Math.Clamp(DrawHeight * 0.018f, 10f, 60f);

                stagePadding.Padding = new MarginPadding
                {
                    Left = horizontal,
                    Right = horizontal,
                    Top = vertical,
                    Bottom = vertical + 18
                };
            }
        }
    }
}
