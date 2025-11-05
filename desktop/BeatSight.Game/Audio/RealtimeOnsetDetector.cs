using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Calibration;

namespace BeatSight.Game.Audio
{
    /// <summary>
    /// Real-time onset detection for drum hits
    /// Uses spectral flux and energy-based detection
    /// </summary>
    public class RealtimeOnsetDetector
    {
        private readonly float threshold;
        private readonly int historySize;
        private readonly Queue<float> energyHistory;
        private float[] previousSpectrum;

        /// <summary>
        /// Event fired when an onset (drum hit) is detected
        /// </summary>
        public event Action<OnsetEvent>? OnsetDetected;

        /// <summary>
        /// Minimum time between onsets in milliseconds to avoid double-triggering
        /// </summary>
        public double MinTimeBetweenOnsets { get; set; } = 50;

        private double lastOnsetTime;

        public MicCalibrationProfile? CalibrationProfile { get; set; }

        public RealtimeOnsetDetector(float threshold = 0.3f, int historySize = 10)
        {
            this.threshold = threshold;
            this.historySize = historySize;
            this.energyHistory = new Queue<float>(historySize);
            this.previousSpectrum = Array.Empty<float>();
        }

        /// <summary>
        /// Process an audio buffer and detect onsets
        /// </summary>
        public void ProcessBuffer(float[] audioData, int sampleRate, double currentTime)
        {
            if (audioData.Length == 0)
                return;

            // Calculate RMS energy
            float energy = calculateRMS(audioData);

            var profile = CalibrationProfile;
            if (profile != null && profile.AmbientNoiseFloor > 0)
                energy = Math.Max(0, energy - (float)profile.AmbientNoiseFloor);
            energyHistory.Enqueue(energy);

            if (energyHistory.Count > historySize)
                energyHistory.Dequeue();

            // Calculate spectral flux (difference between successive spectra)
            float[] spectrum = calculateSpectrum(audioData);
            float spectralFlux = 0;

            if (previousSpectrum.Length == spectrum.Length)
            {
                for (int i = 0; i < spectrum.Length; i++)
                {
                    float diff = spectrum[i] - previousSpectrum[i];
                    spectralFlux += Math.Max(0, diff); // Only positive changes
                }
            }

            previousSpectrum = spectrum;

            // Check for onset
            if (energyHistory.Count >= historySize)
            {
                float avgEnergy = energyHistory.Average();
                float energyRatio = avgEnergy > 0 ? energy / avgEnergy : 0;

                // Detect onset if energy spike + spectral change
                if (energyRatio > (1 + threshold) && spectralFlux > threshold)
                {
                    // Avoid double-triggering
                    if (currentTime - lastOnsetTime >= MinTimeBetweenOnsets)
                    {
                        lastOnsetTime = currentTime;

                        var onsetEvent = new OnsetEvent
                        {
                            Time = currentTime,
                            Energy = energy,
                            SpectralFlux = spectralFlux,
                            Spectrum = spectrum,
                            EstimatedType = estimateDrumType(spectrum, energy)
                        };

                        OnsetDetected?.Invoke(onsetEvent);
                    }
                }
            }
        }

        private float calculateRMS(float[] audioData)
        {
            float sum = 0;
            for (int i = 0; i < audioData.Length; i++)
            {
                sum += audioData[i] * audioData[i];
            }
            return (float)Math.Sqrt(sum / audioData.Length);
        }

        private float[] calculateSpectrum(float[] audioData)
        {
            // Simple spectrum estimation using frequency bands
            // In a real implementation, use FFT
            int bands = 8;
            float[] spectrum = new float[bands];

            int samplesPerBand = audioData.Length / bands;

            for (int band = 0; band < bands; band++)
            {
                float energy = 0;
                int start = band * samplesPerBand;
                int end = Math.Min(start + samplesPerBand, audioData.Length);

                for (int i = start; i < end; i++)
                {
                    energy += Math.Abs(audioData[i]);
                }

                spectrum[band] = energy / samplesPerBand;
            }

            return spectrum;
        }

        private DrumType estimateDrumType(float[] spectrum, float energy)
        {
            var profile = CalibrationProfile;
            if (profile?.DrumSignatures != null && profile.DrumSignatures.Count > 0)
            {
                var normalizedSpectrum = normalizeSpectrum(spectrum);
                DrumType bestType = DrumType.Unknown;
                float bestScore = float.MaxValue;

                foreach (var kvp in profile.DrumSignatures)
                {
                    var signature = kvp.Value;
                    if (signature.AverageSpectrum.Length != spectrum.Length || signature.SampleCount == 0)
                        continue;

                    var sigNormalized = signature.NormalizedSpectrum;
                    if (sigNormalized.Length != normalizedSpectrum.Length)
                        continue;
                    float spectrumDistance = 0;
                    for (int i = 0; i < normalizedSpectrum.Length; i++)
                    {
                        float diff = normalizedSpectrum[i] - sigNormalized[i];
                        spectrumDistance += diff * diff;
                    }

                    float energyDistance = Math.Abs(energy - signature.AverageEnergy);
                    float score = spectrumDistance * 0.8f + energyDistance * 4f;

                    if (score < bestScore)
                    {
                        bestScore = score;
                        bestType = kvp.Key;
                    }
                }

                if (bestType != DrumType.Unknown)
                    return bestType;
            }

            // Fallback heuristic when no calibration is available
            if (spectrum.Length < 3)
                return DrumType.Unknown;

            float lowEnergy = spectrum[0] + spectrum[1];
            float midEnergy = spectrum[2] + spectrum[3] + spectrum[4];
            float highEnergy = spectrum[5] + spectrum[6] + (spectrum.Length > 7 ? spectrum[7] : 0);

            if (lowEnergy > midEnergy && lowEnergy > highEnergy)
                return DrumType.Kick;
            else if (midEnergy > lowEnergy && midEnergy > highEnergy)
                return DrumType.Snare;
            else if (highEnergy > lowEnergy && highEnergy > midEnergy)
                return DrumType.Cymbal;

            return DrumType.Unknown;
        }

        private float[] normalizeSpectrum(float[] spectrum)
        {
            float sum = 0;
            for (int i = 0; i < spectrum.Length; i++)
                sum += spectrum[i];

            if (sum <= 0)
                return (float[])spectrum.Clone();

            float[] normalized = new float[spectrum.Length];
            for (int i = 0; i < spectrum.Length; i++)
                normalized[i] = spectrum[i] / sum;

            return normalized;
        }

        /// <summary>
        /// Reset the detector state
        /// </summary>
        public void Reset()
        {
            energyHistory.Clear();
            previousSpectrum = Array.Empty<float>();
            lastOnsetTime = 0;
        }
    }

    public class OnsetEvent
    {
        public double Time { get; init; }
        public float Energy { get; init; }
        public float SpectralFlux { get; init; }
        public float[] Spectrum { get; init; } = Array.Empty<float>();
        public DrumType EstimatedType { get; init; }
    }

    public enum DrumType
    {
        Unknown,
        Kick,
        Snare,
        Tom,
        Cymbal,
        HiHat
    }
}
