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
        private static readonly Dictionary<string, Color4> componentColours = new Dictionary<string, Color4>
        {
            // Core palette tuned for strong lane contrast in 3D.
            {"kick", new Color4(172, 116, 255, 255)},
            {"snare", new Color4(255, 82, 102, 255)},
            {"hihat", new Color4(246, 192, 58, 255)},
            {"hihat_closed", new Color4(246, 192, 58, 255)},
            {"hihat_open", new Color4(255, 210, 84, 255)},
            {"hihat_pedal", new Color4(218, 168, 52, 255)},
            {"tom_high", new Color4(68, 156, 255, 255)},
            {"tom_mid", new Color4(52, 136, 236, 255)},
            {"tom_low", new Color4(40, 118, 220, 255)},
            {"tom", new Color4(52, 136, 236, 255)},
            {"crash", new Color4(74, 220, 142, 255)},
            {"ride", new Color4(255, 158, 88, 255)},
            {"ride_bell", new Color4(255, 158, 88, 255)},
            {"ride_bow", new Color4(244, 144, 76, 255)},
            {"china", new Color4(255, 118, 206, 255)},
            {"splash", new Color4(86, 218, 228, 255)},
            {"cross_stick", new Color4(255, 206, 96, 255)},
        };

        /// <summary>
        /// Resolves the colour for a component name, stripping ranked suffixes
        /// (e.g. "crash_1" → "crash", "china_2" → "china", "tom_1" → "tom").
        /// </summary>
        private static Color4 resolveComponentColour(string component)
        {
            string key = component.ToLowerInvariant();

            // Direct match first
            if (componentColours.TryGetValue(key, out var colour))
                return colour;

            // Strip trailing _N suffix (e.g. crash_1 → crash, ride_bell_2 → ride_bell)
            int lastUnderscore = key.LastIndexOf('_');
            if (lastUnderscore > 0 && lastUnderscore < key.Length - 1)
            {
                bool allDigits = true;
                for (int i = lastUnderscore + 1; i < key.Length; i++)
                {
                    if (!char.IsDigit(key[i]))
                    {
                        allDigits = false;
                        break;
                    }
                }

                if (allDigits)
                {
                    string baseName = key[..lastUnderscore];
                    if (componentColours.TryGetValue(baseName, out colour))
                        return colour;
                }
            }

            // Fallback: substring matching for partial hits
            if (key.Contains("crash")) return componentColours["crash"];
            if (key.Contains("china")) return componentColours["china"];
            if (key.Contains("splash")) return componentColours["splash"];
            if (key.Contains("ride")) return componentColours["ride"];
            if (key.Contains("tom")) return componentColours["tom"];
            if (key.Contains("hat") || key.Contains("hh")) return componentColours["hihat"];
            if (key.Contains("snare")) return componentColours["snare"];
            if (key.Contains("kick")) return componentColours["kick"];

            // Default gray for truly unknown components
            return new Color4(180, 180, 200, 255);
        }

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
        private readonly Box manuscriptCrossLineA;
        private readonly Box manuscriptCrossLineB;
        private readonly Box manuscriptFlagPrimary;
        private readonly Box manuscriptFlagSecondary;
        private readonly Box manuscriptFlagTertiary;
        private readonly Box? glowBox;
        private readonly Box stem;
        private readonly Bindable<bool> showGlowEffects;
        private readonly Bindable<bool> showParticleEffects;
        private LaneViewMode viewMode = LaneViewMode.TwoDimensional;
        private readonly bool isKickNote;
        private readonly int originalLane;
        private bool kickGlobalMode;
        private int manuscriptFlagCount;
        private float lastAppliedDepth = float.NaN;
        private readonly float velocityAlpha;

        public DrawableNote(HitObject hitObject, int lane, Bindable<bool> showGlow, Bindable<bool> showParticles)
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

            AccentColour = resolveComponentColour(hitObject.Component);

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

            manuscriptCrossLineA = new Box
            {
                Width = 2,
                Height = 14,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = AccentColour,
                Alpha = 0
            };
            children.Add(manuscriptCrossLineA);

            manuscriptCrossLineB = new Box
            {
                Width = 2,
                Height = 14,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = AccentColour,
                Alpha = 0
            };
            children.Add(manuscriptCrossLineB);

            manuscriptFlagPrimary = new Box
            {
                Width = 14,
                Height = 2,
                Anchor = Anchor.Centre,
                Origin = Anchor.CentreLeft,
                Colour = AccentColour,
                Alpha = 0
            };
            children.Add(manuscriptFlagPrimary);

            manuscriptFlagSecondary = new Box
            {
                Width = 14,
                Height = 2,
                Anchor = Anchor.Centre,
                Origin = Anchor.CentreLeft,
                Colour = AccentColour,
                Alpha = 0
            };
            children.Add(manuscriptFlagSecondary);

            manuscriptFlagTertiary = new Box
            {
                Width = 14,
                Height = 2,
                Anchor = Anchor.Centre,
                Origin = Anchor.CentreLeft,
                Colour = AccentColour,
                Alpha = 0
            };
            children.Add(manuscriptFlagTertiary);

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

            if (viewMode == LaneViewMode.Manuscript)
            {
                Colour = Color4.White;
                bool cymbalHead = ManuscriptBackgroundEnhanced.UsesCrossNoteheadForComponent(ComponentName);
                bool ghostNote = Velocity < 0.35;
                bool accentNote = Velocity > 0.85;
                float noteWidth = Math.Max(10f, Width);
                float noteHeight = Math.Max(7f, Height);
                Color4 manuscriptInk = new Color4(228, 236, 248, 255);
                mainBox.Shear = Vector2.Zero;
                noteheadContainer.Masking = true;
                noteheadContainer.CornerRadius = Math.Clamp(noteHeight * 0.44f, 3f, 12f);
                mainBox.Colour = ghostNote ? DesignSystem.WithOpacity(manuscriptInk, 0.40f) : manuscriptInk;
                mainBox.Alpha = cymbalHead ? 0f : 0.96f * velocityAlpha;

                float crossLength = Math.Clamp(noteWidth * 0.95f, 9f, 24f);
                float crossThickness = Math.Clamp(crossLength * 0.15f, 1.5f, 3f);
                manuscriptCrossLineA.Width = crossThickness;
                manuscriptCrossLineA.Height = crossLength;
                manuscriptCrossLineA.Rotation = 45f;
                manuscriptCrossLineA.Colour = manuscriptInk;
                manuscriptCrossLineA.Alpha = cymbalHead ? 0.95f * velocityAlpha : 0f;

                manuscriptCrossLineB.Width = crossThickness;
                manuscriptCrossLineB.Height = crossLength;
                manuscriptCrossLineB.Rotation = -45f;
                manuscriptCrossLineB.Colour = manuscriptInk;
                manuscriptCrossLineB.Alpha = cymbalHead ? 0.95f * velocityAlpha : 0f;

                highlightStrip.Anchor = Anchor.Centre;
                highlightStrip.Origin = Anchor.BottomCentre;
                highlightStrip.Width = 0.9f;
                highlightStrip.Height = Math.Clamp(noteHeight * 0.16f, 1.6f, 3f);
                highlightStrip.Y = -noteHeight * 0.92f;
                highlightStrip.Colour = manuscriptInk;
                highlightStrip.Alpha = accentNote
                    ? 0.72f * velocityAlpha
                    : ghostNote
                        ? 0.24f * velocityAlpha
                        : 0f;

                bool stemDown = ManuscriptBackgroundEnhanced.ShouldUseDownStemForComponent(ComponentName);
                stem.Colour = manuscriptInk;
                stem.Width = Math.Clamp(noteWidth * 0.1f, 1.2f, 2.5f);
                stem.Height = Math.Clamp(noteHeight * 2.65f, 16f, 44f);
                if (stemDown)
                {
                    stem.Anchor = Anchor.CentreLeft;
                    stem.Origin = Anchor.TopCentre;
                    stem.X = noteWidth * 0.34f;
                    stem.Y = -noteHeight * 0.04f;
                }
                else
                {
                    stem.Anchor = Anchor.CentreRight;
                    stem.Origin = Anchor.BottomCentre;
                    stem.X = -noteWidth * 0.34f;
                    stem.Y = noteHeight * 0.04f;
                }
                stem.Alpha = 0.92f * velocityAlpha;

                if (glowBox != null)
                {
                    glowBox.Colour = manuscriptInk;
                    glowBox.Alpha = 0.04f * velocityAlpha;
                }

                updateManuscriptFlagGeometry(noteWidth, noteHeight, stemDown, manuscriptInk);

                return;
            }

            stem.Alpha = 0;
            manuscriptCrossLineA.Alpha = 0;
            manuscriptCrossLineB.Alpha = 0;
            manuscriptFlagPrimary.Alpha = 0;
            manuscriptFlagSecondary.Alpha = 0;
            manuscriptFlagTertiary.Alpha = 0;
            noteheadContainer.Masking = true;
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

        public void SetManuscriptFlagCount(int flagCount)
        {
            int clamped = Math.Clamp(flagCount, 0, 3);
            if (manuscriptFlagCount == clamped)
                return;

            manuscriptFlagCount = clamped;
            if (viewMode == LaneViewMode.Manuscript)
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

        private void updateManuscriptFlagGeometry(float noteWidth, float noteHeight, bool stemDown, Color4 manuscriptInk)
        {
            float stemHeight = Math.Clamp(noteHeight * 2.65f, 16f, 44f);
            float stemTipX = stemDown ? noteWidth * 0.34f : -noteWidth * 0.34f;
            float stemTipY = stemDown
                ? -noteHeight * 0.04f + stemHeight
                : noteHeight * 0.04f - stemHeight;

            float flagWidth = Math.Clamp(noteWidth * 0.72f, 8f, 18f);
            float flagThickness = Math.Clamp(noteHeight * 0.18f, 1.4f, 2.8f);
            float flagSpacing = Math.Clamp(noteHeight * 0.42f, 3f, 7f);
            float flagRotation = stemDown ? -26f : 26f;
            float flagXOffset = stemDown ? -flagWidth * 0.06f : flagWidth * 0.06f;
            float direction = stemDown ? 1f : -1f;

            configureFlag(
                manuscriptFlagPrimary,
                manuscriptFlagCount >= 1,
                stemTipX + flagXOffset,
                stemTipY + direction * flagSpacing * 0.15f,
                flagWidth,
                flagThickness,
                flagRotation,
                manuscriptInk);

            configureFlag(
                manuscriptFlagSecondary,
                manuscriptFlagCount >= 2,
                stemTipX + flagXOffset,
                stemTipY + direction * (flagSpacing * 1.15f),
                flagWidth * 0.94f,
                flagThickness,
                flagRotation,
                manuscriptInk);

            configureFlag(
                manuscriptFlagTertiary,
                manuscriptFlagCount >= 3,
                stemTipX + flagXOffset,
                stemTipY + direction * (flagSpacing * 2.05f),
                flagWidth * 0.88f,
                flagThickness,
                flagRotation,
                manuscriptInk);
        }

        private void configureFlag(
            Box flag,
            bool visible,
            float x,
            float y,
            float width,
            float height,
            float rotation,
            Color4 colour)
        {
            if (!visible)
            {
                flag.Alpha = 0f;
                return;
            }

            flag.X = x;
            flag.Y = y;
            flag.Width = width;
            flag.Height = height;
            flag.Rotation = rotation;
            flag.Colour = colour;
            flag.Alpha = 0.9f * velocityAlpha;
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
                        this.ScaleTo(1.4f, 100, Easing.OutQuint);
                        this.FadeOut(150, Easing.OutQuint);

                        // Glow burst
                        if (showGlowEffects.Value && glowBox != null)
                        {
                            glowBox.ScaleTo(2f, 200, Easing.OutQuint);
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
