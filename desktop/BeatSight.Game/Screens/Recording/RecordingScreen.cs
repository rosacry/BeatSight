using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using BeatSight.Game.Configuration;
using BeatSight.Game.Screens.Editor;
using BeatSight.Game.Services.Recording;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Logging;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Recording
{
    /// <summary>
    /// Live audio recording screen for capturing drum performances.
    /// Features real-time waveform visualization, metronome, and quality settings.
    /// </summary>
    public partial class RecordingScreen : BeatSightScreen
    {
        private GameHost host = null!;
        private AudioRecordingService? recordingService;

        // UI Elements
        private WaveformVisualizer waveformVisualizer = null!;
        private RecordButton recordButton = null!;
        private SpriteText statusText = null!;
        private SpriteText timerText = null!;
        private SpriteText levelText = null!;
        private Box levelBar = null!;
        private Box clipIndicator = null!;
        private Container levelMeterContainer = null!;

        // Metronome UI
        private SpriteText bpmText = null!;
        private BeatIndicator beatIndicator = null!;
        private RecordingActionButton metronomeToggle = null!;
        private RecordingActionButton tapTempoButton = null!;

        // Quality settings
        private RecordingActionButton qualityStandard = null!;
        private RecordingActionButton qualityHigh = null!;
        private RecordingActionButton qualityStudio = null!;

        // State
        private RecordingState state = RecordingState.Idle;
        private readonly BindableDouble bpm = new BindableDouble(120) { MinValue = 40, MaxValue = 240 };
        private readonly BindableBool metronomeEnabled = new BindableBool(false);
        private AudioQuality selectedQuality = AudioQuality.High;

        // Tap tempo
        private readonly List<double> tapTimes = new();

        // Countdown
        private int countdownValue;
        private bool isCountingDown;

        // Recording output
        private string? lastRecordingPath;

        [BackgroundDependencyLoader]
        private void load(GameHost host, BeatSightConfigManager config)
        {
            this.host = host;

            // Initialize recording service
            recordingService = new AudioRecordingService();
            recordingService.LevelChanged += onLevelChanged;
            recordingService.RecordingCompleted += onRecordingCompleted;
            recordingService.Error += onRecordingError;

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Background,
                },
                new ScreenEdgeContainer(scrollable: false)
                {
                    Content = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Children = new Drawable[]
                        {
                            // Header
                            new Container
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 80,
                                Children = new Drawable[]
                                {
                                    new Box
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Colour = UITheme.Surface,
                                    },
                                    new BackButton
                                    {
                                        Anchor = Anchor.CentreLeft,
                                        Origin = Anchor.CentreLeft,
                                        X = 20,
                                        Action = this.Exit,
                                    },
                                    new SpriteText
                                    {
                                        Text = "Live Recording",
                                        Font = BeatSightFont.Title(32),
                                        Colour = UITheme.TextPrimary,
                                        Anchor = Anchor.Centre,
                                        Origin = Anchor.Centre,
                                    },
                                    statusText = new SpriteText
                                    {
                                        Text = "Ready to record",
                                        Font = BeatSightFont.Body(16),
                                        Colour = UITheme.TextSecondary,
                                        Anchor = Anchor.Centre,
                                        Origin = Anchor.Centre,
                                        Y = 25,
                                    },
                                }
                            },

                            // Main content area
                            new Container
                            {
                                RelativeSizeAxes = Axes.Both,
                                Padding = new MarginPadding { Top = 80, Bottom = 200 },
                                Child = new FillFlowContainer
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Direction = FillDirection.Vertical,
                                    Spacing = new Vector2(0, 20),
                                    Padding = new MarginPadding(30),
                                    Children = new Drawable[]
                                    {
                                        // Waveform visualizer
                                        new Container
                                        {
                                            RelativeSizeAxes = Axes.X,
                                            Height = 150,
                                            Masking = true,
                                            CornerRadius = 12,
                                            Children = new Drawable[]
                                            {
                                                new Box
                                                {
                                                    RelativeSizeAxes = Axes.Both,
                                                    Colour = UITheme.BackgroundLayer,
                                                },
                                                waveformVisualizer = new WaveformVisualizer
                                                {
                                                    RelativeSizeAxes = Axes.Both,
                                                    Padding = new MarginPadding(10),
                                                },
                                            }
                                        },

                                        // Level meter and timer row
                                        new Container
                                        {
                                            RelativeSizeAxes = Axes.X,
                                            Height = 60,
                                            Children = new Drawable[]
                                            {
                                                // Level meter
                                                levelMeterContainer = new Container
                                                {
                                                    Width = 300,
                                                    RelativeSizeAxes = Axes.Y,
                                                    Anchor = Anchor.CentreLeft,
                                                    Origin = Anchor.CentreLeft,
                                                    Masking = true,
                                                    CornerRadius = 8,
                                                    Children = new Drawable[]
                                                    {
                                                        new Box
                                                        {
                                                            RelativeSizeAxes = Axes.Both,
                                                            Colour = UITheme.SurfaceAlt,
                                                        },
                                                        levelBar = new Box
                                                        {
                                                            RelativeSizeAxes = Axes.Y,
                                                            Width = 0,
                                                            Colour = UITheme.AccentSecondary,
                                                            Anchor = Anchor.CentreLeft,
                                                            Origin = Anchor.CentreLeft,
                                                            Margin = new MarginPadding(4),
                                                        },
                                                        new Container
                                                        {
                                                            Size = new Vector2(20),
                                                            Anchor = Anchor.CentreRight,
                                                            Origin = Anchor.CentreRight,
                                                            Margin = new MarginPadding(4),
                                                            Masking = true,
                                                            CornerRadius = 10,
                                                            Child = clipIndicator = new Box
                                                            {
                                                                RelativeSizeAxes = Axes.Both,
                                                                Colour = UITheme.AccentWarning,
                                                                Alpha = 0,
                                                            }
                                                        },
                                                        levelText = new SpriteText
                                                        {
                                                            Text = "-∞ dB",
                                                            Font = BeatSightFont.Body(12),
                                                            Colour = UITheme.TextSecondary,
                                                            Anchor = Anchor.CentreLeft,
                                                            Origin = Anchor.CentreLeft,
                                                            X = 10,
                                                        },
                                                    }
                                                },

                                                // Timer
                                                timerText = new SpriteText
                                                {
                                                    Text = "00:00.0",
                                                    Font = BeatSightFont.Title(48),
                                                    Colour = UITheme.TextPrimary,
                                                    Anchor = Anchor.Centre,
                                                    Origin = Anchor.Centre,
                                                },
                                            }
                                        },

                                        // Metronome controls
                                        new Container
                                        {
                                            RelativeSizeAxes = Axes.X,
                                            Height = 100,
                                            Masking = true,
                                            CornerRadius = 12,
                                            Children = new Drawable[]
                                            {
                                                new Box
                                                {
                                                    RelativeSizeAxes = Axes.Both,
                                                    Colour = UITheme.Surface,
                                                },
                                                new FillFlowContainer
                                                {
                                                    RelativeSizeAxes = Axes.Both,
                                                    Direction = FillDirection.Horizontal,
                                                    Spacing = new Vector2(20, 0),
                                                    Padding = new MarginPadding(20),
                                                    Children = new Drawable[]
                                                    {
                                                        metronomeToggle = new RecordingActionButton
                                                        {
                                                            Size = new Vector2(100, 60),
                                                            Text = "Metronome",
                                                            BackgroundColour = UITheme.SurfaceAlt,
                                                            Action = toggleMetronome,
                                                        },
                                                        new FillFlowContainer
                                                        {
                                                            AutoSizeAxes = Axes.Both,
                                                            Direction = FillDirection.Vertical,
                                                            Spacing = new Vector2(0, 5),
                                                            Children = new Drawable[]
                                                            {
                                                                bpmText = new SpriteText
                                                                {
                                                                    Text = "120 BPM",
                                                                    Font = BeatSightFont.Title(24),
                                                                    Colour = UITheme.TextPrimary,
                                                                },
                                                                new BeatSightSliderBar
                                                                {
                                                                    Size = new Vector2(200, 20),
                                                                    Current = { BindTarget = bpm },
                                                                },
                                                            }
                                                        },
                                                        tapTempoButton = new RecordingActionButton
                                                        {
                                                            Size = new Vector2(100, 60),
                                                            Text = "Tap Tempo",
                                                            BackgroundColour = UITheme.SurfaceAlt,
                                                            Action = handleTapTempo,
                                                        },
                                                        beatIndicator = new BeatIndicator
                                                        {
                                                            Size = new Vector2(120, 60),
                                                        },
                                                    }
                                                }
                                            }
                                        },

                                        // Quality settings
                                        new Container
                                        {
                                            RelativeSizeAxes = Axes.X,
                                            Height = 60,
                                            Child = new FillFlowContainer
                                            {
                                                RelativeSizeAxes = Axes.Both,
                                                Direction = FillDirection.Horizontal,
                                                Spacing = new Vector2(10, 0),
                                                Children = new Drawable[]
                                                {
                                                    new SpriteText
                                                    {
                                                        Text = "Quality:",
                                                        Font = BeatSightFont.Body(16),
                                                        Colour = UITheme.TextSecondary,
                                                        Anchor = Anchor.CentreLeft,
                                                        Origin = Anchor.CentreLeft,
                                                    },
                                                    qualityStandard = new RecordingActionButton
                                                    {
                                                        Size = new Vector2(120, 40),
                                                        Text = "Standard",
                                                        BackgroundColour = UITheme.SurfaceAlt,
                                                        Action = () => setQuality(AudioQuality.Standard),
                                                    },
                                                    qualityHigh = new RecordingActionButton
                                                    {
                                                        Size = new Vector2(120, 40),
                                                        Text = "High",
                                                        BackgroundColour = UITheme.AccentPrimary,
                                                        Action = () => setQuality(AudioQuality.High),
                                                    },
                                                    qualityStudio = new RecordingActionButton
                                                    {
                                                        Size = new Vector2(120, 40),
                                                        Text = "Studio",
                                                        BackgroundColour = UITheme.SurfaceAlt,
                                                        Action = () => setQuality(AudioQuality.Studio),
                                                    },
                                                }
                                            }
                                        },
                                    }
                                }
                            },

                            // Bottom controls
                            new Container
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 200,
                                Anchor = Anchor.BottomCentre,
                                Origin = Anchor.BottomCentre,
                                Children = new Drawable[]
                                {
                                    new Box
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Colour = UITheme.Surface,
                                    },
                                    recordButton = new RecordButton
                                    {
                                        Anchor = Anchor.Centre,
                                        Origin = Anchor.Centre,
                                        Action = toggleRecording,
                                    },
                                }
                            },
                        }
                    }
                }
            };

            bpm.BindValueChanged(v =>
            {
                bpmText.Text = $"{(int)v.NewValue} BPM";
                if (recordingService != null)
                    recordingService.MetronomeBpm = (int)v.NewValue;
            }, true);
        }

        protected override void Update()
        {
            base.Update();

            if (state == RecordingState.Recording && recordingService != null)
            {
                var duration = recordingService.RecordingDuration;
                timerText.Text = duration.ToString(@"mm\:ss\.f");
            }

            // Update waveform visualization
            if (recordingService != null && (state == RecordingState.Recording || state == RecordingState.Monitoring))
            {
                waveformVisualizer.UpdateLevels(recordingService.GetFrequencyData());
            }
        }

        private void toggleRecording()
        {
            switch (state)
            {
                case RecordingState.Idle:
                    startMonitoring();
                    break;

                case RecordingState.Monitoring:
                    if (metronomeEnabled.Value)
                        startCountdown();
                    else
                        startRecording();
                    break;

                case RecordingState.Countdown:
                    cancelCountdown();
                    break;

                case RecordingState.Recording:
                    stopRecording();
                    break;

                case RecordingState.Stopped:
                    // Open recorded file in editor
                    if (!string.IsNullOrEmpty(lastRecordingPath))
                        openInEditor(lastRecordingPath);
                    break;
            }
        }

        private void startMonitoring()
        {
            if (recordingService == null) return;

            var settings = GetQualitySettings(selectedQuality);
            recordingService.Initialize(settings.SampleRate, settings.Channels);
            recordingService.StartMonitoring();

            state = RecordingState.Monitoring;
            statusText.Text = "Monitoring - Press to start recording";
            recordButton.SetState(RecordingState.Monitoring);
        }

        private void startCountdown()
        {
            state = RecordingState.Countdown;
            countdownValue = 4;
            isCountingDown = true;

            if (metronomeEnabled.Value)
                recordingService?.StartMetronome((int)bpm.Value);

            // Schedule countdown ticks
            Scheduler.AddDelayed(countdownTick, 60000.0 / bpm.Value, true);
        }

        private void countdownTick()
        {
            if (!isCountingDown) return;

            countdownValue--;
            statusText.Text = countdownValue > 0 ? $"Starting in {countdownValue}..." : "Recording!";
            beatIndicator.Pulse();

            if (countdownValue <= 0)
            {
                isCountingDown = false;
                Scheduler.CancelDelayedTasks();
                startRecording();
            }
        }

        private void cancelCountdown()
        {
            isCountingDown = false;
            Scheduler.CancelDelayedTasks();
            recordingService?.StopMetronome();
            state = RecordingState.Monitoring;
            statusText.Text = "Monitoring - Press to start recording";
            recordButton.SetState(RecordingState.Monitoring);
        }

        private void startRecording()
        {
            if (recordingService == null) return;

            var recordingsDir = Path.Combine(host.Storage.GetFullPath(""), "Recordings");
            Directory.CreateDirectory(recordingsDir);

            var filename = $"recording_{DateTime.Now:yyyyMMdd_HHmmss}.wav";
            var filepath = Path.Combine(recordingsDir, filename);

            recordingService.StartRecording(filepath);
            state = RecordingState.Recording;
            statusText.Text = "Recording...";
            recordButton.SetState(RecordingState.Recording);
            timerText.Colour = UITheme.AccentWarning;
        }

        private void stopRecording()
        {
            if (recordingService == null) return;

            recordingService.StopRecording();
            recordingService.StopMetronome();
            state = RecordingState.Stopped;
            statusText.Text = "Recording complete - Press to open in editor";
            recordButton.SetState(RecordingState.Stopped);
            timerText.Colour = UITheme.TextPrimary;
        }

        private void toggleMetronome()
        {
            metronomeEnabled.Value = !metronomeEnabled.Value;
            metronomeToggle.BackgroundColour = metronomeEnabled.Value ? UITheme.AccentSecondary : UITheme.SurfaceAlt;

            if (metronomeEnabled.Value && state == RecordingState.Recording)
            {
                recordingService?.StartMetronome((int)bpm.Value);
            }
            else
            {
                recordingService?.StopMetronome();
            }
        }

        private void handleTapTempo()
        {
            var now = Time.Current;
            tapTimes.Add(now);

            // Keep only taps within the last 5 seconds
            tapTimes.RemoveAll(t => now - t > 5000);

            if (tapTimes.Count >= 2)
            {
                var intervals = new List<double>();
                for (int i = 1; i < tapTimes.Count; i++)
                    intervals.Add(tapTimes[i] - tapTimes[i - 1]);

                var avgInterval = intervals.Average();
                var newBpm = (int)Math.Round(60000 / avgInterval);
                bpm.Value = Math.Clamp(newBpm, 40, 240);
            }

            beatIndicator.Pulse();
        }

        private void setQuality(AudioQuality quality)
        {
            selectedQuality = quality;

            qualityStandard.BackgroundColour = quality == AudioQuality.Standard ? UITheme.AccentPrimary : UITheme.SurfaceAlt;
            qualityHigh.BackgroundColour = quality == AudioQuality.High ? UITheme.AccentPrimary : UITheme.SurfaceAlt;
            qualityStudio.BackgroundColour = quality == AudioQuality.Studio ? UITheme.AccentPrimary : UITheme.SurfaceAlt;

            // Reinitialize if currently monitoring
            if (state == RecordingState.Monitoring)
            {
                recordingService?.StopMonitoring();
                startMonitoring();
            }
        }

        private void onLevelChanged(float level, bool clipping)
        {
            Schedule(() =>
            {
                // Update level meter
                levelBar.Width = (levelMeterContainer.DrawWidth - 8) * Math.Clamp(level, 0, 1);

                // Colour based on level
                if (level > 0.9f)
                    levelBar.Colour = UITheme.AccentWarning;
                else if (level > 0.7f)
                    levelBar.Colour = Color4.Yellow;
                else
                    levelBar.Colour = UITheme.AccentSecondary;

                // Clipping indicator
                clipIndicator.Alpha = clipping ? 1 : 0;

                // dB display
                var db = level > 0 ? 20 * Math.Log10(level) : -60;
                levelText.Text = $"{db:F1} dB";
            });
        }

        private void onRecordingCompleted(string filepath)
        {
            lastRecordingPath = filepath;
            Schedule(() =>
            {
                Logger.Log($"Recording saved to: {filepath}", LoggingTarget.Runtime);
            });
        }

        private void onRecordingError(string message)
        {
            Schedule(() =>
            {
                statusText.Text = $"Error: {message}";
                statusText.Colour = UITheme.AccentWarning;
                state = RecordingState.Idle;
                recordButton.SetState(RecordingState.Idle);
            });
        }

        private void openInEditor(string audioPath)
        {
            this.Push(new EditorScreen(audioPath));
        }

        public override bool OnExiting(ScreenExitEvent e)
        {
            CleanupRecordingService();
            return base.OnExiting(e);
        }

        /// <summary>
        /// Properly clean up the recording service by unsubscribing from events first.
        /// This prevents memory leaks if the screen is disposed without calling OnExiting.
        /// </summary>
        private void CleanupRecordingService()
        {
            if (recordingService != null)
            {
                recordingService.LevelChanged -= onLevelChanged;
                recordingService.RecordingCompleted -= onRecordingCompleted;
                recordingService.Error -= onRecordingError;
                recordingService.Dispose();
                recordingService = null!;
            }
        }

        protected override void Dispose(bool isDisposing)
        {
            if (isDisposing)
                CleanupRecordingService();

            base.Dispose(isDisposing);
        }

        private static QualitySettings GetQualitySettings(AudioQuality quality) => quality switch
        {
            AudioQuality.Standard => new QualitySettings(44100, 2, 128000),
            AudioQuality.High => new QualitySettings(48000, 2, 256000),
            AudioQuality.Studio => new QualitySettings(96000, 2, 320000),
            _ => new QualitySettings(48000, 2, 256000),
        };

        private record QualitySettings(int SampleRate, int Channels, int BitRate);
    }

    public enum RecordingState
    {
        Idle,
        Monitoring,
        Countdown,
        Recording,
        Stopped,
    }

    public enum AudioQuality
    {
        Standard,
        High,
        Studio,
    }

    /// <summary>
    /// Circular record button with state-based styling.
    /// </summary>
    public partial class RecordButton : Container
    {
        public Action? Action;

        private Circle outerRing = null!;
        private Circle innerCircle = null!;
        private Box stopSquare = null!;
        private SpriteText label = null!;

        public RecordButton()
        {
            Size = new Vector2(120);
            Anchor = Anchor.Centre;
            Origin = Anchor.Centre;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            Children = new Drawable[]
            {
                outerRing = new Circle
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.TextMuted,
                },
                new Circle
                {
                    RelativeSizeAxes = Axes.Both,
                    Size = new Vector2(0.9f),
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Colour = UITheme.Background,
                },
                innerCircle = new Circle
                {
                    RelativeSizeAxes = Axes.Both,
                    Size = new Vector2(0.7f),
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Colour = UITheme.AccentWarning,
                },
                stopSquare = new Box
                {
                    Size = new Vector2(40),
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Colour = UITheme.Background,
                    Alpha = 0,
                },
                label = new BeatSightSpriteText
                {
                    Text = "START",
                    Font = BeatSightFont.Button(14),
                    Colour = UITheme.TextPrimary,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Y = 70,
                },
            };
        }

        protected override bool OnClick(osu.Framework.Input.Events.ClickEvent e)
        {
            Action?.Invoke();
            return true;
        }

        public void SetState(RecordingState state)
        {
            switch (state)
            {
                case RecordingState.Idle:
                    innerCircle.FadeColour(UITheme.AccentWarning, 200);
                    stopSquare.FadeOut(200);
                    label.Text = "START";
                    outerRing.FadeColour(UITheme.TextMuted, 200);
                    break;

                case RecordingState.Monitoring:
                    innerCircle.FadeColour(UITheme.AccentSecondary, 200);
                    stopSquare.FadeOut(200);
                    label.Text = "RECORD";
                    outerRing.FadeColour(UITheme.AccentSecondary, 200);
                    this.Loop(b => b.ScaleTo(1.05f, 500).Then().ScaleTo(1f, 500));
                    break;

                case RecordingState.Countdown:
                    innerCircle.FadeColour(UITheme.AccentWarning, 200);
                    label.Text = "CANCEL";
                    break;

                case RecordingState.Recording:
                    this.ClearTransforms();
                    this.ScaleTo(1f);
                    innerCircle.FadeColour(UITheme.AccentWarning, 200);
                    stopSquare.FadeIn(200);
                    label.Text = "STOP";
                    outerRing.FadeColour(UITheme.AccentWarning, 200);
                    // Pulsing animation during recording
                    outerRing.Loop(b => b.FadeTo(0.5f, 300).Then().FadeTo(1f, 300));
                    break;

                case RecordingState.Stopped:
                    this.ClearTransforms();
                    outerRing.ClearTransforms();
                    outerRing.Alpha = 1;
                    innerCircle.FadeColour(UITheme.AccentSuccess, 200);
                    stopSquare.FadeOut(200);
                    label.Text = "OPEN";
                    outerRing.FadeColour(UITheme.AccentSuccess, 200);
                    break;
            }
        }
    }

    /// <summary>
    /// Visual beat indicator for metronome.
    /// </summary>
    public partial class BeatIndicator : Container
    {
        private readonly Circle[] beats = new Circle[4];
        private int currentBeat = -1;

        [BackgroundDependencyLoader]
        private void load()
        {
            var flow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(10, 0),
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
            };

            for (int i = 0; i < 4; i++)
            {
                beats[i] = new Circle
                {
                    Size = new Vector2(20),
                    Colour = UITheme.TextMuted,
                    Anchor = Anchor.CentreLeft,
                    Origin = Anchor.CentreLeft,
                };
                flow.Add(beats[i]);
            }

            Add(flow);
        }

        public void Pulse()
        {
            currentBeat = (currentBeat + 1) % 4;

            for (int i = 0; i < 4; i++)
            {
                if (i == currentBeat)
                {
                    beats[i].FadeColour(i == 0 ? UITheme.AccentPrimary : UITheme.AccentSecondary, 50);
                    beats[i].ScaleTo(1.3f, 50).Then().ScaleTo(1f, 200, Easing.OutQuint);
                }
                else
                {
                    beats[i].FadeColour(UITheme.TextMuted, 200);
                }
            }
        }

        public void Reset()
        {
            currentBeat = -1;
            foreach (var c in beats)
                c.Colour = UITheme.TextMuted;
        }
    }

    /// <summary>
    /// Real-time audio waveform visualization.
    /// </summary>
    public partial class WaveformVisualizer : Container
    {
        private readonly Box[] bars = new Box[64];

        [BackgroundDependencyLoader]
        private void load()
        {
            var barWidth = Math.Max(2, (DrawWidth / 64f) - 2);

            for (int i = 0; i < 64; i++)
            {
                bars[i] = new Box
                {
                    Width = barWidth,
                    Height = 4,
                    Anchor = Anchor.BottomLeft,
                    Origin = Anchor.BottomLeft,
                    X = i * (barWidth + 2),
                    Colour = UITheme.AccentSecondary,
                };
                Add(bars[i]);
            }
        }

        public void UpdateLevels(float[] levels)
        {
            if (levels == null || levels.Length == 0) return;

            var step = levels.Length / 64f;
            var maxHeight = DrawHeight - 10;

            for (int i = 0; i < 64 && i * step < levels.Length; i++)
            {
                var index = (int)(i * step);
                var level = levels[index];
                var targetHeight = Math.Max(4, level * maxHeight);

                bars[i].ResizeHeightTo(targetHeight, 50, Easing.OutQuint);

                // Colour gradient based on level
                if (level > 0.8f)
                    bars[i].Colour = UITheme.AccentWarning;
                else if (level > 0.5f)
                    bars[i].Colour = Color4.Yellow;
                else
                    bars[i].Colour = UITheme.AccentSecondary;
            }
        }
    }

    /// <summary>
    /// Simple action button for recording screen controls.
    /// </summary>
    public partial class RecordingActionButton : BeatSightButton
    {
        public RecordingActionButton()
        {
            Anchor = Anchor.CentreLeft;
            Origin = Anchor.CentreLeft;
        }

        protected override SpriteText CreateText()
        {
            return new BeatSightSpriteText
            {
                Depth = -1,
                Origin = Anchor.Centre,
                Anchor = Anchor.Centre,
                Font = BeatSightFont.Button(16f),
                UseFullGlyphHeight = false,
                Colour = Color4.White,
            };
        }
    }
}
