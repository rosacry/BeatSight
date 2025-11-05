using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using BeatSight.Game.Audio;
using ManagedBass;
using osu.Framework.Logging;
using TagLib;

namespace BeatSight.Game.Services.Decode
{
    public sealed class DecodeService
    {
        private const int waveformBuckets = 2400;

        public async Task<DecodedAudio> DecodeAsync(string audioPath, int bucketCount = waveformBuckets, IProgress<double>? progress = null, CancellationToken cancellationToken = default)
        {
            if (string.IsNullOrWhiteSpace(audioPath))
                throw new ArgumentException("Audio path must be provided", nameof(audioPath));

            if (!System.IO.File.Exists(audioPath))
                throw new FileNotFoundException("Audio file not found", audioPath);

            bucketCount = Math.Max(1, bucketCount);

            cancellationToken.ThrowIfCancellationRequested();
            progress?.Report(0.01);

            var metadata = await Task.Run(() => readMetadata(audioPath), cancellationToken).ConfigureAwait(false);
            progress?.Report(0.05);

            var decoded = await Task.Run(() => decodeInternal(audioPath, bucketCount, metadata, progress, cancellationToken), cancellationToken).ConfigureAwait(false);
            progress?.Report(1.0);
            return decoded;
        }

        private static DecodedAudio decodeInternal(string audioPath, int bucketCount, (double DurationSeconds, int SampleRate, int Channels) metadata, IProgress<double>? progress, CancellationToken cancellationToken)
        {
            int handle = 0;
            bool bassInitialisedByDecode = false;

            try
            {
                if (!Bass.Init(Bass.NoSoundDevice, metadata.SampleRate > 0 ? metadata.SampleRate : 44100, DeviceInitFlags.Default))
                {
                    var initError = Bass.LastError;
                    if (initError != Errors.Already)
                        throw new InvalidOperationException($"BASS init failed: {initError}");
                }
                else
                {
                    bassInitialisedByDecode = true;
                }

                handle = Bass.CreateStream(audioPath, 0, 0, BassFlags.Decode | BassFlags.Float | BassFlags.Prescan);
                if (handle == 0)
                    throw new InvalidOperationException($"BASS decode stream failed: {Bass.LastError}");

                var info = Bass.ChannelGetInfo(handle);
                int channels = info.Channels > 0 ? info.Channels : (metadata.Channels > 0 ? metadata.Channels : 2);
                int sampleRate = info.Frequency > 0 ? info.Frequency : (metadata.SampleRate > 0 ? metadata.SampleRate : 44100);

                long lengthBytes = Bass.ChannelGetLength(handle);
                double durationSeconds = 0;
                if (lengthBytes > 0)
                {
                    double derivedSeconds = Bass.ChannelBytes2Seconds(handle, lengthBytes);
                    if (double.IsFinite(derivedSeconds) && derivedSeconds > 0)
                        durationSeconds = derivedSeconds;
                }

                if (durationSeconds <= 0)
                    durationSeconds = metadata.DurationSeconds;

                if (durationSeconds <= 0)
                    durationSeconds = 1; // guard for zero-duration assets

                long framesTotal = lengthBytes > 0
                    ? lengthBytes / (sizeof(float) * Math.Max(1, channels))
                    : (long)Math.Max(1, durationSeconds * sampleRate);

                double framesPerBucket = Math.Max(1, (double)framesTotal / bucketCount);
                int bufferFrames = Math.Min(32768, Math.Max(4096, (int)Math.Ceiling(framesPerBucket * 2)));

                var buffer = new float[bufferFrames * Math.Max(1, channels)];
                var minima = new float[bucketCount];
                var maxima = new float[bucketCount];

                long processedFrames = 0;
                double lastProgress = 0;

                while (true)
                {
                    cancellationToken.ThrowIfCancellationRequested();

                    int bytesRead = Bass.ChannelGetData(handle, buffer, buffer.Length * sizeof(float));
                    if (bytesRead <= 0)
                        break;

                    int framesRead = bytesRead / (sizeof(float) * Math.Max(1, channels));
                    for (int frame = 0; frame < framesRead; frame++)
                    {
                        cancellationToken.ThrowIfCancellationRequested();

                        float amplitude = 0f;
                        int offset = frame * channels;
                        for (int ch = 0; ch < channels; ch++)
                        {
                            float sample = buffer[offset + ch];
                            amplitude = Math.Max(amplitude, Math.Abs(sample));
                        }

                        int bucketIndex = (int)Math.Min(bucketCount - 1, Math.Floor(processedFrames / framesPerBucket));
                        maxima[bucketIndex] = Math.Max(maxima[bucketIndex], amplitude);
                        minima[bucketIndex] = Math.Min(minima[bucketIndex], -amplitude);

                        processedFrames++;
                    }

                    if (progress != null && framesTotal > 0)
                    {
                        double ratio = Math.Clamp((double)processedFrames / framesTotal, 0, 1);
                        if (ratio - lastProgress >= 0.015)
                        {
                            lastProgress = ratio;
                            progress.Report(0.08 + 0.9 * ratio);
                        }
                    }
                }

                if (processedFrames > 0 && durationSeconds <= 1)
                    durationSeconds = processedFrames / (double)sampleRate;

                var waveform = new WaveformData(minima, maxima, durationSeconds, sampleRate, channels);
                progress?.Report(0.98);

                return new DecodedAudio(audioPath, waveform);
            }
            finally
            {
                if (handle != 0)
                    Bass.StreamFree(handle);

                if (bassInitialisedByDecode)
                {
                    if (!Bass.Free())
                        Logger.Log($"[decode] failed to free temporary BASS device: {Bass.LastError}", LoggingTarget.Runtime, LogLevel.Debug);
                }
            }
        }

        private static (double DurationSeconds, int SampleRate, int Channels) readMetadata(string path)
        {
            try
            {
                using var tag = TagLib.File.Create(path);
                return (tag.Properties.Duration.TotalSeconds, tag.Properties.AudioSampleRate, tag.Properties.AudioChannels);
            }
            catch (Exception ex)
            {
                Logger.Log($"[decode] metadata probe failed for '{path}': {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
                return (0, 0, 0);
            }
        }
    }

    public readonly record struct DecodedAudio(string Path, WaveformData Waveform);
}
