using System.Collections.Generic;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    internal partial class ThreeDKickLane : Container
    {
        public readonly Container PulseContainer;
        private readonly int totalLanes;
        private readonly List<Box> rungs = new List<Box>();
        private const int RungCount = 6;

        public ThreeDKickLane(int totalLanes)
        {
            this.totalLanes = totalLanes;
            RelativeSizeAxes = Axes.Both;

            PulseContainer = new Container { RelativeSizeAxes = Axes.Both };
            AddInternal(PulseContainer);

            for (int i = 0; i < RungCount; i++)
            {
                var box = new Box
                {
                    Origin = Anchor.Centre,
                    Colour = new Color4(150, 120, 220, 150)
                };
                rungs.Add(box);
                AddInternal(box);
            }

            // Main hit bar
            AddInternal(new Box
            {
                Origin = Anchor.Centre,
                Colour = new Color4(230, 210, 255, 220),
                Height = 6,
                Name = "HitBar"
            });
        }

        protected override void Update()
        {
            base.Update();
            if (DrawWidth <= 0 || DrawHeight <= 0) return;

            float centerX = DrawWidth / 2f;
            float bottomY = DrawHeight * 0.85f;
            float topY = DrawHeight * 0.15f;

            float highwayWidthAtBottom = DrawWidth * 0.85f;
            float totalHeight = bottomY - topY;

            // Calculate width at any Y
            float GetWidthAtY(float y)
            {
                float t = (y - topY) / totalHeight;
                return lerp(highwayWidthAtBottom * 0.35f, highwayWidthAtBottom, t);
            }

            // Update Rungs (going backwards from hit line)
            for (int i = 0; i < RungCount; i++)
            {
                // Distance in pixels from bottom
                float dist = i * 14;
                float y = bottomY - dist;
                float w = GetWidthAtY(y);

                var box = rungs[i];
                box.Position = new Vector2(centerX, y);
                box.Size = new Vector2(w, 3);
            }

            // Update Hit Bar
            var hitBar = InternalChildren[InternalChildren.Count - 1];
            hitBar.Position = new Vector2(centerX, bottomY);
            hitBar.Size = new Vector2(highwayWidthAtBottom, 6);
        }

        private static float lerp(float start, float end, float amount) => start + (end - start) * amount;
    }
}
