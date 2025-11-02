using System;
using System.Collections.Generic;
using System.IO;
using BeatSight.Game.Beatmaps;
using osu.Framework.Allocation;
using osu.Framework.Audio;
using osu.Framework.Audio.Track;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osu.Framework.Timing;
using osuTK;
using osuTK.Graphics;
using System.Linq;

namespace BeatSight.Game.Screens.Gameplay
{
    public partial class GameplayScreen : Screen
    {
        private static readonly Dictionary<osuTK.Input.Key, int> laneKeyBindings = new()
        {
            { osuTK.Input.Key.S, 0 },
            { osuTK.Input.Key.D, 1 },
            { osuTK.Input.Key.F, 2 },
            { osuTK.Input.Key.Space, 3 },
            { osuTK.Input.Key.J, 4 },
            { osuTK.Input.Key.K, 5 },
            { osuTK.Input.Key.L, 6 }
        };

        private readonly string? requestedBeatmapPath;
        private double fallbackElapsed;
        private bool fallbackRunning;

        private Beatmap? beatmap;
        private string? beatmapPath;
        private Track? track;

        private GameplayPlayfield? playfield;
        private SpriteText statusText = null!;
        private SpriteText offsetValueText = null!;
        private readonly BindableDouble offsetAdjustment = new BindableDouble
        {
            MinValue = -120,
            MaxValue = 120,
            Default = 0,
            Precision = 1
        };
        private double offsetMilliseconds;

        [Resolved]
        private AudioManager audioManager { get; set; } = null!;

        [Resolved]
        private GameHost host { get; set; } = null!;

