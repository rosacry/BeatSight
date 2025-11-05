using System;
using System.Collections.Generic;
using BeatSight.Game.Audio;

namespace BeatSight.Game.Calibration
{
    /// <summary>
    /// Stores per-drum microphone calibration data gathered from the user.
    /// </summary>
    public class MicCalibrationProfile
    {
        public string Version { get; set; } = "1.0";
        public DateTime CompletedAt { get; set; } = DateTime.UtcNow;
        public Dictionary<DrumType, DrumSignature> DrumSignatures { get; set; } = new();
        public double AmbientNoiseFloor { get; set; }
        public class DrumSignature
        {
            public float[] AverageSpectrum { get; set; } = Array.Empty<float>();
            public float AverageEnergy { get; set; }
            public float PeakEnergy { get; set; }
            public int SampleCount { get; set; }

            public float[] NormalizedSpectrum
            {
                get
                {
                    if (AverageSpectrum.Length == 0)
                        return Array.Empty<float>();

                    float sum = 0;
                    for (int i = 0; i < AverageSpectrum.Length; i++)
                        sum += AverageSpectrum[i];

                    if (sum <= 0)
                        return AverageSpectrum;

                    float[] normalized = new float[AverageSpectrum.Length];
                    for (int i = 0; i < AverageSpectrum.Length; i++)
                        normalized[i] = AverageSpectrum[i] / sum;

                    return normalized;
                }
            }
        }
    }
}
