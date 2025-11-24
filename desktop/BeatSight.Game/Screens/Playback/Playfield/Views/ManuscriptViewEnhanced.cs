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
    /// Redesigned manuscript view renderer (traditional drum notation style).
    /// 
    /// Key improvements:
    /// - Proper staff notation layout following standard percussion conventions
    /// - Clean, musician-friendly visual design
    /// - Better component-to-position mapping
    /// - Support for dynamics and articulation visualization
    /// - Cleaner playhead and measure markers
    /// 
    /// Notes are placed on a staff following standard percussion notation,
    /// designed for musicians familiar with reading sheet music.
    /// </summary>
    public class ManuscriptViewEnhanced : PlayfieldViewBaseEnhanced
    {
        public override Configuration.LaneViewMode ViewMode => Configuration.LaneViewMode.Manuscript;

        // Position constants
        public override float HitLineYRatio => DesignSystem.HitLineRatioManuscript;
        public override float SpawnYRatio => 0f;

        // Staff layout constants
        private const float NoteheadDiameter = 16f;
        private const float StemLength = 38f;
        private const float StemWidth = 1.5f;

        private ManuscriptBackgroundEnhanced? backgroundDrawable;

        #region Background Creation

        public override Drawable CreateBackground(float width, float height, int laneCount, bool useGlobalKick)
        {
            backgroundDrawable = new ManuscriptBackgroundEnhanced();
            return backgroundDrawable;
        }

        #endregion

        #region Strike Zone Creation

        public override Drawable CreateStrikeZone()
        {
            return new ManuscriptStrikeZoneEnhanced();
        }

        #endregion

        #region Note Position Updates

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
            float y = CalculateY(progress, hitLineY, travelDistance);

            // Calculate X position based on component (staff position)
            float x = CalculateManuscriptX(note.ComponentName, drawWidth);

            note.Position = new Vector2(x, y);
            note.Scale = Vector2.One;
            note.Rotation = 0;

            // Fade notes that pass the hit line
            note.Alpha = IsNoteVisible(y, hitLineY, note.Height) ? 1 : 0;
        }

        public override void ApplyNoteStyle(DrawableNote note)
        {
            note.SetViewMode(Configuration.LaneViewMode.Manuscript);
        }

        #endregion
    }

    /// <summary>
    /// Enhanced manuscript-style background with traditional staff lines.
    /// Designed to look like professional sheet music paper.
    /// </summary>
    internal partial class ManuscriptBackgroundEnhanced : CompositeDrawable
    {
        // Staff dimensions
        private const int StaffLineCount = 5;
        private const float LineThickness = 1.2f;
        private const float LedgerLineThickness = 0.9f;
        private const int LedgerLinesAbove = 2;
        private const int LedgerLinesBelow = 2;

        // Classic sheet music colors
        private static readonly Color4 PaperBackground = new Color4(252, 250, 244, 255);
        private static readonly Color4 PaperVignette = new Color4(245, 242, 232, 255);
        private static readonly Color4 StaffLineColor = new Color4(35, 38, 45, 255);
        private static readonly Color4 LedgerLineColor = new Color4(75, 78, 88, 180);

        private Container? staffContainer;
        private ClefIndicatorEnhanced? clefIndicator;

        public ManuscriptBackgroundEnhanced()
        {
            RelativeSizeAxes = Axes.Both;
            BuildVisuals();
        }

        private void BuildVisuals()
        {
            // Paper background with subtle gradient
            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(PaperBackground, PaperVignette)
            });

            // Subtle top vignette for depth
            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    new Color4(0, 0, 0, 12),
                    Color4.Transparent),
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre
            });

            // Subtle bottom shadow
            AddInternal(new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    Color4.Transparent,
                    new Color4(0, 0, 0, 18)),
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre
            });

            // Staff container
            staffContainer = new Container
            {
                RelativeSizeAxes = Axes.Y,
                Width = DrawWidth * DesignSystem.StaffWidthRatio,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre
            };

            // Draw the 5 main staff lines as vertical lines (since notes scroll vertically)
            for (int i = 0; i < StaffLineCount; i++)
            {
                float x = (i - (StaffLineCount - 1) / 2f) * DesignSystem.StaffLineSpacing;

                staffContainer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = LineThickness,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = x,
                    Colour = StaffLineColor
                });
            }

            // Ledger lines above staff (for cymbals)
            for (int i = 1; i <= LedgerLinesAbove; i++)
            {
                float x = ((StaffLineCount - 1) / 2f + i) * DesignSystem.StaffLineSpacing;

                staffContainer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = LedgerLineThickness,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = x,
                    Colour = LedgerLineColor,
                    Alpha = DesignSystem.LedgerLineOpacity
                });
            }

            // Ledger lines below staff (for bass drum)
            for (int i = 1; i <= LedgerLinesBelow; i++)
            {
                float x = -((StaffLineCount - 1) / 2f + i) * DesignSystem.StaffLineSpacing;

                staffContainer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Y,
                    Width = LedgerLineThickness,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = x,
                    Colour = LedgerLineColor,
                    Alpha = DesignSystem.LedgerLineOpacity
                });
            }

            AddInternal(staffContainer);

            // Percussion clef indicator
            clefIndicator = new ClefIndicatorEnhanced
            {
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Y = 25
            };
            AddInternal(clefIndicator);

            // Component legend (positioned at top right)
            AddInternal(CreateComponentLegend());
        }

        protected override void Update()
        {
            base.Update();

            // Update staff container width based on current draw width
            if (staffContainer != null)
            {
                staffContainer.Width = DrawWidth * DesignSystem.StaffWidthRatio;
            }
        }

        private Drawable CreateComponentLegend()
        {
            // Small legend showing what each staff position represents
            var legend = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 3),
                Anchor = Anchor.TopRight,
                Origin = Anchor.TopRight,
                Margin = new MarginPadding { Top = 15, Right = 15 },
                Alpha = 0.65f
            };

            var items = new[]
            {
                ("Cymbals", DesignSystem.ColorCrash),
                ("Hi-Hat", DesignSystem.ColorHiHat),
                ("Toms", DesignSystem.ColorTomMid),
                ("Snare", DesignSystem.ColorSnare),
                ("Kick", DesignSystem.ColorKick)
            };

            foreach (var (label, color) in items)
            {
                legend.Add(new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Horizontal,
                    Spacing = new Vector2(6, 0),
                    Children = new Drawable[]
                    {
                        new Circle
                        {
                            Size = new Vector2(8, 8),
                            Colour = color
                        },
                        new SpriteText
                        {
                            Text = label,
                            Font = new FontUsage("Roboto", 11),
                            Colour = new Color4(60, 65, 75, 255)
                        }
                    }
                });
            }

            return legend;
        }

        /// <summary>
        /// Get the X offset for a component on the staff.
        /// Static utility method for use by other classes.
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
                "kick" or "bass" => -2.5f * DesignSystem.StaffLineSpacing,

                // Snare - middle of staff
                "snare" or "rimshot" or "cross_stick" or "crossstick" or "sidestick" => 0f,

                // Hi-hat - above top line
                "hihat" or "hihat_closed" or "hh" or "hihat_open" or "hho" => 2.5f * DesignSystem.StaffLineSpacing,
                "hihat_pedal" or "hhp" => -2f * DesignSystem.StaffLineSpacing,

                // Toms - spaces between lines
                "tom_high" or "high_tom" => 1.5f * DesignSystem.StaffLineSpacing,
                "tom_mid" or "mid_tom" or "tom" => 1f * DesignSystem.StaffLineSpacing,
                "tom_low" or "low_tom" or "floor_tom" => 0.5f * DesignSystem.StaffLineSpacing,

                // Cymbals - above staff
                "crash" or "crash_cymbal" or "china" or "china_cymbal" => 3.5f * DesignSystem.StaffLineSpacing,
                "ride" or "ride_cymbal" or "splash" or "splash_cymbal" => 3f * DesignSystem.StaffLineSpacing,

                // Miscellaneous
                "cowbell" or "tambourine" => 2f * DesignSystem.StaffLineSpacing,

                // Default to center
                _ => 0f
            };
        }
    }

    /// <summary>
    /// Enhanced percussion clef indicator.
    /// The percussion clef consists of two vertical bars.
    /// </summary>
    internal partial class ClefIndicatorEnhanced : CompositeDrawable
    {
        private const float BarWidth = 4f;
        private const float BarHeight = 32f;
        private const float BarSpacing = 10f;

        public ClefIndicatorEnhanced()
        {
            Size = new Vector2(BarSpacing + BarWidth * 2, BarHeight);

            InternalChildren = new Drawable[]
            {
                // Left bar
                new Box
                {
                    Width = BarWidth,
                    Height = BarHeight,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = -BarSpacing / 2,
                    Colour = new Color4(35, 38, 45, 255)
                },
                // Right bar
                new Box
                {
                    Width = BarWidth,
                    Height = BarHeight,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    X = BarSpacing / 2,
                    Colour = new Color4(35, 38, 45, 255)
                }
            };
        }
    }

    /// <summary>
    /// Enhanced strike zone for manuscript view.
    /// A subtle horizontal playhead line.
    /// </summary>
    internal partial class ManuscriptStrikeZoneEnhanced : CompositeDrawable
    {
        private readonly Box mainLine;
        private readonly Box glowLine;

        public ManuscriptStrikeZoneEnhanced()
        {
            RelativeSizeAxes = Axes.X;
            Height = DesignSystem.StrikeZoneHeightManuscript;
            Width = DesignSystem.StaffWidthRatio + 0.1f;
            Anchor = Anchor.BottomCentre;
            Origin = Anchor.BottomCentre;

            // Subtle glow behind the line
            glowLine = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 6,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = DesignSystem.WithOpacity(DesignSystem.ColorPlayhead, 0.3f),
                Blending = BlendingParameters.Additive
            };

            // Main playhead line
            mainLine = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 2,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = DesignSystem.ColorPlayhead
            };

            // End markers (vertical ticks at the edges)
            var leftMarker = new Box
            {
                Width = 2,
                Height = 10,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.Centre,
                Colour = DesignSystem.ColorPlayhead,
                Alpha = 0.6f
            };

            var rightMarker = new Box
            {
                Width = 2,
                Height = 10,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.Centre,
                Colour = DesignSystem.ColorPlayhead,
                Alpha = 0.6f
            };

            InternalChildren = new Drawable[]
            {
                glowLine,
                mainLine,
                leftMarker,
                rightMarker
            };
        }

        public void UpdateGeometry(float drawHeight, float hitLineY)
        {
            float offset = Math.Max(0, drawHeight - hitLineY - Height / 2f);
            Y = -offset;
        }

        public void PulseHit(Color4 color)
        {
            mainLine.Colour = color;
            mainLine.FadeColour(DesignSystem.ColorPlayhead, DesignSystem.AnimationFast);

            glowLine.FadeTo(0.5f, DesignSystem.AnimationQuick)
                   .Then()
                   .FadeTo(0.3f, DesignSystem.AnimationFast);
        }
    }

    /// <summary>
    /// Specialized note renderer for manuscript view.
    /// Creates notation-style note heads with stems.
    /// </summary>
    public partial class ManuscriptNoteDrawable : CompositeDrawable
    {
        private readonly Circle notehead;
        private readonly Box stem;
        private Box? accentMark;

        public ManuscriptNoteDrawable(Color4 color, double velocity)
        {
            Size = new Vector2(16, 16);
            Origin = Anchor.Centre;

            bool isGhost = velocity < DesignSystem.GhostNoteThreshold;
            bool isAccent = velocity > DesignSystem.AccentNoteThreshold;
            float alpha = DesignSystem.GetVelocityAlpha(velocity);

            // Notehead (filled circle for regular notes, open for ghost notes)
            notehead = new Circle
            {
                Size = new Vector2(14, 12),
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = color,
                Alpha = alpha
            };

            // Stem (goes up for notes above middle line, down for below)
            stem = new Box
            {
                Width = 1.5f,
                Height = 35,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.BottomCentre,
                X = -2,
                Y = -6,
                Colour = color,
                Alpha = alpha
            };

            InternalChildren = new Drawable[] { notehead, stem };

            // Accent mark (horizontal line above note)
            if (isAccent)
            {
                accentMark = new Box
                {
                    Width = 12,
                    Height = 2,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.BottomCentre,
                    Y = -stem.Height - 8,
                    Colour = color,
                    Alpha = alpha * 0.8f
                };
                AddInternal(accentMark);
            }

            // Ghost note styling (parentheses or X notehead)
            if (isGhost)
            {
                notehead.BorderThickness = 1.5f;
                notehead.BorderColour = color;
                notehead.Colour = Color4.Transparent;
            }
        }

        /// <summary>
        /// Set stem direction (true = up, false = down).
        /// </summary>
        public void SetStemDirection(bool up)
        {
            if (up)
            {
                stem.Anchor = Anchor.CentreRight;
                stem.Origin = Anchor.BottomCentre;
                stem.X = -2;
                stem.Y = -6;
            }
            else
            {
                stem.Anchor = Anchor.CentreLeft;
                stem.Origin = Anchor.TopCentre;
                stem.X = 2;
                stem.Y = 6;
            }
        }
    }
}
