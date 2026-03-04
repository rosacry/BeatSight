using System;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private Drawable createHeader()
        {
            statusText = new SpriteText
            {
                Text = string.Empty,
                Font = BeatSightFont.Section(18.4f),
                Colour = EditorColours.TextPrimary,
                AllowMultiline = true,
                MaxWidth = 560,
                Truncate = false,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft
            };

            statusDetailLine = new SpriteText
            {
                Font = BeatSightFont.Caption(11.6f),
                Colour = EditorColours.TextSecondary,
                Alpha = 0,
                AllowMultiline = true,
                MaxWidth = 560,
                Truncate = false,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft
            };

            var statusColumn = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 5),
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Children = new Drawable[]
                {
                    statusText,
                    statusDetailLine
                }
            };
            headerStatusColumn = statusColumn;

            timeText = new SpriteText
            {
                Text = formatTime(0),
                Font = BeatSightFont.Numeral(22f),
                Colour = EditorColours.TextPrimary,
                Spacing = Vector2.Zero,
                AllowMultiline = false,
                UseFullGlyphHeight = false,
                Shadow = false,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Margin = new MarginPadding()
            };

            var timeCaption = new SpriteText
            {
                Text = "TIMELINE",
                Font = BeatSightFont.Caption(10f),
                Colour = EditorColours.TextMuted,
                Spacing = Vector2.Zero,
                AllowMultiline = false,
                UseFullGlyphHeight = false,
                Shadow = false,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre
            };
            headerTimeCaptionText = timeCaption;

            var timeBadge = new Container
            {
                Size = new Vector2(188, 54),
                Masking = true,
                CornerRadius = 12,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.CardBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.14f
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 12, Vertical = 3 },
                        Child = headerTimeContentContainer = new Container
                        {
                            RelativeSizeAxes = Axes.Both,
                            Children = new Drawable[]
                            {
                                timeCaption,
                                timeText
                            }
                        }
                    },
                }
            };
            headerTimeBadgeContainer = timeBadge;

            playPauseButton = new EditorButton("Play", EditorColours.AccentPlay)
            {
                Size = new Vector2(120, 42),
                EnableScaleAnimation = false,
                Action = togglePlayback
            };

            saveButton = new EditorButton("Save", EditorColours.AccentSave)
            {
                Size = new Vector2(120, 42),
                EnableScaleAnimation = false,
                Action = saveBeatmap
            };

            undoButton = new EditorButton("Undo", EditorColours.AccentUndo)
            {
                Size = new Vector2(104, 42),
                EnableScaleAnimation = false,
                Action = undoLastEdit
            };

            redoButton = new EditorButton("Redo", EditorColours.AccentRedo)
            {
                Size = new Vector2(104, 42),
                EnableScaleAnimation = false,
                Action = redoLastEdit
            };

            previewToggle = new PreviewToggleButton(previewMode)
            {
                Size = new Vector2(146, 42),
                EnableScaleAnimation = false,
                Alpha = 0
            };

            var buttonFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(10, 0),
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Children = new Drawable[]
                {
                    playPauseButton,
                    saveButton,
                    undoButton,
                    redoButton,
                    previewToggle
                }
            };
            headerButtonFlow = buttonFlow;

            actionHintText = new SpriteText
            {
                Font = BeatSightFont.Caption(11.4f),
                Colour = EditorColours.TextSecondary,
                Alpha = 0,
                Text = string.Empty,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                MaxWidth = 1040,
                AllowMultiline = true,
                Truncate = false
            };

            playbackStatusText = new SpriteText
            {
                Font = BeatSightFont.Caption(11.4f),
                Colour = EditorColours.Warning,
                Alpha = 0,
                Text = string.Empty,
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                MaxWidth = 1040,
                AllowMultiline = true,
                Truncate = false
            };

            historyPanel = new Container
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.TopRight,
                Origin = Anchor.TopRight,
                Margin = new MarginPadding { Top = 72, Right = 24 },
                Child = new Container
                {
                    AutoSizeAxes = Axes.Both,
                    CornerRadius = 9,
                    Masking = true,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = EditorColours.HistoryBackground
                        },
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = EditorColours.PanelStroke,
                            Alpha = 0.16f
                        },
                        new FillFlowContainer
                        {
                            AutoSizeAxes = Axes.Both,
                            Direction = FillDirection.Horizontal,
                            Spacing = new Vector2(14, 0),
                            Padding = new MarginPadding { Horizontal = 12, Vertical = 8 },
                            Children = new Drawable[]
                            {
                                createHistoryColumn("Undo", out undoHeaderText, out undoHistoryFlow),
                                createHistoryColumn("Redo", out redoHeaderText, out redoHistoryFlow)
                            }
                        }
                    }
                }
            };

            backButton.Margin = new MarginPadding();
            backButton.Anchor = Anchor.TopLeft;
            backButton.Origin = Anchor.TopLeft;

            var leadFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(18, 0),
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Children = new Drawable[]
                {
                    backButton,
                    new Container
                    {
                        AutoSizeAxes = Axes.Both,
                        Child = statusColumn
                    }
                }
            };
            headerLeadFlow = leadFlow;

            var mainRow = new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 58f,
                Children = new Drawable[]
                {
                    new Container
                    {
                        AutoSizeAxes = Axes.Both,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Child = leadFlow
                    },
                    new Container
                    {
                        AutoSizeAxes = Axes.Both,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Child = timeBadge
                    },
                    new Container
                    {
                        AutoSizeAxes = Axes.Both,
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        Child = buttonFlow
                    }
                }
            };
            headerPrimaryRowContainer = mainRow;
            historyPanel.Hide();

            var informationFlow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.None,
                Height = 0f,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(6),
                Anchor = Anchor.TopCentre,
                Origin = Anchor.TopCentre,
                Alpha = 0f,
                Children = new Drawable[]
                {
                    actionHintText,
                    playbackStatusText
                }
            };
            headerInformationFlow = informationFlow;

            var content = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, headerContentSpacingY),
                Children = new Drawable[]
                {
                    mainRow,
                    informationFlow
                }
            };

            var header = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.HeaderBackground
                    },
                    headerPrimaryAccentBox = new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 84f,
                        Anchor = Anchor.TopLeft,
                        Origin = Anchor.TopLeft,
                        Colour = ColourInfo.GradientVertical(
                            EditorColours.PanelStroke.Opacity(0.38f),
                            Color4.Transparent)
                    },
                    headerContentContainer = new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Padding = new MarginPadding { Left = 10, Right = 10, Top = 2, Bottom = 0 },
                        Child = content
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.X,
                        Height = 1,
                        Anchor = Anchor.BottomLeft,
                        Origin = Anchor.BottomLeft,
                        Colour = EditorColours.Divider
                    }
                }
            };

            setStatusBase(string.Empty);
            setStatusDetail("Load or import audio to begin mapping.");
            updateActionButtons();
            updatePlaybackAvailabilityUI();
            updateHeaderInformationVisibility();
            layoutHeaderTimeBadgeContent(force: true);

            return header;
        }

        private void layoutHeaderTimeBadgeContent(bool force = false)
        {
            if (headerTimeContentContainer == null || headerTimeCaptionText == null || timeText == null)
                return;

            float contentHeight = headerTimeContentContainer.DrawHeight;
            if (!float.IsFinite(contentHeight) || contentHeight <= 0f)
            {
                float fallbackBadgeHeight = headerTimeBadgeContainer?.DrawHeight > 0
                    ? headerTimeBadgeContainer.DrawHeight
                    : headerTimeBadgeContainer?.Height ?? 54f;
                contentHeight = Math.Max(1f, fallbackBadgeHeight - 6f);
            }

            float captionHeight = headerTimeCaptionText.DrawHeight;
            if (!float.IsFinite(captionHeight) || captionHeight <= 0f)
                captionHeight = Math.Max(6f, headerTimeCaptionText.Font.Size * 0.94f);

            float valueHeight = timeText.DrawHeight;
            if (!float.IsFinite(valueHeight) || valueHeight <= 0f)
                valueHeight = Math.Max(14f, timeText.Font.Size * 0.96f);

            if (!force
                && Math.Abs(contentHeight - lastHeaderTimeContentHeight) < 0.25f)
            {
                return;
            }

            float captionOffsetY = (-contentHeight * 0.18f) + (captionHeight * 0.1f);
            float valueOffsetY = (contentHeight * 0.09f) + Math.Min(3f, valueHeight * 0.08f);

            headerTimeCaptionText.Y = captionOffsetY;
            timeText.Y = valueOffsetY;

            lastHeaderTimeContentHeight = contentHeight;
        }
    }
}
