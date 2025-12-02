using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using osu.Framework.Logging;

namespace BeatSight.Game.Services.Recording
{
    /// <summary>
    /// Cross-platform audio recording service.
    /// Uses NAudio on Windows, or falls back to platform-specific implementations.
    /// </summary>
    public class AudioRecordingService : IDisposable
    {
        // Events
        public event Action<float, bool>? LevelChanged;
        public event Action<string>? RecordingCompleted;
        public event Action<string>? Error;

        // Recording state
        private bool isRecording;
        private bool isMonitoring;
        private DateTime recordingStartTime;
        private string? currentFilePath;

        // Audio settings
        private int sampleRate = 48000;
        private int channels = 2;

        // Metronome
        private bool metronomeEnabled;
        private int metronomeBpm = 120;
        private Timer? metronomeTimer;
        private int beatCount;

        // Platform-specific recorder
        private IPlatformAudioRecorder? recorder;

        // Frequency data for visualization
        private readonly float[] frequencyData = new float[64];
        private readonly object frequencyLock = new object();

        public TimeSpan RecordingDuration => isRecording
            ? DateTime.UtcNow - recordingStartTime
            : TimeSpan.Zero;

        public int MetronomeBpm
        {
            get => metronomeBpm;
            set => metronomeBpm = Math.Clamp(value, 40, 240);
        }

        public void Initialize(int sampleRate, int channels)
        {
            this.sampleRate = sampleRate;
            this.channels = channels;

            try
            {
                // Try to initialize platform-specific recorder
                if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
                {
                    recorder = new WindowsAudioRecorder(sampleRate, channels);
                }
                else if (RuntimeInformation.IsOSPlatform(OSPlatform.OSX))
                {
                    recorder = new MacOSAudioRecorder(sampleRate, channels);
                }
                else if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux))
                {
                    recorder = new LinuxAudioRecorder(sampleRate, channels);
                }
                else
                {
                    Error?.Invoke("Unsupported platform for audio recording");
                    return;
                }

                recorder.DataAvailable += onDataAvailable;
                recorder.Error += s => Error?.Invoke(s);

                Logger.Log($"Audio recording initialized: {sampleRate}Hz, {channels}ch", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to initialize audio recording: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
                Error?.Invoke($"Failed to initialize audio: {ex.Message}");
            }
        }

