// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.Screens.Playback.Playfield.Views;
using BeatSight.Game.UI.Theming;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    /// <summary>
    /// Enhanced unified timing strike zone that adapts its appearance
    /// across all view modes (2D, 3D, Manuscript) with consistent hit feedback.
    /// Uses the centralized DesignSystem for colors and styling.
    /// </summary>
    internal sealed partial class TimingStrikeZoneEnhanced : CompositeDrawable
    {
        #region Visual Components

        private readonly Container strikeBody;
        private readonly Box fillBox;
        private readonly Box glowBox;
        private readonly Box topEdge;
        private readonly Box centerLine;
        private readonly Container pulseContainer;

        #endregion

        #region State

        private LaneViewMode viewMode = LaneViewMode.TwoDimensional;
        private bool useGlobalKick = true;
        private float baselineOffset;
        private float visualHeight;

        #endregion

        /// <summary>
        /// The visual height of the strike zone.
        /// </summary>
        public float VisualHitZoneHeight => visualHeight;

        public TimingStrikeZoneEnhanced()
        {
            RelativeSizeAxes = Axes.X;
            Anchor = Anchor.BottomCentre;
            Origin = Anchor.BottomCentre;
            Width = 0.98f;
            Height = DesignSystem.StrikeZoneHeight;
            AlwaysPresent = true;

            InternalChildren = new Drawable[]
            {
                // Outer pulse container for hit feedback
                pulseContainer = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                },

                // Main body container
                strikeBody = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = DesignSystem.RadiusSmall,
                    BorderThickness = 2,
                    BorderColour = DesignSystem.ColorStrikeZoneBorder,
                    Children = new Drawable[]
                    {
                        // Background fill
                        fillBox = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = DesignSystem.ColorStrikeZoneFill,
                        },

                        // Glow layer
                        glowBox = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = DesignSystem.ColorStrikeZoneBorder,
                            Alpha = 0.2f,
                            Blending = BlendingParameters.Additive,
                        },

                        // Center timing line
                        centerLine = new Box
                        {
                            RelativeSizeAxes = Axes.X,
                            Height = 2,
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Colour = DesignSystem.ColorStrikeZoneBorder.Lighten(0.3f),
                            Alpha = 0.6f,
                        },
                    },
                },

                // Top edge highlight
                topEdge = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 2,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    Colour = DesignSystem.ColorStrikeZoneBorder,
                    Alpha = 0.8f,
                },
            };

            UpdateAppearance();
        }

        #region Public API

        /// <summary>
        /// Sets the lane layout for positioning.
        /// </summary>
        public void SetLaneLayout(LaneLayout layout)
        {
            // Reserved for future per-lane customization
            _ = layout;
        }

        /// <summary>
        /// Sets whether global kick mode is active.
        /// </summary>
        public void SetKickMode(bool globalKick)
        {
            if (useGlobalKick == globalKick)
                return;

            useGlobalKick = globalKick;
            UpdateAppearance();
        }

        /// <summary>
        /// Sets the current view mode.
        /// </summary>
        public void SetViewMode(LaneViewMode mode)
        {
            if (viewMode == mode)
                return;

            viewMode = mode;
            UpdateAppearance();
        }

        /// <summary>
        /// Updates the geometry of the strike zone based on the current layout.
        /// </summary>
        public void UpdateGeometry(
            float drawWidth,
            float drawHeight,
            float hitLineY,
            float spawnTop,
            float laneWidth,
            int lanes,
            int visibleLanes,
            int kickLaneIndex,
            bool globalKick,
            LaneViewMode mode)
        {
            useGlobalKick = globalKick;
            viewMode = mode;

            // Calculate dimensions based on view mode
            float baseHeight = mode switch
            {
                LaneViewMode.ThreeDimensional => Math.Clamp(drawHeight * 0.064f, 20f, 50f),
                LaneViewMode.Manuscript => 6f,
                _ => DesignSystem.StrikeZoneHeight,
            };

            Height = baseHeight;
            visualHeight = baseHeight;

            // Position relative to hit line
            float offsetFromBottom = Math.Clamp(drawHeight - hitLineY - baseHeight / 2f, 0f, drawHeight);
            baselineOffset = offsetFromBottom;
            Y = -baselineOffset;

            // Adjust width based on view mode
            float widthFactor = mode switch
            {
                LaneViewMode.ThreeDimensional => DesignSystem.HighwayWidthFactor,
                LaneViewMode.Manuscript => 0.6f,
                _ => 0.98f,
            };
            Width = Math.Clamp(widthFactor, 0.5f, 0.99f);

            // Adjust corner radius
            float cornerRadius = mode switch
            {
                LaneViewMode.ThreeDimensional => Math.Clamp(baseHeight * 0.4f, 4f, 16f),
                LaneViewMode.Manuscript => 0f, // No rounding for manuscript
                _ => DesignSystem.RadiusSmall,
            };
            strikeBody.CornerRadius = cornerRadius;

            // Adjust border thickness
            strikeBody.BorderThickness = mode switch
            {
                LaneViewMode.ThreeDimensional => Math.Clamp(baseHeight * 0.18f, 1.5f, 4f),
                LaneViewMode.Manuscript => 1f,
                _ => 2f,
            };

            // Apply 3D shear
            if (mode == LaneViewMode.ThreeDimensional)
            {
                Shear = new Vector2(DesignSystem.HighwayShear, 0);
            }
            else
            {
                Shear = Vector2.Zero;
            }

            UpdateAppearance();
        }

        /// <summary>
        /// Triggers a pulse animation when a note is hit.
        /// </summary>
        public void PulseHit(HitResult result)
        {
            var color = DesignSystem.GetJudgmentColor(result);

            // Flash the glow
            glowBox.FadeColour(color, 30)
                   .Then()
                   .FadeColour(DesignSystem.ColorStrikeZoneBorder, 200);

            glowBox.FadeTo(0.6f, 30)
                   .Then()
                   .FadeTo(0.2f, 200);

            // Scale pulse
            strikeBody.ScaleTo(1.02f, 50, Easing.OutQuint)
                      .Then()
                      .ScaleTo(1f, 150, Easing.OutQuint);

            // Edge effect for perfect hits
            if (result == HitResult.Perfect)
            {
                pulseContainer.EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Glow,
                    Colour = Color4Extensions.Opacity(color, 0.6f),
                    Radius = 15,
                };
                pulseContainer.FadeEdgeEffectTo(0, 300, Easing.OutQuint);
            }
        }

        #endregion

        #region Appearance

        private void UpdateAppearance()
        {
            switch (viewMode)
            {
                case LaneViewMode.Manuscript:
                    UpdateManuscriptAppearance();
                    break;
                case LaneViewMode.ThreeDimensional:
                    Update3DAppearance();
                    break;
                default:
                    Update2DAppearance();
                    break;
            }
        }

        private void Update2DAppearance()
        {
            var borderColor = useGlobalKick
                ? DesignSystem.ColorKick.Lighten(0.2f)
                : DesignSystem.ColorStrikeZoneBorder;

            var fillColor = useGlobalKick
                ? Color4Extensions.Opacity(DesignSystem.ColorKick, 0.15f)
                : DesignSystem.ColorStrikeZoneFill;

            strikeBody.BorderColour = borderColor;
            fillBox.Colour = fillColor;
            glowBox.Colour = borderColor;
            glowBox.Alpha = 0.25f;

            topEdge.Colour = borderColor;
            topEdge.Alpha = 0.8f;
            topEdge.Height = 2f;

            centerLine.Colour = borderColor.Lighten(0.3f);
            centerLine.Alpha = 0.6f;
            centerLine.Height = 2f;

            // Set alpha directly instead of using transforms to prevent accumulation
            Alpha = 0.95f;
        }

        private void Update3DAppearance()
        {
            var borderColor = useGlobalKick
                ? DesignSystem.ColorKick.Lighten(0.34f)
                : new Color4(255, 218, 172, 248);

            var fillColor = useGlobalKick
                ? Color4Extensions.Opacity(DesignSystem.ColorKick, 0.16f)
                : new Color4(72, 56, 94, 126);

            strikeBody.BorderColour = borderColor;
            fillBox.Colour = fillColor;
            glowBox.Colour = borderColor;
            glowBox.Alpha = 0.5f;

            topEdge.Colour = borderColor.Lighten(0.2f);
            topEdge.Alpha = 1f;

            centerLine.Colour = borderColor;
            centerLine.Alpha = 0.68f;
            centerLine.Height = 3;

            // Set alpha directly instead of using transforms to prevent accumulation
            Alpha = 0.96f;
        }

        private void UpdateManuscriptAppearance()
        {
            // Manuscript view: minimal, just a playhead line
            var lineColor = DesignSystem.ColorManuscriptPlayhead;

            strikeBody.BorderColour = Color4.Transparent;
            fillBox.Colour = Color4.Transparent;
            glowBox.Alpha = 0;

            topEdge.Colour = lineColor;
            topEdge.Alpha = 1f;
            topEdge.Height = 2;

            centerLine.Alpha = 0;
            centerLine.Height = 2f;

            // Set alpha directly instead of using transforms to prevent accumulation
            Alpha = 0.85f;
        }

        #endregion
    }
}
