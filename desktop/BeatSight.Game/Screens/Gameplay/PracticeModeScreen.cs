using System;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using osu.Framework.Allocation;
using osu.Framework.Audio.Track;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Gameplay
{
    public partial class PracticeModeScreen : GameplayScreen
    {
        private double loopStartTime = -1;
        private double loopEndTime = -1;
        private bool loopEnabled;

        private Container practiceOverlay = null!;
        private SpriteText loopStatusText = null!;
        private BasicSliderBar<double> difficultySlider = null!;
        private SpriteText difficultyText = null!;
        private Box metronomeIndicator = null!;
        private BasicSliderBar<double> metronomeVolumeSlider = null!;
        private BasicDropdown<MetronomeSoundOption> metronomeSoundDropdown = null!;
        private BasicDropdown<NoteSkinOption> noteSkinDropdown = null!;

        private readonly BindableDouble difficulty = new BindableDouble
        {
            MinValue = 0.25,
            MaxValue = 1.0,
            Default = 1.0,
            Precision = 0.05,
            Value = 1.0
        };
        private BindableDouble? metronomeVolumeControl;
        private Bindable<bool>? metronomeEnabled;
        private Bindable<MetronomeSoundOption>? metronomeSoundSetting;
        private Bindable<NoteSkinOption>? noteSkinSetting;

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        public PracticeModeScreen(string? beatmapPath = null) : base(beatmapPath)
        {
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            // Add practice mode UI overlay
            AddInternal(practiceOverlay = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    // Practice controls panel
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 220,
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Padding = new MarginPadding { Top = 80 },
                        Child = new Container
                        {
                            Width = 500,
                            Height = 220,
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            Masking = true,
                            CornerRadius = 12,
                            Children = new Drawable[]
                            {
                                new Box
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Colour = new Color4(25, 28, 38, 220)
                                },
                                new FillFlowContainer
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Direction = FillDirection.Vertical,
                                    Padding = new MarginPadding(16),
                                    Spacing = new Vector2(0, 12),
                                    Children = new Drawable[]
                                    {
                                        new SpriteText
                                        {
                                            Text = "🎓 Practice Mode",
                                            Font = new FontUsage(size: 22, weight: "Bold"),
                                            Colour = new Color4(120, 200, 255, 255),
                                            Anchor = Anchor.TopCentre,
                                            Origin = Anchor.TopCentre
                                        },
                                        loopStatusText = new SpriteText
                                        {
                                            Text = "[ and ] to set loop points • M for metronome",
                                            Font = new FontUsage(size: 16),
                                            Colour = new Color4(180, 185, 200, 255),
                                            Anchor = Anchor.TopCentre,
                                            Origin = Anchor.TopCentre
                                        },
                                        new GridContainer
                                        {
                                            RelativeSizeAxes = Axes.X,
                                            Height = 40,
                                            ColumnDimensions = new[]
                                            {
                                                new Dimension(GridSizeMode.Relative, 0.4f),
                                                new Dimension(GridSizeMode.Relative, 0.6f)
                                            },
                                            Content = new[]
                                            {
                                                new Drawable[]
                                                {
                                                    difficultyText = new SpriteText
                                                    {
                                                        Text = "Difficulty: 100%",
                                                        Font = new FontUsage(size: 18),
                                                        Colour = Color4.White,
                                                        Anchor = Anchor.CentreLeft,
                                                        Origin = Anchor.CentreLeft
                                                    },
                                                    difficultySlider = new BasicSliderBar<double>
                                                    {
                                                        RelativeSizeAxes = Axes.X,
                                                        Height = 16,
                                                        Current = difficulty,
                                                        Anchor = Anchor.CentreRight,
                                                        Origin = Anchor.CentreRight
                                                    }
                                                }
                                            }
                                        },
                                        new GridContainer
                                        {
                                            RelativeSizeAxes = Axes.X,
                                            Height = 40,
                                            ColumnDimensions = new[]
                                            {
                                                new Dimension(GridSizeMode.Relative, 0.4f),
                                                new Dimension(GridSizeMode.Relative, 0.6f)
                                            },
                                            Content = new[]
                                            {
                                                new Drawable[]
                                                {
                                                    new SpriteText
                                                    {
                                                        Text = "Metronome Volume",
                                                        Font = new FontUsage(size: 18),
                                                        Colour = Color4.White,
                                                        Anchor = Anchor.CentreLeft,
                                                        Origin = Anchor.CentreLeft
                                                    },
                                                    metronomeVolumeSlider = new BasicSliderBar<double>
                                                    {
                                                        RelativeSizeAxes = Axes.X,
                                                        Height = 16,
                                                        Anchor = Anchor.CentreRight,
                                                        Origin = Anchor.CentreRight
                                                    }
                                                }
                                            }
                                        },
                                        new GridContainer
                                        {
                                            RelativeSizeAxes = Axes.X,
                                            Height = 40,
                                            ColumnDimensions = new[]
                                            {
                                                new Dimension(GridSizeMode.Relative, 0.4f),
                                                new Dimension(GridSizeMode.Relative, 0.6f)
                                            },
                                            Content = new[]
                                            {
                                                new Drawable[]
                                                {
                                                    new SpriteText
                                                    {
                                                        Text = "Metronome Sound",
                                                        Font = new FontUsage(size: 18),
                                                        Colour = Color4.White,
                                                        Anchor = Anchor.CentreLeft,
                                                        Origin = Anchor.CentreLeft
                                                    },
                                                    metronomeSoundDropdown = new BasicDropdown<MetronomeSoundOption>
                                                    {
                                                        Width = 220,
                                                        Anchor = Anchor.CentreRight,
                                                        Origin = Anchor.CentreRight
                                                    }
                                                }
                                            }
                                        },
                                        new GridContainer
                                        {
                                            RelativeSizeAxes = Axes.X,
                                            Height = 40,
                                            ColumnDimensions = new[]
                                            {
                                                new Dimension(GridSizeMode.Relative, 0.4f),
                                                new Dimension(GridSizeMode.Relative, 0.6f)
                                            },
                                            Content = new[]
                                            {
                                                new Drawable[]
                                                {
                                                    new SpriteText
                                                    {
                                                        Text = "Note Skin",
                                                        Font = new FontUsage(size: 18),
                                                        Colour = Color4.White,
                                                        Anchor = Anchor.CentreLeft,
                                                        Origin = Anchor.CentreLeft
                                                    },
                                                    noteSkinDropdown = new BasicDropdown<NoteSkinOption>
                                                    {
                                                        Width = 220,
                                                        Anchor = Anchor.CentreRight,
                                                        Origin = Anchor.CentreRight
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    // Metronome indicator
                    new Container
                    {
                        Width = 60,
                        Height = 60,
                        Anchor = Anchor.TopRight,
                        Origin = Anchor.TopRight,
                        Margin = new MarginPadding { Top = 240, Right = 40 },
                        Masking = true,
                        CornerRadius = 30,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = new Color4(30, 30, 42, 180)
                            },
                            metronomeIndicator = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = new Color4(255, 215, 0, 0),
                                Blending = BlendingParameters.Additive
                            }
                        }
                    }
                }
            });

            difficulty.BindValueChanged(e =>
            {
                difficultyText.Text = $"Difficulty: {e.NewValue * 100:0}%";
                applyDifficultyFilter(e.NewValue);
            });

            var metronomeVolumeSource = (Bindable<double>)MetronomeVolumeBinding.GetBoundCopy();
            metronomeVolumeControl = new BindableDouble
            {
                MinValue = 0,
                MaxValue = 1,
                Precision = 0.05
            };
            metronomeVolumeControl.BindTo(metronomeVolumeSource);
            metronomeVolumeSlider.Current = metronomeVolumeControl;

            metronomeSoundSetting = (Bindable<MetronomeSoundOption>)MetronomeSoundBinding.GetBoundCopy();
            metronomeSoundDropdown.Items = Enum.GetValues<MetronomeSoundOption>();
            metronomeSoundDropdown.Current = metronomeSoundSetting;

            noteSkinSetting = config.GetBindable<NoteSkinOption>(BeatSightSetting.NoteSkin);
            noteSkinDropdown.Items = Enum.GetValues<NoteSkinOption>();
            noteSkinDropdown.Current = noteSkinSetting;

            metronomeEnabled = (Bindable<bool>)MetronomeEnabledBinding.GetBoundCopy();
            metronomeEnabled.BindValueChanged(onMetronomeEnabledChanged, true);

            MetronomeTick += onMetronomeTick;
        }

        private void applyDifficultyFilter(double percentage)
        {
            if (beatmap == null || playfield == null)
                return;

            // Keep notes based on percentage (evenly distributed)
            var filteredHitObjects = new System.Collections.Generic.List<HitObject>();
            var totalNotes = beatmap.HitObjects.Count;

            if (percentage >= 1.0)
            {
                // 100% - keep all notes
                filteredHitObjects = beatmap.HitObjects.ToList();
            }
            else
            {
                // Filter notes evenly across the song
                int keepEvery = Math.Max(1, (int)(1.0 / percentage));

                for (int i = 0; i < totalNotes; i++)
                {
                    if (i % keepEvery == 0)
                    {
                        filteredHitObjects.Add(beatmap.HitObjects[i]);
                    }
                }
            }

            // Create filtered beatmap
            var filteredBeatmap = new Beatmap
            {
                Version = beatmap.Version,
                Metadata = beatmap.Metadata,
                Timing = beatmap.Timing,
                Audio = beatmap.Audio,
                DrumKit = beatmap.DrumKit,
                HitObjects = filteredHitObjects,
                Editor = beatmap.Editor
            };

            // Reload playfield with filtered notes
            playfield.LoadBeatmap(filteredBeatmap);
        }

        protected override void Update()
        {
            base.Update();

            // Check for loop boundaries
            if (loopEnabled && loopStartTime >= 0 && loopEndTime > loopStartTime)
            {
                double currentTime = getCurrentTime();

                if (currentTime >= loopEndTime)
                {
                    // Loop back to start
                    if (track != null)
                        track.Seek(loopStartTime);
                }
            }

        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == osuTK.Input.Key.BracketLeft && !e.Repeat)
            {
                // Set loop start point
                loopStartTime = getCurrentTime();
                updateLoopStatus();
                return true;
            }

            if (e.Key == osuTK.Input.Key.BracketRight && !e.Repeat)
            {
                // Set loop end point
                loopEndTime = getCurrentTime();
                updateLoopStatus();
                return true;
            }

            if (e.Key == osuTK.Input.Key.M && !e.Repeat)
            {
                // Toggle metronome
                if (metronomeEnabled != null)
                    metronomeEnabled.Value = !metronomeEnabled.Value;
                return true;
            }

            if (e.Key == osuTK.Input.Key.C && !e.Repeat)
            {
                // Clear loop
                loopStartTime = -1;
                loopEndTime = -1;
                loopEnabled = false;
                updateLoopStatus();
                return true;
            }

            return base.OnKeyDown(e);
        }

        private void updateLoopStatus()
        {
            if (loopStartTime >= 0 && loopEndTime > loopStartTime)
            {
                loopEnabled = true;
                double duration = (loopEndTime - loopStartTime) / 1000.0;
                loopStatusText.Text = $"Loop: {formatTime(loopStartTime)} → {formatTime(loopEndTime)} ({duration:0.0}s) • C to clear";
                loopStatusText.Colour = new Color4(120, 255, 120, 255);
            }
            else if (loopStartTime >= 0)
            {
                loopEnabled = false;
                loopStatusText.Text = $"Loop start: {formatTime(loopStartTime)} • Press ] to set end";
                loopStatusText.Colour = new Color4(255, 215, 120, 255);
            }
            else
            {
                loopEnabled = false;
                loopStatusText.Text = "[ and ] to set loop points • M for metronome";
                loopStatusText.Colour = new Color4(180, 185, 200, 255);
            }
        }

        private static string formatTime(double milliseconds)
        {
            var time = TimeSpan.FromMilliseconds(milliseconds);
            return $"{time.Minutes:00}:{time.Seconds:00}.{time.Milliseconds / 100:0}";
        }

        private void onMetronomeEnabledChanged(ValueChangedEvent<bool> state)
        {
            if (metronomeIndicator == null)
                return;

            metronomeIndicator.FadeTo(state.NewValue ? 1f : 0.3f, 200, Easing.OutQuint);
        }

        private void onMetronomeTick(double _)
        {
            if (metronomeIndicator == null)
                return;

            metronomeIndicator.ClearTransforms();
            metronomeIndicator
                .FadeColour(new Color4(255, 215, 0, 255), 50, Easing.OutQuint)
                .Then()
                .FadeColour(new Color4(255, 215, 0, 0), 300, Easing.OutQuint);
        }

        protected override void Dispose(bool isDisposing)
        {
            if (isDisposing)
            {
                MetronomeTick -= onMetronomeTick;
                metronomeEnabled?.UnbindAll();
                metronomeVolumeControl?.UnbindAll();
                metronomeSoundSetting?.UnbindAll();
                noteSkinSetting?.UnbindAll();
            }

            base.Dispose(isDisposing);
        }


    }
}
