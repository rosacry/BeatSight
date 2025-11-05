using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Audio;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Calibration;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Gameplay
{
    /// <summary>
    /// Live input mode using real-time microphone capture for drum detection
    /// </summary>
    public partial class LiveInputModeScreen : GameplayScreen
    {
        private MicrophoneCapture? microphone;
        private RealtimeOnsetDetector? onsetDetector;
        private LiveInputHudOverlay hud = null!;
        private bool isListening;

        private MicCalibrationManager? calibrationManager;
        private MicCalibrationProfile? calibrationProfile;
        private MicCalibrationOverlay? calibrationOverlay;
        private bool calibrationInProgress;
        private bool calibrationRequired;
        private bool calibrationDeviceMismatch;
        private bool awaitingCalibrationStart;
        private bool awaitingStepTransition;
        private Bindable<bool> calibrationCompletedBindable = null!;
        private Bindable<string> calibrationProfilePathBindable = null!;
        private Bindable<string> calibrationLastUpdatedBindable = null!;
        private Bindable<string> calibrationDeviceIdBindable = null!;
        private int currentCalibrationIndex;
        private int currentHitCount;
        private double ambientEnergySum;
        private int ambientEnergySampleCount;
        private double ambientDuration;
        private CalibrationStep[] calibrationSteps = Array.Empty<CalibrationStep>();
        private readonly Dictionary<DrumType, List<float[]>> calibrationSpectra = new();
        private readonly Dictionary<DrumType, List<float>> calibrationEnergies = new();

        private const int meter_count = LiveInputHudOverlay.LaneCount;
        private float[] meterLevels = new float[meter_count];
        private double[] lastHitTimes = new double[meter_count];
        private readonly float detectorThreshold = 0.25f;

        public LiveInputModeScreen(string? beatmapPath = null) : base(beatmapPath)
        {
        }

        [BackgroundDependencyLoader]
        private void load(GameHost host, BeatSightConfigManager configManager)
        {
            microphone = new MicrophoneCapture
            {
                BufferMilliseconds = 30
            };

            onsetDetector = new RealtimeOnsetDetector(threshold: 0.25f, historySize: 8)
            {
                MinTimeBetweenOnsets = 40
            };

            onsetDetector.OnsetDetected += onOnsetDetected;
            microphone.Subscribe(onAudioDataReceived);

            calibrationManager = new MicCalibrationManager(host.Storage);
            calibrationCompletedBindable = configManager.GetBindable<bool>(BeatSightSetting.MicCalibrationCompleted);
            calibrationProfilePathBindable = configManager.GetBindable<string>(BeatSightSetting.MicCalibrationProfilePath);
            calibrationLastUpdatedBindable = configManager.GetBindable<string>(BeatSightSetting.MicCalibrationLastUpdated);
            calibrationDeviceIdBindable = configManager.GetBindable<string>(BeatSightSetting.MicCalibrationDeviceId);

            calibrationProfile = calibrationManager.Load();
            if (calibrationProfile != null)
            {
                onsetDetector.CalibrationProfile = calibrationProfile;
                calibrationProfilePathBindable.Value = calibrationManager.GetProfilePath();

                if (!calibrationCompletedBindable.Value)
                    calibrationCompletedBindable.Value = true;
            }
            else
            {
                calibrationCompletedBindable.Value = false;
                calibrationProfilePathBindable.Value = string.Empty;
            }

            calibrationSteps = new[]
            {
                CalibrationStep.CreateAmbient("Ambient Noise", "Stay quiet for 3 seconds so we can measure your room noise floor.", 3.0),
                CalibrationStep.CreateHit(DrumType.Kick, "Kick Drum", "Play your kick drum 6 times with your usual playing force.", 6),
                CalibrationStep.CreateHit(DrumType.Snare, "Snare Drum", "Strike the snare 6 times in the center with consistent velocity.", 6),
                CalibrationStep.CreateHit(DrumType.HiHat, "Hi-Hat", "Close the hats and tap them 6 times with a stick or pedal.", 6),
                CalibrationStep.CreateHit(DrumType.Tom, "Toms", "Play your mid tom 6 times. Use a representative tom if you have multiple.", 6),
                CalibrationStep.CreateHit(DrumType.Cymbal, "Cymbal", "Strike your main crash or ride 6 times with a steady force.", 6)
            };

            calibrationRequired = calibrationProfile == null || !calibrationCompletedBindable.Value;
            calibrationDeviceMismatch = false;
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            AddInternal(hud = new LiveInputHudOverlay());
            hud.RecalibrateRequested += () => showCalibrationIntro(true);
            initialiseLaneLabels();

            AddInternal(calibrationOverlay = new MicCalibrationOverlay());
            calibrationOverlay.Hide();

            if (calibrationRequired)
            {
                awaitingCalibrationStart = true;
                calibrationOverlay.ShowIntro(false, () => beginCalibrationWorkflow(false), null);
                calibrationOverlay.Show();
                hud.SetRecalibrateEnabled(false);
                setStatus("⚠️ Calibration required before scoring.", new Color4(255, 210, 120, 255), LiveInputHudOverlay.StatusState.Warning);
            }
            else
            {
                startListening();
                calibrationOverlay.Hide();
            }

            updateCalibrationSummary();
            refreshDeviceStatus();
        }

        private void initialiseLaneLabels()
        {
            hud?.SetLaneDefaultLabel(0, "S");
            hud?.SetLaneDefaultLabel(1, "D");
            hud?.SetLaneDefaultLabel(2, "F");
            hud?.SetLaneDefaultLabel(3, "Space");
            hud?.SetLaneDefaultLabel(4, "J");
            hud?.SetLaneDefaultLabel(5, "K");
            hud?.SetLaneDefaultLabel(6, "L");
        }

        private void setStatus(string text, Color4 colour, LiveInputHudOverlay.StatusState state)
        {
            hud?.SetStatus(text, colour, state);
        }

        private void updateIdleStatus()
        {
            if (hud == null)
                return;

            if (calibrationDeviceMismatch)
            {
                setStatus("⚠️ Microphone changed — recalibrate for accurate scoring.", new Color4(255, 210, 120, 255), LiveInputHudOverlay.StatusState.Warning);
                return;
            }

            if (calibrationInProgress)
            {
                setStatus("Calibrating microphone…", new Color4(255, 210, 120, 255), LiveInputHudOverlay.StatusState.Calibrating);
                return;
            }

            if (calibrationRequired)
            {
                setStatus("⚠️ Calibration required before scoring.", new Color4(255, 210, 120, 255), LiveInputHudOverlay.StatusState.Warning);
                return;
            }

            if (isListening)
                setStatus("🟢 Listening... Play your drums!", new Color4(120, 255, 120, 255), LiveInputHudOverlay.StatusState.Listening);
            else
                setStatus("⏸ Paused", new Color4(200, 200, 200, 255), LiveInputHudOverlay.StatusState.Paused);
        }

        private void updateCalibrationSummary()
        {
            if (hud == null)
                return;

            if (calibrationDeviceMismatch)
            {
                hud.SetCalibrationSummary("Calibration mismatch: new microphone detected", LiveInputHudOverlay.CalibrationState.Warning);
            }
            else if (calibrationRequired)
            {
                hud.SetCalibrationSummary("Calibration required", LiveInputHudOverlay.CalibrationState.Required);
            }
            else if (calibrationProfile != null)
            {
                hud.SetCalibrationSummary($"Calibrated {calibrationProfile.CompletedAt.ToLocalTime():MMM d, h:mm tt}", LiveInputHudOverlay.CalibrationState.Completed);
            }
            else
            {
                hud.SetCalibrationSummary("Calibration pending", LiveInputHudOverlay.CalibrationState.Unknown);
            }

            hud.SetAmbientNoise(calibrationProfile?.AmbientNoiseFloor);
        }

        private Color4 getHighlightColour(DrumType type) => type switch
        {
            DrumType.Kick => new Color4(255, 180, 120, 255),
            DrumType.Snare => new Color4(120, 200, 255, 255),
            DrumType.HiHat => new Color4(255, 230, 120, 255),
            DrumType.Cymbal => new Color4(140, 220, 200, 255),
            DrumType.Tom => new Color4(200, 160, 255, 255),
            _ => new Color4(200, 205, 220, 255)
        };

        private string formatDrumLabel(DrumType type) => type switch
        {
            DrumType.HiHat => "Hi-Hat",
            DrumType.Unknown => "Unknown",
            _ => type.ToString()
        };

        private float computeConfidence(OnsetEvent onset)
        {
            float ambient = (float)(calibrationProfile?.AmbientNoiseFloor ?? 0);
            float reference = getReferenceEnergy(onset.EstimatedType);
            float energyComponent = reference > 0 ? (onset.Energy - ambient) / reference : onset.Energy * 4f;
            energyComponent = Math.Clamp(energyComponent, 0f, 1.5f);

            float fluxComponent = Math.Clamp((onset.SpectralFlux - detectorThreshold) / (detectorThreshold + 1e-4f), 0f, 1.5f);

            float combined = (energyComponent * 0.6f) + (fluxComponent * 0.4f);
            return Math.Clamp(combined, 0f, 1f);
        }

        private float getReferenceEnergy(DrumType type)
        {
            if (calibrationProfile != null && type != DrumType.Unknown &&
                calibrationProfile.DrumSignatures.TryGetValue(type, out var signature) &&
                signature.AverageEnergy > 0)
            {
                return signature.AverageEnergy;
            }

            if (calibrationProfile != null && calibrationProfile.DrumSignatures.Count > 0)
            {
                var energies = calibrationProfile.DrumSignatures.Values
                    .Select(s => s.AverageEnergy)
                    .Where(v => v > 0)
                    .ToArray();

                if (energies.Length > 0)
                    return (float)energies.Average();
            }

            return 0.08f;
        }

        private double computeLatencyMs(OnsetEvent onset)
        {
            double now = getCurrentTime();
            double latency = now - onset.Time;
            if (latency < 0)
                latency = 0;
            return latency;
        }

        private void showCalibrationIntro(bool isRecalibration)
        {
            if (calibrationInProgress)
                return;

            if (calibrationOverlay == null)
                return;

            awaitingCalibrationStart = true;
            calibrationOverlay.ShowIntro(isRecalibration, () => beginCalibrationWorkflow(isRecalibration), isRecalibration ? cancelRecalibrationPrompt : null);
            calibrationOverlay.Show();
        }

        private void cancelRecalibrationPrompt()
        {
            awaitingCalibrationStart = false;
            calibrationOverlay?.Hide();

            hud?.SetRecalibrateEnabled(true);

            if (!calibrationInProgress)
            {
                updateCalibrationSummary();
                updateIdleStatus();
            }
        }

        private void beginCalibrationWorkflow(bool isRecalibration)
        {
            if (calibrationSteps.Length == 0 || onsetDetector == null)
                return;

            if (calibrationOverlay == null)
                return;

            calibrationInProgress = true;
            awaitingCalibrationStart = false;
            awaitingStepTransition = false;
            currentCalibrationIndex = 0;
            calibrationDeviceMismatch = false;
            currentHitCount = 0;
            ambientEnergySum = 0;
            ambientEnergySampleCount = 0;
            ambientDuration = 0;
            calibrationSpectra.Clear();
            calibrationEnergies.Clear();

            onsetDetector.Reset();
            onsetDetector.CalibrationProfile = null;

            calibrationCompletedBindable.Value = false;

            calibrationProfile = null;
            calibrationProfilePathBindable.Value = string.Empty;
            calibrationLastUpdatedBindable.Value = string.Empty;
            calibrationDeviceIdBindable.Value = string.Empty;
            calibrationRequired = true;

            setStatus("Calibrating microphone…", new Color4(255, 210, 120, 255), LiveInputHudOverlay.StatusState.Calibrating);
            hud?.SetRecalibrateEnabled(false);
            updateCalibrationSummary();

            prepareCurrentStep();

            if (!isListening)
                startListening();
        }

        private void refreshDeviceStatus()
        {
            string? deviceName = microphone?.CurrentDeviceProductName;

            if (string.IsNullOrWhiteSpace(deviceName))
            {
                int deviceIndex = microphone?.DeviceIndex ?? 0;
                deviceName = MicrophoneCapture.GetDeviceProductName(deviceIndex)
                             ?? MicrophoneCapture.GetDefaultDeviceProductName()
                             ?? "Unknown Microphone";
            }

            hud?.SetDeviceName(deviceName);
            checkForDeviceDrift(deviceName);
        }

        private void checkForDeviceDrift(string deviceName)
        {
            bool mismatch = calibrationCompletedBindable.Value
                            && !string.IsNullOrWhiteSpace(calibrationDeviceIdBindable.Value)
                            && !string.Equals(calibrationDeviceIdBindable.Value, deviceName, StringComparison.OrdinalIgnoreCase);

            calibrationDeviceMismatch = mismatch;

            if (!mismatch)
            {
                updateCalibrationSummary();
                updateIdleStatus();
                return;
            }

            calibrationRequired = true;
            setStatus("⚠️ Microphone changed — recalibrate for accurate scoring.", new Color4(255, 210, 120, 255), LiveInputHudOverlay.StatusState.Warning);
            hud?.SetCalibrationSummary("Microphone changed — recalibration required", LiveInputHudOverlay.CalibrationState.Warning);

            if (isListening)
            {
                microphone?.Stop();
                isListening = false;
            }

            updateIdleStatus();

            if (!calibrationInProgress)
            {
                hud?.SetRecalibrateEnabled(true);

                if (calibrationOverlay != null && !awaitingCalibrationStart)
                {
                    awaitingCalibrationStart = true;
                    calibrationOverlay.ShowIntro(true, () => beginCalibrationWorkflow(true), cancelRecalibrationPrompt);
                    calibrationOverlay.Show();
                }
            }
        }

        private void prepareCurrentStep()
        {
            awaitingStepTransition = false;
            currentHitCount = 0;

            if (calibrationOverlay == null)
                return;

            var step = calibrationSteps[currentCalibrationIndex];

            if (step.IsAmbient)
            {
                ambientEnergySum = 0;
                ambientEnergySampleCount = 0;
                ambientDuration = 0;
            }

            calibrationOverlay.ShowCalibrationStep(step, currentCalibrationIndex + 1, calibrationSteps.Length);

            if (step.IsAmbient)
                calibrationOverlay.UpdateAmbientProgress(0, step.DurationSeconds);
            else
                calibrationOverlay.UpdateHitProgress(0, step.RequiredHits);
        }

        private void handleAmbientSample(float[] audioData, int sampleRate)
        {
            if (!calibrationInProgress || calibrationSteps.Length == 0)
                return;

            var step = calibrationSteps[currentCalibrationIndex];
            if (!step.IsAmbient)
                return;

            if (awaitingStepTransition)
                return;

            float energy = 0;
            for (int i = 0; i < audioData.Length; i++)
                energy += audioData[i] * audioData[i];

            energy = (float)Math.Sqrt(energy / Math.Max(1, audioData.Length));

            ambientEnergySum += energy;
            ambientEnergySampleCount++;
            ambientDuration += audioData.Length / (double)sampleRate;

            var overlay = calibrationOverlay;
            if (overlay != null)
            {
                double captured = ambientDuration;
                double target = step.DurationSeconds;
                Schedule(() => overlay.UpdateAmbientProgress(captured, target));
            }

            if (ambientDuration >= step.DurationSeconds && !awaitingStepTransition)
            {
                awaitingStepTransition = true;
                Schedule(advanceCalibrationStep);
            }
        }

        private void handleCalibrationOnset(OnsetEvent onset)
        {
            if (!calibrationInProgress || calibrationSteps.Length == 0)
                return;

            var step = calibrationSteps[currentCalibrationIndex];
            if (!step.DrumTarget.HasValue)
                return;

            if (awaitingStepTransition)
                return;

            var target = step.DrumTarget.Value;

            if (!calibrationSpectra.TryGetValue(target, out var spectraList))
            {
                spectraList = new List<float[]>();
                calibrationSpectra[target] = spectraList;
            }

            if (!calibrationEnergies.TryGetValue(target, out var energyList))
            {
                energyList = new List<float>();
                calibrationEnergies[target] = energyList;
            }

            spectraList.Add((float[])onset.Spectrum.Clone());
            energyList.Add(onset.Energy);

            currentHitCount = Math.Min(step.RequiredHits, currentHitCount + 1);

            var overlay = calibrationOverlay;
            if (overlay != null)
                Schedule(() => overlay.UpdateHitProgress(currentHitCount, step.RequiredHits));

            int lane = mapDrumTypeToLane(target);
            if (lane >= 0 && lane < meter_count)
            {
                double currentTime = getCurrentTime();
                lastHitTimes[lane] = currentTime;

                Schedule(() =>
                {
                    hud?.FlashLane(lane, formatDrumLabel(target), getHighlightColour(target));
                });
            }

            if (currentHitCount >= step.RequiredHits && !awaitingStepTransition)
            {
                awaitingStepTransition = true;
                Schedule(advanceCalibrationStep);
            }
        }

        private void advanceCalibrationStep()
        {
            if (!calibrationInProgress)
                return;

            if (currentCalibrationIndex + 1 >= calibrationSteps.Length)
            {
                finalizeCalibration();
                return;
            }

            currentCalibrationIndex++;
            prepareCurrentStep();
        }

        private void finalizeCalibration()
        {
            calibrationInProgress = false;
            awaitingStepTransition = false;
            awaitingCalibrationStart = false;

            var profile = new MicCalibrationProfile
            {
                CompletedAt = DateTime.UtcNow,
                AmbientNoiseFloor = ambientEnergySampleCount > 0 ? ambientEnergySum / Math.Max(1, ambientEnergySampleCount) : 0
            };

            foreach (var kvp in calibrationSpectra)
            {
                var drumType = kvp.Key;
                var spectraList = kvp.Value;
                if (spectraList.Count == 0)
                    continue;

                int length = spectraList[0].Length;
                float[] averageSpectrum = new float[length];

                foreach (var spectrum in spectraList)
                {
                    for (int i = 0; i < length; i++)
                        averageSpectrum[i] += spectrum[i];
                }

                for (int i = 0; i < length; i++)
                    averageSpectrum[i] /= spectraList.Count;

                if (!calibrationEnergies.TryGetValue(drumType, out var energyList) || energyList.Count == 0)
                    continue;

                float peakEnergy = energyList.Max();
                float averageEnergy = (float)energyList.Average();

                profile.DrumSignatures[drumType] = new MicCalibrationProfile.DrumSignature
                {
                    AverageSpectrum = averageSpectrum,
                    AverageEnergy = averageEnergy,
                    PeakEnergy = peakEnergy,
                    SampleCount = spectraList.Count
                };
            }

            calibrationProfile = profile;
            if (onsetDetector != null)
                onsetDetector.CalibrationProfile = profile;

            var capturedDevice = microphone?.CurrentDeviceProductName
                                 ?? MicrophoneCapture.GetDeviceProductName(microphone?.DeviceIndex ?? 0)
                                 ?? MicrophoneCapture.GetDefaultDeviceProductName()
                                 ?? string.Empty;
            calibrationDeviceIdBindable.Value = capturedDevice;
            calibrationDeviceMismatch = false;
            if (!string.IsNullOrWhiteSpace(capturedDevice))
                hud?.SetDeviceName(capturedDevice);

            int expectedSignatures = calibrationSteps.Count(s => s.DrumTarget.HasValue);
            if (profile.DrumSignatures.Count < expectedSignatures)
            {
                calibrationRequired = true;
                setStatus("Calibration incomplete — need more hits.", new Color4(255, 150, 120, 255), LiveInputHudOverlay.StatusState.Warning);
                hud?.SetCalibrationSummary("Calibration incomplete", LiveInputHudOverlay.CalibrationState.Warning);
                hud?.SetRecalibrateEnabled(true);
                calibrationOverlay?.ShowError("Not every drum was captured. Let's run calibration again.", () => beginCalibrationWorkflow(true));
                return;
            }

            calibrationManager?.Save(profile);

            calibrationCompletedBindable.Value = true;
            calibrationLastUpdatedBindable.Value = profile.CompletedAt.ToString("O");
            calibrationProfilePathBindable.Value = calibrationManager?.GetProfilePath() ?? string.Empty;

            calibrationRequired = false;

            hud?.SetRecalibrateEnabled(true);
            updateCalibrationSummary();

            if (!isListening)
                startListening();

            setStatus("🟢 Calibration complete!", new Color4(120, 255, 120, 255), LiveInputHudOverlay.StatusState.Listening);

            calibrationOverlay?.ShowCompletion(() =>
            {
                calibrationOverlay.Hide();
                updateIdleStatus();
            }, profile);
        }

        private void startListening()
        {
            try
            {
                if (microphone == null)
                    return;

                if (!microphone.IsCapturing)
                    microphone.Start();

                isListening = true;
                refreshDeviceStatus();
                updateIdleStatus();
            }
            catch (Exception ex)
            {
                setStatus($"❌ Error: {ex.Message}", new Color4(255, 100, 100, 255), LiveInputHudOverlay.StatusState.Error);
            }
        }

        private void stopListening()
        {
            microphone?.Stop();
            isListening = false;
            updateIdleStatus();
            hud?.ResetLastOnset();
        }

        private void onAudioDataReceived(float[] audioData, int sampleRate)
        {
            if (!isListening || onsetDetector == null)
                return;

            if (calibrationInProgress)
                handleAmbientSample(audioData, sampleRate);

            if (!awaitingCalibrationStart)
            {
                double currentTime = getCurrentTime();
                onsetDetector.ProcessBuffer(audioData, sampleRate, currentTime);
            }

            Schedule(() => updateLevelMeters(audioData));
        }

        private void updateLevelMeters(float[] audioData)
        {
            // Calculate RMS energy for visualization
            float energy = 0;
            for (int i = 0; i < audioData.Length; i++)
            {
                energy += audioData[i] * audioData[i];
            }
            energy = (float)Math.Sqrt(energy / audioData.Length);

            // Distribute energy across meters
            for (int i = 0; i < meter_count; i++)
            {
                // Decay existing level
                meterLevels[i] *= 0.9f;

                // Add new energy
                if (energy > meterLevels[i])
                    meterLevels[i] = Math.Min(1f, energy * 8f);

                hud?.SetMeterLevel(i, meterLevels[i]);
            }
        }

        private void onOnsetDetected(OnsetEvent onset)
        {
            if (calibrationInProgress)
            {
                handleCalibrationOnset(onset);
                return;
            }

            // Map detected onset to lane based on drum type
            int lane = mapDrumTypeToLane(onset.EstimatedType);

            if (lane >= 0 && lane < meter_count)
            {
                double currentTime = getCurrentTime();

                // Avoid duplicate hits
                if (currentTime - lastHitTimes[lane] < 50)
                    return;

                lastHitTimes[lane] = currentTime;

                float confidence = computeConfidence(onset);
                double latency = computeLatencyMs(onset);

                // Flash the corresponding meter and update last-hit info
                Schedule(() =>
                {
                    hud?.FlashLane(lane, formatDrumLabel(onset.EstimatedType), getHighlightColour(onset.EstimatedType));
                    hud?.SetLastOnset(onset.EstimatedType, onset.Energy, confidence, latency);
                });

                // Simulate key press for the lane
                // This will trigger the existing hit detection in GameplayPlayfield
                simulateLaneHit(lane);
            }
        }

        private static int mapDrumTypeToLane(DrumType type) => DrumLaneHeuristics.ResolveLane(type);

        private void simulateLaneHit(int lane)
        {
            // Register hit with the playfield
            Schedule(() =>
            {
                if (playfield != null)
                {
                    double currentTime = getCurrentTime();
                    var result = playfield.HandleInput(lane, currentTime);

                    // Visual feedback based on result
                    if (result != GameplayPlayfield.HitResult.None)
                    {
                        System.Diagnostics.Debug.WriteLine($"Detected hit on lane {lane}: {result}");
                    }
                }
            });
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == osuTK.Input.Key.M && !e.Repeat)
            {
                // Toggle listening
                if (isListening)
                    stopListening();
                else
                    startListening();

                return true;
            }

            if (e.Key == osuTK.Input.Key.C && !e.Repeat)
            {
                showCalibrationIntro(true);
                return true;
            }

            // Still allow manual key presses for testing
            return base.OnKeyDown(e);
        }

        public override void OnSuspending(ScreenTransitionEvent e)
        {
            base.OnSuspending(e);
            stopListening();
        }

        public override bool OnExiting(ScreenExitEvent e)
        {
            stopListening();
            return base.OnExiting(e);
        }

        protected override void Dispose(bool isDisposing)
        {
            base.Dispose(isDisposing);

            if (onsetDetector != null)
                onsetDetector.OnsetDetected -= onOnsetDetected;

            microphone?.Dispose();
            onsetDetector = null;
        }

        private partial class MicCalibrationOverlay : CompositeDrawable
        {
            private readonly SpriteText titleText;
            private readonly SpriteText instructionText;
            private readonly SpriteText progressText;
            private readonly SpriteText statusText;
            private readonly BasicButton primaryButton;
            private readonly BasicButton secondaryButton;

            private Action? primaryAction;
            private Action? secondaryAction;

            public MicCalibrationOverlay()
            {
                RelativeSizeAxes = Axes.Both;
                Alpha = 0;
                AlwaysPresent = true;

                InternalChildren = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(10, 12, 20, 200)
                    },
                    new Container
                    {
                        Width = 520,
                        AutoSizeAxes = Axes.Y,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Masking = true,
                        CornerRadius = 14,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = new Color4(32, 38, 58, 235)
                            },
                            new FillFlowContainer
                            {
                                RelativeSizeAxes = Axes.X,
                                AutoSizeAxes = Axes.Y,
                                Direction = FillDirection.Vertical,
                                Padding = new MarginPadding(24),
                                Spacing = new Vector2(0, 12),
                                Children = new Drawable[]
                                {
                                    titleText = new SpriteText
                                    {
                                        Font = new FontUsage(size: 26, weight: "Bold"),
                                        Colour = Color4.White,
                                        Text = "Microphone Calibration"
                                    },
                                    instructionText = new SpriteText
                                    {
                                        Font = new FontUsage(size: 18),
                                        Colour = new Color4(210, 215, 230, 255),
                                        Text = string.Empty
                                    },
                                    progressText = new SpriteText
                                    {
                                        Font = new FontUsage(size: 16),
                                        Colour = new Color4(180, 185, 200, 255),
                                        Text = string.Empty
                                    },
                                    statusText = new SpriteText
                                    {
                                        Font = new FontUsage(size: 16),
                                        Colour = new Color4(255, 210, 130, 255),
                                        Text = string.Empty
                                    },
                                    new FillFlowContainer
                                    {
                                        RelativeSizeAxes = Axes.X,
                                        AutoSizeAxes = Axes.Y,
                                        Direction = FillDirection.Horizontal,
                                        Spacing = new Vector2(12, 0),
                                        Children = new Drawable[]
                                        {
                                            primaryButton = new BasicButton
                                            {
                                                Text = "Start Calibration",
                                                Width = 220,
                                                Height = 36
                                            },
                                            secondaryButton = new BasicButton
                                            {
                                                Text = "Back",
                                                Width = 160,
                                                Height = 36
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                };

                primaryButton.Action = () => primaryAction?.Invoke();
                secondaryButton.Action = () => secondaryAction?.Invoke();
                configureSecondaryButton(null, null);
            }

            public void ShowIntro(bool isRecalibration, Action startAction, Action? cancelAction)
            {
                this.FadeIn(200);
                titleText.Text = isRecalibration ? "Recalibrate Your Drum Kit" : "Microphone Calibration";
                instructionText.Text = "We need to learn how your kit sounds so we can score accurately. Use headphones or lower your speakers to prevent bleed.";
                progressText.Text = "We'll capture ambient noise and each major drum piece.";
                statusText.Text = "Click Start when you're ready.";
                statusText.Colour = new Color4(120, 220, 255, 255);

                configurePrimaryButton("Start Calibration", startAction);
                configureSecondaryButton(isRecalibration ? "Cancel" : null, cancelAction);
            }

            public void ShowCalibrationStep(CalibrationStep step, int index, int total)
            {
                this.FadeIn(100);
                titleText.Text = $"Step {index}/{total}: {step.Title}";
                instructionText.Text = step.Instruction;
                statusText.Text = step.IsAmbient ? "Stay quiet so we can measure the room." : "Play the requested hits at a comfortable volume.";
                statusText.Colour = new Color4(255, 210, 120, 255);

                progressText.Text = step.IsAmbient
                    ? $"Quiet listening: 0.0s / {step.DurationSeconds:0.0}s"
                    : $"Hits captured: 0/{step.RequiredHits}";

                configurePrimaryButton(step.IsAmbient ? "Listening…" : "Capturing…", null);
                configureSecondaryButton(null, null);
            }

            public void UpdateHitProgress(int hits, int required)
            {
                progressText.Text = $"Hits captured: {hits}/{required}";
                if (hits >= required)
                {
                    statusText.Text = "Great! Hold steady while we store that.";
                    statusText.Colour = new Color4(120, 255, 120, 255);
                }
                else
                {
                    statusText.Text = "Keep hitting the requested drum.";
                    statusText.Colour = new Color4(255, 210, 120, 255);
                }
            }

            public void UpdateAmbientProgress(double capturedSeconds, double targetSeconds)
            {
                double clamped = Math.Min(capturedSeconds, targetSeconds);
                progressText.Text = $"Quiet listening: {clamped:0.0}s / {targetSeconds:0.0}s";

                if (clamped >= targetSeconds)
                {
                    statusText.Text = "Got it! Preparing the next step.";
                    statusText.Colour = new Color4(120, 255, 120, 255);
                }
                else
                {
                    statusText.Text = "Hold still while we listen.";
                    statusText.Colour = new Color4(255, 210, 120, 255);
                }
            }

            public void ShowCompletion(Action finishAction, MicCalibrationProfile profile)
            {
                this.FadeIn(150);
                titleText.Text = "Calibration Complete 🎉";
                instructionText.Text = "Your kit signature is saved. You can recalibrate any time from Live Input.";

                if (profile.DrumSignatures.Keys.Any())
                    progressText.Text = "Captured: " + string.Join(", ", profile.DrumSignatures.Keys.Select(formatDrumType));
                else
                    progressText.Text = "Captured: (none)";

                statusText.Text = $"Ambient noise floor: {profile.AmbientNoiseFloor:0.000}";
                statusText.Colour = new Color4(120, 255, 120, 255);

                configurePrimaryButton("Finish", finishAction);
                configureSecondaryButton(null, null);
            }

            public void ShowError(string message, Action? retryAction)
            {
                titleText.Text = "Calibration Error";
                instructionText.Text = "We couldn't save the calibration.";
                progressText.Text = message;
                statusText.Text = "Try again or come back later.";
                statusText.Colour = new Color4(255, 120, 120, 255);

                configurePrimaryButton(retryAction != null ? "Retry" : "Close", retryAction ?? (() => this.Hide()));
                configureSecondaryButton(null, null);
            }

            private void configurePrimaryButton(string text, Action? action)
            {
                primaryButton.Text = text;
                primaryAction = action;
                bool enabled = action != null;
                primaryButton.Enabled.Value = enabled;
                primaryButton.Alpha = enabled ? 1f : 0.35f;
            }

            private void configureSecondaryButton(string? text, Action? action)
            {
                if (string.IsNullOrEmpty(text) || action == null)
                {
                    secondaryAction = null;
                    secondaryButton.Text = "Cancel";
                    secondaryButton.Enabled.Value = false;
                    secondaryButton.Alpha = 0.25f;
                }
                else
                {
                    secondaryAction = action;
                    secondaryButton.Text = text;
                    secondaryButton.Enabled.Value = true;
                    secondaryButton.Alpha = 1f;
                }
            }

            private static string formatDrumType(DrumType type) => type switch
            {
                DrumType.HiHat => "Hi-Hat",
                DrumType.Tom => "Tom",
                _ => type.ToString()
            };
        }

        private readonly struct CalibrationStep
        {
            public string Title { get; }
            public string Instruction { get; }
            public DrumType? DrumTarget { get; }
            public int RequiredHits { get; }
            public double DurationSeconds { get; }
            public bool IsAmbient => DrumTarget == null && DurationSeconds > 0;

            private CalibrationStep(string title, string instruction, DrumType? drumTarget, int requiredHits, double durationSeconds)
            {
                Title = title;
                Instruction = instruction;
                DrumTarget = drumTarget;
                RequiredHits = requiredHits;
                DurationSeconds = durationSeconds;
            }

            public static CalibrationStep CreateAmbient(string title, string instruction, double durationSeconds) =>
                new CalibrationStep(title, instruction, null, 0, durationSeconds);

            public static CalibrationStep CreateHit(DrumType drumTarget, string title, string instruction, int requiredHits) =>
                new CalibrationStep(title, instruction, drumTarget, requiredHits, 0);
        }
    }
}
