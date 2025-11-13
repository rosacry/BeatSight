using System;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens.Gameplay;
using osu.Framework.Bindables;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    public partial class GameplayPreview : CompositeDrawable
    {
        private readonly Func<double> currentTimeProvider;
        private GameplayReplayHost replayHost = null!;
        private SpriteText placeholderText = null!;
        private Beatmap? beatmap;
        private Bindable<LanePreset> lanePresetSetting = null!;
        private LaneLayout currentLaneLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        public GameplayPreview(Func<double> currentTimeProvider)
        {
            this.currentTimeProvider = currentTimeProvider;

            RelativeSizeAxes = Axes.Both;
            Masking = true;
            CornerRadius = 10;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(24, 26, 38, 235)
                },
                replayHost = new GameplayReplayHost(currentTimeProvider)
                {
                    RelativeSizeAxes = Axes.Both
                },
                placeholderText = new SpriteText
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Font = new FontUsage(size: 18, weight: "Medium"),
                    Colour = new Color4(200, 205, 220, 255),
                    Text = "Load a beatmap to preview gameplay"
                }
            };

            lanePresetSetting = config.GetBindable<LanePreset>(BeatSightSetting.LanePreset);
            lanePresetSetting.BindValueChanged(onLanePresetChanged, true);

            // Beatmap will be applied in LoadComplete() to ensure all components are ready
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Apply any beatmap that was set before we finished loading
            if (beatmap != null)
            {
                osu.Framework.Logging.Logger.Log($"[GameplayPreview] LoadComplete: applying pending beatmap with {beatmap.HitObjects.Count} notes, replayHost={(replayHost == null ? "NULL" : "exists")}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);

                if (replayHost != null)
                {
                    replayHost.SetLaneLayout(currentLaneLayout);
                    replayHost.SetBeatmap(beatmap);
                }
                else
                {
                    osu.Framework.Logging.Logger.Log("[GameplayPreview] LoadComplete: ERROR - replayHost is NULL!", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
                }

                updatePlaceholderState();
            }
        }
        public void SetBeatmap(Beatmap? beatmap)
        {
            this.beatmap = beatmap;

            osu.Framework.Logging.Logger.Log($"[GameplayPreview] SetBeatmap called: beatmap={(beatmap == null ? "null" : $"{beatmap.HitObjects.Count} notes")}, IsLoaded={IsLoaded}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);

            if (!IsLoaded)
            {
                osu.Framework.Logging.Logger.Log("[GameplayPreview] SetBeatmap: not loaded yet, will apply in LoadComplete", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
                return;
            }

            // Immediately update the replay host and placeholder
            replayHost?.SetLaneLayout(currentLaneLayout);
            replayHost?.SetBeatmap(beatmap);
            updatePlaceholderState();
        }

        public void RefreshBeatmap()
        {
            if (!IsLoaded)
                return;

            replayHost?.SetLaneLayout(currentLaneLayout);
            replayHost?.RefreshBeatmap();
            updatePlaceholderState();
        }

        private void onLanePresetChanged(ValueChangedEvent<LanePreset> preset)
        {
            currentLaneLayout = LaneLayoutFactory.Create(preset.NewValue);

            if (replayHost != null)
                replayHost.SetLaneLayout(currentLaneLayout);
        }

        private void updatePlaceholderState()
        {
            if (placeholderText == null)
                return;

            bool showPlaceholder = beatmap == null || beatmap.HitObjects.Count == 0;
            osu.Framework.Logging.Logger.Log($"[GameplayPreview] updatePlaceholderState: showPlaceholder={showPlaceholder}, beatmap={(beatmap == null ? "null" : $"{beatmap.HitObjects.Count} notes")}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
            placeholderText.FadeTo(showPlaceholder ? 1f : 0f, 200, Easing.OutQuint);
        }
    }
}
