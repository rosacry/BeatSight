using System;
using System.Collections.Generic;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    internal partial class KickGuideLine : Container
    {
        private const float minLineHeight = 18f;
        private const float maxLineHeight = 48f;
        private float currentLineHeight = 26f;
        private readonly Box glowFill;
        private readonly Box pulseOverlay;
        private readonly Box sweepHighlight;
        private readonly Box ambientGlow;
        private readonly Container lineContainer;
        // private double lastPulseTime; // Removed unused field
        private float baselineCentre;

        private readonly List<DrawableNote> kickPulseFrameNotes = new();
        private readonly List<DrawableNote> kickPulseRemovalBuffer = new();
        private readonly Dictionary<DrawableNote, Drawable> activeKickPulses = new();
        private Container? kickPulseContainer;
        // private Container? kickGuideBand; // Removed unused field

        public KickGuideLine()
        {
            RelativeSizeAxes = Axes.Both;

            ambientGlow = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = currentLineHeight * 3.6f,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Colour = UITheme.KickGlobalGlow,
                Alpha = 0f,
                Blending = BlendingParameters.Additive
            };

            lineContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = currentLineHeight,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Masking = true,
                CornerRadius = Math.Clamp(currentLineHeight / 2f, 10f, 18f),
                Alpha = 0f,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Glow,
                    Colour = UITheme.Emphasise(UITheme.KickGlobalGlow, 1.2f),
                    Radius = 14,
                    Roundness = 1.4f
                }
            };

            var baseFill = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = ColourInfo.GradientVertical(
                    UITheme.Emphasise(UITheme.KickGlobalFill, 1.08f),
                    UITheme.Emphasise(UITheme.KickGlobalFill, 0.82f))
            };

            glowFill = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = UITheme.KickGlobalGlow,
                Alpha = 0f,
                Blending = BlendingParameters.Additive
            };

            sweepHighlight = new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = 0.12f,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                RelativePositionAxes = Axes.X,
                Colour = new Color4(240, 220, 255, 140),
                Alpha = 0.42f,
                Blending = BlendingParameters.Additive
            };

            var topEdge = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 3,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Colour = UITheme.Emphasise(UITheme.KickGlobalGlow, 1.38f)
            };

            var bottomEdge = new Box
            {
                RelativeSizeAxes = Axes.X,
                Height = 4,
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre,
                Colour = UITheme.Emphasise(UITheme.KickGlobalFill, 0.9f)
            };

            pulseOverlay = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = UITheme.Emphasise(UITheme.KickGlobalGlow, 1.18f),
                Alpha = 0,
                Blending = BlendingParameters.Additive
            };

            lineContainer.AddRange(new Drawable[]
            {
                baseFill,
                glowFill,
                topEdge,
                bottomEdge,
                pulseOverlay,
                sweepHighlight
            });

            kickPulseContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
            };

            InternalChildren = new Drawable[]
            {
                ambientGlow,
                lineContainer,
                kickPulseContainer
            };

            baselineCentre = currentLineHeight / 2f;
            applyBaselineOffset();
            sweepHighlight.X = -0.22f;

            // Ensure visibility
            lineContainer.Alpha = 1f;
            ambientGlow.Alpha = 0.4f;
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            sweepHighlight?.Loop(sequence => sequence
                .MoveToX(1.18f, 2600, Easing.InOutSine)
                .Then()
                .MoveToX(-0.22f, 2600, Easing.InOutSine));
        }

        public void ResetVisuals()
        {
            pulseOverlay.FinishTransforms(true);
            pulseOverlay.Alpha = 0;
            // Don't hide the line itself on reset, just the effects
            // lineContainer.Alpha = 0f; 
            // ambientGlow.Alpha = 0f;
            // lastPulseTime = double.NegativeInfinity;
        }

        public void UpdateBaseline(float viewportHeight, float hitLineY, float strikeZoneHeight)
        {
            if (viewportHeight <= 0 || float.IsNaN(viewportHeight) || float.IsInfinity(viewportHeight))
                return;

            float targetHeight = strikeZoneHeight > 0
                ? Math.Clamp(strikeZoneHeight * 0.9f, minLineHeight, maxLineHeight)
                : Math.Clamp(viewportHeight * 0.038f, minLineHeight, maxLineHeight);

            if (Math.Abs(targetHeight - currentLineHeight) > 0.5f)
                applyLineHeight(targetHeight);

            // Center the line on the hitLineY
            // hitLineY is relative to the top of the playfield
            // This container is likely positioned at TopCentre or similar
            // We need to adjust Y or internal offset

            // Actually, PlaybackPlayfield positions this container. 
            // UpdateBaseline might be intended to adjust internal elements?
            // But baselineCentre seems to be about vertical centering within the line height?

            // Let's just ensure the line height is applied
        }

        private void applyBaselineOffset()
        {
            // If we need to offset content within the line
        }

        private void applyLineHeight(float height)
        {
            currentLineHeight = height;
            if (lineContainer != null)
            {
                lineContainer.Height = height;
                lineContainer.CornerRadius = Math.Clamp(height / 2f, 10f, 18f);
            }
            if (ambientGlow != null)
            {
                ambientGlow.Height = height * 3.6f;
            }
        }

        private KickPulse getOrCreatePulse(DrawableNote note)
        {
            if (activeKickPulses.TryGetValue(note, out var existing))
                return (KickPulse)existing;

            var pulse = new KickPulse();
            if (kickPulseContainer != null)
                kickPulseContainer.Add(pulse);

            activeKickPulses[note] = pulse;
            return pulse;
        }

        private void releasePulse(DrawableNote note)
        {
            if (activeKickPulses.TryGetValue(note, out var pulse))
            {
                activeKickPulses.Remove(note);
                pulse.Expire();
            }
        }

        public void UpdateKickNotes(List<DrawableNote> notes, double currentTime, float drawHeight, double approachDuration)
        {
            // Update active pulses and create new ones for visible kick notes
            foreach (var note in notes)
            {
                if (!note.IsKick) continue;

                double timeUntil = note.HitTime - currentTime;

                // Show pulses for approaching notes and slightly past notes (hit effect)
                // Range: from approachDuration (spawn) to -200ms (faded out)
                if (timeUntil <= approachDuration && timeUntil >= -200)
                {
                    var pulse = getOrCreatePulse(note);
                    pulse.Note = note;
                    pulse.UpdateVisual(timeUntil, approachDuration, 200, 50, true);
                }
            }

            // Cleanup old pulses
            kickPulseRemovalBuffer.Clear();
            foreach (var kvp in activeKickPulses)
            {
                double timeUntil = kvp.Key.HitTime - currentTime;
                // Remove if too far past or if the note was reset/removed from the list (though list check is hard here)
                // Just check time for now
                if (timeUntil < -200 || timeUntil > approachDuration + 100)
                {
                    kickPulseRemovalBuffer.Add(kvp.Key);
                }
            }

            foreach (var note in kickPulseRemovalBuffer)
            {
                releasePulse(note);
            }
        }
    }
}