        public void StartMonitoring()
        {
            if (recorder == null)
            {
                Error?.Invoke("Audio recorder not initialized");
                return;
            }

            try
            {
                recorder.StartCapture(null); // null path = monitoring only
                isMonitoring = true;
                Logger.Log("Audio monitoring started", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Error?.Invoke($"Failed to start monitoring: {ex.Message}");
            }
        }

        public void StopMonitoring()
        {
            if (!isMonitoring) return;

            try
            {
                recorder?.StopCapture();
                isMonitoring = false;
                Logger.Log("Audio monitoring stopped", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Logger.Log($"Error stopping monitoring: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
            }
        }

        public void StartRecording(string filePath)
        {
            if (recorder == null)
            {
                Error?.Invoke("Audio recorder not initialized");
                return;
            }

            try
            {
                // Stop monitoring if active
                if (isMonitoring)
                    recorder.StopCapture();

                currentFilePath = filePath;
                recorder.StartCapture(filePath);
                recordingStartTime = DateTime.UtcNow;
                isRecording = true;
                isMonitoring = false;

                Logger.Log($"Recording started: {filePath}", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Error?.Invoke($"Failed to start recording: {ex.Message}");
            }
        }

        public void StopRecording()
        {
            if (!isRecording) return;

            try
            {
                recorder?.StopCapture();
                isRecording = false;

                if (!string.IsNullOrEmpty(currentFilePath))
                {
                    RecordingCompleted?.Invoke(currentFilePath);
                }

                Logger.Log($"Recording stopped: {RecordingDuration.TotalSeconds:F1}s", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Error?.Invoke($"Failed to stop recording: {ex.Message}");
            }
        }

        public void StartMetronome(int bpm)
        {
            metronomeBpm = bpm;
            metronomeEnabled = true;
            beatCount = 0;

            var interval = TimeSpan.FromMilliseconds(60000.0 / bpm);
            metronomeTimer = new Timer(onMetronomeTick, null, TimeSpan.Zero, interval);

            Logger.Log($"Metronome started at {bpm} BPM", LoggingTarget.Runtime);
        }

        public void StopMetronome()
        {
            metronomeEnabled = false;
            metronomeTimer?.Dispose();
            metronomeTimer = null;
            beatCount = 0;

            Logger.Log("Metronome stopped", LoggingTarget.Runtime);
        }

        public float[] GetFrequencyData()
        {
            lock (frequencyLock)
            {
                return (float[])frequencyData.Clone();
            }
        }

        private void onDataAvailable(float[] samples, float peakLevel, bool isClipping)
        {
            // Update frequency data for visualization
            lock (frequencyLock)
            {
                // Simple FFT approximation using sample magnitudes
                // In a real implementation, use proper FFT
                int samplesPerBin = samples.Length / 64;
                for (int i = 0; i < 64; i++)
                {
                    float sum = 0;
                    int start = i * samplesPerBin;
                    int end = Math.Min(start + samplesPerBin, samples.Length);

                    for (int j = start; j < end; j++)
                    {
                        sum += Math.Abs(samples[j]);
                    }

                    frequencyData[i] = samplesPerBin > 0 ? sum / samplesPerBin : 0;
                }
            }

            LevelChanged?.Invoke(peakLevel, isClipping);
        }

        private void onMetronomeTick(object? state)
        {
            if (!metronomeEnabled) return;

            bool isAccent = beatCount % 4 == 0;
            PlayMetronomeClick(isAccent);
            beatCount++;
        }

        protected virtual void PlayMetronomeClick(bool isAccent)
        {
            // Override in platform-specific implementations
            // or use audio engine to play click sound
        }

        public void Dispose()
        {
            StopRecording();
            StopMonitoring();
            StopMetronome();
            recorder?.Dispose();
        }
    }

    /// <summary>
    /// Interface for platform-specific audio recording.
    /// </summary>
    public interface IPlatformAudioRecorder : IDisposable
    {
        event Action<float[], float, bool>? DataAvailable;
        event Action<string>? Error;

        void StartCapture(string? filePath);
        void StopCapture();
    }

    /// <summary>
    /// Windows audio recorder using WASAPI (via NAudio when available).
    /// Falls back to basic WaveIn if NAudio is not available.
    /// </summary>
    public class WindowsAudioRecorder : IPlatformAudioRecorder
    {
        public event Action<float[], float, bool>? DataAvailable;
        public event Action<string>? Error;

        private readonly int sampleRate;
        private readonly int channels;
        private bool isCapturing;
        private FileStream? fileStream;
        private BinaryWriter? writer;
        private long dataChunkPosition;
        private int totalSamplesWritten;

        public WindowsAudioRecorder(int sampleRate, int channels)
        {
            this.sampleRate = sampleRate;
            this.channels = channels;
        }

        public void StartCapture(string? filePath)
        {
            if (isCapturing) return;

            try
            {
                if (!string.IsNullOrEmpty(filePath))
                {
                    // Initialize WAV file
                    fileStream = new FileStream(filePath, FileMode.Create);
                    writer = new BinaryWriter(fileStream);
                    WriteWavHeader(writer, sampleRate, channels, 16);
                    dataChunkPosition = fileStream.Position;
                    totalSamplesWritten = 0;
                }

                // Start capturing audio
                // TODO: Use NAudio or platform APIs for actual capture
                // For now, simulate with dummy data for structure validation
                isCapturing = true;

                // In real implementation:
                // - Use NAudio.Wave.WasapiCapture for Windows
                // - Or use Windows.Devices.Enumeration + AudioGraph for UWP

                Logger.Log("Windows audio capture started (stub implementation)", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Error?.Invoke(ex.Message);
            }
        }

        public void StopCapture()
        {
            if (!isCapturing) return;

            try
            {
                isCapturing = false;

                if (writer != null && fileStream != null)
                {
                    // Update WAV header with final size
                    FinalizeWavHeader(writer, fileStream, dataChunkPosition, totalSamplesWritten);
                    writer.Dispose();
                    fileStream.Dispose();
                    writer = null;
                    fileStream = null;
                }

                Logger.Log("Windows audio capture stopped", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Error?.Invoke(ex.Message);
            }
        }

        private static void WriteWavHeader(BinaryWriter writer, int sampleRate, int channels, int bitsPerSample)
        {
            int byteRate = sampleRate * channels * bitsPerSample / 8;
            int blockAlign = channels * bitsPerSample / 8;

            // RIFF header
            writer.Write(System.Text.Encoding.ASCII.GetBytes("RIFF"));
            writer.Write(0); // Placeholder for file size
            writer.Write(System.Text.Encoding.ASCII.GetBytes("WAVE"));

            // fmt chunk
            writer.Write(System.Text.Encoding.ASCII.GetBytes("fmt "));
            writer.Write(16); // Chunk size
            writer.Write((short)1); // Audio format (PCM)
            writer.Write((short)channels);
            writer.Write(sampleRate);
            writer.Write(byteRate);
            writer.Write((short)blockAlign);
            writer.Write((short)bitsPerSample);

            // data chunk header
            writer.Write(System.Text.Encoding.ASCII.GetBytes("data"));
            writer.Write(0); // Placeholder for data size
        }

        private static void FinalizeWavHeader(BinaryWriter writer, FileStream stream, long dataChunkPosition, int totalSamples)
        {
            long fileSize = stream.Length;

            // Update RIFF chunk size
            stream.Seek(4, SeekOrigin.Begin);
            writer.Write((int)(fileSize - 8));

            // Update data chunk size
            stream.Seek(dataChunkPosition - 4, SeekOrigin.Begin);
            writer.Write(totalSamples * 2); // 16-bit samples

            stream.Seek(0, SeekOrigin.End);
        }

        public void Dispose()
        {
            StopCapture();
        }
    }

    /// <summary>
    /// macOS audio recorder using Core Audio.
    /// </summary>
    public class MacOSAudioRecorder : IPlatformAudioRecorder
    {
        public event Action<float[], float, bool>? DataAvailable;
        public event Action<string>? Error;

        private readonly int sampleRate;
        private readonly int channels;
        private bool isCapturing;

        public MacOSAudioRecorder(int sampleRate, int channels)
        {
            this.sampleRate = sampleRate;
            this.channels = channels;
        }

        public void StartCapture(string? filePath)
        {
            if (isCapturing) return;

            // TODO: Implement Core Audio capture
            // Use AVFoundation or Core Audio APIs
            isCapturing = true;
            Logger.Log("macOS audio capture started (stub implementation)", LoggingTarget.Runtime);
        }

        public void StopCapture()
        {
            if (!isCapturing) return;
            isCapturing = false;
            Logger.Log("macOS audio capture stopped", LoggingTarget.Runtime);
        }

        public void Dispose()
        {
            StopCapture();
        }
    }

    /// <summary>
    /// Linux audio recorder using ALSA or PulseAudio.
    /// </summary>
    public class LinuxAudioRecorder : IPlatformAudioRecorder
    {
        public event Action<float[], float, bool>? DataAvailable;
        public event Action<string>? Error;

        private readonly int sampleRate;
        private readonly int channels;
        private bool isCapturing;

        public LinuxAudioRecorder(int sampleRate, int channels)
        {
            this.sampleRate = sampleRate;
            this.channels = channels;
        }

        public void StartCapture(string? filePath)
        {
            if (isCapturing) return;

            // TODO: Implement ALSA/PulseAudio capture
            // Could use arecord subprocess or native bindings
            isCapturing = true;
            Logger.Log("Linux audio capture started (stub implementation)", LoggingTarget.Runtime);
        }

        public void StopCapture()
        {
            if (!isCapturing) return;
            isCapturing = false;
            Logger.Log("Linux audio capture stopped", LoggingTarget.Runtime);
        }

        public void Dispose()
        {
            StopCapture();
        }
    }
}
