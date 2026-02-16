using System;
using System.Collections.Generic;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osuTK;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void applyCompactEditorDensity(EditorResponsiveLayoutMetrics metrics, Vector2 viewport, bool force)
        {
            float compactBlend = Math.Clamp((820f - viewport.Y) / 160f, 0f, 1f);
            float widthCompactBlend = Math.Clamp((1500f - viewport.X) / 380f, 0f, 1f);
            compactBlend = Math.Max(compactBlend, widthCompactBlend);
            if (metrics.UseStackedInspector)
                compactBlend = Math.Max(compactBlend, 0.42f);
            else
                compactBlend = Math.Max(0f, compactBlend - 0.28f);

            if (viewport.Y <= 760f)
                compactBlend = Math.Max(compactBlend, 0.82f);

            if (!force && lastCompactBlend >= 0 && Math.Abs(compactBlend - lastCompactBlend) < 0.015f)
                return;

            applyHeaderDensity(compactBlend, viewport);
            applyTimelineToolboxDensity(compactBlend, viewport);
            applyInspectorDensity(compactBlend, viewport);
            applyFooterDensity(compactBlend, viewport);
            applyInspectorHierarchy(compactBlend);

            lastCompactBlend = compactBlend;
        }

        private void applyInspectorHierarchy(float compactBlend)
        {
            if (inspectorSectionsFlow == null
                || inspectorMetadataSection == null
                || inspectorTimingSection == null
                || inspectorStatsSection == null
                || inspectorGenerationSection == null)
            {
                return;
            }

            bool compactOrder = compactBlend >= 0.42f;
            if (compactOrder == inspectorCompactHierarchy)
                return;

            inspectorCompactHierarchy = compactOrder;
            inspectorSectionsFlow.Clear(false);
            foreach (var section in getInspectorSectionsInOrder(compactOrder))
                inspectorSectionsFlow.Add(section);
        }

        private Drawable[] getInspectorSectionsInOrder(bool compactOrder)
        {
            if (inspectorSectionsByKey.Count == 0)
                return Array.Empty<Drawable>();

            var orderedKeys = EditorInspectorCopy.GetSectionOrder(compactOrder);
            var result = new List<Drawable>(orderedKeys.Length);
            foreach (var key in orderedKeys)
            {
                if (inspectorSectionsByKey.TryGetValue(key, out var section))
                    result.Add(section);
            }

            return result.ToArray();
        }

        private void applyHeaderDensity(float compactBlend, Vector2 viewport)
        {
            float aspect = viewport.X / Math.Max(1f, viewport.Y);
            float ultraWideRelax = Math.Clamp((aspect - 2.0f) / 0.85f, 0f, 1f);
            float widthRelax = Math.Clamp((viewport.X - 1920f) / 1200f, 0f, 1f);
            float statusFontSize = blend(18.4f, 16f, compactBlend) + ultraWideRelax * 0.55f;
            float detailFontSize = blend(11.6f, 10.3f, compactBlend) + ultraWideRelax * 0.28f;
            float timeFontSize = blend(22.4f, 19.4f, compactBlend) + ultraWideRelax * 0.7f;
            float timeCaptionFontSize = blend(9.8f, 8.8f, compactBlend) + ultraWideRelax * 0.2f;
            float hintFontSize = blend(11.4f, 10.2f, compactBlend) + ultraWideRelax * 0.25f;
            float buttonHeight = blend(42f, 36f, compactBlend) + ultraWideRelax * 1.1f;
            float buttonFontSize = blend(13.4f, 11.8f, compactBlend) + widthRelax * 0.35f;
            float buttonSpacing = blend(8f, 6f, compactBlend) + ultraWideRelax * 1.1f;
            float horizontalPadding = blend(24f, 18f, compactBlend) + ultraWideRelax * 2.3f;
            float verticalPadding = blend(12f, 9f, compactBlend) + ultraWideRelax * 0.8f;
            float infoSpacing = blend(6f, 4f, compactBlend);
            float contentSpacing = blend(10f, 8f, compactBlend);
            float playButtonWidth = blend(114f, 96f, compactBlend);
            float saveButtonWidth = blend(112f, 96f, compactBlend);
            float undoButtonWidth = blend(98f, 84f, compactBlend);
            float redoButtonWidth = blend(98f, 84f, compactBlend);
            float previewButtonWidth = blend(132f, 110f, compactBlend);
            float timeBadgeWidth = blend(196f, 170f, compactBlend);
            float timeBadgeHeight = blend(62f, 54f, compactBlend);
            float controlsBaseWidth = playButtonWidth + saveButtonWidth + undoButtonWidth + redoButtonWidth + previewButtonWidth + buttonSpacing * 4f;
            float availableContentWidth = Math.Max(1f, viewport.X - (horizontalPadding * 2f + timeBadgeWidth));
            float targetButtonBudget = ResponsiveLayout.ClampFraction(viewport.X, 0.38f, 360f, 760f);
            float buttonBudget = Math.Clamp(targetButtonBudget, 320f, Math.Max(320f, availableContentWidth - 220f));
            float widthScale = Math.Clamp(buttonBudget / Math.Max(1f, controlsBaseWidth), 0.56f, 1.06f);
            float hierarchyScale = Math.Clamp(1f - compactBlend * 0.04f + ultraWideRelax * 0.03f, 0.94f, 1.05f);
            float controlScale = Math.Clamp(widthScale * hierarchyScale, 0.60f, 1.10f);

            buttonSpacing *= Math.Clamp(controlScale, 0.9f, 1.06f);
            buttonHeight *= Math.Clamp(controlScale, 0.92f, 1.04f);
            playButtonWidth *= controlScale;
            saveButtonWidth *= controlScale;
            undoButtonWidth *= controlScale;
            redoButtonWidth *= controlScale;
            previewButtonWidth *= controlScale;

            statusText.Font = BeatSightFont.Section(statusFontSize);
            float desiredStatusWidth = blend(560f, 480f, compactBlend) + ultraWideRelax * 110f;
            float minStatusWidth = viewport.X <= 1400f ? 220f : 280f;
            float statusRemaining = Math.Max(minStatusWidth, availableContentWidth - controlsBaseWidth * controlScale - 24f);
            statusText.MaxWidth = Math.Clamp(Math.Min(desiredStatusWidth, statusRemaining), minStatusWidth, desiredStatusWidth + 32f);
            statusDetailLine.Font = BeatSightFont.Caption(detailFontSize);
            statusDetailLine.MaxWidth = statusText.MaxWidth;

            if (headerStatusColumn != null)
                headerStatusColumn.Spacing = new Vector2(0, blend(5f, 3.5f, compactBlend));

            if (headerTimeBadgeContainer != null)
            {
                headerTimeBadgeContainer.Size = new Vector2(timeBadgeWidth, timeBadgeHeight);
                headerTimeBadgeContainer.CornerRadius = blend(12f, 10f, compactBlend);
            }

            if (headerTimeCaptionText != null)
                headerTimeCaptionText.Font = BeatSightFont.Caption(timeCaptionFontSize);

            if (timeText != null)
                timeText.Font = BeatSightFont.Numeral(timeFontSize);

            if (actionHintText != null)
            {
                actionHintText.Font = BeatSightFont.Caption(hintFontSize);
                actionHintText.MaxWidth = blend(1040f, 860f, compactBlend) + ultraWideRelax * 180f;
            }

            if (playbackStatusText != null)
            {
                playbackStatusText.Font = BeatSightFont.Caption(hintFontSize);
                playbackStatusText.MaxWidth = blend(1040f, 860f, compactBlend) + ultraWideRelax * 180f;
            }

            if (headerButtonFlow != null)
                headerButtonFlow.Spacing = new Vector2(buttonSpacing, 0);

            if (playPauseButton != null)
            {
                playPauseButton.Size = new Vector2(playButtonWidth, buttonHeight);
                playPauseButton.SetContentDensity(buttonFontSize, blend(9f, 8f, compactBlend));
            }
            if (saveButton != null)
            {
                saveButton.Size = new Vector2(saveButtonWidth, buttonHeight);
                saveButton.SetContentDensity(buttonFontSize, blend(9f, 8f, compactBlend));
            }
            if (undoButton != null)
            {
                undoButton.Size = new Vector2(undoButtonWidth, buttonHeight);
                undoButton.SetContentDensity(buttonFontSize, blend(9f, 8f, compactBlend));
            }
            if (redoButton != null)
            {
                redoButton.Size = new Vector2(redoButtonWidth, buttonHeight);
                redoButton.SetContentDensity(buttonFontSize, blend(9f, 8f, compactBlend));
            }
            if (previewToggle != null)
            {
                previewToggle.Size = new Vector2(previewButtonWidth, buttonHeight);
                previewToggle.SetContentDensity(
                    labelSize: blend(12.8f, 11.3f, compactBlend) + widthRelax * 0.25f,
                    iconSize: blend(15f, 13.4f, compactBlend),
                    spacing: blend(6f, 5f, compactBlend),
                    cornerRadius: blend(9f, 8f, compactBlend));
            }

            if (headerInformationFlow != null)
                headerInformationFlow.Spacing = new Vector2(0, infoSpacing);

            if (headerContentContainer != null)
                headerContentContainer.Padding = new MarginPadding { Horizontal = horizontalPadding, Vertical = verticalPadding };

            if (headerContentContainer?.Child is FillFlowContainer contentFlow)
                contentFlow.Spacing = new Vector2(0, contentSpacing);
        }

        private void applyInspectorDensity(float compactBlend, Vector2 viewport)
        {
            float aspect = viewport.X / Math.Max(1f, viewport.Y);
            float ultraWideRelax = Math.Clamp((aspect - 2.0f) / 0.85f, 0f, 1f);
            float textBoxHeight = blend(36f, 32f, compactBlend) + ultraWideRelax * 0.8f;
            float textBoxFontSize = blend(13.8f, 12.8f, compactBlend) + ultraWideRelax * 0.22f;
            float sliderHeight = blend(26f, 23f, compactBlend);
            float buttonHeight = blend(34f, 30f, compactBlend) + ultraWideRelax * 0.65f;
            float buttonCorner = blend(7f, 6f, compactBlend);
            float buttonFont = blend(11.6f, 10.5f, compactBlend) + ultraWideRelax * 0.2f;
            float sectionTitleFont = blend(13f, 12f, compactBlend) + ultraWideRelax * 0.35f;
            float fieldLabelFont = blend(11.4f, 10.6f, compactBlend) + ultraWideRelax * 0.25f;
            float sectionSpacing = blend(10.6f, 8.5f, compactBlend) + ultraWideRelax * 0.8f;
            float sectionPaddingH = blend(13f, 11f, compactBlend) + ultraWideRelax * 1.2f;
            float sectionPaddingV = blend(10f, 8f, compactBlend) + ultraWideRelax * 0.65f;
            float fieldSpacing = blend(6.6f, 5.4f, compactBlend);
            float sectionsSpacing = blend(12.8f, 10.7f, compactBlend) + ultraWideRelax * 0.9f;
            float outerPaddingH = blend(12f, 10f, compactBlend) + ultraWideRelax * 1.2f;
            float outerPaddingV = blend(12f, 10f, compactBlend) + ultraWideRelax * 0.6f;

            foreach (var textBox in inspectorTextBoxes)
            {
                textBox.Height = textBoxHeight;
                textBox.TextSize = textBoxFontSize;
                textBox.CornerRadius = blend(8f, 7f, compactBlend);
            }

            foreach (var slider in inspectorSliders)
                slider.Height = sliderHeight;

            foreach (var button in inspectorActionButtons)
            {
                button.Height = buttonHeight;
                button.CornerRadius = buttonCorner;
            }
            foreach (var label in inspectorActionButtonTexts)
                label.Font = BeatSightFont.Button(buttonFont);

            refreshInspectorActionLabelWidths();
            applyInspectorActionRowWidths(compactBlend, viewport);

            foreach (var titleText in inspectorSectionTitleTexts)
                titleText.Font = BeatSightFont.Section(sectionTitleFont);

            foreach (var labelText in inspectorFieldLabelTexts)
                labelText.Font = BeatSightFont.Caption(fieldLabelFont);

            foreach (var body in inspectorSectionBodies)
            {
                body.Spacing = new Vector2(0, sectionSpacing);
                body.Padding = new MarginPadding { Horizontal = sectionPaddingH, Vertical = sectionPaddingV };
            }

            foreach (var flow in inspectorFieldFlows)
                flow.Spacing = new Vector2(0, fieldSpacing);

            if (inspectorSectionsFlow != null)
            {
                inspectorSectionsFlow.Spacing = new Vector2(0, sectionsSpacing);
                inspectorSectionsFlow.Padding = new MarginPadding { Horizontal = outerPaddingH, Vertical = outerPaddingV };
            }
        }

        private void applyInspectorActionRowWidths(float compactBlend, Vector2 viewport)
        {
            if (inspectorActionRowContainers.Count == 0)
                return;

            float viewportWidth = viewport.X > 0 ? viewport.X : 1280f;

            foreach (var (rowContainer, columnCount) in inspectorActionRowContainers)
            {
                float widthFraction = EditorResponsiveLayout.ResolveInspectorActionRowWidthFraction(
                    viewportWidth,
                    inspectorStackedLayout,
                    columnCount,
                    compactBlend);

                if (inspectorStackedLayout && widthFraction < 0.999f)
                {
                    rowContainer.Anchor = Anchor.TopCentre;
                    rowContainer.Origin = Anchor.TopCentre;
                    rowContainer.Width = widthFraction;
                }
                else
                {
                    rowContainer.Anchor = Anchor.TopLeft;
                    rowContainer.Origin = Anchor.TopLeft;
                    rowContainer.Width = 1f;
                }
            }
        }

        private void applyFooterDensity(float compactBlend, Vector2 viewport)
        {
            float aspect = viewport.X / Math.Max(1f, viewport.Y);
            float ultraWideRelax = Math.Clamp((aspect - 2.0f) / 0.85f, 0f, 1f);
            float collapseScale = footerTipsCollapsed ? 0.42f : 1f;
            if (footerRootContainer != null)
            {
                footerRootContainer.Padding = new MarginPadding
                {
                    Horizontal = blend(12f, 9f, compactBlend) + ultraWideRelax * 1.2f,
                    Vertical = (blend(11f, 6.5f, compactBlend) + ultraWideRelax * 0.5f) * collapseScale
                };
                footerRootContainer.CornerRadius = blend(12f, 9.5f, compactBlend);
            }

            if (footerInnerContainer != null)
            {
                footerInnerContainer.Padding = new MarginPadding
                {
                    Horizontal = blend(15f, 9f, compactBlend),
                    Vertical = blend(9f, 4.5f, compactBlend) * collapseScale
                };
            }

            if (footerTipFlow != null)
                footerTipFlow.Spacing = new Vector2(blend(18f, 10.5f, compactBlend) + ultraWideRelax * 1.2f, 0);

            foreach (var keyText in footerKeyTexts)
            {
                keyText.Font = BeatSightFont.Title(blend(11.2f, 9.6f, compactBlend));
                keyText.Margin = new MarginPadding
                {
                    Horizontal = blend(7f, 5.5f, compactBlend),
                    Vertical = blend(4f, 2.5f, compactBlend)
                };
            }

            foreach (var actionText in footerActionTexts)
                actionText.Font = BeatSightFont.Caption(blend(11f, 9.4f, compactBlend));

            if (footerCollapsedText != null)
                footerCollapsedText.Font = BeatSightFont.Caption(blend(11.2f, 9.8f, compactBlend));
        }

        private static float blend(float normal, float compact, float t)
            => normal + (compact - normal) * t;
    }
}
