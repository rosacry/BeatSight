using System;
using BeatSight.Game.Audio;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Gameplay
{
    /// <summary>
    /// Heads-up display for microphone-driven gameplay.
    /// Provides live status, device info, lane meters, and last hit telemetry.
    /// </summary>
    public partial class LiveInputHudOverlay : CompositeDrawable
    {
        public const int LaneCount = 7;

        private readonly SpriteText titleText;
        private readonly SpriteText statusText;
        private readonly SpriteText statusStateText;
        private readonly SpriteText calibrationText;
        private readonly SpriteText deviceText;
        private readonly SpriteText ambientText;
        private readonly SpriteText lastHitText;
        private readonly SpriteText confidenceText;
        private readonly SpriteText latencyText;
        private LaneMeter[] laneMeters = Array.Empty<LaneMeter>();
        private readonly BasicButton recalibrateButton;
        private readonly SpriteText recalibrateHintText;
        private readonly Circle statusIndicator;

        public event Action? RecalibrateRequested;

        public LiveInputHudOverlay()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChild = new Container
            {
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                AutoSizeAxes = Axes.Both,
                Margin = new MarginPadding { Top = 72 },
                Child = new Container
                {
                    Width = 460,
                    AutoSizeAxes = Axes.Y,
                    Masking = true,
                    CornerRadius = 12,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(20, 24, 34, 220)
                        },
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Direction = FillDirection.Vertical,
                            Padding = new MarginPadding(20),
                            Spacing = new Vector2(0, 10),
                            Children = new Drawable[]
                            {
                                new FillFlowContainer
                                {
                                    RelativeSizeAxes = Axes.X,
                                    AutoSizeAxes = Axes.Y,
                                    Direction = FillDirection.Horizontal,
                                    Spacing = new Vector2(10, 0),
                                    Children = new Drawable[]
                                    {
                                        statusIndicator = new Circle
                                        {
                                            Size = new Vector2(14),
                                            Colour = stateColour(StatusState.Info)
                                        },
                                        new FillFlowContainer
                                        {
                                            RelativeSizeAxes = Axes.X,
                                            AutoSizeAxes = Axes.Y,
                                            Direction = FillDirection.Vertical,
                                            Spacing = new Vector2(0, 2),
                                            Children = new Drawable[]
                                            {
                                                titleText = new SpriteText
                                                {
                                                    Text = "Live Input",
                                                    Font = new FontUsage(size: 22, weight: "Bold"),
                                                    Colour = Color4.White
                                                },
                                                statusStateText = new SpriteText
                                                {
                                                    Text = "INIT",
                                                    Font = new FontUsage(size: 12, weight: "Bold"),
                                                    Colour = new Color4(170, 175, 190, 255)
                                                }
                                            }
                                        }
                                    }
                                },
                                statusText = new SpriteText
                                {
                                    Text = "Initializing…",
                                    Font = new FontUsage(size: 16),
                                    Colour = new Color4(200, 205, 215, 255)
                                },
                                calibrationText = new SpriteText
                                {
                                    Text = "Calibration pending",
                                    Font = new FontUsage(size: 14),
                                    Colour = new Color4(210, 180, 120, 255)
                                },
                                deviceText = new SpriteText
                                {
                                    Text = "Device: —",
                                    Font = new FontUsage(size: 14),
                                    Colour = new Color4(155, 160, 175, 255)
                                },
                                ambientText = new SpriteText
                                {
                                    Text = "Ambient noise: —",
                                    Font = new FontUsage(size: 12),
                                    Colour = new Color4(140, 145, 165, 255)
                                },
                                new FillFlowContainer
                                {
                                    RelativeSizeAxes = Axes.X,
                                    AutoSizeAxes = Axes.Y,
                                    Direction = FillDirection.Horizontal,
                                    Spacing = new Vector2(12, 0),
                                    Children = new Drawable[]
                                    {
                                        lastHitText = new SpriteText
                                        {
                                            Text = "Last hit: —",
                                            Font = new FontUsage(size: 13),
                                            Colour = new Color4(200, 205, 220, 255)
                                        },
                                        confidenceText = new SpriteText
                                        {
                                            Text = "Confidence: —",
                                            Font = new FontUsage(size: 13),
                                            Colour = new Color4(180, 185, 200, 255)
                                        },
                                        latencyText = new SpriteText
                                        {
                                            Text = "Latency: —",
                                            Font = new FontUsage(size: 13),
                                            Colour = new Color4(180, 185, 200, 255)
                                        }
                                    }
                                },
                                createLaneMeters(),
                                new FillFlowContainer
                                {
                                    RelativeSizeAxes = Axes.X,
                                    AutoSizeAxes = Axes.Y,
                                    Direction = FillDirection.Vertical,
                                    Spacing = new Vector2(6, 0),
                                    Children = new Drawable[]
                                    {
                                        recalibrateButton = new BasicButton
                                        {
                                            Text = "Recalibrate Mic",
                                            Width = 170,
                                            Height = 34
                                        },
                                        recalibrateHintText = new SpriteText
                                        {
                                            Text = "Shortcut: press C to recalibrate",
                                            Font = new FontUsage(size: 11),
                                            Colour = new Color4(150, 155, 170, 255)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            };

            recalibrateButton.Action = () => RecalibrateRequested?.Invoke();
        }

        public void SetStatus(string text, Color4 colour, StatusState state)
        {
            statusText.Text = text;
            statusText.Colour = colour;
            statusIndicator.FadeColour(stateColour(state), 100);
            statusStateText.Text = stateLabel(state);
            statusStateText.Colour = stateColour(state);
        }

        public void SetCalibrationSummary(string text, CalibrationState state)
        {
            calibrationText.Text = text;
            calibrationText.Colour = calibrationColour(state);
        }

        public void SetDeviceName(string name)
        {
            deviceText.Text = $"Device: {name}";
        }

        public void SetAmbientNoise(double? noiseFloor)
        {
            ambientText.Text = noiseFloor.HasValue
                ? $"Ambient noise: {noiseFloor.Value:0.0000} RMS"
                : "Ambient noise: —";
        }

        public void SetLastOnset(DrumType type, float energy, float confidence, double latencyMs)
        {
            string label = type == DrumType.Unknown ? "Unknown" : type.ToString();
            lastHitText.Text = $"Last hit: {label}";
            confidenceText.Text = confidence >= 0
                ? $"Confidence: {Math.Clamp((int)Math.Round(confidence * 100f), 0, 100)}%"
                : "Confidence: —";
            latencyText.Text = latencyMs >= 0
                ? $"Latency: {latencyMs:0} ms"
                : "Latency: —";
            confidenceText.Colour = confidenceColour(confidence);
        }

        public void ResetLastOnset()
        {
            lastHitText.Text = "Last hit: —";
            confidenceText.Text = "Confidence: —";
            latencyText.Text = "Latency: —";
            confidenceText.Colour = new Color4(180, 185, 200, 255);
        }

        public void SetRecalibrateEnabled(bool enabled)
        {
            recalibrateButton.Enabled.Value = enabled;
            recalibrateButton.FadeTo(enabled ? 1f : 0.35f, 120);
        }

        public void SetRecalibrateHintVisible(bool visible)
        {
            recalibrateHintText.FadeTo(visible ? 1f : 0f, 120);
        }

        public void SetMeterLevel(int lane, float value)
        {
            if (lane < 0 || lane >= laneMeters.Length)
                return;

            laneMeters[lane].SetLevel(value);
        }

        public void FlashLane(int lane, string label, Color4 highlight)
        {
            if (lane < 0 || lane >= laneMeters.Length)
                return;

            laneMeters[lane].Flash(label, highlight);
        }

        public void SetLaneDefaultLabel(int lane, string label)
        {
            if (lane < 0 || lane >= laneMeters.Length)
                return;

            laneMeters[lane].SetDefaultLabel(label);
        }

        private Drawable createLaneMeters()
        {
            laneMeters = new LaneMeter[LaneCount];
            var flow = new FillFlowContainer
            {
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(6, 0),
                Margin = new MarginPadding { Top = 6 }
            };

            for (int i = 0; i < LaneCount; i++)
            {
                var meter = new LaneMeter((i + 1).ToString());
                laneMeters[i] = meter;
                flow.Add(meter);
            }

            return flow;
        }

        private static string stateLabel(StatusState state) => state switch
        {
            StatusState.Listening => "LISTENING",
            StatusState.Calibrating => "CALIBRATING",
            StatusState.Warning => "WARNING",
            StatusState.Error => "ERROR",
            StatusState.Paused => "PAUSED",
            _ => "INFO"
        };

        private static Color4 stateColour(StatusState state) => state switch
        {
            StatusState.Listening => new Color4(100, 210, 140, 255),
            StatusState.Calibrating => new Color4(255, 200, 120, 255),
            StatusState.Warning => new Color4(255, 200, 120, 255),
            StatusState.Error => new Color4(255, 120, 120, 255),
            StatusState.Paused => new Color4(170, 175, 190, 255),
            _ => new Color4(140, 160, 220, 255)
        };

        private static Color4 calibrationColour(CalibrationState state) => state switch
        {
            CalibrationState.Completed => new Color4(120, 220, 160, 255),
            CalibrationState.Warning => new Color4(255, 200, 120, 255),
            CalibrationState.Required => new Color4(255, 140, 140, 255),
            _ => new Color4(200, 205, 220, 255)
        };

        private static Color4 confidenceColour(float confidence)
        {
            if (confidence < 0)
                return new Color4(180, 185, 200, 255);

            float clamped = Math.Clamp(confidence, 0, 1);
            byte g = (byte)(160 + (95 * clamped));
            byte r = (byte)(255 - (95 * clamped));
            return new Color4(r, g, 150, 255);
        }

        public enum StatusState
        {
            Info,
            Listening,
            Calibrating,
            Warning,
            Error,
            Paused
        }

        public enum CalibrationState
        {
            Unknown,
            Completed,
            Warning,
            Required
        }

        private partial class LaneMeter : CompositeDrawable
        {
            private readonly Box fill;
            private readonly SpriteText labelText;
            private readonly Color4 baseFillColour = new Color4(90, 180, 255, 255);
            private readonly Color4 baseBackgroundColour = new Color4(40, 44, 60, 255);

            private string defaultLabel;

            public LaneMeter(string defaultLabel)
            {
                this.defaultLabel = defaultLabel;

                Width = 48;
                Height = 76;
                Masking = true;
                CornerRadius = 6;

                InternalChildren = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = baseBackgroundColour
                    },
                    fill = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = baseFillColour,
                        Anchor = Anchor.BottomLeft,
                        Origin = Anchor.BottomLeft,
                        Height = 0
                    },
                    labelText = new SpriteText
                    {
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.BottomCentre,
                        Margin = new MarginPadding { Bottom = 4 },
                        Colour = new Color4(200, 205, 220, 255),
                        Font = new FontUsage(size: 12),
                        Text = defaultLabel
                    }
                };
            }

            public void SetLevel(float value)
            {
                float clamped = Math.Clamp(value, 0, 1);
                fill.ResizeHeightTo(clamped, 60, Easing.OutQuint);
            }

            public void Flash(string label, Color4 highlight)
            {
                fill.ClearTransforms();
                fill.FadeColour(highlight, 50).Then().FadeColour(baseFillColour, 200);

                labelText.Text = label;
                labelText.FadeColour(Color4.White, 30);
                labelText.Delay(700).FadeColour(new Color4(200, 205, 220, 255), 100);
                labelText.Delay(700).Schedule(() => labelText.Text = defaultLabel);
            }

            public void SetDefaultLabel(string label)
            {
                defaultLabel = label;
                labelText.Text = label;
            }
        }
    }
}
