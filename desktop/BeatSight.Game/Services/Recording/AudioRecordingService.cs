using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;
using NAudio.CoreAudioApi;
using NAudio.Wave;
using osu.Framework.Logging;

namespace BeatSight.Game.Services.Recording
{
    /// <summary>
    /// Cross-platform audio recording service.
    /// Uses NAudio WasapiCapture on Windows, native APIs on macOS/Linux.
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
    /// Windows audio recorder using NAudio WASAPI capture.
    /// Provides low-latency, high-quality audio capture from any input device.
    /// </summary>
    public class WindowsAudioRecorder : IPlatformAudioRecorder
    {
        public event Action<float[], float, bool>? DataAvailable;
        public event Action<string>? Error;

        private readonly int sampleRate;
        private readonly int channels;
        private WasapiCapture? capture;
        private WaveFileWriter? waveWriter;
        private bool isCapturing;
        private string? currentFilePath;

        // Buffer for processing
        private readonly float[] processingBuffer = new float[4096];

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
                currentFilePath = filePath;

                // Initialize WASAPI capture (default capture device)
                capture = new WasapiCapture();

                // Log device info
                Logger.Log($"Recording device: {capture.WaveFormat.SampleRate}Hz, {capture.WaveFormat.Channels}ch, {capture.WaveFormat.BitsPerSample}bit", LoggingTarget.Runtime);

                // Set up file writer if recording to file
                if (!string.IsNullOrEmpty(filePath))
                {
                    // Create output format (convert to standard WAV format)
                    var outputFormat = new WaveFormat(sampleRate, 16, channels);
                    waveWriter = new WaveFileWriter(filePath, outputFormat);
                }

                capture.DataAvailable += onCaptureDataAvailable;
                capture.RecordingStopped += onRecordingStopped;

                capture.StartRecording();
                isCapturing = true;

                Logger.Log($"Windows WASAPI capture started{(filePath != null ? $": {filePath}" : " (monitoring)")}", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to start Windows capture: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
                Error?.Invoke($"Failed to start recording: {ex.Message}");
                Cleanup();
            }
        }

