using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osuTK;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private Drawable createFooter()
        {
            footerKeyTexts.Clear();
            footerActionTexts.Clear();

            var tips = new (string key, string action)[]
            {
                ("F1", "Show/hide shortcuts"),
                ("Esc", "Clear selection / Back"),
                ("Space", "Play/Pause"),
                ("Shift+Space", "Rewind to start"),
                ("Ctrl+[ / Ctrl+]", "Playback rate"),
                ("Ctrl+0", "Reset playback rate"),
                ("Ctrl+T", "Open timing setup"),
                ("Left/Right", "Seek"),
                ("Ctrl +/-", "Zoom timeline"),
                ("Ctrl+Alt +/-", "Scale waveform"),
                ("[ / ]", "Change snap"),
                ("G", "Toggle beat grid"),
                ("I", "Toggle inspector panel"),
                (", / .", "Previous/next note"),
                ("Home / End", "Jump first/last note"),
                ("PgUp/PgDn", "Shift selection notation lane"),
                ("Ctrl+PgUp/PgDn", "Cycle selection articulation"),
                ("1-9", "Quick lane reassign (left->right)"),
                ("Alt+Left/Right", "Nudge selected note/range"),
                ("Delete", "Remove selected note/range"),
                ("Q", "Quantize selected note/range"),
                ("Ctrl+A", "Select all notes"),
                ("Ctrl+D", "Duplicate selected note/range"),
                ("Ctrl+S", "Save"),
                ("Ctrl+Shift+H", "Toggle history panel"),
                ("Ctrl+Z", "Undo"),
                ("Ctrl+Y / Ctrl+Shift+Z", "Redo")
            };

            var tipFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(18, 0),
                Children = tips.Select(t => createTip(t.key, t.action)).ToArray()
            };
            footerTipFlow = tipFlow;

            var horizontalScroll = new BeatSightScrollContainer(Direction.Horizontal)
            {
                RelativeSizeAxes = Axes.Both,
                ScrollbarVisible = false,
                Child = new Container
                {
                    RelativeSizeAxes = Axes.Y,
                    AutoSizeAxes = Axes.X,
                    Child = tipFlow
                }
            };

            footerCollapsedText = new SpriteText
            {
                Text = "Shortcuts hidden. Press F1 to show.",
                Font = BeatSightFont.Caption(11.2f),
                Colour = EditorColours.TextSecondary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Margin = new MarginPadding { Left = 2 }
            };

            var root = footerRootContainer = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Horizontal = 12, Vertical = 11 },
                Masking = true,
                CornerRadius = 12,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.HeaderBackground
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.PanelStroke,
                        Alpha = 0.1f
                    },
                    footerInnerContainer = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 15, Vertical = 9 },
                        Children = new Drawable[]
                        {
                            footerTipsContainer = new Container
                            {
                                RelativeSizeAxes = Axes.Both,
                                Child = horizontalScroll
                            },
                            footerCollapsedContainer = new Container
                            {
                                RelativeSizeAxes = Axes.Both,
                                Child = new FillFlowContainer
                                {
                                    AutoSizeAxes = Axes.Both,
                                    Direction = FillDirection.Horizontal,
                                    Spacing = new Vector2(10, 0),
                                    Anchor = Anchor.CentreLeft,
                                    Origin = Anchor.CentreLeft,
                                    Children = new Drawable[]
                                    {
                                        createCollapsedFooterKeycap("F1"),
                                        footerCollapsedText
                                    }
                                }
                            }
                        }
                    },
                }
            };

            refreshFooterShortcutVisibility();
            return root;
        }

        private Drawable createTip(string key, string action)
        {
            var keyText = new SpriteText
            {
                Text = key,
                Font = BeatSightFont.Title(11.2f),
                Colour = EditorColours.TextPrimary,
                Margin = new MarginPadding { Horizontal = 7, Vertical = 4 },
                UseFullGlyphHeight = false
            };
            footerKeyTexts.Add(keyText);

            var actionText = new SpriteText
            {
                Text = action,
                Font = BeatSightFont.Caption(11f),
                Colour = EditorColours.TextSecondary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };
            footerActionTexts.Add(actionText);

            return new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(8, 0),
                Children = new Drawable[]
                {
                    new Container
                    {
                        AutoSizeAxes = Axes.Both,
                        Masking = true,
                        CornerRadius = 6,
                        Children = new Drawable[]
                        {
                            new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = EditorColours.Lighten(EditorColours.ControlsBackground, 1.18f)
                            },
                            keyText
                        }
                    },
                    actionText
                }
            };
        }

        private Drawable createCollapsedFooterKeycap(string key)
        {
            return new Container
            {
                AutoSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 6,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = EditorColours.Lighten(EditorColours.ControlsBackground, 1.18f)
                    },
                    new SpriteText
                    {
                        Text = key,
                        Font = BeatSightFont.Title(11.2f),
                        Colour = EditorColours.TextPrimary,
                        Margin = new MarginPadding { Horizontal = 7, Vertical = 4 },
                        UseFullGlyphHeight = false
                    }
                }
            };
        }

        private void toggleFooterShortcutsCollapsed()
        {
            footerTipsCollapsed = !footerTipsCollapsed;
            refreshFooterShortcutVisibility();
            applyResponsiveEditorLayout(force: true);
            appendStatusDetail(footerTipsCollapsed ? "Shortcuts hidden" : "Shortcuts shown");
        }

        private void refreshFooterShortcutVisibility()
        {
            if (footerTipsContainer == null || footerCollapsedContainer == null)
                return;

            bool collapsed = footerTipsCollapsed;
            footerTipsContainer.Alpha = collapsed ? 0 : 1;
            footerTipsContainer.AlwaysPresent = !collapsed;

            footerCollapsedContainer.Alpha = collapsed ? 1 : 0;
            footerCollapsedContainer.AlwaysPresent = collapsed;
        }

        private void toggleHistoryPanelVisibility()
        {
            historyPanelVisible = !historyPanelVisible;
            updateHistoryPanel();
            appendStatusDetail(historyPanelVisible ? "History panel shown" : "History panel hidden");
        }

        private Drawable createHistoryColumn(string title, out SpriteText headerText, out FillFlowContainer listFlow)
        {
            headerText = new SpriteText
            {
                Text = title,
                Font = BeatSightFont.Title(11f),
                Colour = EditorColours.TextPrimary
            };

            listFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(3)
            };

            return new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(6),
                Children = new Drawable[]
                {
                    headerText,
                    listFlow
                }
            };
        }

        private void updateHistoryPanel()
        {
            if (historyPanel == null || undoHistoryFlow == null || redoHistoryFlow == null)
                return;

            updateHistoryColumn(undoStack, undoHeaderText, undoHistoryFlow, "Undo");
            updateHistoryColumn(redoStack, redoHeaderText, redoHistoryFlow, "Redo");

            bool anyEntries = undoStack.Count > 0 || redoStack.Count > 0;
            if (anyEntries && historyPanelVisible)
            {
                historyPanel.Show();
                historyPanel.FadeTo(1f, 120, Easing.OutQuint);
            }
            else
            {
                historyPanel.FadeOut(120, Easing.OutQuint);
                historyPanel.Hide();
            }
        }

        private void updateHistoryColumn(IReadOnlyList<EditorSnapshot> stack, SpriteText? header, FillFlowContainer listFlow, string title)
        {
            if (header != null)
                header.Text = $"{title} ({stack.Count})";

            listFlow.Clear();

            if (stack.Count == 0)
                return;

            int startIndex = Math.Max(0, stack.Count - historyPreviewCount);
            for (int i = stack.Count - 1; i >= startIndex; i--)
            {
                bool isNewest = i == stack.Count - 1;
                listFlow.Add(createHistoryEntry(stack[i], isNewest));
            }
        }

        private Drawable createHistoryEntry(EditorSnapshot snapshot, bool emphasise)
        {
            string title = string.IsNullOrWhiteSpace(snapshot.Description)
                ? formatTime(snapshot.CurrentTime)
                : snapshot.Description;

            int snapValue = snapshot.SnapDivisor > 0 ? snapshot.SnapDivisor : snapDivisor;
            double zoomValue = snapshot.Zoom > 0 ? snapshot.Zoom : timelineZoom;

            string details = $"{formatTime(snapshot.CurrentTime)} | Snap {snapValue} | Zoom {zoomValue:0.00}";

            return new Container
            {
                AutoSizeAxes = Axes.Both,
                Masking = true,
                CornerRadius = 5,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = emphasise
                            ? EditorColours.Lighten(EditorColours.CardBackground, 1.15f)
                            : EditorColours.Lighten(EditorColours.CardBackground, 1.02f)
                    },
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(1, 0),
                        Padding = new MarginPadding { Horizontal = 6, Vertical = 4 },
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = title,
                                Font = BeatSightFont.Body(9.6f),
                                Colour = emphasise ? EditorColours.HistoryEntryEmphasis : EditorColours.HistoryEntryMuted
                            },
                            new SpriteText
                            {
                                Text = details,
                                Font = BeatSightFont.Caption(8.8f),
                                Colour = EditorColours.TextMuted
                            }
                        }
                    }
                }
            };
        }

        private Drawable createHistoryPlaceholder()
        {
            return new SpriteText
            {
                Text = "No entries yet",
                Font = BeatSightFont.Caption(8.8f),
                Colour = EditorColours.TextMuted
            };
        }
    }
}
