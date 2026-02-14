using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.UI.Components;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;

namespace BeatSight.Game.Screens.Editor
{
    internal readonly record struct InspectorActionRowContract(
        int ColumnCount,
        float WidthFraction,
        Anchor Anchor,
        Anchor Origin);

    internal readonly record struct EditorHeaderLayoutContract(
        float StatusMaxWidth,
        float ActionHintMaxWidth,
        float PlaybackStatusMaxWidth);

    internal readonly record struct EditorTimelineToolboxLayoutContract(
        float ContentSpacingX,
        float ZoomSliderWidth,
        float ZoomSliderHeight,
        float WaveformSliderWidth,
        float WaveformSliderHeight,
        float SectionRowSpacingX,
        float MiniButtonHeight);

    internal readonly record struct InspectorLayoutContract(
        bool IsStackedLayout,
        InspectorActionRowContract[] ActionRows,
        EditorHeaderLayoutContract Header,
        EditorTimelineToolboxLayoutContract TimelineToolbox);

    public partial class EditorScreen
    {
        private bool inspectorStackedLayout;
        private bool inspectorCollapsed;
        private readonly List<BeatSightTextBox> inspectorTextBoxes = new();
        private readonly List<BasicButton> inspectorActionButtons = new();
        private readonly List<SpriteText> inspectorActionButtonTexts = new();
        private readonly List<(BasicButton Button, SpriteText Label, bool FillWidth, float WidthHint)> inspectorActionLayouts = new();
        private readonly List<(Container RowContainer, int ColumnCount)> inspectorActionRowContainers = new();
        private readonly List<BeatSightSliderBar> inspectorSliders = new();
        private readonly List<FillFlowContainer> inspectorSectionBodies = new();
        private readonly List<FillFlowContainer> inspectorFieldFlows = new();
        private readonly List<SpriteText> inspectorSectionTitleTexts = new();
        private readonly List<SpriteText> inspectorFieldLabelTexts = new();
        private readonly List<SpriteText> footerKeyTexts = new();
        private readonly List<SpriteText> footerActionTexts = new();
        private readonly Dictionary<EditorInspectorSectionKey, Drawable> inspectorSectionsByKey = new();
        private Drawable inspectorMetadataSection = null!;
        private Drawable inspectorTimingSection = null!;
        private Drawable inspectorStatsSection = null!;
        private Drawable inspectorGenerationSection = null!;
        private bool inspectorCompactHierarchy;

        private BasicTextBox releaseInput = null!;
        private BasicTextBox providerInput = null!;
        private BasicTextBox descriptionInput = null!;
        private BasicTextBox titleInput = null!;
        private BasicTextBox artistInput = null!;
        private BasicTextBox creatorInput = null!;
        private BasicTextBox sourceInput = null!;
        private BasicTextBox tagsInput = null!;
        private BasicTextBox bpmInput = null!;
        private BasicTextBox offsetInput = null!;
        private BasicTextBox tempoHintsInput = null!;

        private Bindable<string> quantizationGrid = new Bindable<string>("sixteenth");
        private BindableDouble maxSnapError = new BindableDouble(12.0) { MinValue = 1.0, MaxValue = 50.0, Precision = 0.1 };
        private BindableDouble confidenceThreshold = new BindableDouble(0.3) { MinValue = 0.1, MaxValue = 0.9, Precision = 0.01 };
        private BindableDouble detectionSensitivity = new BindableDouble(60.0) { MinValue = 1.0, MaxValue = 100.0, Precision = 1.0 };
        private BindableBool isolateDrums = new BindableBool(true);
        private BindableBool forceQuantization = new BindableBool(false);
        private BindableBool useMlClassifier = new BindableBool(true);

        private SpriteText noteCountValue = null!;
        private SpriteText selectionSummaryText = null!;
        private SpriteText mapLengthValue = null!;
        private SpriteText densityValue = null!;
        private SpriteText bpmStatValue = null!;
        private BeatSight.Game.UI.Components.Dropdown<string> componentReassignDropdown = null!;
        private readonly Bindable<string> componentReassignSelection = new Bindable<string>("kick");

        internal InspectorLayoutContract CaptureInspectorLayoutContract()
        {
            var rows = inspectorActionRowContainers
                .Select(entry => new InspectorActionRowContract(
                    entry.ColumnCount,
                    entry.RowContainer.Width,
                    entry.RowContainer.Anchor,
                    entry.RowContainer.Origin))
                .ToArray();

            var header = new EditorHeaderLayoutContract(
                statusText?.MaxWidth ?? 0f,
                actionHintText?.MaxWidth ?? 0f,
                playbackStatusText?.MaxWidth ?? 0f);

            var timelineToolbox = new EditorTimelineToolboxLayoutContract(
                timelineToolboxContentFlow?.Spacing.X ?? 0f,
                timelineZoomSliderContainer?.Width ?? 0f,
                timelineZoomSliderContainer?.Height ?? 0f,
                timelineWaveformSliderContainer?.Width ?? 0f,
                timelineWaveformSliderContainer?.Height ?? 0f,
                timelineSectionControlRows.Count > 0 ? timelineSectionControlRows[0].Spacing.X : 0f,
                timelineMiniButtons.Count > 0 ? timelineMiniButtons[0].Height : 0f);

            return new InspectorLayoutContract(inspectorStackedLayout, rows, header, timelineToolbox);
        }
    }
}
