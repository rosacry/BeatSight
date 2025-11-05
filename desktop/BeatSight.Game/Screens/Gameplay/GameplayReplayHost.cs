using System;
using BeatSight.Game.Beatmaps;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Gameplay
{
    public partial class GameplayReplayHost : CompositeDrawable
    {
        private readonly Func<double> currentTimeProvider;
        private GameplayPlayfield playfield = null!;
        private Beatmap? beatmap;

        public GameplayReplayHost(Func<double> currentTimeProvider)
        {
            this.currentTimeProvider = currentTimeProvider;

            RelativeSizeAxes = Axes.Both;
            Masking = true;
            CornerRadius = 10;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            InternalChild = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(18, 20, 30, 255)
                    },
                    playfield = new GameplayPlayfield(currentTimeProvider)
                    {
                        RelativeSizeAxes = Axes.Both,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Scale = new Vector2(0.72f),
                        Margin = new MarginPadding { Top = 18, Bottom = 32, Left = 26, Right = 26 }
                    },
                    new PreviewHitLine
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 3,
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.BottomCentre,
                        Y = -28
                    }
                }
            };
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Apply any beatmap that was set before we finished loading
            if (beatmap != null)
            {
                osu.Framework.Logging.Logger.Log($"[GameplayReplayHost] LoadComplete: applying pending beatmap with {beatmap.HitObjects.Count} notes", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
                applyBeatmap();
            }
        }

        public void SetBeatmap(Beatmap? beatmap)
        {
            this.beatmap = beatmap;

            osu.Framework.Logging.Logger.Log($"[GameplayReplayHost] SetBeatmap called: beatmap={(beatmap == null ? "null" : $"{beatmap.HitObjects.Count} notes")}, IsLoaded={IsLoaded}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);

            if (!IsLoaded)
            {
                osu.Framework.Logging.Logger.Log("[GameplayReplayHost] SetBeatmap: not loaded yet, will apply in LoadComplete", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
                return;
            }

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
            {
                osu.Framework.Logging.Logger.Log("[GameplayReplayHost] applyBeatmap: playfield is NULL!", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);
                return;
            }

            osu.Framework.Logging.Logger.Log($"[GameplayReplayHost] applyBeatmap: beatmap={(beatmap == null ? "null" : $"{beatmap.HitObjects.Count} notes")}", osu.Framework.Logging.LoggingTarget.Runtime, osu.Framework.Logging.LogLevel.Important);

            // Enable preview mode so notes won't be auto-judged in the editor
            playfield.SetPreviewMode(true);

            if (beatmap != null)
                playfield.LoadBeatmap(beatmap);
            else
                playfield.LoadBeatmap(new Beatmap());
        }

        private partial class PreviewHitLine : CompositeDrawable
        {
            public PreviewHitLine()
            {
                RelativeSizeAxes = Axes.X;
                Height = 3;
                Masking = true;
                CornerRadius = 1.5f;

                InternalChild = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(255, 200, 120, 200)
                };
            }
        }
    }
}