        public GameplayScreen(string? beatmapPath = null)
        {
            requestedBeatmapPath = beatmapPath;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(10, 10, 18, 255)
                },
                new GridContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    RowDimensions = new[]
                    {
                        new Dimension(GridSizeMode.Absolute, 60),
                        new Dimension()
                    },
                    Content = new[]
                    {
                        new Drawable[]
                        {
                            createHeader()
                        },
                        new Drawable[]
                        {
                            createPlayfieldArea()
                        }
                    }
                }
            };

            loadBeatmap();

            offsetAdjustment.BindValueChanged(value =>
            {
                offsetMilliseconds = value.NewValue;
                if (offsetValueText != null)
                    offsetValueText.Text = formatOffsetLabel(value.NewValue);
            }, true);
        }

        private Drawable createHeader()
        {
            statusText = new SpriteText
            {
                Text = "Loading beatmap…",
                Font = new FontUsage(size: 24, weight: "Medium"),
                Colour = Color4.White,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
            };

            offsetValueText = new SpriteText
            {
                Font = new FontUsage(size: 18),
                Colour = new Color4(200, 205, 220, 255),
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Text = formatOffsetLabel(0)
            };

            var offsetSlider = new BasicSliderBar<double>
            {
                Width = 220,
                Height = 14,
                Current = offsetAdjustment,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
            };

            var rightColumn = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Spacing = new Vector2(0, 6),
                Children = new Drawable[]
                {
                    offsetValueText,
                    offsetSlider,
                    new SpriteText
                    {
                        Text = "Esc — back to song select",
                        Font = new FontUsage(size: 18),
                        Colour = new Color4(180, 180, 200, 255),
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight
                    }
                }
            };

            return new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Padding = new MarginPadding { Left = 40, Right = 40, Top = 10, Bottom = 10 },
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Relative, 0.6f),
                    new Dimension(GridSizeMode.Relative, 0.4f)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        new FillFlowContainer
                        {
                            AutoSizeAxes = Axes.Both,
                            Direction = FillDirection.Vertical,
                            Children = new Drawable[] { statusText }
                        },
                        rightColumn
                    }
                }
            };
        }

        private Drawable createPlayfieldArea()
        {
            playfield = new GameplayPlayfield(getCurrentTime)
            {
                RelativeSizeAxes = Axes.Both,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Size = new Vector2(0.8f, 1f),
                Margin = new MarginPadding { Left = 40, Right = 40, Bottom = 40 }
            };

            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    playfield,
                    new HitLine
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 4,
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.Centre,
                        Y = -80
                    }
                }
            };
        }

        private void loadBeatmap()
        {
            if (!tryResolveBeatmapPath(out string? path))
            {
                statusText.Text = "No beatmaps found. Return to add a map.";
                return;
            }

            try
            {
                beatmap = BeatmapLoader.LoadFromFile(path!);
                beatmapPath = path;
                statusText.Text = $"Loaded: {beatmap.Metadata.Artist} — {beatmap.Metadata.Title}";
                loadTrack();
                fallbackElapsed = 0;
                fallbackRunning = false;
            }
            catch (Exception ex)
            {
                statusText.Text = $"Failed to load beatmap: {ex.Message}";
            }
        }

        private bool tryResolveBeatmapPath(out string? path)
        {
            if (!string.IsNullOrEmpty(requestedBeatmapPath))
            {
                path = requestedBeatmapPath;
                return true;
            }

            if (BeatmapLibrary.TryGetDefaultBeatmapPath(out var fallback))
            {
                path = fallback;
                return true;
            }

            path = null;
            return false;
        }

        private void loadTrack()
        {
            disposeTrack();

            if (beatmap == null || beatmapPath == null)
                return;

            if (string.IsNullOrWhiteSpace(beatmap.Audio.Filename))
            {
                statusText.Text += "\nBeatmap has no audio file declared.";
                createVirtualTrack();
                return;
            }

            string resolvedAudioPath = Path.IsPathRooted(beatmap.Audio.Filename)
                ? beatmap.Audio.Filename
                : Path.Combine(Path.GetDirectoryName(beatmapPath) ?? string.Empty, beatmap.Audio.Filename);

            if (!File.Exists(resolvedAudioPath))
            {
                statusText.Text += $"\nAudio file missing: {resolvedAudioPath}";
                createVirtualTrack();
                return;
            }

            try
            {
                string cacheDirectory = host.Storage.GetFullPath("BeatmapAudio");
                Directory.CreateDirectory(cacheDirectory);

                string cachedName = $"{beatmap.Metadata.BeatmapId}_{Path.GetFileName(resolvedAudioPath)}";
                string cachedPath = Path.Combine(cacheDirectory, cachedName);

                File.Copy(resolvedAudioPath, cachedPath, overwrite: true);

                string relativePath = Path.Combine("BeatmapAudio", cachedName).Replace(Path.DirectorySeparatorChar, '/');

                track = audioManager.Tracks.Get(relativePath);
                track.Completed += onTrackCompleted;
                fallbackRunning = false;
            }
            catch (Exception ex)
            {
                statusText.Text += $"\nAudio load failed ({ex.Message}). Using silent timing.";
                createVirtualTrack();
            }
        }

        private void createVirtualTrack()
        {
            track = null;
        }

        private void startPlayback(bool restart)
        {
            if (track != null)
            {
                if (restart)
                    track.Seek(0);

                track.Start();
            }
            else
            {
                if (restart)
                    fallbackElapsed = 0;

                fallbackRunning = true;
            }
        }

        private void stopPlayback()
        {
            track?.Stop();
            fallbackRunning = false;
        }

        private void disposeTrack()
        {
            if (track == null)
                return;

            track.Stop();
            track.Completed -= onTrackCompleted;
            track.Dispose();
            track = null;
        }

        private void onTrackCompleted()
        {
            Schedule(() =>
            {
                stopPlayback();
                statusText.Text += "\nPlayback complete";
            });
        }

        private static string formatOffsetLabel(double value) => $"Offset: {value:+0;-0;0} ms";

        private double getCurrentTime() => (track?.CurrentTime ?? fallbackElapsed) + offsetMilliseconds;

        protected override void LoadComplete()
        {
            base.LoadComplete();

            if (beatmap != null)
                playfield?.LoadBeatmap(beatmap);
        }

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);
            startPlayback(restart: true);
        }

        public override void OnResuming(ScreenTransitionEvent e)
        {
            base.OnResuming(e);
            startPlayback(restart: false);
        }

        public override void OnSuspending(ScreenTransitionEvent e)
        {
            base.OnSuspending(e);
            stopPlayback();
        }

        public override bool OnExiting(ScreenExitEvent e)
        {
            stopPlayback();
            return base.OnExiting(e);
        }

        protected override void Update()
        {
            base.Update();

            if (fallbackRunning && track == null)
                fallbackElapsed += Time.Elapsed;
        }

        protected override void Dispose(bool isDisposing)
        {
            base.Dispose(isDisposing);
            disposeTrack();
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == osuTK.Input.Key.Escape)
            {
                this.Exit();
                return true;
            }

            if (!e.Repeat && playfield != null && laneKeyBindings.TryGetValue(e.Key, out int lane))
            {
                var result = playfield.HandleInput(lane, getCurrentTime());
                if (result != GameplayPlayfield.HitResult.None)
                    return true;
            }

            return base.OnKeyDown(e);
        }

        private partial class HitLine : CompositeDrawable
        {
            public HitLine()
            {
                RelativeSizeAxes = Axes.X;
                Height = 4;
                Masking = true;
                CornerRadius = 2;

                InternalChildren = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(255, 184, 108, 255)
                    }
                };
            }
        }
    }

    internal partial class GameplayPlayfield : CompositeDrawable
    {
        private const int laneCount = 7;
        private const double approachDuration = 1800; // milliseconds from spawn to hit line
        private const double perfectWindow = 35;
        private const double greatWindow = 80;
        private const double goodWindow = 130;
        private const double mehWindow = 180;
        private const double missWindow = 220;

        private readonly Func<double> currentTimeProvider;
        private readonly List<DrawableNote> notes = new();

        private Container noteLayer = null!;
        private SpriteText comboText = null!;
        private SpriteText accuracyText = null!;
        private SpriteText judgementText = null!;

        private int combo;
        private int totalNotes;
        private int judgedNotes;
        private double accuracyScore;

        public GameplayPlayfield(Func<double> currentTimeProvider)
        {
            this.currentTimeProvider = currentTimeProvider;

            RelativeSizeAxes = Axes.Both;
            Masking = true;
            CornerRadius = 12;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(26, 26, 40, 255)
                },
                createLaneGrid(),
                noteLayer = new Container
                {
                    RelativeSizeAxes = Axes.Both
                },
                createOverlay()
            };
        }

        private Drawable createOverlay()
        {
            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Padding = new MarginPadding { Top = 16 },
                Spacing = new Vector2(0, 6),
                Children = new Drawable[]
                {
                    comboText = new SpriteText
                    {
                        Font = new FontUsage(size: 32, weight: "Medium"),
                        Colour = Color4.White,
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Text = "Combo: 0"
                    },
                    accuracyText = new SpriteText
                    {
                        Font = new FontUsage(size: 22),
                        Colour = new Color4(200, 205, 220, 255),
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Text = "Accuracy: --"
                    },
                    judgementText = new SpriteText
                    {
                        Font = new FontUsage(size: 26, weight: "Medium"),
                        Colour = new Color4(255, 196, 120, 255),
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Text = "Ready"
                    }
                }
            };
        }

        private Drawable createLaneGrid()
        {
            var laneContainer = new GridContainer
            {
                RelativeSizeAxes = Axes.Both,
                ColumnDimensions = Enumerable.Repeat(new Dimension(GridSizeMode.Relative, 1f / laneCount), laneCount).ToArray(),
                Content = new[]
                {
                    Enumerable.Range(0, laneCount).Select(createLaneBackground).ToArray()
                }
            };

            return laneContainer;
        }

        private Drawable createLaneBackground(int laneIndex)
        {
            float intensity = laneIndex % 2 == 0 ? 0.16f : 0.22f;
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4((byte)(intensity * 255), (byte)(intensity * 255), 60, 255)
                    }
                }
            };
        }

        public void LoadBeatmap(Beatmap beatmap)
        {
            noteLayer.Clear();
            notes.Clear();

            combo = 0;
            totalNotes = 0;
            judgedNotes = 0;
            accuracyScore = 0;

            comboText.Text = "Combo: 0";
            accuracyText.Text = "Accuracy: --";
            judgementText.Text = "Ready";

            foreach (var hit in beatmap.HitObjects)
            {
                int lane = resolveLane(hit);
                var note = new DrawableNote(hit, lane)
                {
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.Centre,
                };

                noteLayer.Add(note);
                notes.Add(note);
            }

            totalNotes = notes.Count;
        }

        public HitResult HandleInput(int lane, double inputTime)
        {
            var candidate = notes
                .Where(n => n.Lane == lane && !n.IsJudged)
                .OrderBy(n => Math.Abs(n.HitTime - inputTime))
                .FirstOrDefault();

            if (candidate == null)
                return HitResult.None;

            double offset = inputTime - candidate.HitTime;
            double absOffset = Math.Abs(offset);

            HitResult result;
            if (absOffset <= perfectWindow)
                result = HitResult.Perfect;
            else if (absOffset <= greatWindow)
                result = HitResult.Great;
            else if (absOffset <= goodWindow)
                result = HitResult.Good;
            else if (absOffset <= mehWindow)
                result = HitResult.Meh;
            else
                return HitResult.None;

            applyResult(candidate, result, offset);
            return result;
        }

        protected override void Update()
        {
            base.Update();

            double currentTime = currentTimeProvider();
            float laneWidth = DrawWidth / laneCount;
            float hitLineY = DrawHeight * 0.85f;
            float spawnTop = DrawHeight * 0.05f;
            float travelDistance = hitLineY - spawnTop;

            foreach (var note in notes)
            {
                if (note.IsJudged)
                    continue;

                double timeUntilHit = note.HitTime - currentTime;
                double progress = 1 - (timeUntilHit / approachDuration);

                float clampedProgress = (float)Math.Clamp(progress, 0, 1.1);
                float y = hitLineY - travelDistance * (1 - clampedProgress);
                y = Math.Clamp(y, spawnTop, hitLineY + 40);

                float x = laneWidth * note.Lane + laneWidth / 2f;

                note.Position = new Vector2(x, y);
                note.Alpha = timeUntilHit < -200 ? 0 : 1;

                if (timeUntilHit < -missWindow)
                    applyResult(note, HitResult.Miss, timeUntilHit);
            }
        }

        private void applyResult(DrawableNote note, HitResult result, double offset)
        {
            if (note.IsJudged)
                return;

            note.ApplyResult(result);

            judgedNotes++;
            if (result == HitResult.Miss)
                combo = 0;
            else
                combo++;

            comboText.Text = $"Combo: {combo}";

            accuracyScore += scoreFor(result);
            updateAccuracyText();

            var accent = note.AccentColour;
            judgementText.Text = result switch
            {
                HitResult.Perfect => "Perfect",
                HitResult.Great => "Great",
                HitResult.Good => "Good",
                HitResult.Meh => "Meh",
                HitResult.Miss => "Miss",
                _ => string.Empty
            };

            judgementText.FlashColour(accent, 80, Easing.OutQuint);
        }

        private void updateAccuracyText()
        {
            if (totalNotes == 0 || judgedNotes == 0)
            {
                accuracyText.Text = "Accuracy: --";
                return;
            }

            double accuracy = Math.Clamp(accuracyScore / totalNotes, 0, 1) * 100;
            accuracyText.Text = $"Accuracy: {accuracy:0.00}%";
        }

        private static double scoreFor(HitResult result) => result switch
        {
            HitResult.Perfect => 1.0,
            HitResult.Great => 0.8,
            HitResult.Good => 0.5,
            HitResult.Meh => 0.2,
            _ => 0,
        };

        private static int resolveLane(HitObject hit)
        {
            if (hit.Lane is int lane)
                return Math.Clamp(lane, 0, laneCount - 1);

            string key = hit.Component.ToLowerInvariant();

            if (componentLaneMap.TryGetValue(key, out lane))
                return lane;

            return 3; // default lane
        }

        private static readonly Dictionary<string, int> componentLaneMap = new Dictionary<string, int>
        {
            {"kick", 0},
            {"hihat_pedal", 1},
            {"snare", 2},
            {"hihat", 3},
            {"hihat_closed", 3},
            {"hihat_open", 3},
            {"tom_high", 4},
            {"tom_mid", 5},
            {"tom_low", 5},
            {"crash", 6},
            {"crash2", 6},
            {"ride", 6},
            {"ride_bell", 6},
            {"china", 6},
            {"splash", 6}
        };

        public enum HitResult
        {
            None,
            Miss,
            Meh,
            Good,
            Great,
            Perfect
        }
    }

    internal partial class DrawableNote : CompositeDrawable
    {
        private static readonly Dictionary<string, Color4> componentColours = new Dictionary<string, Color4>
        {
            {"kick", new Color4(255, 105, 97, 255)},
            {"snare", new Color4(64, 156, 255, 255)},
            {"hihat", new Color4(255, 221, 89, 255)},
            {"hihat_closed", new Color4(255, 221, 89, 255)},
            {"hihat_open", new Color4(255, 195, 0, 255)},
            {"tom_high", new Color4(138, 201, 38, 255)},
            {"tom_mid", new Color4(76, 201, 240, 255)},
            {"tom_low", new Color4(128, 128, 255, 255)},
            {"crash", new Color4(255, 159, 243, 255)},
            {"ride", new Color4(250, 177, 160, 255)},
            {"china", new Color4(255, 204, 92, 255)}
        };

        public double HitTime { get; }
        public int Lane { get; }
        public bool IsJudged { get; private set; }
        public string ComponentName { get; }
        public Color4 AccentColour { get; }

        public DrawableNote(HitObject hitObject, int lane)
        {
            HitTime = hitObject.Time;
            ComponentName = hitObject.Component;
            Lane = lane;

            Size = new Vector2(60, 26);
            CornerRadius = 8;
            Masking = true;

            AccentColour = componentColours.TryGetValue(hitObject.Component.ToLowerInvariant(), out var colour)
                ? colour
                : new Color4(180, 180, 200, 255);

            Colour = AccentColour;

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = AccentColour
                }
            };
        }

        public void ApplyResult(GameplayPlayfield.HitResult result)
        {
            if (IsJudged)
                return;

            IsJudged = true;

            switch (result)
            {
                case GameplayPlayfield.HitResult.Miss:
                    this.FlashColour(new Color4(255, 80, 90, 255), 120, Easing.OutQuint);
                    this.FadeColour(new Color4(120, 20, 30, 200), 120, Easing.OutQuint);
                    this.Delay(150).FadeOut(180).Expire();
                    break;

                default:
                    this.FadeOut(180).ScaleTo(1.2f, 180, Easing.OutQuint).Expire();
                    break;
            }
        }
    }
}
