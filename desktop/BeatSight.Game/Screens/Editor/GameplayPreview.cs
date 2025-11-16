using System;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
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
        private PreviewPlaceholder previewDisplay = null!;
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
                previewDisplay = new PreviewPlaceholder(currentTimeProvider)
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
                osu.Framework.Logging.Logger.Log($"[GameplayPreview] LoadComplete: applying pending beatmap with {beatmap.HitObjects.Count} notes", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
                previewDisplay?.SetLaneLayout(currentLaneLayout);
                previewDisplay?.SetBeatmap(beatmap);
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
            previewDisplay?.SetLaneLayout(currentLaneLayout);
            previewDisplay?.SetBeatmap(beatmap);
            updatePlaceholderState();
        }

        public void RefreshBeatmap()
        {
            if (!IsLoaded)
                return;

            previewDisplay?.SetLaneLayout(currentLaneLayout);
            previewDisplay?.RefreshBeatmap();
            updatePlaceholderState();
        }

        private void onLanePresetChanged(ValueChangedEvent<LanePreset> preset)
        {
            currentLaneLayout = LaneLayoutFactory.Create(preset.NewValue);

            previewDisplay?.SetLaneLayout(currentLaneLayout);
        }

        private void updatePlaceholderState()
        {
            if (placeholderText == null)
                return;

            int noteCount = beatmap?.HitObjects.Count ?? 0;
            bool showPlaceholder = noteCount == 0;
            osu.Framework.Logging.Logger.Log($"[GameplayPreview] updatePlaceholderState: showPlaceholder={showPlaceholder}, beatmap={(beatmap == null ? "null" : $"{noteCount} notes")}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
            placeholderText.Text = showPlaceholder
                ? "Load a beatmap to preview gameplay"
                : $"Preview disabled (beatmap has {noteCount} notes)";

            placeholderText.FadeTo(1f, 200, Easing.OutQuint);
        }

        private partial class PreviewPlaceholder : CompositeDrawable
        {
            private readonly Func<double> timeProvider;
            private Beatmap? beatmap;
            private LaneLayout laneLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);

            public PreviewPlaceholder(Func<double> timeProvider)
            {
                this.timeProvider = timeProvider;
                RelativeSizeAxes = Axes.Both;
                Masking = true;
                CornerRadius = 8;

                InternalChild = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(18, 20, 30, 255)
                };
            }

            public void SetBeatmap(Beatmap? beatmap)
            {
                this.beatmap = beatmap;
                // No-op for now – preview visuals were retired with gameplay replay host.
            }

            public void RefreshBeatmap()
            {
                // No-op; kept for API compatibility with existing editor flow.
            }

            public void SetLaneLayout(LaneLayout layout)
            {
                laneLayout = layout;
            }
        }
    }
}
