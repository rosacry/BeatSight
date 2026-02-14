using System;
using System.Linq;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Graphics.UserInterface;
using osuTK;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private Drawable createInspectorSection(string title, params Drawable[] content)
        {
            var titleText = new SpriteText
            {
                Text = title,
                Font = BeatSightFont.Section(13f),
                Colour = EditorColours.TextPrimary
            };
            inspectorSectionTitleTexts.Add(titleText);

            var sectionBody = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(10),
                Padding = new MarginPadding { Horizontal = 13, Vertical = 10 },
                Children = new Drawable[]
                {
                    titleText
                }.Concat(content).ToArray()
            };
            inspectorSectionBodies.Add(sectionBody);

            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 9,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.SectionBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.08f
                    },
                    sectionBody
                }
            };
        }

        private Drawable createInspectorField(string label, Drawable control)
        {
            var labelText = new SpriteText
            {
                Text = label,
                Font = BeatSightFont.Caption(11.4f),
                Colour = EditorColours.TextSecondary,
                RelativeSizeAxes = Axes.X,
                AllowMultiline = true,
                Truncate = false
            };
            inspectorFieldLabelTexts.Add(labelText);

            var fieldFlow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(6),
                Children = new Drawable[]
                {
                    labelText,
                    new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Child = control
                    }
                }
            };
            inspectorFieldFlows.Add(fieldFlow);
            return fieldFlow;
        }

        private Drawable createInspectorFieldPair((string label, Drawable control) left, (string label, Drawable control) right)
        {
            return new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                RowDimensions = new[]
                {
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
                        createInspectorGridCell(createInspectorField(left.label, left.control), rightPadding: 4),
                        createInspectorGridCell(createInspectorField(right.label, right.control), leftPadding: 4)
                    }
                }
            };
        }

        private Drawable createInspectorGridCell(Drawable child, float leftPadding = 0, float rightPadding = 0)
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Padding = new MarginPadding
                {
                    Left = leftPadding,
                    Right = rightPadding
                },
                Child = child
            };
        }

        private Drawable createInspectorButtonRow(params (string label, Action action)[] buttons)
            => createInspectorButtonGrid(buttons.Length, buttons);

        private Drawable createInspectorButtonGrid(int columns, params (string label, Action action)[] buttons)
        {
            if (buttons.Length == 0)
                return new Container { RelativeSizeAxes = Axes.X, Height = 0 };

            int columnCount = Math.Clamp(columns, 1, buttons.Length);
            int rowCount = (buttons.Length + columnCount - 1) / columnCount;

            var columnDimensions = new Dimension[columnCount];
            for (int i = 0; i < columnCount; i++)
                columnDimensions[i] = new Dimension(GridSizeMode.Relative, 1f / columnCount);

            var content = new Drawable[rowCount][];
            for (int row = 0; row < rowCount; row++)
            {
                var rowChildren = new Drawable[columnCount];
                for (int column = 0; column < columnCount; column++)
                {
                    int buttonIndex = row * columnCount + column;
                    bool hasButton = buttonIndex < buttons.Length;
                    float rightPadding = column < columnCount - 1 ? inspectorButtonColumnSpacing : 0;
                    float bottomPadding = row < rowCount - 1 ? inspectorButtonRowSpacing : 0;

                    rowChildren[column] = new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Padding = new MarginPadding
                        {
                            Right = rightPadding,
                            Bottom = bottomPadding
                        },
                        Child = hasButton
                            ? createInspectorButton(buttons[buttonIndex].label, buttons[buttonIndex].action, fillWidth: true)
                            : new Container { RelativeSizeAxes = Axes.X, Height = 0 }
                    };
                }

                content[row] = rowChildren;
            }

            var grid = new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                RowDimensions = Enumerable.Repeat(new Dimension(GridSizeMode.AutoSize), rowCount).ToArray(),
                ColumnDimensions = columnDimensions,
                Content = content
            };

            var rowContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Width = 1f,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Child = grid
            };

            inspectorActionRowContainers.Add((rowContainer, columnCount));
            return rowContainer;
        }

        private Drawable createInspectorButton(string text, Action action, float width = 88, bool fillWidth = false)
        {
            var button = new BasicButton
            {
                Height = 34,
                Masking = true,
                CornerRadius = 7,
                BackgroundColour = EditorColours.Lighten(EditorColours.ControlsBackground, 1.16f),
                Action = action
            };
            inspectorActionButtons.Add(button);

            if (fillWidth)
                button.RelativeSizeAxes = Axes.X;
            else
                button.Size = new Vector2(width, 34);

            float maxTextWidth = fillWidth ? Math.Max(48f, width - 14f) : Math.Max(24f, width - 14f);

            var labelText = new SpriteText
            {
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Text = text,
                Font = BeatSightFont.Button(11.8f),
                Colour = EditorColours.TextPrimary,
                Truncate = true,
                MaxWidth = maxTextWidth,
                UseFullGlyphHeight = false
            };
            inspectorActionButtonTexts.Add(labelText);
            inspectorActionLayouts.Add((button, labelText, fillWidth, width));
            button.Child = labelText;

            return button;
        }

        private Drawable createInspectorStatBadge(string label, out SpriteText valueLabel)
        {
            valueLabel = new SpriteText
            {
                Text = "--",
                Font = BeatSightFont.Title(14.8f),
                Colour = EditorColours.TextPrimary
            };

            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Masking = true,
                CornerRadius = 7,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.Lighten(EditorColours.CardBackground, 1.05f)
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(3),
                        Padding = new MarginPadding { Horizontal = 9, Vertical = 7 },
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = label,
                                Font = BeatSightFont.Caption(10.2f),
                                Colour = EditorColours.TextSecondary
                            },
                            valueLabel
                        }
                    }
                }
            };
        }
    }
}
