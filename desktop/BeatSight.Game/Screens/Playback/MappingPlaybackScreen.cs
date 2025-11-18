using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Audio;
using osu.Framework.Audio.Track;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.IO.Stores;
using osu.Framework.Logging;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback
{
    public partial class MappingPlaybackScreen : Screen
    {
        private readonly string? requestedBeatmapPath;

        private Beatmap? beatmap;
        private string? beatmapPath;
        private Track? track;
        private double cachedDurationMs;
        private double fallbackElapsed;
        private bool fallbackRunning;
        private bool isPlaying;

        private SpriteText titleText = null!;
        private SpriteText subtitleText = null!;
        private SpriteText statusText = null!;
        private SpriteText metadataText = null!;
        private BasicButton playPauseButton = null!;
        private BasicButton restartButton = null!;
        private BasicButton mixToggleButton = null!;
        private SeekSlider progressSlider = null!;
        private Bindable<double> sliderBindable = null!;
        private PlaybackTimeline timeline = null!;

        private StorageBackedResourceStore? storageResourceStore;
        private ITrackStore? storageTrackStore;
        private string? cachedFullMixPath;
        private string? cachedDrumStemPath;
        private bool drumStemAvailable;
        private bool drumsOnlyMode;
        private bool suppressSliderUpdate;

        private Bindable<bool> drumStemPreferredSetting = null!;
        private Bindable<LanePreset> lanePresetSetting = null!;
        private LaneLayout currentLaneLayout = LaneLayoutFactory.Create(LanePreset.DrumSevenLane);

        [Resolved]
        private AudioManager audioManager { get; set; } = null!;

        [Resolved]
        private GameHost host { get; set; } = null!;

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        public MappingPlaybackScreen(string? beatmapPath = null)
        {
            requestedBeatmapPath = beatmapPath;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            drumStemPreferredSetting = config.GetBindable<bool>(BeatSightSetting.DrumStemPlaybackOnly);
            lanePresetSetting = config.GetBindable<LanePreset>(BeatSightSetting.LanePreset);

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(18, 21, 30, 255)
                },
                new ScreenEdgeContainer
                {
                    EdgePadding = new MarginPadding { Horizontal = 60, Vertical = 40 },
                    Content = new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 18),
                        Children = new Drawable[]
                        {
                            titleText = new SpriteText
                            {
                                Font = BeatSightFont.Title(42f),
                                Colour = Color4.White
                            },
                            subtitleText = new SpriteText
                            {
                                Font = BeatSightFont.Subtitle(20f),
                                Colour = new Color4(200, 205, 220, 255)
                            },
                            metadataText = new SpriteText
                            {
                                Font = BeatSightFont.Body(18f),
                                Colour = new Color4(170, 175, 195, 255)
                            },
                            timeline = new PlaybackTimeline
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 220
                            },
                            progressSlider = new SeekSlider
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 18
                            },
                            new FillFlowContainer
                            {
                                AutoSizeAxes = Axes.Both,
                                Direction = FillDirection.Horizontal,
                                Spacing = new Vector2(12, 0),
                                Children = new Drawable[]
                                {
                                    playPauseButton = new BasicButton
                                    {
                                        Text = "Play",
                                        Width = 120,
                                        Height = 44,
                                        BackgroundColour = new Color4(90, 155, 110, 255),
                                        CornerRadius = 8,
                                        Masking = true
                                    },
                                    restartButton = new BasicButton
                                    {
                                        Text = "Restart",
                                        Width = 120,
                                        Height = 44,
                                        BackgroundColour = new Color4(100, 120, 180, 255),
                                        CornerRadius = 8,
                                        Masking = true
                                    },
                                    mixToggleButton = new BasicButton
                                    {
                                        Text = "Audio: Full Mix",
                                        Width = 180,
                                        Height = 44,
                                        BackgroundColour = new Color4(105, 105, 140, 255),
                                        CornerRadius = 8,
                                        Masking = true
                                    }
                                }
                            },
                            statusText = new SpriteText
                            {
                                Font = BeatSightFont.Caption(18f),
                                Colour = new Color4(180, 190, 210, 255)
                            }
                        }
                    }
                }
            };

            sliderBindable = progressSlider.Current;
            sliderBindable.BindValueChanged(e =>
            {
                if (suppressSliderUpdate)
                    return;

                seekToNormalised(e.NewValue);
            });

            playPauseButton.Action = togglePlayPause;
            restartButton.Action = () => startPlayback(restart: true);
            mixToggleButton.Action = toggleDrumMix;

            drumStemPreferredSetting.BindValueChanged(e => applyDrumStemPreference(e.NewValue));
            applyDrumStemPreference(drumStemPreferredSetting.Value);

            lanePresetSetting.BindValueChanged(e => onLanePresetChanged(e.NewValue));
            onLanePresetChanged(lanePresetSetting.Value);

            loadBeatmap();
        }

        private void loadBeatmap()
        {
            statusText.Text = string.Empty;

            if (!tryResolveBeatmapPath(out string? path) || string.IsNullOrWhiteSpace(path))
            {
                titleText.Text = "No beatmap selected";
                subtitleText.Text = string.Empty;
                metadataText.Text = string.Empty;
                disableTransport();
                return;
            }

            try
            {
                beatmap = BeatmapLoader.LoadFromFile(path);
                beatmapPath = path;
                DrumLaneHeuristics.ApplyToBeatmap(beatmap, currentLaneLayout);

                titleText.Text = beatmap.Metadata.Title;
                subtitleText.Text = $"{beatmap.Metadata.Artist} • mapped by {beatmap.Metadata.Creator}";
                metadataText.Text = buildMetadataSummary(beatmap);

                prepareAudioCaches(Path.Combine(Path.GetDirectoryName(path) ?? string.Empty, beatmap.Audio.Filename));
                refreshTrackFromCache();
                cachedDurationMs = resolveDurationMs();
                timeline.BuildTimeline(beatmap, cachedDurationMs, currentLaneLayout);
                statusText.Text = "Ready";
                enableTransport();
            }
            catch (Exception ex)
            {
                Logger.Error(ex, "Failed to load beatmap playback");
                titleText.Text = "Failed to load beatmap";
                subtitleText.Text = ex.Message;
                metadataText.Text = string.Empty;
                disableTransport();
            }
        }

        private double resolveDurationMs()
        {
            double beatmapDuration = beatmap?.Audio.Duration ?? 0;
            if (track != null && track.Length > 0)
                return track.Length;

            return beatmapDuration > 0 ? beatmapDuration : 1;
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

        private string buildMetadataSummary(Beatmap beatmap)
        {
            var tags = beatmap.Metadata.Tags.Any()
                ? string.Join(", ", beatmap.Metadata.Tags)
                : "no tags";

            string difficulty = beatmap.Metadata.Difficulty > 0
                ? $"★ {beatmap.Metadata.Difficulty:0.0}"
                : "unrated";

            return $"BPM {beatmap.Timing.Bpm:0} • Offset {beatmap.Timing.Offset} ms • {difficulty} • Tags: {tags}";
        }

        private void enableTransport()
        {
            playPauseButton.Enabled.Value = true;
            restartButton.Enabled.Value = true;
            mixToggleButton.Enabled.Value = drumStemAvailable;
            updateMixToggle();
        }

        private void disableTransport()
        {
            playPauseButton.Enabled.Value = false;
            restartButton.Enabled.Value = false;
            mixToggleButton.Enabled.Value = false;
            sliderBindable.Value = 0;
            timeline.UpdateProgress(0);
            stopPlayback();
        }

        private void togglePlayPause()
        {
            if (isPlaying)
            {
                pausePlayback();
            }
            else
            {
                startPlayback(restart: false);
            }
        }

        private void startPlayback(bool restart)
        {
            if (track == null && !string.IsNullOrEmpty(cachedFullMixPath))
                refreshTrackFromCache();

            resetCompletionState();

            if (restart)
            {
                if (track != null)
                    track.Seek(0);
                fallbackElapsed = 0;
            }

            if (track != null)
            {
                track.Start();
                isPlaying = true;
            }
            else
            {
                fallbackRunning = true;
                isPlaying = true;
            }

            playPauseButton.Text = "Pause";
            statusText.Text = "Playing";
        }

        private void pausePlayback()
        {
            if (track != null)
                track.Stop();

            fallbackRunning = false;
            isPlaying = false;
            playPauseButton.Text = "Play";
            statusText.Text = "Paused";
        }

        private void stopPlayback()
        {
            if (track != null)
            {
                track.Stop();
                track.Completed -= onTrackCompleted;
                track.Dispose();
                track = null;
            }

            fallbackRunning = false;
            isPlaying = false;
            playPauseButton.Text = "Play";
        }

        private void resetCompletionState()
        {
            lineCompletionAnnounced = false;
        }

        private bool lineCompletionAnnounced;

        protected override void Update()
        {
            base.Update();

            double elapsed;

            if (track != null)
            {
                elapsed = track.CurrentTime;
            }
            else
            {
                if (fallbackRunning)
                    fallbackElapsed += Time.Elapsed;

                elapsed = fallbackElapsed;
            }

            if (cachedDurationMs <= 0)
                cachedDurationMs = resolveDurationMs();

            double normalised = Math.Clamp(elapsed / Math.Max(1, cachedDurationMs), 0, 1);
            suppressSliderUpdate = true;
            sliderBindable.Value = normalised;
            suppressSliderUpdate = false;
            timeline.UpdateProgress(normalised);

            if (normalised >= 1 && !lineCompletionAnnounced)
            {
                statusText.Text = "Playback complete";
                playPauseButton.Text = "Play";
                isPlaying = false;
                lineCompletionAnnounced = true;
            }
        }

        private void seekToNormalised(double normalised)
        {
            if (cachedDurationMs <= 0)
                cachedDurationMs = resolveDurationMs();

            double targetMs = Math.Clamp(normalised, 0, 1) * cachedDurationMs;

            if (track != null)
            {
                track.Seek(targetMs);
                if (!isPlaying)
                    track.Stop();
            }
            else
            {
                fallbackElapsed = targetMs;
            }

            timeline.UpdateProgress(Math.Clamp(normalised, 0, 1));
            statusText.Text = $"Position {(int)targetMs} ms";
        }

        private void onTrackCompleted()
        {
            Schedule(() =>
            {
                isPlaying = false;
                playPauseButton.Text = "Play";
                statusText.Text = "Playback complete";
            });
        }

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);
            startPlayback(restart: true);
        }

        public override void OnSuspending(ScreenTransitionEvent e)
        {
            base.OnSuspending(e);
            pausePlayback();
        }

        public override void OnResuming(ScreenTransitionEvent e)
        {
            base.OnResuming(e);
            statusText.Text = "Ready";
        }

        public override bool OnExiting(ScreenExitEvent e)
        {
            stopPlayback();
            return base.OnExiting(e);
        }

        protected override void Dispose(bool isDisposing)
        {
            stopPlayback();
            storageTrackStore?.Dispose();
            storageResourceStore?.Dispose();
            base.Dispose(isDisposing);
        }

        private void ensureAudioStores()
        {
            storageResourceStore ??= new StorageBackedResourceStore(host.Storage);
            storageTrackStore ??= audioManager.GetTrackStore(storageResourceStore);
        }

        private void prepareAudioCaches(string resolvedAudioPath)
        {
            ensureAudioStores();

            cachedFullMixPath = null;
            cachedDrumStemPath = null;
            drumStemAvailable = false;

            if (beatmap == null || string.IsNullOrWhiteSpace(resolvedAudioPath) || !File.Exists(resolvedAudioPath))
            {
                statusText.Text = "Audio file missing";
                return;
            }

            string cacheFolder = "PlaybackAudio";
            string cachePrefix = sanitizeFileComponent(beatmap.Metadata.BeatmapId ?? string.Empty);

            if (string.IsNullOrEmpty(cachePrefix))
                cachePrefix = sanitizeFileComponent(Path.GetFileNameWithoutExtension(resolvedAudioPath));

            if (string.IsNullOrEmpty(cachePrefix))
                cachePrefix = "beatmap";

            string extension = Path.GetExtension(resolvedAudioPath);
            string cachedName = $"{cachePrefix}_full{extension}";
            string relativePath = Path.Combine(cacheFolder, cachedName).Replace(Path.DirectorySeparatorChar, '/');
            string absolutePath = host.Storage.GetFullPath(relativePath.Replace('/', Path.DirectorySeparatorChar));

            string? mixDirectory = Path.GetDirectoryName(absolutePath);
            if (!string.IsNullOrEmpty(mixDirectory))
                Directory.CreateDirectory(mixDirectory);

            File.Copy(resolvedAudioPath, absolutePath, overwrite: true);
            cachedFullMixPath = relativePath;

            string? drumStemSource = resolveDrumStemSourcePath();
            if (!string.IsNullOrEmpty(drumStemSource) && File.Exists(drumStemSource))
            {
                string drumExtension = Path.GetExtension(drumStemSource);
                string drumCachedName = $"{cachePrefix}_drums{drumExtension}";
                string drumRelativePath = Path.Combine(cacheFolder, drumCachedName).Replace(Path.DirectorySeparatorChar, '/');
                string drumAbsolutePath = host.Storage.GetFullPath(drumRelativePath.Replace('/', Path.DirectorySeparatorChar));

                string? drumDirectory = Path.GetDirectoryName(drumAbsolutePath);
                if (!string.IsNullOrEmpty(drumDirectory))
                    Directory.CreateDirectory(drumDirectory);

                try
                {
                    File.Copy(drumStemSource, drumAbsolutePath, overwrite: true);
                    cachedDrumStemPath = drumRelativePath;
                    drumStemAvailable = true;
                }
                catch (Exception ex)
                {
                    Logger.Log($"[Playback] Failed to cache drum stem '{drumStemSource}': {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
                    cachedDrumStemPath = null;
                    drumStemAvailable = false;
                }
            }

            drumsOnlyMode = drumStemAvailable && (drumStemPreferredSetting?.Value ?? false);
            updateMixToggle();
        }

        private string? resolveDrumStemSourcePath()
        {
            if (beatmap == null || string.IsNullOrWhiteSpace(beatmap.Audio.DrumStem))
                return null;

            string path = beatmap.Audio.DrumStem!;

            if (!Path.IsPathRooted(path))
            {
                string baseDirectory = Path.GetDirectoryName(beatmapPath ?? string.Empty) ?? string.Empty;
                path = Path.Combine(baseDirectory, path);
            }

            return path;
        }

        private void refreshTrackFromCache()
        {
            ensureAudioStores();

            disposeTrack();

            string? targetRelativePath = drumsOnlyMode && drumStemAvailable ? cachedDrumStemPath : cachedFullMixPath;

            if (string.IsNullOrEmpty(targetRelativePath) || storageTrackStore == null)
            {
                track = null;
                return;
            }

            var loadedTrack = storageTrackStore.Get(targetRelativePath);

            if (loadedTrack == null)
            {
                Logger.Log($"[Playback] Unable to resolve cached track '{targetRelativePath}'", LoggingTarget.Runtime, LogLevel.Debug);
                track = null;
                return;
            }

            track = loadedTrack;
            track.Completed += onTrackCompleted;
            cachedDurationMs = track.Length;
        }

        private void disposeTrack()
        {
            if (track == null)
                return;

            track.Completed -= onTrackCompleted;
            track.Dispose();
            track = null;
        }

        private void toggleDrumMix()
        {
            if (!drumStemAvailable)
                return;

            drumStemPreferredSetting.Value = !drumStemPreferredSetting.Value;
        }

        private void applyDrumStemPreference(bool preferDrumsOnly)
        {
            setDrumMixMode(preferDrumsOnly);
        }

        private void setDrumMixMode(bool drumsOnlyRequested)
        {
            bool targetDrumsOnly = drumsOnlyRequested && drumStemAvailable;

            if (drumsOnlyMode == targetDrumsOnly)
            {
                updateMixToggle();
                return;
            }

            double resumeTime = track?.CurrentTime ?? fallbackElapsed;
            bool wasPlaying = isPlaying || fallbackRunning;

            drumsOnlyMode = targetDrumsOnly;

            refreshTrackFromCache();

            if (track != null)
            {
                track.Seek(Math.Max(0, resumeTime));
                if (wasPlaying)
                    track.Start();
                isPlaying = wasPlaying;
                fallbackRunning = false;
            }
            else
            {
                fallbackElapsed = Math.Max(0, resumeTime);
                fallbackRunning = wasPlaying;
                isPlaying = wasPlaying;
            }

            updateMixToggle();
        }

        private void updateMixToggle()
        {
            mixToggleButton.Text = drumsOnlyMode ? "Audio: Drums Only" : "Audio: Full Mix";
            mixToggleButton.Enabled.Value = drumStemAvailable;
        }

        private void onLanePresetChanged(LanePreset preset)
        {
            currentLaneLayout = LaneLayoutFactory.Create(preset);

            if (beatmap != null)
            {
                DrumLaneHeuristics.ApplyToBeatmap(beatmap, currentLaneLayout);
                timeline.BuildTimeline(beatmap, cachedDurationMs, currentLaneLayout);
            }
        }

        private static string sanitizeFileComponent(string value)
        {
            if (string.IsNullOrEmpty(value))
                return string.Empty;

            var invalid = Path.GetInvalidFileNameChars();
            var filtered = new string(value.Where(c => !invalid.Contains(c)).ToArray());
            return string.IsNullOrEmpty(filtered) ? string.Empty : filtered;
        }

        protected override bool OnKeyDown(osu.Framework.Input.Events.KeyDownEvent e)
        {
            if (e.Key == osuTK.Input.Key.Space && !e.Repeat)
            {
                togglePlayPause();
                return true;
            }

            if (e.Key == osuTK.Input.Key.Home)
            {
                startPlayback(restart: true);
                return true;
            }

            return base.OnKeyDown(e);
        }

        private partial class SeekSlider : BeatSightSliderBar
        {
            public SeekSlider()
            {
                Current = new BindableDouble
                {
                    MinValue = 0,
                    MaxValue = 1,
                    Precision = 0.001
                };
            }
        }

        private partial class PlaybackTimeline : CompositeDrawable
        {
            private readonly Container laneContent;
            private Container[] laneColumns = Array.Empty<Container>();
            private Box? progressMarker;
            private double durationMs = 1;

            private static readonly Dictionary<string, Color4> componentColours = new(StringComparer.OrdinalIgnoreCase)
            {
                {"kick", new Color4(255, 145, 120, 255)},
                {"snare", new Color4(255, 220, 120, 255)},
                {"hihat", new Color4(140, 230, 255, 255)},
                {"ride", new Color4(150, 200, 255, 255)},
                {"crash", new Color4(200, 150, 255, 255)},
                {"tom", new Color4(170, 255, 170, 255)}
            };

            private static readonly DrumComponentCategory[] labelPriority =
            {
                DrumComponentCategory.Kick,
                DrumComponentCategory.Snare,
                DrumComponentCategory.HiHatClosed,
                DrumComponentCategory.HiHatOpen,
                DrumComponentCategory.HiHatPedal,
                DrumComponentCategory.TomHigh,
                DrumComponentCategory.TomMid,
                DrumComponentCategory.TomLow,
                DrumComponentCategory.Ride,
                DrumComponentCategory.Crash,
                DrumComponentCategory.China,
                DrumComponentCategory.Splash,
                DrumComponentCategory.Cowbell,
                DrumComponentCategory.Percussion
            };

            public PlaybackTimeline()
            {
                Masking = true;
                CornerRadius = 10;

                InternalChildren = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(26, 30, 42, 255)
                    },
                    laneContent = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Left = 4, Right = 4, Top = 8, Bottom = 8 }
                    }
                };
            }

            public void BuildTimeline(Beatmap beatmap, double durationMs, LaneLayout layout)
            {
                if (beatmap == null)
                    throw new ArgumentNullException(nameof(beatmap));
                if (layout == null)
                    throw new ArgumentNullException(nameof(layout));

                this.durationMs = Math.Max(durationMs, 1);

                if (progressMarker != null)
                {
                    RemoveInternal(progressMarker, true);
                    progressMarker = null;
                }

                laneContent.Clear();

                int laneCount = layout.LaneCount;
                if (laneCount <= 0)
                {
                    laneColumns = Array.Empty<Container>();
                    return;
                }

                var labels = buildLaneLabels(layout);
                laneColumns = new Container[laneCount];

                var laneFlow = new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Direction = FillDirection.Horizontal,
                    Spacing = new Vector2(5, 0)
                };

                laneContent.Add(laneFlow);

                for (int i = 0; i < laneCount; i++)
                {
                    var lane = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Width = 1f / laneCount,
                        Masking = true,
                        CornerRadius = 8,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = new Color4(30, 34, 46, 255)
                            },
                            new SpriteText
                            {
                                Anchor = Anchor.TopCentre,
                                Origin = Anchor.TopCentre,
                                Y = 6,
                                Font = BeatSightFont.Button(16f),
                                Colour = new Color4(210, 215, 230, 255),
                                Text = labels[i]
                            }
                        }
                    };

                    laneColumns[i] = lane;
                    laneFlow.Add(lane);
                }

                foreach (var hit in beatmap.HitObjects.OrderBy(h => h.Time))
                {
                    int lane = resolveLaneForHit(hit, layout);
                    if (lane < 0 || lane >= laneColumns.Length)
                        continue;

                    addHitMarker(laneColumns[lane], hit);
                }

                progressMarker = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 2,
                    Colour = new Color4(255, 255, 255, 160),
                    RelativePositionAxes = Axes.Y
                };

                AddInternal(progressMarker);
            }

            public void UpdateProgress(double normalised)
            {
                if (progressMarker == null)
                    return;

                progressMarker.Y = (float)Math.Clamp(normalised, 0, 1);
            }

            private int resolveLaneForHit(HitObject hit, LaneLayout layout)
            {
                if (hit.Lane.HasValue)
                    return layout.ClampLane(hit.Lane.Value);

                return DrumLaneHeuristics.ResolveLane(hit.Component, layout);
            }

            private void addHitMarker(Container lane, HitObject hit)
            {
                if (durationMs <= 0)
                    return;

                double normalised = Math.Clamp(hit.Time / durationMs, 0, 1);
                Color4 colour = resolveColour(hit.Component);

                var marker = new Circle
                {
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.Centre,
                    Size = new Vector2(12),
                    Colour = colour,
                    RelativePositionAxes = Axes.Y,
                    Y = (float)normalised + 0.02f
                };

                lane.Add(marker);
            }

            private string[] buildLaneLabels(LaneLayout layout)
            {
                var labels = new string[layout.LaneCount];

                for (int lane = 0; lane < layout.LaneCount; lane++)
                {
                    var names = new List<string>();

                    foreach (var category in labelPriority)
                    {
                        if (!layout.Categories.TryGetValue(category, out var lanes))
                            continue;

                        if (!lanes.Contains(lane))
                            continue;

                        string friendly = getFriendlyName(category);
                        if (!names.Contains(friendly))
                            names.Add(friendly);

                        if (names.Count == 2)
                            break;
                    }

                    labels[lane] = names.Count switch
                    {
                        0 => $"Lane {lane + 1}",
                        1 => names[0],
                        _ => string.Join(" / ", names)
                    };
                }

                return labels;
            }

            private static string getFriendlyName(DrumComponentCategory category) => category switch
            {
                DrumComponentCategory.Kick => "Kick",
                DrumComponentCategory.Snare => "Snare",
                DrumComponentCategory.HiHatClosed => "Hi-Hat",
                DrumComponentCategory.HiHatOpen => "Hi-Hat",
                DrumComponentCategory.HiHatPedal => "Hi-Hat Pedal",
                DrumComponentCategory.TomHigh => "High Tom",
                DrumComponentCategory.TomMid => "Mid Tom",
                DrumComponentCategory.TomLow => "Floor Tom",
                DrumComponentCategory.Ride => "Ride",
                DrumComponentCategory.Crash => "Crash",
                DrumComponentCategory.China => "China",
                DrumComponentCategory.Splash => "Splash",
                DrumComponentCategory.Cowbell => "Cowbell",
                DrumComponentCategory.Percussion => "FX",
                _ => category.ToString()
            };

            private Color4 resolveColour(string component)
            {
                string normalised = component.ToLowerInvariant();

                if (componentColours.TryGetValue(normalised, out var colour))
                    return colour;

                if (normalised.Contains("kick") || normalised.Contains("bass"))
                    return componentColours["kick"];
                if (normalised.Contains("snare"))
                    return componentColours["snare"];
                if (normalised.Contains("hat"))
                    return componentColours["hihat"];
                if (normalised.Contains("ride"))
                    return componentColours["ride"];
                if (normalised.Contains("crash") || normalised.Contains("china"))
                    return componentColours["crash"];
                if (normalised.Contains("tom"))
                    return componentColours["tom"];

                return new Color4(220, 220, 220, 255);
            }
        }
    }
}
