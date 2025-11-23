using osu.Framework.Allocation;
using osu.Framework.Audio;
using osu.Framework.Audio.Sample;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Utils;
using System;
using System.Collections.Generic;

namespace BeatSight.Game.Audio
{
    /// <summary>
    /// Manages UI sound effects with dynamic modulation, spatial audio, and rhythmic awareness.
    /// </summary>
    public partial class UIAudioController : Component
    {
        private Sample? hoverSample;
        private Sample? clickSample;
        private Sample? backSample;
        private Sample? transitionSample;

        // Fallbacks using intro sounds if specific UI sounds aren't present
        private Sample? shimmerSample;
        private Sample? impactSample;
        private Sample? glitchSample;

        private int clickCombo = 0;
        private double lastClickTime = 0;
        private const double COMBO_RESET_TIME = 500; // ms

        public event Action? OnClickEvent;

        // Master switch for audio output. Default to false as per user request.
        public bool AudioEnabled { get; set; } = false;

        [BackgroundDependencyLoader]
        private void load(AudioManager audio)
        {
            // Try to load specific UI sounds. 
            // In a real scenario, these files would need to be added to Resources/Samples/UI/
            hoverSample = audio.Samples.Get("UI/hover");
            clickSample = audio.Samples.Get("UI/click");
            backSample = audio.Samples.Get("UI/back");
            transitionSample = audio.Samples.Get("UI/transition");

            // Fallbacks
            shimmerSample = audio.Samples.Get("intro_shimmer");
            impactSample = audio.Samples.Get("intro_impact");
            glitchSample = audio.Samples.Get("intro_glitch");
        }

        /// <summary>
        /// Plays a hover sound, spatially panned based on the X position (0..1).
        /// </summary>
        public void PlayHover(float screenX = 0.5f)
        {
            if (!AudioEnabled) return;

            var sample = hoverSample ?? shimmerSample;
            if (sample == null) return;

            var channel = sample.GetChannel();

            // Pan based on screen position (-0.8 to 0.8 to avoid extreme hard panning)
            float pan = (Math.Clamp(screenX, 0f, 1f) * 1.6f) - 0.8f;
            channel.Balance.Value = pan;

            // If using fallback shimmer, pitch it up and make it quiet to simulate a "light" hover
            if (sample == shimmerSample)
            {
                channel.Frequency.Value = 2.0 + RNG.NextDouble(-0.1, 0.1);
                channel.Volume.Value = 0.15;
            }
            else
            {
                // Standard hover variation
                channel.Frequency.Value = 1.0 + RNG.NextDouble(-0.05, 0.05);
                channel.Volume.Value = 0.4;
            }

            channel.Play();
        }

        /// <summary>
        /// Plays a click sound. Rapid clicks will increase in pitch (combo system).
        /// </summary>
        public void PlayClick(bool important = false)
        {
            // Always fire the event for visuals
            OnClickEvent?.Invoke();

            if (!AudioEnabled) return;

            var sample = clickSample ?? impactSample;
            if (sample == null) return;

            double currentTime = Time.Current;
            if (currentTime - lastClickTime < COMBO_RESET_TIME)
            {
                clickCombo++;
            }
            else
            {
                clickCombo = 0;
            }
            lastClickTime = currentTime;

            var channel = sample.GetChannel();

            // Pitch goes up with combo, capped at some limit
            double pitchOffset = Math.Min(clickCombo * 0.05, 0.5);

            if (important)
            {
                // Important clicks are deeper but still affected by combo slightly
                channel.Frequency.Value = 0.8 + (pitchOffset * 0.5);
                channel.Volume.Value = 1.0;
            }
            else
            {
                channel.Frequency.Value = 1.0 + pitchOffset + RNG.NextDouble(-0.02, 0.02);
                channel.Volume.Value = 0.8;
            }

            // If using fallback impact, it's very loud, so attenuate it
            if (sample == impactSample)
            {
                channel.Volume.Value *= 0.3;
                // Make it shorter/snappier by pitching up if it's a big impact sound
                if (!important) channel.Frequency.Value *= 1.5;
            }

            channel.Play();
        }

        public void PlayBack()
        {
            if (!AudioEnabled) return;

            var sample = backSample ?? glitchSample;
            if (sample == null) return;

            var channel = sample.GetChannel();
            channel.Frequency.Value = 0.9; // Lower pitch for "going back"

            if (sample == glitchSample)
            {
                channel.Volume.Value = 0.2;
                channel.Frequency.Value = 1.2; // Glitch sounds better high pitched
            }

            channel.Play();
        }

        public void PlayTransition()
        {
            if (!AudioEnabled) return;

            var sample = transitionSample ?? shimmerSample;
            if (sample == null) return;

            var channel = sample.GetChannel();
            channel.Volume.Value = 0.5;

            // Long sweep
            if (sample == shimmerSample)
            {
                channel.Frequency.Value = 0.8;
            }

            channel.Play();
        }
    }
}
