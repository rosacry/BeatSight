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

        /// <summary>The color of the highlight overlay (low opacity).</summary>
        private static readonly Color4 HighlightColor = new Color4(255, 200, 100, 45); // Warm amber tint

        /// <summary>The color of the leading edge indicator.</summary>
        private static readonly Color4 EdgeColor = new Color4(255, 160, 60, 180); // Brighter amber

        /// <summary>The color of the "now playing" glow.</summary>
        private static readonly Color4 GlowColor = new Color4(255, 220, 140, 100);

        /// <summary>Width of the leading edge line.</summary>
        private const float EdgeLineWidth = 3f;

        /// <summary>Width of the glow effect around the edge.</summary>
        private const float GlowWidth = 12f;

        /// <summary>How many milliseconds of audio the highlight covers (lookahead window).</summary>
        private const double DefaultLookaheadMs = 500;

        #endregion

        #region Visual Components

        private Box highlightOverlay = null!;
        private Box leadingEdge = null!;
        private Box leadingGlow = null!;
        private Container noteHighlightContainer = null!;

        #endregion

        #region State

        private double currentTimeMs;
        private double lookaheadMs = DefaultLookaheadMs;
        private float staffStartX;
        private float staffEndX;
        private float staffCenterX;
        private List<HitObjectInfo>? currentHitObjects;
        private readonly Dictionary<int, NoteHighlightRing> activeHighlights = new();

        #endregion

        #region Bindables

        /// <summary>Whether the highlighter is enabled.</summary>
        public readonly BindableBool Enabled = new BindableBool(true);

        /// <summary>The opacity of the highlight overlay (0-1).</summary>
        public readonly BindableFloat HighlightOpacity = new BindableFloat(0.4f)
        {
            MinValue = 0f,
            MaxValue = 1f
        };

        /// <summary>Whether to show per-note glow rings.</summary>
        public readonly BindableBool ShowNoteHighlights = new BindableBool(true);

        #endregion

        public ManuscriptPlaybackHighlighter()
        {
            RelativeSizeAxes = Axes.Both;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            // Main highlight overlay - starts from left edge, width controlled by playback position
            highlightOverlay = new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = 0,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Colour = ColourInfo.GradientHorizontal(
                    DesignSystem.WithOpacity(HighlightColor, 0.1f),
                    HighlightColor)
            };

            // Glow effect at the leading edge (blurred appearance)
            leadingGlow = new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = GlowWidth,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.Centre,
                Colour = ColourInfo.GradientHorizontal(
                    Color4.Transparent,
                    GlowColor),
                Blending = BlendingParameters.Additive
            };

            // Sharp leading edge line
            leadingEdge = new Box
            {
                RelativeSizeAxes = Axes.Y,
                Width = EdgeLineWidth,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.Centre,
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
                leadingGlow,
                leadingEdge,
                noteHighlightContainer
            };

            // Bind to enabled state
            Enabled.BindValueChanged(e => Alpha = e.NewValue ? 1f : 0f, true);
            HighlightOpacity.BindValueChanged(e =>
            {
                highlightOverlay.Colour = ColourInfo.GradientHorizontal(
                    DesignSystem.WithOpacity(HighlightColor, 0.1f * e.NewValue),
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

            // Calculate highlight width based on playback position
            // The highlight represents the "played" portion of the measure
            // We use a cyclic pattern based on BPM to create a sweeping effect
            float beatDurationMs = 60000f / (float)bpm;
            float measureDurationMs = beatDurationMs * 4; // Assuming 4/4 time

            // Calculate position within the current measure (0-1)
            float measureProgress = (float)((timeMs % measureDurationMs) / measureDurationMs);

            // Map measure progress to staff width
            float staffWidth = staffEndX - staffStartX;
            float highlightWidth = staffWidth * measureProgress;

            // Update highlight overlay
            highlightOverlay.X = staffStartX;
            highlightOverlay.Width = highlightWidth;

            // Update leading edge position
            float edgeX = staffStartX + highlightWidth;
            leadingEdge.X = edgeX;
            leadingGlow.X = edgeX;

            // Update per-note highlights if enabled
            if (ShowNoteHighlights.Value && currentHitObjects != null)
            {
                UpdateNoteHighlights(timeMs, measureProgress);
            }
        }

        private void UpdateNoteHighlights(double timeMs, float measureProgress)
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
            highlightOverlay.Width = 0;
            leadingEdge.X = staffStartX;
            leadingGlow.X = staffStartX;
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
