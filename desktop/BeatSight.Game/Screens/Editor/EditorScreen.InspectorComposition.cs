using System;
using System.Globalization;
using System.Linq;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osuTK;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private Drawable createInspectorPanel()
        {
            inspectorTextBoxes.Clear();
            inspectorActionButtons.Clear();
            inspectorActionButtonTexts.Clear();
            inspectorActionLayouts.Clear();
            inspectorSliders.Clear();
            inspectorSectionBodies.Clear();
            inspectorFieldFlows.Clear();
            inspectorSectionTitleTexts.Clear();
            inspectorFieldLabelTexts.Clear();
            var inspectorCopy = EditorInspectorCopy.Active;

            releaseInput = createInspectorTextBox(inspectorCopy.PlaceholderRelease);
            releaseInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.ReleaseDate = e.NewValue);

            providerInput = createInspectorTextBox(inspectorCopy.PlaceholderProvider);
            providerInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.Provider = e.NewValue ?? string.Empty);

            descriptionInput = createInspectorTextBox(inspectorCopy.PlaceholderDescription);
            descriptionInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.Description = e.NewValue ?? string.Empty);

            titleInput = createInspectorTextBox("Song title");
            titleInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.Title = e.NewValue ?? string.Empty, refreshStatus: true);

            artistInput = createInspectorTextBox("Artist");
            artistInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.Artist = e.NewValue ?? string.Empty, refreshStatus: true);

            creatorInput = createInspectorTextBox("Mapper");
            creatorInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.Creator = e.NewValue ?? string.Empty);

            sourceInput = createInspectorTextBox("Source/Album");
            sourceInput.Current.ValueChanged += e => applyMetadataChange(meta => meta.Source = string.IsNullOrWhiteSpace(e.NewValue) ? null : e.NewValue);

            tagsInput = createInspectorTextBox("tag1, tag2");
            tagsInput.Current.ValueChanged += e => applyMetadataChange(meta =>
            {
                meta.Tags = string.IsNullOrWhiteSpace(e.NewValue)
                    ? new System.Collections.Generic.List<string>()
                    : e.NewValue!.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                        .Select(tag => tag.ToLowerInvariant())
                        .ToList();
            });

            bpmInput = createInspectorTextBox(inspectorCopy.PlaceholderBpm);
            bpmInput.Current.ValueChanged += e => applyBpmText(e.NewValue);

            offsetInput = createInspectorTextBox(inspectorCopy.PlaceholderOffset);
            offsetInput.Current.ValueChanged += e => applyOffsetText(e.NewValue);

            var titleArtistRow = createInspectorFieldPair(("Title", titleInput), ("Artist", artistInput));
            var creatorSourceRow = createInspectorFieldPair(("Creator", creatorInput), ("Source", sourceInput));
            var releaseProviderRow = createInspectorFieldPair((inspectorCopy.LabelRelease, releaseInput), (inspectorCopy.LabelProvider, providerInput));

            inspectorMetadataSection = createInspectorSection(inspectorCopy.SectionMetadata,
                titleArtistRow,
                creatorSourceRow,
                createInspectorField("Tags", tagsInput),
                releaseProviderRow,
                createInspectorField(inspectorCopy.LabelDescription, descriptionInput));

            var timingPairRow = createInspectorFieldPair(("BPM", bpmInput), ("Offset", offsetInput));
            inspectorTimingSection = createInspectorSection(inspectorCopy.SectionEdit,
                createInspectorField("Selection", createSelectionPanel(inspectorCopy)),
                timingPairRow,
                createInspectorButtonRow(("Half", () => adjustBpmByFactor(0.5)), ("x2", () => adjustBpmByFactor(2)), ("Reset", resetBpmToDefault)));

            var notesBadge = createInspectorStatBadge("Notes", out noteCountValue);
            var lengthBadge = createInspectorStatBadge("Length", out mapLengthValue);
            var densityBadge = createInspectorStatBadge("Density", out densityValue);
            var bpmBadge = createInspectorStatBadge("Active BPM", out bpmStatValue);

            var statsGrid = new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize),
                    new Dimension(GridSizeMode.AutoSize)
                },
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Relative, 0.5f),
                    new Dimension(GridSizeMode.Relative, 0.5f)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        createInspectorGridCell(notesBadge, rightPadding: 4),
                        createInspectorGridCell(lengthBadge, leftPadding: 4)
                    },
                    new Drawable[]
                    {
                        createInspectorGridCell(densityBadge, rightPadding: 4),
                        createInspectorGridCell(bpmBadge, leftPadding: 4)
                    }
                }
            };

            inspectorStatsSection = createInspectorSection(inspectorCopy.SectionStats, statsGrid);

            var generationQuantization = new BeatSight.Game.UI.Components.Dropdown<string>
            {
                RelativeSizeAxes = Axes.X,
                Items = new[] { "quarter", "eighth", "sixteenth", "thirty_second" },
                Current = quantizationGrid
            };

            var generationTopRow = createInspectorFieldPair(
                ("Grid", generationQuantization),
                ("Snap (ms)", createGenerationSlider(maxSnapError, value => $"{value:0.0} ms")));
            var generationSensitivityRow = createInspectorFieldPair(
                ("Confidence", createGenerationSlider(confidenceThreshold, value => $"{value:P0} ({value:0.00})")),
                ("Sensitivity", createGenerationSlider(detectionSensitivity, value => $"{value:0}")));

            var generationTogglesRow = new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize)
                },
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Relative, 0.34f),
                    new Dimension(GridSizeMode.Relative, 0.33f),
                    new Dimension(GridSizeMode.Relative, 0.33f)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        createInspectorGridCell(new BeatSightCheckbox { Current = isolateDrums, LabelText = "Isolate", LabelFontSize = 11.2f }, rightPadding: 4),
                        createInspectorGridCell(new BeatSightCheckbox { Current = forceQuantization, LabelText = "Force Quant.", LabelFontSize = 11.2f }, leftPadding: 2, rightPadding: 2),
                        createInspectorGridCell(new BeatSightCheckbox { Current = useMlClassifier, LabelText = "ML Classifier", LabelFontSize = 11.2f }, leftPadding: 4)
                    }
                }
            };

            inspectorGenerationSection = createInspectorSection(inspectorCopy.SectionAi,
                generationTopRow,
                generationSensitivityRow,
                generationTogglesRow,
                createInspectorField(inspectorCopy.LabelTempoHints, tempoHintsInput = createInspectorTextBox(inspectorCopy.PlaceholderTempoHints)),
                new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Direction = FillDirection.Horizontal,
                    Spacing = new Vector2(9, 0),
                    Children = new Drawable[]
                    {
                        new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            Width = 0.68f,
                            Height = 38,
                            Child = new BeatSightButton
                            {
                                RelativeSizeAxes = Axes.Both,
                                Text = "Run Pipeline",
                                BackgroundColour = UITheme.AccentPrimary,
                                Action = runPipeline
                            }
                        },
                        new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            Width = 0.32f,
                            Height = 38,
                            Child = new BeatSightButton
                            {
                                RelativeSizeAxes = Axes.Both,
                                Text = "Logs",
                                BackgroundColour = EditorColours.ControlsBackground,
                                Action = () => logOverlay.FadeIn(200)
                            }
                        }
                    }
                });

            inspectorSectionsByKey.Clear();
            inspectorSectionsByKey[EditorInspectorSectionKey.Metadata] = inspectorMetadataSection;
            inspectorSectionsByKey[EditorInspectorSectionKey.Edit] = inspectorTimingSection;
            inspectorSectionsByKey[EditorInspectorSectionKey.Stats] = inspectorStatsSection;
            inspectorSectionsByKey[EditorInspectorSectionKey.Ai] = inspectorGenerationSection;

            var sections = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(12),
                Padding = new MarginPadding { Horizontal = 12, Vertical = 12 },
                Children = getInspectorSectionsInOrder(compactOrder: false)
            };
            inspectorSectionsFlow = sections;

            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 15,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.InspectorBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.12f
                    },
                    new PassiveScrollContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Child = new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Child = sections
                        }
                    }
                }
            };
        }

        private Drawable createSelectionPanel(EditorInspectorCopyProfile inspectorCopy)
        {
            selectionSummaryText = new SpriteText
            {
                Text = inspectorCopy.SelectionNoneText,
                Font = BeatSightFont.Caption(13.4f),
                Colour = EditorColours.TextSecondary,
                RelativeSizeAxes = Axes.X,
                AllowMultiline = true
            };
            componentReassignDropdown = new BeatSight.Game.UI.Components.Dropdown<string>
            {
                RelativeSizeAxes = Axes.X,
                Items = Array.Empty<string>(),
                Current = componentReassignSelection
            };
            refreshComponentReassignmentOptions();

            var navigationRow = createInspectorButtonRow(("Prev", () => jumpToAdjacentNote(false)), ("Next", () => jumpToAdjacentNote(true)), ("Center", centerOnSelection));
            var selectionRow = createInspectorButtonRow((inspectorCopy.SelectionButton, selectAllNotes), (inspectorCopy.QuantizeButton, quantizeSelectedToGrid));
            var transientRow = createInspectorButtonRow(("Snap Audio", snapSelectionToTransient));
            var manuscriptLaneRow = createInspectorButtonRow(("Notation -", () => shiftSelectionToAdjacentNotationLane(false)), ("Notation +", () => shiftSelectionToAdjacentNotationLane(true)));
            var manuscriptArticulationRow = createInspectorButtonRow(
                ("Ghost", () => applyNotationArticulationPreset(NotationArticulationPreset.Ghost)),
                ("Normal", () => applyNotationArticulationPreset(NotationArticulationPreset.Normal)),
                ("Accent", () => applyNotationArticulationPreset(NotationArticulationPreset.Accent)));
            var editRow = createInspectorButtonRow((inspectorCopy.DuplicateButton, duplicateSelectedNote), (inspectorCopy.DeleteButton, deleteSelectedNote));
            var adjustmentRow = createInspectorButtonGrid(2,
                ("Nudge -", () => nudgeSelectedNote(false)),
                ("Nudge +", () => nudgeSelectedNote(true)),
                ("Vel -", () => adjustSelectedVelocity(false)),
                ("Vel +", () => adjustSelectedVelocity(true)));
            var shortcutHint = new SpriteText
            {
                Text = inspectorCopy.ShortcutHint,
                Font = BeatSightFont.Caption(10.8f),
                Colour = EditorColours.TextMuted,
                AllowMultiline = true,
                RelativeSizeAxes = Axes.X
            };
            var componentRow = new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                RowDimensions = new[]
                {
                    new Dimension(GridSizeMode.AutoSize)
                },
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Relative, 0.66f),
                    new Dimension(GridSizeMode.Relative, 0.34f)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Padding = new MarginPadding { Right = 6 },
                            Child = componentReassignDropdown
                        },
                        new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Child = createInspectorButton(inspectorCopy.ReassignApplyButton, reassignSelectedComponent, fillWidth: true)
                        }
                    }
                }
            };

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(7),
                Children = new Drawable[]
                {
                    selectionSummaryText,
                    selectionRow,
                    navigationRow,
                    adjustmentRow,
                    componentRow,
                    manuscriptLaneRow,
                    manuscriptArticulationRow,
                    transientRow,
                    editRow,
                    shortcutHint
                }
            };
        }

        private BeatSightTextBox createInspectorTextBox(string placeholder)
        {
            var textBox = new BeatSightTextBox
            {
                RelativeSizeAxes = Axes.X,
                Height = 36,
                PlaceholderText = placeholder,
                CornerRadius = 8,
                FontSize = 13.8f
            };
            inspectorTextBoxes.Add(textBox);
            return textBox;
        }

        private Drawable createGenerationSlider(BindableDouble bindable, Func<double, string> formatter)
        {
            var slider = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = 26,
                Current = bindable,
                DragStepMultiplier = 1,
                KeyboardStepMultiplier = 1
            };
            inspectorSliders.Add(slider);

            var valueText = new SpriteText
            {
                Font = BeatSightFont.Caption(10.8f),
                Colour = EditorColours.TextSecondary,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Text = formatter(bindable.Value)
            };

            var minText = new SpriteText
            {
                Font = BeatSightFont.Caption(10f),
                Colour = EditorColours.TextMuted,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Text = bindable.MinValue.ToString("0.##", CultureInfo.InvariantCulture)
            };

            var maxText = new SpriteText
            {
                Font = BeatSightFont.Caption(10f),
                Colour = EditorColours.TextMuted,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Text = bindable.MaxValue.ToString("0.##", CultureInfo.InvariantCulture)
            };

            bindable.BindValueChanged(e =>
            {
                valueText.Text = formatter(e.NewValue);
            }, true);

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(4, 0),
                Children = new Drawable[]
                {
                    slider,
                    new GridContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 15,
                        ColumnDimensions = new[]
                        {
                            new Dimension(GridSizeMode.Relative, 0.25f),
                            new Dimension(GridSizeMode.Relative, 0.5f),
                            new Dimension(GridSizeMode.Relative, 0.25f)
                        },
                        Content = new[]
                        {
                            new Drawable[]
                            {
                                minText,
                                valueText,
                                maxText
                            }
                        }
                    }
                }
            };
        }
    }
}
