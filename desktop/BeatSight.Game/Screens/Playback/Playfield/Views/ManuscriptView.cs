using System;
using System.Collections.Generic;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield.Views
{
    /// <summary>
    /// Manuscript view renderer (traditional drum notation style).
    /// Notes are placed on a staff following standard percussion notation conventions.
    /// Designed for musicians familiar with reading sheet music.
    /// </summary>
    public class ManuscriptView : PlayfieldViewBase
    {
        public override Configuration.LaneViewMode ViewMode => Configuration.LaneViewMode.Manuscript;

        // Staff layout constants
        private const float HitLinePosition = 0.88f;
        private const float StaffLineSpacing = 12f; // Spacing between staff lines
        private const float StaffWidth = 320f; // Fixed staff width
        private const int StaffLineCount = 5;

        // Note appearance
        private const float NoteheadSize = 16f;
        private const float StemLength = 40f;
        private const float StemWidth = 2f;

        // Staff positioning - percussion notation uses spaces and lines
        // We map drum components to specific staff positions
        private static readonly Dictionary<string, float> ComponentStaffPositions = new Dictionary<string, float>
        {
            // Below the staff (bass drum area)
            ["kick"] = -2.5f,

            // On the staff (snare area)
            ["snare"] = 0f,
            ["rimshot"] = 0f,
            ["cross_stick"] = 0f,

            // Above center (tom area)
            ["tom_low"] = 0.5f,
            ["tom_mid"] = 1f,
            ["tom_high"] = 1.5f,

            // Top of staff and above (hi-hat area)
            ["hihat_closed"] = 2f,
            ["hihat_open"] = 2f,
            ["hihat_pedal"] = -2f,

            // Way above staff (cymbals)
            ["ride"] = 2.5f,
            ["crash"] = 3f,
            ["china"] = 3f,
            ["splash"] = 3f,

            // Miscellaneous
            ["cowbell"] = 2f,
            ["percussion"] = 1f
        };

        private ManuscriptBackground? backgroundDrawable;

        public override float HitLineYRatio => HitLinePosition;

        public override Drawable CreateBackground(float width, float height, int laneCount, bool useGlobalKick)
        {
            backgroundDrawable = new ManuscriptBackground(width, height);
            return backgroundDrawable;
        }

        public override Drawable CreateStrikeZone()
        {
            return new ManuscriptStrikeZone();
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
            // Calculate Y position (notes scroll top to bottom)
            float y = hitLineY - travelDistance * (1 - progress);

            // Calculate X position based on component (staff position)
            float staffCenterX = drawWidth / 2;
            float staffPos = GetStaffPosition(note.ComponentName);

            // Map staff position to X coordinate
            float x = staffCenterX + staffPos * StaffLineSpacing;

            note.Position = new Vector2(x, y);
            note.Scale = Vector2.One;
            note.Rotation = 0;

            // Fade notes that pass the hit line
            note.Alpha = y > hitLineY + note.Height / 2 + 2 ? 0 : 1;
        }

        public override void ApplyNoteStyle(DrawableNote note)
        {
            note.SetViewMode(Configuration.LaneViewMode.Manuscript);
        }

        /// <summary>
        /// Get the staff position for a drum component.
        /// Returns a float where 0 = middle line, positive = above, negative = below.
        /// Each unit represents one staff line/space distance.
        /// </summary>
        private static float GetStaffPosition(string component)
        {
            if (string.IsNullOrEmpty(component))
                return 0f;

            string key = component.ToLowerInvariant();

            if (ComponentStaffPositions.TryGetValue(key, out float position))
                return position;

            // Try partial matches for compound names
            foreach (var kvp in ComponentStaffPositions)
            {
                if (key.Contains(kvp.Key))
                    return kvp.Value;
            }

            return 0f; // Default to middle of staff
        }
    }

    /// <summary>
    /// Manuscript-style background with traditional staff lines.
    /// Designed to look like sheet music paper.
    /// </summary>
    internal partial class ManuscriptBackground : CompositeDrawable
    {
        private const float PaperMarginRatio = 0.15f;
        private const int StaffLineCount = 5;
        private const float LineSpacing = 12f;
        private const float LineThickness = 1.5f;

        // Classic sheet music colors
        private static readonly Color4 PaperColour = new Color4(252, 250, 242, 255); // Warm off-white
        private static readonly Color4 StaffLineColour = new Color4(40, 40, 45, 255); // Near black
        private static readonly Color4 LedgerLineColour = new Color4(80, 80, 90, 200); // Lighter for ledger lines

        public ManuscriptBackground(float parentWidth, float parentHeight)
        {
            RelativeSizeAxes = Axes.Both;
            BuildVisuals();
        }

        private void BuildVisuals()
        {
            // Paper background with subtle texture gradient
            var paperGradient = ColourInfo.GradientVertical(
                new Color4(255, 253, 248, 255),
                new Color4(248, 245, 235, 255));

            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = paperGradient
            });

            // Subtle vignette effect for depth
            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    new Color4(0, 0, 0, 15),
                    Color4.Transparent),
                Height = 0.3f,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre
            });

            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    Color4.Transparent,
                    new Color4(0, 0, 0, 20)),
                Height = 0.2f,
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre
            });

            // Staff container (centered, fixed width)
            var staffContainer = new Container
            {
                Width = 280,
                RelativeSizeAxes = Axes.Y,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre
            };

            // Draw the 5 main staff lines
            float staffHeight = (StaffLineCount - 1) * LineSpacing;
            float staffTopOffset = -staffHeight / 2;

            for (int i = 0; i < StaffLineCount; i++)
            {
                staffContainer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = LineThickness,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = (i - 2) * LineSpacing, // Center the staff
                    Colour = StaffLineColour
                });
            }

            // Add ledger lines above and below the staff
            // Above staff (for cymbals)
            for (int i = 1; i <= 2; i++)
            {
                staffContainer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = LineThickness * 0.8f,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = (2 + i) * LineSpacing,
                    Colour = LedgerLineColour,
                    Alpha = 0.6f
                });
            }

            // Below staff (for bass drum)
            for (int i = 1; i <= 2; i++)
            {
                staffContainer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = LineThickness * 0.8f,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = (-2 - i) * LineSpacing,
                    Colour = LedgerLineColour,
                    Alpha = 0.6f
                });
            }

            AddInternal(staffContainer);

            // Add percussion clef indicator (simplified visual)
            AddInternal(new ClefIndicator
            {
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Y = 30
            });
        }
    }

    /// <summary>
    /// Simple percussion clef indicator for the manuscript view.
    /// </summary>
    internal partial class ClefIndicator : CompositeDrawable
    {
        public ClefIndicator()
        {
            Size = new Vector2(30, 50);

            // Two vertical bars (percussion clef symbol)
            InternalChildren = new Drawable[]
            {
                new Box
                {
                    Width = 4,
                    Height = 36,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = -6,
                    Colour = new Color4(40, 40, 45, 255)
                },
                new Box
                {
                    Width = 4,
                    Height = 36,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = 6,
                    Colour = new Color4(40, 40, 45, 255)
                }
            };
        }
    }

    /// <summary>
    /// Strike zone for manuscript view.
    /// Subtle horizontal line indicating the playback position.
    /// </summary>
    internal partial class ManuscriptStrikeZone : CompositeDrawable
    {
        private const float ZoneHeight = 6f;

        public ManuscriptStrikeZone()
        {
            RelativeSizeAxes = Axes.X;
            Height = ZoneHeight;
            Width = 0.7f;
            Anchor = Anchor.BottomCentre;
            Origin = Anchor.BottomCentre;

            InternalChildren = new Drawable[]
            {
                // Main playhead line
                new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 2,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Colour = new Color4(180, 60, 60, 200)
                },
                // Subtle glow
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(200, 80, 80, 50),
                    Blending = BlendingParameters.Additive
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
