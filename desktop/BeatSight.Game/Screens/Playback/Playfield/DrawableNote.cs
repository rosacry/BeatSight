using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;
using osu.Framework.Extensions.Color4Extensions;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    internal partial class DrawableNote : CompositeDrawable
    {
        private static readonly Dictionary<string, Color4> componentColours = new Dictionary<string, Color4>
        {
            {"kick", new Color4(186, 145, 255, 255)},
            {"snare", new Color4(64, 156, 255, 255)},
            {"hihat", new Color4(255, 221, 89, 255)},
            {"hihat_closed", new Color4(255, 221, 89, 255)},
            {"hihat_open", new Color4(255, 195, 0, 255)},
            {"tom_high", new Color4(138, 201, 38, 255)},
            {"tom_mid", new Color4(76, 201, 240, 255)},
            {"tom_low", new Color4(128, 128, 255, 255)},
            {"crash", new Color4(255, 159, 243, 255)},
            {"ride", new Color4(250, 177, 160, 255)},
            {"china", new Color4(255, 204, 92, 255)}
        };

        public double HitTime { get; }
        public int Lane { get; private set; }
        public bool IsJudged { get; private set; }
        public string ComponentName { get; }
        public Color4 AccentColour { get; }
        public bool IsKick => isKickNote;

        public bool IsDisposedPublic => IsDisposed;

        private readonly Box mainBox;
        private readonly Box highlightStrip;
        private readonly Box? glowBox;
        private readonly Box stem;
        private readonly CircularContainer? approachCircle;
        private readonly Bindable<bool> showApproachCircles;
        private readonly Bindable<bool> showGlowEffects;
        private readonly Bindable<bool> showParticleEffects;
        private LaneViewMode viewMode = LaneViewMode.TwoDimensional;
        private float approachProgress = 1f;
        private readonly bool isKickNote;
        private readonly int originalLane;
        private bool kickGlobalMode;
        private float lastAppliedDepth = float.NaN;
        private readonly float velocityAlpha;

        public DrawableNote(HitObject hitObject, int lane, Bindable<bool> showApproach, Bindable<bool> showGlow, Bindable<bool> showParticles)
        {
            HitTime = hitObject.Time;
            ComponentName = hitObject.Component;
            Lane = lane;
            originalLane = lane;
            showApproachCircles = showApproach;
            showGlowEffects = showGlow;
            showParticleEffects = showParticles;
            isKickNote = !string.IsNullOrEmpty(hitObject.Component) && hitObject.Component.IndexOf("kick", StringComparison.OrdinalIgnoreCase) >= 0;

            // Calculate opacity based on velocity (0.0 - 1.0)
            // Map 0.0 -> 0.4 (ghost note)
            // Map 1.0 -> 1.0 (accent)
            float velocity = (float)Math.Clamp(hitObject.Velocity, 0.0, 1.0);
            velocityAlpha = 0.4f + 0.6f * velocity;

            Size = new Vector2(60, 26);
            Origin = Anchor.Centre;
            CornerRadius = 8;
            Masking = true;

            AccentColour = componentColours.TryGetValue(hitObject.Component.ToLowerInvariant(), out var colour)
                ? colour
                : new Color4(180, 180, 200, 255);

            Colour = AccentColour;

            var children = new List<Drawable>();

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
                children.Add(glowBox);
            }

            // Always add main box
            mainBox = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = AccentColour,
                Alpha = velocityAlpha
            };
            children.Add(mainBox);

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

            // Add approach circle if enabled
            if (showApproach.Value)
            {
                approachCircle = new CircularContainer
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Size = new Vector2(80, 80),
                    Masking = true,
                    BorderThickness = 3,
                    BorderColour = AccentColour,
                    Alpha = 0.7f, // Slightly more transparent to reduce overlap visual issues
                    Child = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Alpha = 0,
                        AlwaysPresent = true
                    }
                };
                children.Add(approachCircle);
            }

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

            // Approach circle scales down as note gets closer
            if (!IsJudged && showApproachCircles.Value && approachCircle != null && approachCircle.Alpha > 0)
            {
                float progress = Math.Clamp(approachProgress, 0f, 1f);
                approachCircle.Scale = new Vector2(1 + (1 - progress) * 2);
            }
        }

        public void SetViewMode(LaneViewMode mode)
        {
            viewMode = mode;

            if (viewMode == LaneViewMode.Manuscript)
            {
                mainBox.Shear = Vector2.Zero;
                CornerRadius = 10;
                Size = new Vector2(20, 20);
                highlightStrip.Alpha = 0;
                stem.Alpha = 1 * velocityAlpha;

                if (glowBox != null)
                    glowBox.Alpha = 0.2f * velocityAlpha;

                return;
            }

            stem.Alpha = 0;

            if (viewMode == LaneViewMode.TwoDimensional)
            {
                mainBox.Shear = Vector2.Zero;
                if (isKickNote && kickGlobalMode)
                {
                    float assumedHeight = Height > 0 ? Height : 18f;
                    CornerRadius = Math.Min(assumedHeight / 2f, 9f);
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

                CornerRadius = 6;
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
                mainBox.Shear = new Vector2(-0.25f, 0);
                if (isKickNote && kickGlobalMode)
                {
                    float assumedHeight = Height > 0 ? Height : 18f;
                    CornerRadius = Math.Min(assumedHeight / 2.2f, 10f);
                    highlightStrip.Anchor = Anchor.Centre;
                    highlightStrip.Origin = Anchor.Centre;
                    highlightStrip.Width = 1f;
                    highlightStrip.Height = Math.Clamp(assumedHeight * 0.24f, 2f, 6f);
                    highlightStrip.Alpha = 0.6f * velocityAlpha;
                    highlightStrip.Y = -assumedHeight * 0.14f;
                    highlightStrip.Colour = new Color4(255, 230, 210, 210);
                    if (glowBox != null)
                        glowBox.Alpha = 0.5f * velocityAlpha;
                    return;
                }

                CornerRadius = Math.Min(Height / 2.4f, 11f);
                highlightStrip.Anchor = Anchor.Centre;
                highlightStrip.Origin = Anchor.Centre;
                highlightStrip.Width = 1f;
                highlightStrip.Height = Math.Clamp(Height * 0.26f, 2f, 6f);
                highlightStrip.Y = -Height * 0.16f;
                highlightStrip.Alpha = 0.64f * velocityAlpha;
                highlightStrip.Colour = new Color4(255, 228, 205, 210);
                if (glowBox != null)
                    glowBox.Alpha = 0.5f * velocityAlpha;
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

        public void SetApproachProgress(float progress) => approachProgress = Math.Clamp(progress, 0f, 1f);

        public void ApplyKickLineDimensions(float width, float height, LaneViewMode mode)
        {
            if (!isKickNote || !kickGlobalMode)
                return;

            Width = width;
            Height = height;

            if (mode == LaneViewMode.TwoDimensional)
            {
                CornerRadius = Math.Min(height / 2f, 9f);
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
                CornerRadius = Math.Min(height / 2.4f, 11f);
                highlightStrip.Anchor = Anchor.Centre;
                highlightStrip.Origin = Anchor.Centre;
                highlightStrip.Width = 1f;
                highlightStrip.Height = Math.Clamp(height * 0.26f, 2f, 6f);
                highlightStrip.Y = -height * 0.16f;
                highlightStrip.Alpha = 0.64f * velocityAlpha;
                highlightStrip.Colour = new Color4(255, 228, 205, 210);
                if (glowBox != null)
                    glowBox.Alpha = 0.5f;
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
            approachCircle?.ClearTransforms();

            // Hide approach circle
            if (showApproachCircles.Value && approachCircle != null)
                approachCircle.FadeOut(100);

            switch (result)
            {
                case HitResult.Miss:
                    this.FlashColour(new Color4(255, 80, 90, 255), 90, Easing.OutQuint);
                    this.FadeColour(new Color4(120, 20, 30, 200), 120, Easing.OutQuint);
                    this.MoveToY(Y + 18, 160, Easing.OutQuint);
                    this.FadeOut(140, Easing.OutQuint).Expire();
                    break;

                case HitResult.Perfect:
                case HitResult.Great:
                    if (showParticleEffects.Value)
                    {
                        // Burst effect
                        this.ScaleTo(1.4f, 100, Easing.OutQuint);
                        this.FadeOut(150, Easing.OutQuint).Expire();

                        // Glow burst
                        if (showGlowEffects.Value && glowBox != null)
                        {
                            glowBox.ScaleTo(2f, 200, Easing.OutQuint);
                            glowBox.FadeOut(200, Easing.OutQuint);
                        }
                    }
                    else
                    {
                        this.FadeOut(150).Expire();
                    }
                    break;

                default:
                    this.FadeOut(180).ScaleTo(1.2f, 180, Easing.OutQuint).Expire();
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

            if (mainBox != null)
            {
                mainBox.ClearTransforms();
                mainBox.Colour = AccentColour;
                mainBox.Alpha = 1;
            }

            if (glowBox != null)
            {
                glowBox.ClearTransforms();
                glowBox.Alpha = 0.3f;
                glowBox.Scale = Vector2.One;
            }

            if (highlightStrip != null)
            {
                highlightStrip.ClearTransforms();
            }

            if (approachCircle != null)
            {
                approachCircle.ClearTransforms();
                approachCircle.Alpha = 0;
                approachCircle.Scale = Vector2.One;
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