        private void onCaptureDataAvailable(object? sender, WaveInEventArgs e)
        {
            if (e.BytesRecorded == 0) return;

            try
            {
                var captureFormat = capture!.WaveFormat;
                int bytesPerSample = captureFormat.BitsPerSample / 8;
                int sampleCount = e.BytesRecorded / bytesPerSample;

                // Convert to float samples for processing
                float[] samples = new float[sampleCount];
                float peak = 0f;
                bool isClipping = false;

                if (captureFormat.BitsPerSample == 32 && captureFormat.Encoding == WaveFormatEncoding.IeeeFloat)
                {
                    // 32-bit float samples
                    Buffer.BlockCopy(e.Buffer, 0, samples, 0, e.BytesRecorded);
                }
                else if (captureFormat.BitsPerSample == 16)
                {
                    // 16-bit PCM samples
                    for (int i = 0; i < sampleCount; i++)
                    {
                        short sample = BitConverter.ToInt16(e.Buffer, i * 2);
                        samples[i] = sample / 32768f;
                    }
                }
                else if (captureFormat.BitsPerSample == 24)
                {
                    // 24-bit PCM samples
                    for (int i = 0; i < sampleCount; i++)
                    {
                        int sample = (e.Buffer[i * 3 + 2] << 16) | (e.Buffer[i * 3 + 1] << 8) | e.Buffer[i * 3];
                        if ((sample & 0x800000) != 0) sample |= unchecked((int)0xFF000000); // Sign extend
                        samples[i] = sample / 8388608f;
                    }
                }
                else if (captureFormat.BitsPerSample == 32)
                {
                    // 32-bit PCM samples
                    for (int i = 0; i < sampleCount; i++)
                    {
                        int sample = BitConverter.ToInt32(e.Buffer, i * 4);
                        samples[i] = sample / 2147483648f;
                    }
                }

                // Calculate peak level and check for clipping
                for (int i = 0; i < samples.Length; i++)
                {
                    float abs = Math.Abs(samples[i]);
                    if (abs > peak) peak = abs;
                    if (abs >= 0.99f) isClipping = true;
                }

                // Write to file if recording
                if (waveWriter != null)
                {
                    // Resample if necessary and convert to 16-bit for file
                    WriteToFile(samples, captureFormat);
                }

                // Notify listeners
                DataAvailable?.Invoke(samples, peak, isClipping);
            }
            catch (Exception ex)
            {
                Logger.Log($"Error processing capture data: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
            }
        }

        private void WriteToFile(float[] samples, WaveFormat captureFormat)
        {
            if (waveWriter == null) return;

            try
            {
                // Convert to target format (16-bit stereo at target sample rate)
                // For simplicity, we'll write the samples directly if formats match
                // A real implementation would use a resampler for sample rate conversion

                // Convert float to 16-bit samples
                var buffer = new byte[samples.Length * 2];
                for (int i = 0; i < samples.Length; i++)
                {
                    // Clamp to prevent overflow
                    float sample = Math.Clamp(samples[i], -1f, 1f);
                    short pcmSample = (short)(sample * 32767f);
                    buffer[i * 2] = (byte)(pcmSample & 0xFF);
                    buffer[i * 2 + 1] = (byte)((pcmSample >> 8) & 0xFF);
                }

                // Handle channel conversion if needed
                if (captureFormat.Channels != channels)
                {
                    // Simple channel mixing (mono to stereo or stereo to mono)
                    buffer = ConvertChannels(buffer, captureFormat.Channels, channels);
                }

                waveWriter.Write(buffer, 0, buffer.Length);
            }
            catch (Exception ex)
            {
                Logger.Log($"Error writing to file: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
            }
        }

        private static byte[] ConvertChannels(byte[] input, int inputChannels, int outputChannels)
        {
            if (inputChannels == outputChannels) return input;

            int inputSamples = input.Length / (2 * inputChannels);
            var output = new byte[inputSamples * 2 * outputChannels];

            for (int i = 0; i < inputSamples; i++)
            {
                if (inputChannels == 1 && outputChannels == 2)
                {
                    // Mono to stereo: duplicate sample
                    short sample = BitConverter.ToInt16(input, i * 2);
                    byte[] sampleBytes = BitConverter.GetBytes(sample);
                    output[i * 4] = sampleBytes[0];
                    output[i * 4 + 1] = sampleBytes[1];
                    output[i * 4 + 2] = sampleBytes[0];
                    output[i * 4 + 3] = sampleBytes[1];
                }
                else if (inputChannels == 2 && outputChannels == 1)
                {
                    // Stereo to mono: average channels
                    short left = BitConverter.ToInt16(input, i * 4);
                    short right = BitConverter.ToInt16(input, i * 4 + 2);
                    short mono = (short)((left + right) / 2);
                    byte[] sampleBytes = BitConverter.GetBytes(mono);
                    output[i * 2] = sampleBytes[0];
                    output[i * 2 + 1] = sampleBytes[1];
                }
            }

            return output;
        }

        private void onRecordingStopped(object? sender, StoppedEventArgs e)
        {
            if (e.Exception != null)
            {
                Error?.Invoke($"Recording stopped due to error: {e.Exception.Message}");
            }
        }

        public void StopCapture()
        {
            if (!isCapturing) return;

            try
            {
                capture?.StopRecording();
                Cleanup();
                isCapturing = false;
                Logger.Log("Windows WASAPI capture stopped", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Logger.Log($"Error stopping capture: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
                Error?.Invoke(ex.Message);
            }
        }

        private void Cleanup()
        {
            waveWriter?.Dispose();
            waveWriter = null;

            if (capture != null)
            {
                capture.DataAvailable -= onCaptureDataAvailable;
                capture.RecordingStopped -= onRecordingStopped;
                capture.Dispose();
                capture = null;
            }
        }

        public void Dispose()
        {
            StopCapture();
        }
    }

    /// <summary>
    /// macOS audio recorder using AVFoundation via ffmpeg subprocess.
    /// Falls back to using the 'rec' command from SoX if ffmpeg is unavailable.
    /// </summary>
    public class MacOSAudioRecorder : IPlatformAudioRecorder
    {
        public event Action<float[], float, bool>? DataAvailable;
        public event Action<string>? Error;

        private readonly int sampleRate;
        private readonly int channels;
        private Process? recordingProcess;
        private bool isCapturing;
        private string? currentFilePath;
        private Thread? monitorThread;
        private CancellationTokenSource? cts;

        // Simulated level monitoring (real implementation would parse audio data)
        private readonly Random levelRandom = new Random();

        public MacOSAudioRecorder(int sampleRate, int channels)
        {
            this.sampleRate = sampleRate;
            this.channels = channels;
        }

        public void StartCapture(string? filePath)
        {
            if (isCapturing) return;

            try
            {
                currentFilePath = filePath;
                cts = new CancellationTokenSource();

                if (!string.IsNullOrEmpty(filePath))
                {
                    // Use ffmpeg to capture from default audio input device
                    // On macOS, use avfoundation input
                    var startInfo = new ProcessStartInfo
                    {
                        FileName = "ffmpeg",
                        Arguments = $"-f avfoundation -i \":default\" -ar {sampleRate} -ac {channels} -y \"{filePath}\"",
                        UseShellExecute = false,
                        RedirectStandardError = true,
                        RedirectStandardOutput = true,
                        CreateNoWindow = true,
                    };

                    recordingProcess = new Process { StartInfo = startInfo };
                    recordingProcess.ErrorDataReceived += onProcessErrorData;
                    recordingProcess.Start();
                    recordingProcess.BeginErrorReadLine();

                    Logger.Log($"macOS ffmpeg capture started: {filePath}", LoggingTarget.Runtime);
                }

                isCapturing = true;

                // Start level monitoring thread
                monitorThread = new Thread(MonitorLevels) { IsBackground = true };
                monitorThread.Start();

                Logger.Log("macOS audio capture started", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to start macOS capture: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);

                // Try fallback to SoX 'rec' command
                if (ex.Message.Contains("ffmpeg") || ex is System.ComponentModel.Win32Exception)
                {
                    TryFallbackCapture(filePath);
                }
                else
                {
                    Error?.Invoke($"Failed to start recording: {ex.Message}. Please install ffmpeg: brew install ffmpeg");
                }
            }
        }

        private void TryFallbackCapture(string? filePath)
        {
            try
            {
                if (string.IsNullOrEmpty(filePath)) return;

                var startInfo = new ProcessStartInfo
                {
                    FileName = "rec",
                    Arguments = $"-r {sampleRate} -c {channels} \"{filePath}\"",
                    UseShellExecute = false,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                };

                recordingProcess = new Process { StartInfo = startInfo };
                recordingProcess.Start();
                isCapturing = true;

                Logger.Log($"macOS SoX rec fallback started: {filePath}", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Error?.Invoke($"Failed to start recording. Please install ffmpeg (brew install ffmpeg) or SoX (brew install sox): {ex.Message}");
            }
        }

        private void MonitorLevels()
        {
            var token = cts?.Token ?? CancellationToken.None;
            var samples = new float[64];

            while (!token.IsCancellationRequested && isCapturing)
            {
                try
                {
                    // Generate simulated level data
                    // In a real implementation, we'd read from a pipe or analyze the file
                    float peak = 0f;
                    for (int i = 0; i < samples.Length; i++)
                    {
                        samples[i] = (float)(levelRandom.NextDouble() * 0.5);
                        if (samples[i] > peak) peak = samples[i];
                    }

                    DataAvailable?.Invoke(samples, peak, peak > 0.95f);
                    Thread.Sleep(50); // Update ~20 times per second
                }
                catch (OperationCanceledException)
                {
                    break;
                }
            }
        }

        private void onProcessErrorData(object sender, DataReceivedEventArgs e)
        {
            if (!string.IsNullOrEmpty(e.Data))
            {
                // ffmpeg outputs progress to stderr
                Logger.Log($"ffmpeg: {e.Data}", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        public void StopCapture()
        {
            if (!isCapturing) return;

            try
            {
                cts?.Cancel();
                isCapturing = false;

                if (recordingProcess != null && !recordingProcess.HasExited)
                {
                    // Send 'q' to ffmpeg to gracefully stop, or kill if that fails
                    try
                    {
                        recordingProcess.StandardInput?.WriteLine("q");
                        if (!recordingProcess.WaitForExit(2000))
                        {
                            recordingProcess.Kill();
                        }
                    }
                    catch
                    {
                        recordingProcess.Kill();
                    }
                }

                recordingProcess?.Dispose();
                recordingProcess = null;
                monitorThread = null;

                Logger.Log("macOS audio capture stopped", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Logger.Log($"Error stopping macOS capture: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
            }
        }

        public void Dispose()
        {
            StopCapture();
            cts?.Dispose();
        }
    }

    /// <summary>
    /// Linux audio recorder using ALSA (arecord) or PulseAudio (parecord/ffmpeg).
    /// </summary>
    public class LinuxAudioRecorder : IPlatformAudioRecorder
    {
        public event Action<float[], float, bool>? DataAvailable;
        public event Action<string>? Error;

        private readonly int sampleRate;
        private readonly int channels;
        private Process? recordingProcess;
        private bool isCapturing;
        private string? currentFilePath;
        private Thread? monitorThread;
        private CancellationTokenSource? cts;

        private readonly Random levelRandom = new Random();

        public LinuxAudioRecorder(int sampleRate, int channels)
        {
            this.sampleRate = sampleRate;
            this.channels = channels;
        }

        public void StartCapture(string? filePath)
        {
            if (isCapturing) return;

            try
            {
                currentFilePath = filePath;
                cts = new CancellationTokenSource();

                if (!string.IsNullOrEmpty(filePath))
                {
                    // Try PulseAudio first (more common on modern Linux)
                    if (!TryStartPulseAudio(filePath))
                    {
                        // Fall back to ALSA
                        TryStartAlsa(filePath);
                    }
                }

                isCapturing = true;

                // Start level monitoring thread
                monitorThread = new Thread(MonitorLevels) { IsBackground = true };
                monitorThread.Start();

                Logger.Log("Linux audio capture started", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to start Linux capture: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
                Error?.Invoke($"Failed to start recording: {ex.Message}. Please install ffmpeg or alsa-utils.");
            }
        }

        private bool TryStartPulseAudio(string filePath)
        {
            try
            {
                // Use ffmpeg with PulseAudio input
                var startInfo = new ProcessStartInfo
                {
                    FileName = "ffmpeg",
                    Arguments = $"-f pulse -i default -ar {sampleRate} -ac {channels} -y \"{filePath}\"",
                    UseShellExecute = false,
                    RedirectStandardError = true,
                    RedirectStandardInput = true,
                    CreateNoWindow = true,
                };

                recordingProcess = new Process { StartInfo = startInfo };
                recordingProcess.ErrorDataReceived += onProcessErrorData;
                recordingProcess.Start();
                recordingProcess.BeginErrorReadLine();

                Logger.Log($"Linux PulseAudio/ffmpeg capture started: {filePath}", LoggingTarget.Runtime);
                return true;
            }
            catch
            {
                return false;
            }
        }

        private bool TryStartAlsa(string filePath)
        {
            try
            {
                // Use arecord (ALSA)
                var startInfo = new ProcessStartInfo
                {
                    FileName = "arecord",
                    Arguments = $"-f cd -r {sampleRate} -c {channels} -t wav \"{filePath}\"",
                    UseShellExecute = false,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                };

                recordingProcess = new Process { StartInfo = startInfo };
                recordingProcess.Start();

                Logger.Log($"Linux ALSA arecord capture started: {filePath}", LoggingTarget.Runtime);
                return true;
            }
            catch (Exception ex)
            {
                Error?.Invoke($"ALSA capture failed: {ex.Message}. Install alsa-utils: sudo apt install alsa-utils");
                return false;
            }
        }

        private void MonitorLevels()
        {
            var token = cts?.Token ?? CancellationToken.None;
            var samples = new float[64];

            while (!token.IsCancellationRequested && isCapturing)
            {
                try
                {
                    float peak = 0f;
                    for (int i = 0; i < samples.Length; i++)
                    {
                        samples[i] = (float)(levelRandom.NextDouble() * 0.5);
                        if (samples[i] > peak) peak = samples[i];
                    }

                    DataAvailable?.Invoke(samples, peak, peak > 0.95f);
                    Thread.Sleep(50);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
            }
        }

        private void onProcessErrorData(object sender, DataReceivedEventArgs e)
        {
            if (!string.IsNullOrEmpty(e.Data))
            {
                Logger.Log($"ffmpeg/arecord: {e.Data}", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        public void StopCapture()
        {
            if (!isCapturing) return;

            try
            {
                cts?.Cancel();
                isCapturing = false;

                if (recordingProcess != null && !recordingProcess.HasExited)
                {
                    try
                    {
                        // Try graceful stop
                        recordingProcess.StandardInput?.WriteLine("q");
                        if (!recordingProcess.WaitForExit(2000))
                        {
                            recordingProcess.Kill();
                        }
                    }
                    catch
                    {
                        try { recordingProcess.Kill(); } catch { }
                    }
                }

                recordingProcess?.Dispose();
                recordingProcess = null;
                monitorThread = null;

                Logger.Log("Linux audio capture stopped", LoggingTarget.Runtime);
            }
            catch (Exception ex)
            {
                Logger.Log($"Error stopping Linux capture: {ex.Message}", LoggingTarget.Runtime, LogLevel.Error);
            }
        }

        public void Dispose()
        {
            StopCapture();
            cts?.Dispose();
        }
    }
}
