using System;
using System.Collections.Generic;
using NAudio.Wave;
using osu.Framework.Logging;

namespace BeatSight.Game.Audio
{
    /// <summary>
    /// Handles real-time microphone audio capture for drum detection
    /// </summary>
    public class MicrophoneCapture : IDisposable
    {
        private WaveInEvent? waveIn;
        private readonly List<AudioDataReceivedHandler> dataHandlers = new();
        private bool isCapturing;

        public int DeviceIndex { get; private set; } = 0;
        public string CurrentDeviceProductName { get; private set; } = string.Empty;

        public delegate void AudioDataReceivedHandler(float[] audioData, int sampleRate);

        /// <summary>
        /// Sample rate for audio capture (44.1 kHz standard)
        /// </summary>
        public int SampleRate { get; private set; } = 44100;

        /// <summary>
        /// Number of audio channels (mono = 1, stereo = 2)
        /// </summary>
        public int Channels { get; private set; } = 1;

        /// <summary>
        /// Buffer size in milliseconds
        /// </summary>
        public int BufferMilliseconds { get; set; } = 50;

        /// <summary>
        /// Whether microphone capture is currently active
        /// </summary>
        public bool IsCapturing => isCapturing;

        /// <summary>
        /// Subscribe to receive audio data callbacks
        /// </summary>
        public void Subscribe(AudioDataReceivedHandler handler)
        {
            if (!dataHandlers.Contains(handler))
                dataHandlers.Add(handler);
        }

        /// <summary>
        /// Unsubscribe from audio data callbacks
        /// </summary>
        public void Unsubscribe(AudioDataReceivedHandler handler)
        {
            dataHandlers.Remove(handler);
        }

        /// <summary>
        /// Start capturing audio from the default microphone
        /// </summary>
        public void Start(int deviceIndex = 0)
        {
            if (isCapturing)
            {
                Logger.Log("Microphone capture already running", level: LogLevel.Important);
                return;
            }

            try
            {
                DeviceIndex = Math.Clamp(deviceIndex, 0, Math.Max(0, WaveInEvent.DeviceCount - 1));
                CurrentDeviceProductName = GetDeviceProductName(DeviceIndex) ?? string.Empty;

                waveIn = new WaveInEvent
                {
                    DeviceNumber = DeviceIndex,
                    WaveFormat = new WaveFormat(SampleRate, 16, Channels),
                    BufferMilliseconds = BufferMilliseconds
                };

                waveIn.DataAvailable += onDataAvailable;
                waveIn.StartRecording();
                isCapturing = true;

                var deviceLabel = string.IsNullOrEmpty(CurrentDeviceProductName) ? "Unknown" : CurrentDeviceProductName;
                Logger.Log($"Microphone capture started on '{deviceLabel}': {SampleRate}Hz, {Channels} channel(s)", level: LogLevel.Important);
            }
            catch (Exception ex)
            {
                Logger.Log($"Failed to start microphone capture: {ex.Message}", level: LogLevel.Error);
                waveIn?.Dispose();
                waveIn = null;
                CurrentDeviceProductName = string.Empty;
            }
        }

        /// <summary>
        /// Stop capturing audio
        /// </summary>
        public void Stop()
        {
            if (!isCapturing)
                return;

            try
            {
                waveIn?.StopRecording();
                isCapturing = false;
                Logger.Log("Microphone capture stopped", level: LogLevel.Important);
            }
            catch (Exception ex)
            {
                Logger.Log($"Error stopping microphone capture: {ex.Message}", level: LogLevel.Error);
            }
        }

        /// <summary>
        /// Get list of available audio input devices
        /// </summary>
        public static List<string> GetAvailableDevices()
        {
            var devices = new List<string>();

            try
            {
                for (int i = 0; i < WaveInEvent.DeviceCount; i++)
                {
                    var capabilities = WaveInEvent.GetCapabilities(i);
                    devices.Add($"{i}: {capabilities.ProductName}");
                }
            }
            catch (Exception ex)
            {
                Logger.Log($"Error enumerating audio devices: {ex.Message}", level: LogLevel.Error);
            }

            return devices;
        }

        public static string? GetDeviceProductName(int deviceIndex)
        {
            try
            {
                if (deviceIndex < 0 || deviceIndex >= WaveInEvent.DeviceCount)
                    return null;

                var capabilities = WaveInEvent.GetCapabilities(deviceIndex);
                return capabilities.ProductName;
            }
            catch (Exception ex)
            {
                Logger.Log($"Error retrieving device name: {ex.Message}", level: LogLevel.Error);
                return null;
            }
        }

        public static string? GetDefaultDeviceProductName()
        {
            if (WaveInEvent.DeviceCount <= 0)
                return null;

            return GetDeviceProductName(0);
        }

        private void onDataAvailable(object? sender, WaveInEventArgs e)
        {
            if (dataHandlers.Count == 0)
                return;

            // Convert byte array to float array
            int samples = e.BytesRecorded / 2; // 16-bit = 2 bytes per sample
            float[] audioData = new float[samples];

            for (int i = 0; i < samples; i++)
            {
                short sample = BitConverter.ToInt16(e.Buffer, i * 2);
                audioData[i] = sample / 32768f; // Normalize to [-1, 1]
            }

            // Notify all subscribers
            foreach (var handler in dataHandlers)
            {
                try
                {
                    handler(audioData, SampleRate);
                }
                catch (Exception ex)
                {
                    Logger.Log($"Error in audio data handler: {ex.Message}", level: LogLevel.Error);
                }
            }
        }

        public void Dispose()
        {
            Stop();
            waveIn?.Dispose();
            waveIn = null;
            dataHandlers.Clear();
        }
    }
}
