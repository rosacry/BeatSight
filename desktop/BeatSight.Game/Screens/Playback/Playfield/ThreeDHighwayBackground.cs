using System;
using System.Collections.Generic;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback.Playfield
{
    internal sealed partial class ThreeDHighwayBackground : CompositeDrawable
    {
        private const int geometrySegmentCount = 64;
        private const int sweepLineCount = 4;
        private const float receptorDepth = 0.992f;
        private const float receptorInset = 1.0f;

        private const float hitLineYRatio = 0.935f;

        private readonly struct ProfileGeometry
        {
            public ProfileGeometry(float vanishingPointYRatio, float highwayTopWidthRatio, float highwayBottomWidthRatio, float curveExponent, float headerDepth)
            {
                VanishingPointYRatio = vanishingPointYRatio;
                HighwayTopWidthRatio = highwayTopWidthRatio;
                HighwayBottomWidthRatio = highwayBottomWidthRatio;
                CurveExponent = curveExponent;
                HeaderDepth = headerDepth;
            }

            public float VanishingPointYRatio { get; }
            public float HighwayTopWidthRatio { get; }
            public float HighwayBottomWidthRatio { get; }
            public float CurveExponent { get; }
            public float HeaderDepth { get; }
        }

        private static readonly Color4[] laneAccentPalette =
        {
            new Color4(86, 166, 106, 255),
            new Color4(188, 94, 104, 255),
            new Color4(206, 181, 92, 255),
            new Color4(88, 132, 212, 255),
            new Color4(210, 145, 88, 255),
            new Color4(154, 114, 208, 255),
            new Color4(88, 172, 176, 255),
            new Color4(188, 110, 166, 255)
        };

        private readonly LaneLayout laneLayout;
        private readonly bool kickUsesGlobalLine;
        private ThreeDStageProfile stageProfile;
        private readonly int visibleLaneCount;
        private readonly IReadOnlyList<string> visibleLaneLabels;

        private readonly Container perspectiveLaneLayer;
        private readonly Container perspectiveBoundaryLayer;
        private readonly Container laneHeaderLayer;
        private readonly Container laneFooterLayer;
        private readonly Container receptorLayer;
        private readonly Container sweepLineLayer;

        private readonly List<Box[]> laneSegments = new();
        private readonly List<Box[]> boundarySegments = new();
        private readonly List<Container> laneHeaderBoxes = new();
        private readonly List<Box> laneHeaderFills = new();
        private readonly List<SpriteText> laneHeaderTexts = new();
        private readonly List<Container> laneFooterBoxes = new();
        private readonly List<Box> lanePulseLights = new();
        private readonly List<SpriteText> laneFooterTexts = new();
        private readonly List<Container> laneReceptorBoxes = new();
        private readonly List<Box> laneReceptorFills = new();
        private readonly List<Box> laneReceptorGlows = new();
        private readonly List<Box> sweepLines = new();

        private Box? beatPulseOverlay;
        private Box? horizonGlow;
        private Box? receptorRail;
        private Box? strikeZoneGlow;
        private float lastLayoutWidth;
        private float lastLayoutHeight;

        // Beat sync state.
        private double lastBeatTime;
        private double beatInterval = 500;
        private bool beatSyncEnabled = true;

        private static ProfileGeometry resolveProfileGeometry(ThreeDStageProfile profile)
        {
            return profile switch
            {
                ThreeDStageProfile.Arcade => new ProfileGeometry(
                    vanishingPointYRatio: 0.112f,
                    highwayTopWidthRatio: 0.12f,
                    highwayBottomWidthRatio: 0.80f,
                    curveExponent: 1.22f,
                    headerDepth: 0.080f),
                ThreeDStageProfile.Tight => new ProfileGeometry(
                    vanishingPointYRatio: 0.070f,
                    highwayTopWidthRatio: 0.052f,
                    highwayBottomWidthRatio: 0.94f,
                    curveExponent: 1.56f,
                    headerDepth: 0.042f),
                _ => new ProfileGeometry(
                    vanishingPointYRatio: 0.080f,
                    highwayTopWidthRatio: 0.062f,
                    highwayBottomWidthRatio: 0.90f,
                    curveExponent: 1.46f,
                    headerDepth: 0.044f)
            };
        }

        internal static (float RailAlpha, float GlowAlpha, float ReceptorHeightScale, float BorderThickness) ResolveThreeDStrikeZonePresentation(ThreeDStageProfile profile, float drawHeight)
        {
            float safeHeight = float.IsFinite(drawHeight) ? Math.Clamp(drawHeight, 540f, 4320f) : 1080f;
            float compactBoost = safeHeight <= 760f ? 1.08f : safeHeight >= 1440f ? 0.96f : 1f;

            return profile switch
            {
                ThreeDStageProfile.Arcade => (
                    RailAlpha: 0.44f,
                    GlowAlpha: 0.48f,
                    ReceptorHeightScale: 0.96f * compactBoost,
                    BorderThickness: 1.7f),
                ThreeDStageProfile.Tight => (
                    RailAlpha: 0.64f,
                    GlowAlpha: 0.68f,
                    ReceptorHeightScale: 1.10f * compactBoost,
                    BorderThickness: 2.25f),
                _ => (
                    RailAlpha: 0.60f,
                    GlowAlpha: 0.64f,
                    ReceptorHeightScale: 1.08f * compactBoost,
                    BorderThickness: 2.15f)
            };
        }

        internal static (float BeatPulsePeakAlpha, float HorizonPeakAlpha, float HorizonRestingAlpha, float RailPulseBoost, float GlowPulseBoost, float LaneGlowPeakAlpha, float LaneGlowDecayAlpha, float LaneFillEmphasis, byte LaneFillRestingAlpha) ResolveThreeDHitFeedbackPresentation(ThreeDStageProfile profile, float drawHeight)
        {
            float safeHeight = float.IsFinite(drawHeight) ? Math.Clamp(drawHeight, 540f, 4320f) : 1080f;
            float compactBoost = safeHeight <= 760f ? 1.08f : safeHeight >= 1440f ? 0.96f : 1f;

            return profile switch
            {
                ThreeDStageProfile.Arcade => (
                    BeatPulsePeakAlpha: 0.046f * compactBoost,
                    HorizonPeakAlpha: 0.22f * compactBoost,
                    HorizonRestingAlpha: 0.11f,
                    RailPulseBoost: 0.22f * compactBoost,
                    GlowPulseBoost: 0.20f * compactBoost,
                    LaneGlowPeakAlpha: 0.66f * compactBoost,
                    LaneGlowDecayAlpha: 0.24f,
                    LaneFillEmphasis: 1.20f,
                    LaneFillRestingAlpha: (byte)90),
                ThreeDStageProfile.Tight => (
                    BeatPulsePeakAlpha: 0.066f * compactBoost,
                    HorizonPeakAlpha: 0.31f * compactBoost,
                    HorizonRestingAlpha: 0.13f,
                    RailPulseBoost: 0.30f * compactBoost,
                    GlowPulseBoost: 0.28f * compactBoost,
                    LaneGlowPeakAlpha: 0.80f * compactBoost,
                    LaneGlowDecayAlpha: 0.32f,
                    LaneFillEmphasis: 1.30f,
                    LaneFillRestingAlpha: (byte)104),
                _ => (
                    BeatPulsePeakAlpha: 0.058f * compactBoost,
                    HorizonPeakAlpha: 0.28f * compactBoost,
                    HorizonRestingAlpha: 0.12f,
                    RailPulseBoost: 0.28f * compactBoost,
                    GlowPulseBoost: 0.26f * compactBoost,
                    LaneGlowPeakAlpha: 0.74f * compactBoost,
                    LaneGlowDecayAlpha: 0.28f,
                    LaneFillEmphasis: 1.27f,
                    LaneFillRestingAlpha: (byte)98)
            };
        }

        public ThreeDHighwayBackground(LaneLayout laneLayout, bool kickUsesGlobalLine, ThreeDStageProfile stageProfile)
        {
            this.laneLayout = laneLayout;
            this.kickUsesGlobalLine = kickUsesGlobalLine;
            this.stageProfile = stageProfile;
            visibleLaneCount = kickUsesGlobalLine
                ? Math.Max(1, laneLayout.LaneCount - 1)
                : Math.Max(1, laneLayout.LaneCount);
            visibleLaneLabels = buildVisibleLaneLabels();

            RelativeSizeAxes = Axes.Both;

            InternalChildren = new Drawable[]
            {
                createAtmosphereLayer(),
                horizonGlow = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Height = 0.24f,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    Colour = ColourInfo.GradientVertical(
                        new Color4(84, 112, 162, 56),
                        Color4.Transparent)
                },
                perspectiveLaneLayer = new Container
                {
                    RelativeSizeAxes = Axes.Both
                },
                perspectiveBoundaryLayer = new Container
                {
                    RelativeSizeAxes = Axes.Both
                },
                sweepLineLayer = new Container
                {
                    RelativeSizeAxes = Axes.Both
                },
                laneHeaderLayer = new Container
                {
                    RelativeSizeAxes = Axes.Both
                },
                laneFooterLayer = new Container
                {
                    RelativeSizeAxes = Axes.Both
                },
                receptorLayer = new Container
                {
                    RelativeSizeAxes = Axes.Both
                },
                strikeZoneGlow = new Box
                {
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    RelativeSizeAxes = Axes.X,
                    Height = 40f,
                    Width = 0.86f,
                    Colour = ColourInfo.GradientVertical(
                        new Color4(180, 214, 255, 94),
                        new Color4(180, 214, 255, 0)),
                    Blending = BlendingParameters.Additive,
                    Alpha = 0.55f
                },
                beatPulseOverlay = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(142, 188, 255, 24),
                    Blending = BlendingParameters.Additive,
                    Alpha = 0
                }
            };

            buildLaneGeometry();
            buildBoundaryGeometry();
            buildLaneGuides();
            buildLaneReceptors();
            buildSweepLines();
        }

        private Drawable createAtmosphereLayer()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = ColourInfo.GradientVertical(
                            new Color4(8, 12, 22, 255),
                            new Color4(6, 8, 14, 255))
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Height = 0.32f,
                        Anchor = Anchor.TopCentre,
                        Origin = Anchor.TopCentre,
                        Colour = ColourInfo.GradientVertical(
                            new Color4(52, 76, 128, 28),
                            Color4.Transparent)
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Width = 0.34f,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Colour = ColourInfo.GradientHorizontal(
                            new Color4(18, 44, 88, 52),
                            Color4.Transparent)
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Width = 0.34f,
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        Colour = ColourInfo.GradientHorizontal(
                            Color4.Transparent,
                            new Color4(18, 44, 88, 52))
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Width = 0.16f,
                        Anchor = Anchor.BottomLeft,
                        Origin = Anchor.BottomLeft,
                        Colour = ColourInfo.GradientHorizontal(
                            new Color4(94, 164, 236, 54),
                            Color4.Transparent)
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Width = 0.16f,
                        Anchor = Anchor.BottomRight,
                        Origin = Anchor.BottomRight,
                        Colour = ColourInfo.GradientHorizontal(
                            Color4.Transparent,
                            new Color4(94, 164, 236, 54))
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Height = 0.46f,
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.BottomCentre,
                        Colour = ColourInfo.GradientVertical(
                            Color4.Transparent,
                            new Color4(0, 0, 0, 132))
                    }
                }
            };
        }

        private void buildLaneGeometry()
        {
            laneSegments.Clear();
            perspectiveLaneLayer.Clear();

            for (int lane = 0; lane < visibleLaneCount; lane++)
            {
                var segments = new Box[geometrySegmentCount];

                for (int i = 0; i < geometrySegmentCount; i++)
                {
                    var segment = new Box();
                    segments[i] = segment;
                    perspectiveLaneLayer.Add(segment);
                }

                laneSegments.Add(segments);
            }
        }

        private void buildBoundaryGeometry()
        {
            boundarySegments.Clear();
            perspectiveBoundaryLayer.Clear();

            for (int boundary = 0; boundary <= visibleLaneCount; boundary++)
            {
                var segments = new Box[geometrySegmentCount];

                for (int i = 0; i < geometrySegmentCount; i++)
                {
                    var segment = new Box();
                    segments[i] = segment;
                    perspectiveBoundaryLayer.Add(segment);
                }

                boundarySegments.Add(segments);
            }
        }

        private void buildLaneGuides()
        {
            laneHeaderBoxes.Clear();
            laneHeaderFills.Clear();
            laneHeaderTexts.Clear();
            laneFooterBoxes.Clear();
            lanePulseLights.Clear();
            laneFooterTexts.Clear();
            laneHeaderLayer.Clear();
            laneFooterLayer.Clear();

            for (int lane = 0; lane < visibleLaneCount; lane++)
            {
                Color4 accent = laneAccentPalette[lane % laneAccentPalette.Length];
                string label = visibleLaneLabels.Count > lane ? visibleLaneLabels[lane] : $"L{lane + 1}";

                var header = new Container
                {
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft,
                    Masking = true,
                    CornerRadius = 5f
                };

                var headerFill = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(accent.R, accent.G, accent.B, 116)
                };

                header.Add(headerFill);
                header.Add(new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 2f,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Colour = new Color4(255, 255, 255, 228)
                });

                var headerText = new SpriteText
                {
                    Text = label,
                    Font = FrameworkFont.Regular.With(size: 13),
                    Colour = new Color4(240, 246, 255, 242),
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre
                };

                laneHeaderLayer.Add(header);
                laneHeaderLayer.Add(headerText);
                laneHeaderBoxes.Add(header);
                laneHeaderFills.Add(headerFill);
                laneHeaderTexts.Add(headerText);

                var footer = new Container
                {
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft,
                    Masking = true,
                    CornerRadius = 5f
                };

                footer.Add(new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(22, 28, 40, 230)
                });

                var pulseLight = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 3f,
                    Anchor = Anchor.BottomCentre,
                    Origin = Anchor.BottomCentre,
                    Colour = UITheme.Emphasise(accent, 1.12f),
                    Alpha = 0,
                    Blending = BlendingParameters.Additive
                };

                footer.Add(pulseLight);

                var footerText = new SpriteText
                {
                    Text = label,
                    Font = FrameworkFont.Regular.With(size: 11),
                    Colour = new Color4(220, 232, 252, 214),
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopCentre
                };

                laneFooterLayer.Add(footer);
                laneFooterLayer.Add(footerText);
                laneFooterBoxes.Add(footer);
                lanePulseLights.Add(pulseLight);
                laneFooterTexts.Add(footerText);
            }
        }

        private void buildSweepLines()
        {
            sweepLines.Clear();
            sweepLineLayer.Clear();

            for (int i = 0; i < sweepLineCount; i++)
            {
                var sweep = new Box
                {
                    Height = 1.8f,
                    Colour = new Color4(194, 220, 255, 96),
                    Alpha = 0.10f
                };

                sweepLineLayer.Add(sweep);
                sweepLines.Add(sweep);
            }
        }

        private void buildLaneReceptors()
        {
            laneReceptorBoxes.Clear();
            laneReceptorFills.Clear();
            laneReceptorGlows.Clear();
            receptorLayer.Clear();

            receptorRail = new Box
            {
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Colour = new Color4(228, 238, 255, 196),
                Height = 4f,
                Blending = BlendingParameters.Additive
            };
            receptorLayer.Add(receptorRail);

            for (int lane = 0; lane < visibleLaneCount; lane++)
            {
                Color4 accent = laneAccentPalette[lane % laneAccentPalette.Length];
                Color4 emphasised = UITheme.Emphasise(accent, 1.16f);

                var receptor = new Container
                {
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft,
                    Masking = true,
                    CornerRadius = 7f,
                    BorderThickness = 1.8f,
                    BorderColour = new Color4(220, 232, 252, 226)
                };

                receptor.Add(new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(14, 19, 30, 235)
                });

                var fill = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(accent.R, accent.G, accent.B, 116)
                };
                receptor.Add(fill);

                var glow = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(emphasised.R, emphasised.G, emphasised.B, 180),
                    Alpha = 0.30f,
                    Blending = BlendingParameters.Additive
                };
                receptor.Add(glow);

                receptor.Add(new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Height = 2f,
                    Anchor = Anchor.TopCentre,
                    Origin = Anchor.TopCentre,
                    Colour = new Color4(244, 250, 255, 228)
                });

                receptorLayer.Add(receptor);
                laneReceptorBoxes.Add(receptor);
                laneReceptorFills.Add(fill);
                laneReceptorGlows.Add(glow);
            }
        }

        public void ResetKickTimeline() { }
        public void SetKickGuideVisible(bool visible) { }
        public void UpdateKickTimeline(IEnumerable<DrawableNote> notes, double time, double duration) { }

        public void SetBpm(double bpm)
        {
            if (bpm > 0)
                beatInterval = 60000.0 / bpm;
        }

        public void SetBeatSyncEnabled(bool enabled)
            => beatSyncEnabled = enabled;

        public void TriggerBeatPulse(double intensity = 1.0)
        {
            if (!beatSyncEnabled || beatPulseOverlay == null)
                return;

            float pulse = (float)Math.Clamp(intensity, 0.1, 1.0);
            var strikeZonePresentation = ResolveThreeDStrikeZonePresentation(stageProfile, DrawHeight);
            var hitFeedback = ResolveThreeDHitFeedbackPresentation(stageProfile, DrawHeight);

            beatPulseOverlay.ClearTransforms();
            beatPulseOverlay.Alpha = hitFeedback.BeatPulsePeakAlpha * pulse;
            beatPulseOverlay.FadeOut(beatInterval * 0.7, Easing.OutQuad);

            if (horizonGlow != null)
            {
                horizonGlow.ClearTransforms();
                horizonGlow.TransformTo(nameof(horizonGlow.Alpha), hitFeedback.HorizonPeakAlpha * pulse, 60)
                           .Then()
                           .TransformTo(nameof(horizonGlow.Alpha), hitFeedback.HorizonRestingAlpha, beatInterval * 0.6, Easing.OutQuad);
            }

            if (receptorRail != null)
            {
                receptorRail.ClearTransforms();
                receptorRail.Alpha = Math.Min(0.96f, strikeZonePresentation.RailAlpha + hitFeedback.RailPulseBoost * pulse);
                receptorRail.FadeTo(strikeZonePresentation.RailAlpha, beatInterval * 0.55, Easing.OutQuad);
            }

            if (strikeZoneGlow != null)
            {
                strikeZoneGlow.ClearTransforms();
                strikeZoneGlow.Alpha = Math.Min(0.94f, strikeZonePresentation.GlowAlpha + hitFeedback.GlowPulseBoost * pulse);
                strikeZoneGlow.FadeTo(strikeZonePresentation.GlowAlpha, beatInterval * 0.6, Easing.OutQuad);
            }
        }

        public void TriggerLaneHit(int laneIndex, float intensity = 1.0f)
        {
            if (laneIndex < 0 || laneIndex >= lanePulseLights.Count)
                return;

            var pulse = lanePulseLights[laneIndex];
            pulse.ClearTransforms();
            pulse.Alpha = 0.52f * Math.Clamp(intensity, 0.2f, 1.0f);
            pulse.ScaleTo(new Vector2(1.12f, 1f), 70, Easing.OutQuint)
                 .Then()
                 .ScaleTo(Vector2.One, 190, Easing.OutQuad);
            pulse.FadeOut(240, Easing.OutQuad);

            if (laneIndex < laneReceptorGlows.Count)
            {
                float clamped = Math.Clamp(intensity, 0.2f, 1.0f);
                var hitFeedback = ResolveThreeDHitFeedbackPresentation(stageProfile, DrawHeight);
                var receptorGlow = laneReceptorGlows[laneIndex];
                receptorGlow.ClearTransforms();
                receptorGlow.Alpha = Math.Min(0.94f, hitFeedback.LaneGlowPeakAlpha * clamped);
                receptorGlow.FadeTo(hitFeedback.LaneGlowDecayAlpha, 250, Easing.OutQuad);

                var receptorFill = laneReceptorFills[laneIndex];
                Color4 accent = laneAccentPalette[laneIndex % laneAccentPalette.Length];
                receptorFill.ClearTransforms();
                receptorFill.Colour = UITheme.Emphasise(accent, hitFeedback.LaneFillEmphasis);
                receptorFill.FadeColour(new Color4(accent.R, accent.G, accent.B, hitFeedback.LaneFillRestingAlpha), 260, Easing.OutQuad);
            }
        }

        public void SetProfile(ThreeDStageProfile profile)
        {
            if (stageProfile == profile)
                return;

            stageProfile = profile;
            lastLayoutWidth = -1f;
            lastLayoutHeight = -1f;
            updatePerspectiveLayout();
        }

        public void UpdateScroll(double currentTime)
        {
            if (DrawWidth <= 0 || DrawHeight <= 0)
                return;

            updatePerspectiveLayout();
            updateSweepLines(currentTime);

            if (!beatSyncEnabled || beatInterval <= 0)
                return;

            double beatProgress = (currentTime - lastBeatTime) / beatInterval;
            if (beatProgress >= 1.0)
            {
                lastBeatTime = currentTime - (currentTime % beatInterval);
                TriggerBeatPulse(0.55);
            }
        }

        protected override void Update()
        {
            base.Update();
            updatePerspectiveLayout();
        }

        private void updatePerspectiveLayout()
        {
            if (Math.Abs(lastLayoutWidth - DrawWidth) < 0.5f && Math.Abs(lastLayoutHeight - DrawHeight) < 0.5f)
                return;

            lastLayoutWidth = DrawWidth;
            lastLayoutHeight = DrawHeight;

            if (DrawWidth <= 0 || DrawHeight <= 0)
                return;

            ProfileGeometry profile = resolveProfileGeometry(stageProfile);
            float vanishingY = DrawHeight * profile.VanishingPointYRatio;
            float hitY = DrawHeight * hitLineYRatio;
            float topY = vanishingY + 5f;
            float bottomY = hitY - 5f;
            float depthHeight = Math.Max(20f, bottomY - topY);

            float topWidth = DrawWidth * profile.HighwayTopWidthRatio;
            float bottomWidth = DrawWidth * profile.HighwayBottomWidthRatio;

            for (int segmentIndex = 0; segmentIndex < geometrySegmentCount; segmentIndex++)
            {
                float depthStart = segmentIndex / (float)geometrySegmentCount;
                float depthEnd = (segmentIndex + 1f) / geometrySegmentCount;
                float depthMid = (depthStart + depthEnd) * 0.5f;

                float yStart = topY + depthHeight * depthStart;
                float yEnd = topY + depthHeight * depthEnd;
                float segmentHeight = Math.Max(1f, yEnd - yStart + 1.4f);

                float curvedDepth = MathF.Pow(depthMid, profile.CurveExponent);
                float widthAtDepth = lerp(topWidth, bottomWidth, curvedDepth);
                float laneWidth = widthAtDepth / visibleLaneCount;
                float left = (DrawWidth - widthAtDepth) * 0.5f;
                float laneInset = Math.Clamp(laneWidth * 0.035f, 1.0f, 3.5f);

                for (int lane = 0; lane < visibleLaneCount; lane++)
                {
                    var segment = laneSegments[lane][segmentIndex];
                    Color4 accent = laneAccentPalette[lane % laneAccentPalette.Length];
                    Color4 laneBase = UITheme.Mix(new Color4(14, 20, 32, 255), accent, lane % 2 == 0 ? 0.16f : 0.13f);
                    byte laneAlpha = (byte)(96 + curvedDepth * 86);

                    segment.X = left + lane * laneWidth + laneInset;
                    segment.Y = yStart - 0.7f;
                    segment.Width = Math.Max(1f, laneWidth - laneInset * 2f);
                    segment.Height = segmentHeight;
                    segment.Colour = new Color4(laneBase.R, laneBase.G, laneBase.B, laneAlpha);
                }

                for (int boundary = 0; boundary <= visibleLaneCount; boundary++)
                {
                    bool edge = boundary == 0 || boundary == visibleLaneCount;
                    var segment = boundarySegments[boundary][segmentIndex];
                    float boundaryX = left + laneWidth * boundary;
                    byte alpha = edge ? (byte)(150 + curvedDepth * 95) : (byte)(104 + curvedDepth * 82);

                    segment.X = boundaryX - (edge ? 1.25f : 0.8f);
                    segment.Y = yStart - 0.7f;
                    segment.Width = edge ? 2.5f : 1.6f;
                    segment.Height = segmentHeight;
                    segment.Colour = new Color4(198, 216, 246, alpha);
                }
            }

            layoutLaneGuides(topY, hitY, topWidth, bottomWidth, profile.HeaderDepth);
        }

        private void layoutLaneGuides(float topY, float hitY, float topWidth, float bottomWidth, float headerDepth)
        {
            float compactBoost = DrawHeight <= 760f ? 1.12f : 1f;
            float headerFontSize = Math.Clamp(12f * compactBoost, 11f, 15f);
            float footerFontSize = Math.Clamp(10f * compactBoost, 10f, 13f);
            float headerHeight = Math.Clamp(24f * compactBoost, 22f, 32f);
            float footerHeight = Math.Clamp(15f * compactBoost, 13f, 20f);

            float headerWidth = lerp(topWidth, bottomWidth, headerDepth) / visibleLaneCount;
            float headerLeft = (DrawWidth - lerp(topWidth, bottomWidth, headerDepth)) * 0.5f;
            float headerY = Math.Max(6f, topY + 4f);

            float footerDepth = 1f;
            float footerWidth = lerp(topWidth, bottomWidth, footerDepth) / visibleLaneCount;
            float footerLeft = (DrawWidth - lerp(topWidth, bottomWidth, footerDepth)) * 0.5f;
            float footerY = hitY - footerHeight - 3f;

            for (int lane = 0; lane < visibleLaneCount; lane++)
            {
                Color4 accent = laneAccentPalette[lane % laneAccentPalette.Length];

                var header = laneHeaderBoxes[lane];
                header.X = headerLeft + lane * headerWidth + 1f;
                header.Y = headerY;
                header.Width = Math.Max(1f, headerWidth - 2f);
                header.Height = headerHeight;

                laneHeaderFills[lane].Colour = new Color4(accent.R, accent.G, accent.B, 160);

                var headerText = laneHeaderTexts[lane];
                headerText.Font = FrameworkFont.Regular.With(size: headerFontSize);
                headerText.X = header.X + header.Width * 0.5f;
                headerText.Y = headerY + (header.Height - headerFontSize) * 0.5f - 1f;

                var footer = laneFooterBoxes[lane];
                footer.X = footerLeft + lane * footerWidth + 1f;
                footer.Y = footerY;
                footer.Width = Math.Max(1f, footerWidth - 2f);
                footer.Height = footerHeight;

                var footerText = laneFooterTexts[lane];
                footerText.Font = FrameworkFont.Regular.With(size: footerFontSize);
                footerText.X = footer.X + footer.Width * 0.5f;
                footerText.Y = footerY + (footer.Height - footerFontSize) * 0.5f - 1f;
            }

            layoutLaneReceptors(hitY, topWidth, bottomWidth);
        }

        private void layoutLaneReceptors(float hitY, float topWidth, float bottomWidth)
        {
            if (laneReceptorBoxes.Count == 0)
                return;

            var strikeZonePresentation = ResolveThreeDStrikeZonePresentation(stageProfile, DrawHeight);
            float receptorWidthAtDepth = lerp(topWidth, bottomWidth, receptorDepth);
            float receptorLaneWidth = receptorWidthAtDepth / visibleLaneCount;
            float receptorLeft = (DrawWidth - receptorWidthAtDepth) * 0.5f;
            float receptorHeight = Math.Clamp(DrawHeight * 0.042f * strikeZonePresentation.ReceptorHeightScale, 20f, 44f);
            float receptorY = hitY - receptorHeight * 0.56f;

            for (int lane = 0; lane < laneReceptorBoxes.Count; lane++)
            {
                var receptor = laneReceptorBoxes[lane];
                receptor.X = receptorLeft + lane * receptorLaneWidth + receptorInset;
                receptor.Y = receptorY;
                receptor.Width = Math.Max(1.5f, receptorLaneWidth - receptorInset * 2f);
                receptor.Height = receptorHeight;
                receptor.BorderThickness = strikeZonePresentation.BorderThickness;
            }

            if (receptorRail != null)
            {
                receptorRail.X = receptorLeft - 2f;
                receptorRail.Y = hitY + 0.5f;
                receptorRail.Width = receptorWidthAtDepth + 4f;
                receptorRail.Height = 5f;
                receptorRail.Alpha = strikeZonePresentation.RailAlpha;
            }

            if (strikeZoneGlow != null)
            {
                strikeZoneGlow.Y = hitY - receptorHeight * 0.85f;
                strikeZoneGlow.Height = receptorHeight * 1.56f;
                strikeZoneGlow.Width = Math.Clamp((receptorWidthAtDepth + 18f) / Math.Max(1f, DrawWidth), 0.45f, 0.96f);
                strikeZoneGlow.Alpha = strikeZonePresentation.GlowAlpha;
            }
        }

        private void updateSweepLines(double currentTime)
        {
            ProfileGeometry profile = resolveProfileGeometry(stageProfile);
            float vanishingY = DrawHeight * profile.VanishingPointYRatio + 3f;
            float hitY = DrawHeight * hitLineYRatio - 8f;
            float depthHeight = Math.Max(20f, hitY - vanishingY);
            float topWidth = DrawWidth * profile.HighwayTopWidthRatio;
            float bottomWidth = DrawWidth * profile.HighwayBottomWidthRatio;

            for (int i = 0; i < sweepLines.Count; i++)
            {
                float cycle = (float)((currentTime * 0.00045 + i / (float)sweepLines.Count) % 1.0);
                float depth = 1f - cycle;
                float y = vanishingY + depthHeight * depth;
                float width = lerp(topWidth, bottomWidth, MathF.Pow(depth, 1.15f));

                var line = sweepLines[i];
                line.X = (DrawWidth - width) * 0.5f;
                line.Y = y;
                line.Width = width;
                line.Height = depth > 0.78f ? 2.0f : 1.2f;
                line.Alpha = 0.030f + (1f - depth) * 0.095f;
            }
        }

        private IReadOnlyList<string> buildVisibleLaneLabels()
        {
            var labels = new List<string>(visibleLaneCount);
            for (int visualLane = 0; visualLane < visibleLaneCount; visualLane++)
            {
                int actualLane = getActualLaneIndex(visualLane);
                labels.Add(resolveLaneLabel(actualLane));
            }

            return labels;
        }

        private int getActualLaneIndex(int visualLane)
        {
            if (!kickUsesGlobalLine)
                return visualLane;

            return visualLane >= laneLayout.KickLane
                ? visualLane + 1
                : visualLane;
        }

        private string resolveLaneLabel(int actualLane)
        {
            if (actualLane == laneLayout.KickLane)
                return "K";
            if (actualLane == laneLayout.SnareLane)
                return "SN";
            if (actualLane == laneLayout.HiHatLane)
                return "HH";
            if (actualLane == laneLayout.RideLane)
                return "RD";

            if (laneContains(DrumComponentCategory.Crash, actualLane) || laneContains(DrumComponentCategory.Crash2, actualLane))
                return "CR";
            if (laneContains(DrumComponentCategory.China, actualLane))
                return "CH";
            if (laneContains(DrumComponentCategory.Splash, actualLane))
                return "SP";
            if (laneContains(DrumComponentCategory.TomHigh, actualLane))
                return "T1";
            if (laneContains(DrumComponentCategory.TomMid, actualLane))
                return "T2";
            if (laneContains(DrumComponentCategory.TomLow, actualLane))
                return "T3";
            if (laneContains(DrumComponentCategory.Percussion, actualLane) || laneContains(DrumComponentCategory.AuxPercussion, actualLane))
                return "PR";

            return $"L{actualLane + 1}";
        }

        private bool laneContains(DrumComponentCategory category, int lane)
        {
            var lanes = laneLayout.GetLanesFor(category);
            for (int i = 0; i < lanes.Count; i++)
            {
                if (lanes[i] == lane)
                    return true;
            }

            return false;
        }

        private static float lerp(float start, float end, float amount)
            => start + (end - start) * amount;
    }
}
