using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.Services.Decode;
using osu.Framework.Logging;

namespace BeatSight.Game.Audio
{
    public class WaveformData
    {
        public WaveformData(float[] minimums, float[] maximums, double durationSeconds, int sampleRate, int channels)
        {
            Minima = minimums;
            Maxima = maximums;
            DurationSeconds = durationSeconds;
            SampleRate = sampleRate;
            Channels = channels;
            BucketDurationSeconds = minimums.Length > 0 ? durationSeconds / minimums.Length : 0;
        }

        public float[] Minima { get; }
        public float[] Maxima { get; }
        public int BucketCount => Minima.Length;
        public double DurationSeconds { get; }
        public double BucketDurationSeconds { get; }
        public int SampleRate { get; }
        public int Channels { get; }
    }

    public static class WaveformDataBuilder
    {
        private const int defaultBucketCount = 2000;

        public static async Task<WaveformData?> BuildAsync(string audioPath, int bucketCount = defaultBucketCount, IProgress<double>? progress = null, CancellationToken cancellationToken = default)
        {
            if (string.IsNullOrWhiteSpace(audioPath) || !File.Exists(audioPath))
                return null;

            try
            {
                var decodeService = new DecodeService();
                var decoded = await decodeService.DecodeAsync(audioPath, bucketCount, progress, cancellationToken).ConfigureAwait(false);
                return decoded.Waveform;
            }
            catch (OperationCanceledException)
            {
                throw;
            }
            catch (Exception ex)
            {
                Logger.Error(ex, $"Failed to build waveform for '{audioPath}'");
                return null;
            }
        }
    }
}
