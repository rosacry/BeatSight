// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Screens.Playback.Playfield.Views;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    /// <summary>
    /// Shared note renderer that provides consistent note visuals across all view modes.
    /// Handles velocity/dynamics visualization, articulation rendering, and hit feedback.
    /// </summary>
    public partial class NoteRenderer : CompositeDrawable
    {
        #region Properties

        public double HitTime { get; }
        public int Lane { get; private set; }
        public bool IsJudged { get; private set; }
        public string ComponentName { get; }
        public Color4 AccentColour { get; }
        public bool IsKick { get; }
        public double Velocity { get; }

        // Articulation properties for future AI mapper integration
        public NoteArticulation Articulation { get; set; } = NoteArticulation.Normal;
        public bool IsGhostNote => Velocity < 0.3;
        public bool IsAccent => Velocity > 0.8;

        #endregion

        #region State

        private LaneViewMode viewMode = LaneViewMode.TwoDimensional;
        private readonly int originalLane;
        private bool kickGlobalMode;
        private float approachProgress = 1f;
        private float lastAppliedDepth = float.NaN;
        private readonly float velocityAlpha;

        #endregion

        #region Visual Components

        private Box mainBody = null!;
        private Box highlightStrip = null!;
        private Box? glowBox;
        private Box? stem;
        private Container? accentMarker;
        private Container? ghostMarker;

        private Bindable<bool> showGlowEffects = null!;
        private Bindable<bool> showVelocityIndicators = null!;

        // Constants for view modes (mirrors DesignSystem but avoids naming conflicts)
        private const float note_width_2d = 60f;
        private const float note_height_2d = 20f;
        private const float note_width_3d = 55f;
        private const float note_height_3d = 22f;
        private const float note_corner_3d = 10f;
        private const float manuscript_note_size = 20f;
        private const float highway_shear = -0.24f;

        #endregion

        public NoteRenderer(HitObject hitObject, int lane)
        {
            HitTime = hitObject.Time;
            ComponentName = hitObject.Component;
            Lane = lane;
            originalLane = lane;
            IsKick = !string.IsNullOrEmpty(hitObject.Component) &&
                     hitObject.Component.IndexOf("kick", StringComparison.OrdinalIgnoreCase) >= 0;
            Velocity = hitObject.Velocity;

            // Use design system for velocity alpha calculation
            velocityAlpha = DesignSystem.GetVelocityAlpha((float)Velocity);

            // Get color from design system
            AccentColour = DesignSystem.GetComponentColor(hitObject.Component);

            // Default size - will be adjusted per view mode
            Size = new Vector2(60, 26);
            Origin = Anchor.Centre;
        }

        [BackgroundDependencyLoader]
        private void load(BeatSightConfigManager config)
        {
            showGlowEffects = config.GetBindable<bool>(BeatSightSetting.ShowGlowEffects);
            // Default to true for velocity indicators
            showVelocityIndicators = new Bindable<bool>(true);

            BuildVisuals();
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Start glow animation if enabled
            if (!IsJudged && showGlowEffects.Value && glowBox != null)
            {
                glowBox.Loop(b => b.FadeTo(0.5f * velocityAlpha, 600).Then().FadeTo(0.2f * velocityAlpha, 600));
            }
        }

        protected override void Update()
        {
            base.Update();
            // No approach circles to update - this is a drum analysis tool
        }

        #region Visual Building

        private void BuildVisuals()
        {
            var children = new List<Drawable>();

            // Glow layer
            if (showGlowEffects.Value)
            {
                glowBox = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = AccentColour,
                    Alpha = 0.3f * velocityAlpha,
                    Blending = BlendingParameters.Additive,
                };
                children.Add(glowBox);
            }

            // Main body
            mainBody = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = AccentColour,
                Alpha = velocityAlpha,
            };
            children.Add(mainBody);

            // Stem (for manuscript view)
            stem = new Box
            {
                Width = 2,
                Height = 35,
                Anchor = Anchor.Centre,
                Origin = Anchor.BottomCentre,
                Colour = AccentColour,
                Alpha = 0,
            };
            children.Add(stem);

            // Highlight strip
            highlightStrip = new Box
            {
                RelativeSizeAxes = Axes.X,
                Width = 0.8f,
                Height = 5,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Colour = new Color4(255, 255, 255, (byte)(0.35f * 255)),
            };
            children.Add(highlightStrip);

            // Velocity indicators
            if (showVelocityIndicators.Value)
            {
                if (IsAccent)
                {
                    accentMarker = CreateAccentMarker();
                    children.Add(accentMarker);
                }
                else if (IsGhostNote)
                {
                    ghostMarker = CreateGhostMarker();
                    children.Add(ghostMarker);
                }
            }

            Masking = true;
            CornerRadius = DesignSystem.RadiusSmall;
            InternalChildren = children.ToArray();
        }

        private Container CreateAccentMarker()
        {
            return new Container
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.BottomCentre,
                Y = -2,
                Child = new SpriteText
                {
                    Text = ">",
                    Font = FontUsage.Default.With(size: 14, weight: "Bold"),
                    Colour = AccentColour.Lighten(0.3f),
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                },
            };
        }

        private Container CreateGhostMarker()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Child = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Transparent,
                },
                Masking = true,
                BorderThickness = 1,
                BorderColour = new Color4(AccentColour.R, AccentColour.G, AccentColour.B, 0.4f),
            };
        }

        #endregion

        #region View Mode Adaptation

        public void SetViewMode(LaneViewMode mode)
        {
            viewMode = mode;

            switch (mode)
            {
                case LaneViewMode.Manuscript:
                    ApplyManuscriptStyle();
                    break;
                case LaneViewMode.ThreeDimensional:
                    Apply3DStyle();
                    break;
                default:
                    Apply2DStyle();
                    break;
            }
        }

        private void Apply2DStyle()
        {
            mainBody.Shear = Vector2.Zero;
            Shear = Vector2.Zero;
            if (stem != null) stem.Alpha = 0;

            if (IsKick && kickGlobalMode)
            {
                ApplyKickStyle2D();
                return;
            }

            CornerRadius = DesignSystem.RadiusSmall;
            Size = new Vector2(DesignSystem.NoteWidth2D, DesignSystem.NoteHeight2D);

            highlightStrip.Anchor = Anchor.TopCentre;
            highlightStrip.Origin = Anchor.TopCentre;
            highlightStrip.Width = 0.75f;
            highlightStrip.Height = 4;
            highlightStrip.Y = 0;
            highlightStrip.Alpha = 0.35f * velocityAlpha;
            highlightStrip.Colour = new Color4(255, 255, 255, (byte)(0.35f * 255));

            if (glowBox != null)
                glowBox.Alpha = 0.3f * velocityAlpha;

            if (accentMarker != null)
                accentMarker.Alpha = showVelocityIndicators.Value && IsAccent ? 1 : 0;

            if (ghostMarker != null)
                ghostMarker.Alpha = showVelocityIndicators.Value && IsGhostNote ? 1 : 0;
        }

        private void Apply3DStyle()
        {
            mainBody.Shear = new Vector2(DesignSystem.HighwayShear * 0.5f, 0);
            Shear = Vector2.Zero;
            if (stem != null) stem.Alpha = 0;

            if (IsKick && kickGlobalMode)
            {
                ApplyKickStyle3D();
                return;
            }

            CornerRadius = DesignSystem.NoteCornerRadius3D;
            Size = new Vector2(DesignSystem.NoteWidth3D, DesignSystem.NoteHeight3D);

            highlightStrip.Anchor = Anchor.Centre;
            highlightStrip.Origin = Anchor.Centre;
            highlightStrip.Width = 1f;
            highlightStrip.Height = Math.Clamp(Height * 0.26f, 2f, 6f);
            highlightStrip.Y = -Height * 0.16f;
            highlightStrip.Alpha = 0.64f * velocityAlpha;
            highlightStrip.Colour = new Color4(255, 228, 205, 210);

            if (glowBox != null)
                glowBox.Alpha = 0.5f * velocityAlpha;

            if (accentMarker != null)
                accentMarker.Alpha = 0; // Hide in 3D

            if (ghostMarker != null)
                ghostMarker.Alpha = showVelocityIndicators.Value && IsGhostNote ? 0.5f : 0;
        }

        private void ApplyManuscriptStyle()
        {
            mainBody.Shear = Vector2.Zero;
            Shear = Vector2.Zero;

            CornerRadius = DesignSystem.ManuscriptNoteSize / 2;
            Size = new Vector2(DesignSystem.ManuscriptNoteSize);

            highlightStrip.Alpha = 0;

            if (stem != null)
            {
                stem.Alpha = velocityAlpha;
                stem.Colour = AccentColour;
            }

            if (glowBox != null)
                glowBox.Alpha = 0.2f * velocityAlpha;

            // Show accent/ghost markers in manuscript view
            if (accentMarker != null)
            {
                accentMarker.Alpha = showVelocityIndicators.Value && IsAccent ? 1 : 0;
                accentMarker.Y = -DesignSystem.ManuscriptNoteSize / 2 - 4;
            }

            if (ghostMarker != null)
                ghostMarker.Alpha = showVelocityIndicators.Value && IsGhostNote ? 1 : 0;
        }

        private void ApplyKickStyle2D()
        {
            float height = Height > 0 ? Height : 18f;
            CornerRadius = Math.Min(height / 2f, 9f);
            Size = new Vector2(Width, height);

            highlightStrip.Anchor = Anchor.Centre;
            highlightStrip.Origin = Anchor.Centre;
            highlightStrip.Width = 1f;
            highlightStrip.Height = Math.Clamp(height * 0.32f, 3f, 8f);
            highlightStrip.Y = -height * 0.1f;
            highlightStrip.Alpha = 0.55f * velocityAlpha;
            highlightStrip.Colour = new Color4(255, 244, 255, 190);

            if (glowBox != null)
                glowBox.Alpha = 0.42f * velocityAlpha;
        }

        private void ApplyKickStyle3D()
        {
            float height = Height > 0 ? Height : 18f;
            CornerRadius = Math.Min(height / 2.4f, 11f);

            highlightStrip.Anchor = Anchor.Centre;
            highlightStrip.Origin = Anchor.Centre;
            highlightStrip.Width = 1f;
            highlightStrip.Height = Math.Clamp(height * 0.26f, 2f, 6f);
            highlightStrip.Y = -height * 0.16f;
            highlightStrip.Alpha = 0.64f * velocityAlpha;
            highlightStrip.Colour = new Color4(255, 228, 205, 210);

            if (glowBox != null)
                glowBox.Alpha = 0.5f * velocityAlpha;
        }

        #endregion

        #region Kick Mode

        public void ApplyKickMode(bool useGlobalLine, int globalLane)
        {
            if (!IsKick)
                return;

            kickGlobalMode = useGlobalLine;
            Lane = useGlobalLine ? globalLane : originalLane;
            SetViewMode(viewMode);
        }

        public void ApplyKickLineDimensions(float width, float height, LaneViewMode mode)
        {
            if (!IsKick || !kickGlobalMode)
                return;

            Width = width;
            Height = height;
            SetViewMode(mode);
        }

        #endregion

        #region Animation & State

        public void SetApproachProgress(float progress)
        {
            approachProgress = Math.Clamp(progress, 0f, 1f);
        }

        internal bool ShouldUpdateDepth(float targetDepth, float tolerance)
        {
            if (float.IsNaN(lastAppliedDepth) || Math.Abs(lastAppliedDepth - targetDepth) >= tolerance)
            {
                lastAppliedDepth = targetDepth;
                return true;
            }
            return false;
        }

        public void ApplyResult(HitResult result)
        {
            if (IsJudged)
                return;

            IsJudged = true;

            // Clear all ongoing transformations
            this.ClearTransforms();
            mainBody?.ClearTransforms();
            highlightStrip?.ClearTransforms();
            glowBox?.ClearTransforms();

            var resultColor = DesignSystem.GetJudgmentColor(result);

            switch (result)
            {
                case HitResult.Miss:
                    this.FlashColour(DesignSystem.ColorMiss, DesignSystem.AnimationFast, Easing.OutQuint);
                    this.FadeColour(DesignSystem.ColorMiss.Darken(0.5f), DesignSystem.AnimationMedium, Easing.OutQuint);
                    this.MoveToY(Y + 18, DesignSystem.AnimationMedium, Easing.OutQuint);
                    this.FadeOut(DesignSystem.AnimationMedium, Easing.OutQuint).Expire();
                    break;

                case HitResult.Perfect:
                    // Perfect: bright burst
                    this.ScaleTo(1.4f, DesignSystem.AnimationFast, Easing.OutQuint);
                    this.FlashColour(Color4.White, 50);
                    this.FadeOut(DesignSystem.AnimationMedium, Easing.OutQuint).Expire();

                    if (showGlowEffects.Value && glowBox != null)
                    {
                        glowBox.ScaleTo(2.5f, DesignSystem.AnimationSlow, Easing.OutQuint);
                        glowBox.FadeOut(DesignSystem.AnimationSlow, Easing.OutQuint);
                    }
                    break;

                case HitResult.Great:
                    this.ScaleTo(1.3f, DesignSystem.AnimationFast, Easing.OutQuint);
                    this.FadeOut(DesignSystem.AnimationMedium, Easing.OutQuint).Expire();

                    if (showGlowEffects.Value && glowBox != null)
                    {
                        glowBox.ScaleTo(2f, DesignSystem.AnimationMedium, Easing.OutQuint);
                        glowBox.FadeOut(DesignSystem.AnimationMedium, Easing.OutQuint);
                    }
                    break;

                default:
                    this.FadeOut(DesignSystem.AnimationSlow).ScaleTo(1.2f, DesignSystem.AnimationSlow, Easing.OutQuint).Expire();
                    break;
            }
        }

        public void Reset()
        {
            IsJudged = false;
            LifetimeEnd = double.MaxValue;

            this.ClearTransforms();
            this.Alpha = 1;
            this.Scale = Vector2.One;
            this.Rotation = 0;
            this.Colour = AccentColour;

            mainBody.ClearTransforms();
            mainBody.Colour = AccentColour;
            mainBody.Alpha = velocityAlpha;

            if (glowBox != null)
            {
                glowBox.ClearTransforms();
                glowBox.Alpha = 0.3f * velocityAlpha;
                glowBox.Scale = Vector2.One;
            }

            highlightStrip.ClearTransforms();

            SetViewMode(viewMode);
        }

        public void RestartAnimation()
        {
            if (!IsJudged && showGlowEffects.Value && glowBox != null)
            {
                glowBox.ClearTransforms();
                glowBox.Loop(b => b.FadeTo(0.5f * velocityAlpha, 600).Then().FadeTo(0.2f * velocityAlpha, 600));
            }
        }

        #endregion
    }

    #region Supporting Types

    /// <summary>
    /// Note articulation types for future AI mapper integration.
    /// </summary>
    public enum NoteArticulation
    {
        /// <summary>Normal strike</summary>
        Normal,

        /// <summary>Ghost note (very soft)</summary>
        Ghost,

        /// <summary>Accent (emphasized hit)</summary>
        Accent,

        /// <summary>Rimshot (snare)</summary>
        Rimshot,

        /// <summary>Cross-stick (snare)</summary>
        CrossStick,

        /// <summary>Flam (grace note)</summary>
        Flam,

        /// <summary>Drag (two grace notes)</summary>
        Drag,

        /// <summary>Buzz roll</summary>
        Buzz,

        /// <summary>Open hi-hat</summary>
        HiHatOpen,

        /// <summary>Closed hi-hat</summary>
        HiHatClosed,

        /// <summary>Half-open hi-hat</summary>
        HiHatHalfOpen,

        /// <summary>Hi-hat foot splash</summary>
        HiHatFootSplash,

        /// <summary>Bell of ride/crash</summary>
        Bell,

        /// <summary>Choke (muted immediately after hit)</summary>
        Choke,
    }

    #endregion
}
