using System;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield.Views
{
    /// <summary>
    /// 2D lane view renderer (osu!mania / StepMania style).
    /// Notes fall vertically down distinct lanes with clear column separation.
    /// Optimized for readability and precise timing visualization.
    /// </summary>
    public class TwoDimensionalLaneView : PlayfieldViewBase
    {
        public override Configuration.LaneViewMode ViewMode => Configuration.LaneViewMode.TwoDimensional;

        // Visual constants for 2D mode
        private const float HitLinePosition = 0.92f; // Lower than default for better visual balance
        private const float LaneGapRatio = 0.02f; // Gap between lanes as ratio of lane width
        private const float NoteFillRatio = 0.82f; // How much of lane width the note fills
        private const float LaneSeparatorWidth = 2f;
        private const float LaneSeparatorAlpha = 0.15f;

        private static readonly Color4 LaneBackgroundDark = new Color4(16, 18, 28, 255);
        private static readonly Color4 LaneBackgroundLight = new Color4(22, 26, 40, 255);
        private static readonly Color4 LaneSeparatorColour = new Color4(255, 255, 255, 40);

        public override float HitLineYRatio => HitLinePosition;

        public override Drawable CreateBackground(float width, float height, int laneCount, bool useGlobalKick)
        {
            var container = new Container
            {
                RelativeSizeAxes = Axes.Both
            };

            int visibleLanes = useGlobalKick ? Math.Max(1, laneCount - 1) : laneCount;
            float laneWidthRatio = 1f / visibleLanes;

            // Create alternating lane backgrounds for visual distinction
            for (int i = 0; i < visibleLanes; i++)
            {
                bool isAlternateLane = i % 2 == 0;
                var laneColour = isAlternateLane ? LaneBackgroundDark : LaneBackgroundLight;

                // Subtle gradient for depth
                var topColour = UITheme.Emphasise(laneColour, 0.85f);
                var bottomColour = UITheme.Emphasise(laneColour, 1.15f);

                container.Add(new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    RelativePositionAxes = Axes.X,
                    Width = laneWidthRatio,
                    X = i * laneWidthRatio,
                    Colour = ColourInfo.GradientVertical(topColour, bottomColour)
                });
            }

            // Lane separators
            for (int i = 1; i < visibleLanes; i++)
            {
                container.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = LaneSeparatorWidth,
                    RelativePositionAxes = Axes.X,
                    X = i * laneWidthRatio,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre,
                    Colour = LaneSeparatorColour
                });
            }

            // Edge highlights
            container.Add(new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = 3,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Colour = ColourInfo.GradientVertical(
                    new Color4(100, 140, 255, 40),
                    new Color4(100, 140, 255, 80))
            });

            container.Add(new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = 3,
                Anchor = Anchor.TopRight,
                Origin = Anchor.TopRight,
                Colour = ColourInfo.GradientVertical(
                    new Color4(100, 140, 255, 40),
                    new Color4(100, 140, 255, 80))
            });

            return container;
        }

        public override Drawable CreateStrikeZone()
        {
            return new TwoDimensionalStrikeZone();
        }

        public override void UpdateNotePosition(
            DrawableNote note,
            float progress,
            float drawWidth,
            float drawHeight,
            float hitLineY,
            float travelDistance,
            NotePositionContext ctx)
        {
            // Calculate Y position based on progress
            float y = hitLineY - travelDistance * (1 - progress);

            if (ctx.UseGlobalKickLine && note.IsKick)
            {
                // Kick notes span the full width as a horizontal bar
                UpdateKickNotePosition(note, y, drawWidth, drawHeight, hitLineY);
            }
            else
            {
                // Regular lane note
                UpdateLaneNotePosition(note, y, drawWidth, ctx);
            }

            // Fade out notes that have passed the hit line
            note.Alpha = y > hitLineY + note.Height / 2 + 2 ? 0 : 1;
        }

        private void UpdateKickNotePosition(DrawableNote note, float y, float drawWidth, float drawHeight, float hitLineY)
        {
            float kickNoteHeight = Math.Clamp(drawHeight * 0.025f, 12f, 24f);

            note.Width = drawWidth;
            note.Height = kickNoteHeight;
            note.Position = new Vector2(drawWidth / 2, y);
            note.Scale = Vector2.One;
            note.Rotation = 0;
        }

        private void UpdateLaneNotePosition(DrawableNote note, float y, float drawWidth, NotePositionContext ctx)
        {
            float laneWidth = drawWidth / ctx.VisibleLaneCount;
            int visualLaneIndex = GetVisualLaneIndex(note.Lane, ctx);

            // Calculate note width based on user preference
            float userScale = (float)(Context?.NoteWidthScale.Value ?? 1.0);
            note.Width = CalculateNoteWidth(laneWidth, userScale);

            // Center note in lane
            float x = laneWidth * visualLaneIndex + laneWidth / 2;

            note.Position = new Vector2(x, y);
            note.Scale = Vector2.One;
            note.Rotation = 0;
        }

        public override void ApplyNoteStyle(DrawableNote note)
        {
            note.SetViewMode(Configuration.LaneViewMode.TwoDimensional);
        }
    }

    /// <summary>
    /// Strike zone visual for 2D lane view.
    /// Clean, wide hit area indicator across all lanes.
    /// </summary>
    internal partial class TwoDimensionalStrikeZone : CompositeDrawable
    {
        private const float ZoneHeight = 22f;
        private const float ZoneBorderThickness = 3f;
        private const float ZoneCornerRadius = 6f;

        private readonly Box fill;
        private readonly Box glowTop;
        private readonly Box glowBottom;

        public TwoDimensionalStrikeZone()
        {
            RelativeSizeAxes = Axes.X;
            Height = ZoneHeight;
            Width = 0.995f;
            Anchor = Anchor.BottomCentre;
            Origin = Anchor.BottomCentre;
            Masking = true;
            CornerRadius = ZoneCornerRadius;

            var zoneColour = new Color4(60, 80, 180, 160);
            var glowColour = new Color4(100, 150, 255, 180);

            InternalChildren = new Drawable[]
            {
                // Main fill
                fill = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = zoneColour
                },
                // Top glow line
                glowTop = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = ZoneBorderThickness,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    Colour = glowColour
                },
                // Bottom accent
                glowBottom = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 2,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Colour = new Color4(200, 220, 255, 100)
                }
            };
        }

        public void UpdateGeometry(float drawHeight, float hitLineY)
        {
            float offset = Math.Max(0, drawHeight - hitLineY - ZoneHeight / 2f);
            Y = -offset;
        }
    }
}
