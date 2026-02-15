using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield.Views
{
    /// <summary>
    /// A playback position highlighter for the Manuscript view.
    /// 
    /// Creates a semi-transparent colored overlay that sweeps horizontally across
    /// the staff. The right edge of the highlight indicates the current playback
    /// position - when it reaches a note's horizontal position, that note should
    /// be played.
    /// 
    /// This provides visual timing guidance for musicians following the notation,
    /// making it easier to anticipate when notes need to be hit.
    /// </summary>
    public partial class ManuscriptPlaybackHighlighter : CompositeDrawable
    {
        #region Configuration

        /// <summary>The color of the cursor body.</summary>
        private static readonly Color4 HighlightColor = new Color4(120, 255, 172, 20);

        /// <summary>The color of the leading edge indicator.</summary>
        private static readonly Color4 EdgeColor = new Color4(144, 255, 190, 228);

        /// <summary>The color of the "now playing" glow.</summary>
        private static readonly Color4 GlowColor = new Color4(116, 255, 176, 94);

        /// <summary>Secondary forward lookahead tint on the right side of the cursor.</summary>
        private static readonly Color4 PreviewColor = new Color4(126, 214, 255, 24);

        /// <summary>Width of the leading edge line.</summary>
        private const float EdgeLineWidth = 2.4f;

        /// <summary>Width of the glow effect around the edge.</summary>
        private const float GlowWidth = 10f;

        /// <summary>How many milliseconds of audio the highlight covers (lookahead window).</summary>
        private const double DefaultLookaheadMs = 500;

        /// <summary>Fallback cursor trail width ratio when timeline duration is unavailable.</summary>
        private const float FallbackTrailWidthRatio = 0.07f;

        #endregion

        #region Visual Components

        private Box highlightOverlay = null!;
        private Box previewOverlay = null!;
        private Box leadingEdge = null!;
        private Box leadingGlow = null!;
        private Box topTick = null!;
        private Box bottomTick = null!;
        private Container noteHighlightContainer = null!;

        #endregion

        #region State

        private double currentTimeMs;
        private double lookaheadMs = DefaultLookaheadMs;
        private float staffStartX;
        private float staffEndX;
        private float staffCenterX;
        private bool hasTimelineWindow;
        private double timelineStartMs;
        private double timelineDurationMs;
        private float timelineLeftX;
        private float timelineRightX;
        private float timelinePlayheadX;
        private List<HitObjectInfo>? currentHitObjects;
        private readonly Dictionary<int, NoteHighlightRing> activeHighlights = new();

        #endregion

        #region Bindables

        /// <summary>Whether the highlighter is enabled.</summary>
        public readonly BindableBool Enabled = new BindableBool(true);

        /// <summary>The opacity of the highlight overlay (0-1).</summary>
        public readonly BindableFloat HighlightOpacity = new BindableFloat(0.30f)
        {
            MinValue = 0f,
            MaxValue = 1f
        };

        /// <summary>Whether to show per-note glow rings.</summary>
        public readonly BindableBool ShowNoteHighlights = new BindableBool(false);

        #endregion

        public ManuscriptPlaybackHighlighter()
        {
            RelativeSizeAxes = Axes.Both;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            // Main cursor body.
            highlightOverlay = new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = 0,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Colour = ColourInfo.GradientHorizontal(
                    Color4.Transparent,
                    HighlightColor)
            };

            // Forward lookahead tint (subtle) on the right side of the playhead.
            previewOverlay = new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = 0,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Colour = ColourInfo.GradientHorizontal(
                    PreviewColor,
                    Color4.Transparent)
            };

            // Glow effect at the leading edge (blurred appearance)
            leadingGlow = new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = GlowWidth,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Colour = ColourInfo.GradientHorizontal(
                    Color4.Transparent,
                    GlowColor),
                Blending = BlendingParameters.Additive
            };

            // Sharp leading edge line
            leadingEdge = new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = EdgeLineWidth + 1f,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Colour = EdgeColor
            };

            topTick = new Box
            {
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopCentre,
                Width = 1.8f,
                Height = 11f,
                Colour = EdgeColor
            };

            bottomTick = new Box
            {
                Anchor = Anchor.TopLeft,
                Origin = Anchor.BottomCentre,
                Width = 1.8f,
                Height = 11f,
                Colour = EdgeColor
            };

            // Container for per-note highlight rings
            noteHighlightContainer = new Container
            {
                RelativeSizeAxes = Axes.Both
            };

            InternalChildren = new Drawable[]
            {
                highlightOverlay,
                previewOverlay,
                leadingGlow,
                leadingEdge,
                topTick,
                bottomTick,
                noteHighlightContainer
            };

            // Bind to enabled state
            Enabled.BindValueChanged(e => Alpha = e.NewValue ? 1f : 0f, true);
            HighlightOpacity.BindValueChanged(e =>
            {
                highlightOverlay.Colour = ColourInfo.GradientHorizontal(
                    Color4.Transparent,
                    DesignSystem.WithOpacity(HighlightColor, e.NewValue));
            }, true);
        }

        /// <summary>
        /// Configure the staff dimensions for proper positioning.
        /// </summary>
        /// <param name="centerX">The center X position of the staff.</param>
        /// <param name="staffWidth">The total width of the staff area.</param>
        public void SetStaffDimensions(float centerX, float staffWidth)
        {
            staffCenterX = centerX;
            staffStartX = centerX - staffWidth / 2f;
            staffEndX = centerX + staffWidth / 2f;

            if (!hasTimelineWindow)
                timelinePlayheadX = staffStartX;
        }

        /// <summary>
        /// Supplies the active sheet timeline window so the cursor follows musical time, not a synthetic loop.
        /// </summary>
        public void SetTimelineWindow(double startTimeMs, double durationMs, float playheadX, float leftX, float rightX)
        {
            timelineStartMs = startTimeMs;
            timelineDurationMs = durationMs;
            timelinePlayheadX = playheadX;
            timelineLeftX = leftX;
            timelineRightX = rightX;
            hasTimelineWindow = durationMs > 1 && rightX > leftX;
        }

        /// <summary>
        /// Set the lookahead window (how far ahead the highlight extends).
        /// </summary>
        public void SetLookahead(double milliseconds)
        {
            lookaheadMs = Math.Max(100, milliseconds);
        }

        /// <summary>
        /// Load hit objects for per-note highlighting.
        /// </summary>
        public void LoadHitObjects(List<HitObjectInfo> hitObjects)
        {
            currentHitObjects = hitObjects;
            ClearNoteHighlights();
        }

        /// <summary>
        /// Update the highlighter based on current playback position.
        /// </summary>
        /// <param name="timeMs">Current playback time in milliseconds.</param>
        /// <param name="bpm">Current beats per minute for timing calculations.</param>
        public void UpdatePlaybackPosition(double timeMs, double bpm)
        {
            currentTimeMs = timeMs;
            float leftBound = hasTimelineWindow ? timelineLeftX : staffStartX;
            float rightBound = hasTimelineWindow ? timelineRightX : staffEndX;
            float edgeX = Math.Clamp(resolveCursorX(timeMs, bpm), leftBound, rightBound);
            float timelineWidth = Math.Max(1f, rightBound - leftBound);
            float staffWidth = Math.Max(1f, staffEndX - staffStartX);
            float cursorWidth = Math.Clamp(staffWidth * 0.0034f, 2.8f, 5.2f);
            float glowWidth = Math.Clamp(cursorWidth * 2.4f, 9f, 13f);
            float overlayWidth = ResolvePlaybackCursorTrailWidth(timelineWidth, timelineDurationMs, bpm, lookaheadMs, hasTimelineWindow);
            float overlayStartX = Math.Max(leftBound, edgeX - overlayWidth);
            float overlayClampedWidth = Math.Max(cursorWidth, edgeX - overlayStartX);
            highlightOverlay.Width = overlayClampedWidth;
            highlightOverlay.X = overlayStartX;

            float previewWidth = Math.Clamp(overlayWidth * 0.16f, 7f, 36f);
            float previewClampedWidth = Math.Max(0f, Math.Min(previewWidth, rightBound - edgeX));
            previewOverlay.Width = previewClampedWidth;
            previewOverlay.X = edgeX;
            previewOverlay.Alpha = previewClampedWidth > 0.1f ? 0.48f : 0f;

            leadingEdge.Width = Math.Clamp(cursorWidth * 0.78f, 1.8f, 3.2f);
            leadingEdge.X = edgeX - leadingEdge.Width * 0.5f;

            leadingGlow.Width = glowWidth;
            leadingGlow.X = edgeX - glowWidth;

            topTick.X = edgeX;
            topTick.Y = 3f;
            topTick.Alpha = 0.92f;

            bottomTick.X = edgeX;
            bottomTick.Y = DrawHeight - 3f;
            bottomTick.Alpha = 0.92f;

            // Per-note glow rings are intentionally disabled by default for sheet readability.
            if (ShowNoteHighlights.Value && currentHitObjects != null)
                UpdateNoteHighlights(timeMs);
        }

        private float resolveCursorX(double timeMs, double bpm)
        {
            if (hasTimelineWindow)
            {
                // Keep playhead anchored for Songsterr-like readability while notation scrolls beneath it.
                return timelinePlayheadX;
            }

            // Fallback for legacy paths without an explicit timeline window.
            float beatDurationMs = 60000f / (float)Math.Max(1.0, bpm);
            float measureDurationMs = beatDurationMs * 4;
            float measureProgress = (float)((timeMs % measureDurationMs) / measureDurationMs);
            return staffStartX + (staffEndX - staffStartX) * measureProgress;
        }

        internal static float ResolvePlaybackCursorTrailWidth(
            float timelineWidth,
            double timelineDurationMs,
            double bpm,
            double configuredLookaheadMs,
            bool hasTimelineWindow)
        {
            float safeWidth = Math.Max(1f, timelineWidth);
            if (!hasTimelineWindow || timelineDurationMs <= 1)
                return Math.Clamp(safeWidth * FallbackTrailWidthRatio, 56f, 190f);

            double beatDurationMs = 60000.0 / Math.Max(1.0, bpm);
            double adaptiveLookahead = Math.Clamp(beatDurationMs, 320.0, 700.0);
            double effectiveLookahead = Math.Max(220.0, Math.Min(900.0, Math.Max(configuredLookaheadMs, adaptiveLookahead)));
            float ratioWidth = (float)(safeWidth * (effectiveLookahead / timelineDurationMs));
            float minWidth = Math.Clamp(safeWidth * 0.045f, 40f, 84f);
            float maxWidth = Math.Clamp(safeWidth * 0.072f, 72f, 132f);
            return Math.Clamp(ratioWidth, minWidth, maxWidth);
        }

        private void UpdateNoteHighlights(double timeMs)
        {
            if (currentHitObjects == null) return;

            // Find notes that are about to be hit (within lookahead window)
            double windowStart = timeMs;
            double windowEnd = timeMs + lookaheadMs;

            foreach (var hitObject in currentHitObjects)
            {
                int id = hitObject.Index;

                // Check if note is within the active window
                if (hitObject.TimeMs >= windowStart && hitObject.TimeMs <= windowEnd)
                {
                    // Calculate how close we are to hitting this note (0 = just entered window, 1 = exactly at hit time)
                    float proximity = 1f - (float)((hitObject.TimeMs - timeMs) / lookaheadMs);

                    if (!activeHighlights.TryGetValue(id, out var highlight))
                    {
                        // Create new highlight ring for this note
                        highlight = new NoteHighlightRing(hitObject.ComponentName);
                        highlight.Position = new Vector2(hitObject.XPosition, hitObject.YPosition);
                        noteHighlightContainer.Add(highlight);
                        activeHighlights[id] = highlight;
                    }

                    // Update highlight intensity based on proximity
                    highlight.SetIntensity(proximity);
                }
                else if (hitObject.TimeMs < windowStart && activeHighlights.TryGetValue(id, out var oldHighlight))
                {
                    // Note has passed - fade out and remove
                    oldHighlight.FadeOut(150).Expire();
                    activeHighlights.Remove(id);
                }
            }
        }

        private void ClearNoteHighlights()
        {
            foreach (var highlight in activeHighlights.Values)
            {
                highlight.Expire();
            }
            activeHighlights.Clear();
        }

        /// <summary>
        /// Pulse the leading edge when a note is hit.
        /// </summary>
        public void PulseOnHit(Color4? color = null)
        {
            var pulseColor = color ?? DesignSystem.ColorAccentPrimary;

            leadingEdge.FadeColour(pulseColor)
                      .FadeColour(EdgeColor, 200);

            leadingGlow.FadeTo(1f)
                      .FadeTo(0.6f, 200);
        }

        /// <summary>
        /// Reset the highlighter to the beginning.
        /// </summary>
        public void Reset()
        {
            currentTimeMs = 0;
            float resetX = hasTimelineWindow ? timelineLeftX : staffStartX;
            highlightOverlay.Width = 0;
            highlightOverlay.X = resetX;
            previewOverlay.Width = 0;
            previewOverlay.X = resetX;
            leadingEdge.X = resetX;
            leadingGlow.X = resetX;
            topTick.X = resetX;
            topTick.Alpha = 0f;
            bottomTick.X = resetX;
            bottomTick.Alpha = 0f;
            ClearNoteHighlights();
        }
    }

    /// <summary>
    /// A glowing ring that appears around notes as they approach the hit time.
    /// Intensity increases as the note gets closer to being played.
    /// </summary>
    internal partial class NoteHighlightRing : CompositeDrawable
    {
        private readonly Circle innerRing;
        private readonly Circle outerGlow;
        private readonly Color4 componentColor;

        private const float BaseSize = 24f;
        private const float MaxSize = 36f;

        public NoteHighlightRing(string componentName)
        {
            componentColor = DesignSystem.GetComponentColor(componentName);

            Size = new Vector2(MaxSize);
            Origin = Anchor.Centre;
            Anchor = Anchor.Centre;

            outerGlow = new Circle
            {
                Size = new Vector2(MaxSize),
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = DesignSystem.WithOpacity(componentColor, 0.3f),
                Blending = BlendingParameters.Additive
            };

            innerRing = new Circle
            {
                Size = new Vector2(BaseSize),
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = Color4.Transparent,
                BorderThickness = 2f,
                BorderColour = componentColor
            };

            InternalChildren = new Drawable[]
            {
                outerGlow,
                innerRing
            };

            Alpha = 0;
        }

        /// <summary>
        /// Set the highlight intensity (0 = just appeared, 1 = at hit time).
        /// </summary>
        public void SetIntensity(float intensity)
        {
            intensity = Math.Clamp(intensity, 0f, 1f);

            // Fade in
            Alpha = 0.3f + intensity * 0.7f;

            // Grow the ring as we approach hit time
            float size = BaseSize + (MaxSize - BaseSize) * intensity;
            innerRing.ResizeTo(new Vector2(size), 50);

            // Increase border thickness and glow
            innerRing.BorderThickness = 2f + intensity * 2f;
            outerGlow.FadeTo(0.2f + intensity * 0.4f, 50);

            // Pulse effect at high intensity
            if (intensity > 0.9f)
            {
                this.ScaleTo(1.1f, 50).Then().ScaleTo(1f, 100);
            }
        }
    }

    /// <summary>
    /// Data structure for tracking hit object positions.
    /// Used by the highlighter to know where notes are located.
    /// </summary>
    public struct HitObjectInfo
    {
        public int Index { get; set; }
        public double TimeMs { get; set; }
        public float XPosition { get; set; }
        public float YPosition { get; set; }
        public string ComponentName { get; set; }
    }
}
