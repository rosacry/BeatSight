using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Screens.Playback.Playfield.Views;
using BeatSight.Game.UI.Theming;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;
using osu.Framework.Extensions.Color4Extensions;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    /// <summary>
    /// Represents a single drum hit note in the playfield.
    /// Handles rendering, animations, and state management for individual notes.
    /// </summary>
    public partial class DrawableNote : CompositeDrawable
    {
        /// <summary>
        /// Resolves the colour for a component name from the shared instrument palette
        /// (ranked suffixes such as "crash_1" resolve like their base component).
        /// </summary>
        private static Color4 resolveComponentColour(string component) => DrumPalette.ForComponent(component);

        public double HitTime { get; }
        public int Lane { get; private set; }
        public bool IsJudged { get; private set; }
        public string ComponentName { get; }
        public Color4 AccentColour { get; }
        public bool IsKick => isKickNote;
        public double Velocity { get; } // New property

        public bool IsDisposedPublic => IsDisposed;

        private readonly Container noteheadContainer;
        private readonly Box mainBox;
        private readonly Box highlightStrip;
        private readonly Box? glowBox;
        private readonly Box stem;
        private readonly Bindable<bool> showGlowEffects;
        private readonly Bindable<bool> showParticleEffects;
        private LaneViewMode viewMode = LaneViewMode.TwoDimensional;
        private readonly bool isKickNote;
        private readonly int originalLane;
        private bool kickGlobalMode;
        private float lastAppliedDepth = float.NaN;
        private readonly float velocityAlpha;

        public DrawableNote(HitObject hitObject, int lane, Bindable<bool> showGlow, Bindable<bool> showParticles, Color4? accentColourOverride = null)
        {
            HitTime = hitObject.Time;
            ComponentName = hitObject.Component;
            Lane = lane;
            originalLane = lane;
            showGlowEffects = showGlow;
            showParticleEffects = showParticles;
            isKickNote = !string.IsNullOrEmpty(hitObject.Component) && hitObject.Component.IndexOf("kick", StringComparison.OrdinalIgnoreCase) >= 0;
            Velocity = hitObject.Velocity;

            // Calculate opacity based on velocity (0.0 - 1.0)
            // Map 0.0 -> 0.4 (ghost note)
            // Map 1.0 -> 1.0 (accent)
            float velocity = (float)Math.Clamp(hitObject.Velocity, 0.0, 1.0);
            velocityAlpha = 0.4f + 0.6f * velocity;

            Size = new Vector2(60, 26);
            Origin = Anchor.Centre;
            Masking = false;

            AccentColour = accentColourOverride ?? resolveComponentColour(hitObject.Component);

            Colour = AccentColour;

            var children = new List<Drawable>();

            noteheadContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 8
            };
            children.Add(noteheadContainer);

            // Add glow box first if enabled
            if (showGlow.Value)
            {
                glowBox = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = AccentColour,
                    Alpha = 0.3f * velocityAlpha,
                    Blending = BlendingParameters.Additive,
                };
                noteheadContainer.Add(glowBox);
            }

            // Always add main box
            mainBox = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = AccentColour,
                Alpha = velocityAlpha
            };
            noteheadContainer.Add(mainBox);

            stem = new Box
            {
                Width = 2,
                Height = 35,
                Anchor = Anchor.Centre,
                Origin = Anchor.BottomCentre,
                Colour = AccentColour,
                Alpha = 0
            };
            children.Add(stem);














            highlightStrip = new Box
            {
                RelativeSizeAxes = Axes.X,
                Width = 0.8f,
                Height = 5,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Colour = new Color4(255, 255, 255, 90),
                Alpha = 0.35f
            };
            children.Add(highlightStrip);

            InternalChildren = children.ToArray();

            SetViewMode(viewMode);
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Pulse animation for glow (must be started after loading)
            // Only start if the note hasn't been judged yet
            if (!IsJudged && showGlowEffects.Value && glowBox != null)
                glowBox.Loop(b => b.FadeTo(0.5f, 600).Then().FadeTo(0.2f, 600));
        }

        protected override void Update()
        {
            base.Update();
            // This is a drum analysis tool - no approach circles to update
        }

        public void SetViewMode(LaneViewMode mode)
        {
            viewMode = mode;

            stem.Alpha = 0;
            noteheadContainer.Masking = true;
            noteheadContainer.Rotation = 0f;
            noteheadContainer.Scale = Vector2.One;
            Colour = AccentColour;
            mainBox.Colour = AccentColour;
            stem.Colour = AccentColour;

            if (viewMode == LaneViewMode.TwoDimensional)
            {
                mainBox.Shear = Vector2.Zero;
                if (isKickNote && kickGlobalMode)
                {
                    float assumedHeight = Height > 0 ? Height : 18f;
                    noteheadContainer.CornerRadius = Math.Min(assumedHeight / 2f, 9f);
                    highlightStrip.Anchor = Anchor.Centre;
                    highlightStrip.Origin = Anchor.Centre;
                    highlightStrip.Width = 1f;
                    highlightStrip.Height = Math.Clamp(assumedHeight * 0.3f, 3f, 8f);
                    highlightStrip.Alpha = 0.55f * velocityAlpha;
                    highlightStrip.Colour = new Color4(255, 244, 255, 180);
                    if (glowBox != null)
                        glowBox.Alpha = 0.4f * velocityAlpha;
                    return;
                }

                noteheadContainer.CornerRadius = 6;
                Size = new Vector2(60, 20);
                highlightStrip.Alpha = 0.3f * velocityAlpha;
                highlightStrip.Width = 0.75f;
                highlightStrip.Height = 4;
                highlightStrip.Anchor = Anchor.TopCentre;
                highlightStrip.Origin = Anchor.TopCentre;
                highlightStrip.Colour = new Color4(255, 255, 255, 90);
                if (!IsJudged)
                {
                    Rotation = 0;
                    Scale = Vector2.One;
                }
            }
            else
            {
                // Keep 3D notes rectangular for lane clarity.
                mainBox.Shear = Vector2.Zero;
                if (isKickNote && kickGlobalMode)
                {
                    float assumedHeight = Height > 0 ? Height : 18f;
                    noteheadContainer.CornerRadius = Math.Min(assumedHeight / 2.0f, 10f);
                    highlightStrip.Anchor = Anchor.Centre;
                    highlightStrip.Origin = Anchor.Centre;
                    highlightStrip.Width = 1f;
                    highlightStrip.Height = Math.Clamp(assumedHeight * 0.18f, 2f, 5f);
                    highlightStrip.Alpha = 0.58f * velocityAlpha;
                    highlightStrip.Y = -assumedHeight * 0.05f;
                    highlightStrip.Colour = new Color4(255, 255, 255, 205);
                    if (glowBox != null)
                        glowBox.Alpha = 0.34f * velocityAlpha;
                    return;
                }

                noteheadContainer.CornerRadius = Math.Min(Height / 2.2f, 10f);
                highlightStrip.Anchor = Anchor.Centre;
                highlightStrip.Origin = Anchor.Centre;
                highlightStrip.Width = 1f;
                highlightStrip.Height = Math.Clamp(Height * 0.18f, 2f, 5f);
                highlightStrip.Y = -Height * 0.06f;
                highlightStrip.Alpha = 0.52f * velocityAlpha;
                highlightStrip.Colour = new Color4(255, 255, 255, 195);
                if (glowBox != null)
                    glowBox.Alpha = 0.30f * velocityAlpha;
            }
        }

        public void ApplyKickMode(bool useGlobalLine, int globalLane)
        {
            if (!isKickNote)
                return;

            kickGlobalMode = useGlobalLine;
            Lane = useGlobalLine ? globalLane : originalLane;

            // Refresh geometry to reflect the new presentation.
            SetViewMode(viewMode);
        }

        public void ApplyKickLineDimensions(float width, float height, LaneViewMode mode)
        {
            if (!isKickNote || !kickGlobalMode)
                return;

            Width = width;
            Height = height;

            if (mode == LaneViewMode.TwoDimensional)
            {
                noteheadContainer.CornerRadius = Math.Min(height / 2f, 9f);
                highlightStrip.Anchor = Anchor.Centre;
                highlightStrip.Origin = Anchor.Centre;
                highlightStrip.Width = 1f;
                highlightStrip.Height = Math.Clamp(height * 0.32f, 3f, 8f);
                highlightStrip.Y = -height * 0.1f;
                highlightStrip.Alpha = 0.58f * velocityAlpha;
                highlightStrip.Colour = new Color4(255, 244, 255, 190);
                if (glowBox != null)
                    glowBox.Alpha = 0.42f * velocityAlpha;
            }
            else
            {
                noteheadContainer.CornerRadius = Math.Min(height / 2.2f, 10f);
                highlightStrip.Anchor = Anchor.Centre;
                highlightStrip.Origin = Anchor.Centre;
                highlightStrip.Width = 1f;
                highlightStrip.Height = Math.Clamp(height * 0.18f, 2f, 5f);
                highlightStrip.Y = -height * 0.06f;
                highlightStrip.Alpha = 0.52f * velocityAlpha;
                highlightStrip.Colour = new Color4(255, 255, 255, 195);
                if (glowBox != null)
                    glowBox.Alpha = 0.30f * velocityAlpha;
            }
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

            // CRITICAL: Clear all ongoing transformations (including infinite loops) to prevent accumulation
            this.ClearTransforms();
            mainBox?.ClearTransforms();
            highlightStrip?.ClearTransforms();
            glowBox?.ClearTransforms();

            switch (result)
            {
                case HitResult.Miss:
                    this.FlashColour(new Color4(255, 80, 90, 255), 90, Easing.OutQuint);
                    this.FadeColour(new Color4(120, 20, 30, 200), 120, Easing.OutQuint);
                    this.MoveToY(Y + 18, 160, Easing.OutQuint);
                    this.FadeOut(140, Easing.OutQuint);
                    break;

                case HitResult.Perfect:
                case HitResult.Great:
                    if (showParticleEffects.Value)
                    {
                        // Burst effect
                        this.ScaleTo(1.12f, 100, Easing.OutQuint);
                        this.FadeOut(150, Easing.OutQuint);

                        // Glow burst (kept close to the note so it does not bleed into neighbouring lanes)
                        if (showGlowEffects.Value && glowBox != null)
                        {
                            glowBox.ScaleTo(1.3f, 200, Easing.OutQuint);
                            glowBox.FadeOut(200, Easing.OutQuint);
                        }
                    }
                    else
                    {
                        this.FadeOut(150);
                    }
                    break;

                default:
                    this.FadeOut(180).ScaleTo(1.2f, 180, Easing.OutQuint);
                    break;
            }
        }

        public void Reset()
        {
            IsJudged = false;
            LifetimeEnd = double.MaxValue;
            lastAppliedDepth = float.NaN;

            this.ClearTransforms();
            this.Alpha = 1;
            this.Scale = Vector2.One;
            this.Rotation = 0;
            this.Colour = AccentColour;

            if (mainBox != null)
            {
                mainBox.ClearTransforms();
                mainBox.Colour = AccentColour;
                mainBox.Alpha = velocityAlpha;
            }

            if (glowBox != null)
            {
                glowBox.ClearTransforms();
                glowBox.Alpha = 0.3f * velocityAlpha;
                glowBox.Scale = Vector2.One;
            }

            if (highlightStrip != null)
            {
                highlightStrip.ClearTransforms();
            }

            SetViewMode(viewMode);
        }

        public void RestartAnimation()
        {
            if (!IsJudged && showGlowEffects.Value && glowBox != null)
            {
                glowBox.ClearTransforms();
                glowBox.Loop(b => b.FadeTo(0.5f, 600).Then().FadeTo(0.2f, 600));
            }
        }
    }
}
