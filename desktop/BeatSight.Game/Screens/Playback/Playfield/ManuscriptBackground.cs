using System;
using BeatSight.Game.Configuration;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    /// <summary>
    /// Manuscript-style background with traditional percussion staff lines.
    /// Provides an authentic sheet music appearance optimized for drum notation.
    /// </summary>
    public partial class ManuscriptBackground : CompositeDrawable
    {
        // Staff configuration
        private const int MainStaffLines = 5;
        private const float LineSpacing = 14f;
        private const float LineThickness = 1.5f;
        private const float StaffWidthRatio = 0.5f;

        // Colours for an authentic paper look
        private static readonly Color4 PaperBase = new Color4(252, 250, 242, 255);
        private static readonly Color4 PaperWarm = new Color4(248, 245, 235, 255);
        private static readonly Color4 InkColour = new Color4(35, 35, 40, 255);
        private static readonly Color4 LedgerLineColour = new Color4(70, 70, 80, 180);
        // PlayheadColour reserved for future playhead visualization
        // private static readonly Color4 PlayheadColour = new Color4(180, 60, 60, 180);

        private Container? staffContainer;

        public ManuscriptBackground()
        {
            RelativeSizeAxes = Axes.Both;
            BuildVisuals();
        }

        private void BuildVisuals()
        {
            // Paper background with warm gradient
            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(PaperBase, PaperWarm)
            });

            // Subtle texture overlay (aged paper effect)
            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    new Color4(0, 0, 0, 8),
                    Color4.Transparent),
                Height = 0.2f,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre
            });

            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    Color4.Transparent,
                    new Color4(0, 0, 0, 15)),
                Height = 0.15f,
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre
            });

            // Create the staff container
            staffContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Width = StaffWidthRatio,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre
            };

            AddInternal(staffContainer);
            BuildStaffLines();

            // Percussion clef indicator
            AddInternal(CreatePercussionClef());
        }

        private void BuildStaffLines()
        {
            if (staffContainer == null) return;

            staffContainer.Clear();

            // Main staff lines (5 lines for standard percussion staff)
            for (int i = 0; i < MainStaffLines; i++)
            {
                float offset = (i - (MainStaffLines - 1) / 2f) * LineSpacing;

                staffContainer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = LineThickness,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = offset,
                    Colour = InkColour
                });
            }

            // Ledger lines above (for cymbals - crash, ride, etc.)
            for (int i = 1; i <= 3; i++)
            {
                float offset = ((MainStaffLines - 1) / 2f + i) * LineSpacing;

                staffContainer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = LineThickness * 0.75f,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = offset,
                    Colour = LedgerLineColour,
                    Alpha = Math.Max(0.3f, 0.8f - i * 0.2f)
                });
            }

            // Ledger lines below (for bass drum)
            for (int i = 1; i <= 2; i++)
            {
                float offset = -((MainStaffLines - 1) / 2f + i) * LineSpacing;

                staffContainer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = LineThickness * 0.75f,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = offset,
                    Colour = LedgerLineColour,
                    Alpha = Math.Max(0.3f, 0.8f - i * 0.2f)
                });
            }
        }

        private Drawable CreatePercussionClef()
        {
            // Percussion clef: two thick vertical bars
            return new Container
            {
                Size = new Vector2(36, 60),
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Y = 25,
                Children = new Drawable[]
                {
                    new Box
                    {
                        Width = 5,
                        Height = 40,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        X = -8,
                        Colour = InkColour
                    },
                    new Box
                    {
                        Width = 5,
                        Height = 40,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        X = 8,
                        Colour = InkColour
                    }
                }
            };
        }

        /// <summary>
        /// Get the X offset for a drum component based on standard percussion notation.
        /// </summary>
        public static float GetStaffPositionForComponent(string component)
        {
            if (string.IsNullOrEmpty(component))
                return 0f;

            string key = component.ToLowerInvariant();

            // Standard drum kit positions on percussion staff
            // Positions are relative to center line (0 = middle line)
            return key switch
            {
                // Bass drum - below staff
                "kick" or "bass" => -2.5f * LineSpacing,

                // Snare - middle of staff
                "snare" => 0f,
                "rimshot" => 0f,
                "cross_stick" or "crossstick" => 0f,
                "sidestick" => 0f,

                // Hi-hat - above top line
                "hihat" or "hihat_closed" or "hh" => 2.5f * LineSpacing,
                "hihat_open" or "hho" => 2.5f * LineSpacing,
                "hihat_pedal" or "hhp" => -2f * LineSpacing,

                // Toms - spaces between lines
                "tom_high" or "high_tom" => 1.5f * LineSpacing,
                "tom_mid" or "mid_tom" or "tom" => 1f * LineSpacing,
                "tom_low" or "low_tom" or "floor_tom" => 0.5f * LineSpacing,

                // Cymbals - way above staff
                "crash" or "crash_cymbal" => 3.5f * LineSpacing,
                "ride" or "ride_cymbal" => 3f * LineSpacing,
                "china" or "china_cymbal" => 3.5f * LineSpacing,
                "splash" or "splash_cymbal" => 3f * LineSpacing,

                // Miscellaneous
                "cowbell" => 2f * LineSpacing,
                "tambourine" => 2f * LineSpacing,

                // Default to center
                _ => 0f
            };
        }
    }
}

