using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Cursor;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;
using osu.Framework.Graphics.Effects;

namespace BeatSight.Game.Screens.SongSelect
{
    public partial class BeatmapCarousel : CompositeDrawable
    {
        public Action<BeatmapLibrary.BeatmapEntry>? BeatmapSelected;

        /// <summary>
        /// Called when user requests to open a beatmap in the editor via context menu.
        /// </summary>
        public Action<BeatmapLibrary.BeatmapEntry>? OpenInEditorRequested;

        /// <summary>
        /// Called when user requests to delete a beatmap via context menu.
        /// </summary>
        public Action<BeatmapLibrary.BeatmapEntry>? DeleteRequested;

        /// <summary>
        /// Called when user requests to add a beatmap to a collection via context menu.
        /// </summary>
        public Action<BeatmapLibrary.BeatmapEntry>? AddToCollectionRequested;

        private readonly Bindable<BeatmapLibrary.BeatmapEntry?> selectedBeatmap = new();
        private FillFlowContainer<BeatmapPanel> flow = null!;
        private BeatSightScrollContainer scroll = null!;

        private List<BeatmapLibrary.BeatmapEntry> allBeatmaps = new();
        private string currentFilter = string.Empty;
        private SortMode currentSortMode = SortMode.Title;
        private double minConfidence = 0.0;
        private string genreFilter = string.Empty;
        private Func<BeatmapLibrary.BeatmapEntry, bool>? customFilter;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChild = scroll = new BeatSightScrollContainer
            {
                RelativeSizeAxes = Axes.Both,
                Masking = false,
                Child = flow = new FillFlowContainer<BeatmapPanel>
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, 10),
                    Padding = new MarginPadding { Top = 10, Bottom = 10, Right = 20, Left = 20 } // Padding for scrollbar and left side
                }
            };
        }

        public void SetBeatmaps(IEnumerable<BeatmapLibrary.BeatmapEntry> beatmaps)
        {
            allBeatmaps = beatmaps.ToList();
            Filter(currentFilter);
        }

        public void SetConfidenceFilter(double min)
        {
            minConfidence = min;
            Filter(currentFilter);
        }

        public void SetGenreFilter(string genre)
        {
            genreFilter = genre;
            Filter(currentFilter);
        }

        /// <summary>
        /// Sets a custom filter predicate. Used for favorites filtering.
        /// </summary>
        public void SetCustomFilter(Func<BeatmapLibrary.BeatmapEntry, bool>? filter)
        {
            customFilter = filter;
            Filter(currentFilter);
        }

        public void Sort(SortMode mode)
        {
            currentSortMode = mode;
            Filter(currentFilter);
        }

        /// <summary>
        /// Selects a random beatmap from the currently filtered list.
        /// </summary>
        /// <returns>True if a random selection was made, false if no beatmaps available.</returns>
        public bool SelectRandom()
        {
            var panels = flow.Children.ToList();
            if (panels.Count == 0)
                return false;

            var random = new Random();
            var randomPanel = panels[random.Next(panels.Count)];
            select(randomPanel.Entry, randomPanel);

            // Scroll to the selected panel
            scroll.ScrollTo(randomPanel);

            return true;
        }

        /// <summary>
        /// Selects the next beatmap in the current filtered/sorted list.
        /// Wraps to the first beatmap after the last one.
        /// </summary>
        public bool SelectNext() => selectRelative(1);

        /// <summary>
        /// Selects the previous beatmap in the current filtered/sorted list.
        /// Wraps to the last beatmap before the first one.
        /// </summary>
        public bool SelectPrevious() => selectRelative(-1);

        public void Filter(string query)
        {
            currentFilter = query;
            var filtered = allBeatmaps.Where(b => matchesFilter(b, query)).ToList();

            // Apply sorting
            switch (currentSortMode)
            {
                case SortMode.Title:
                    filtered = filtered.OrderBy(b => b.Beatmap.Metadata.Title).ToList();
                    break;
                case SortMode.Artist:
                    filtered = filtered.OrderBy(b => b.Beatmap.Metadata.Artist).ToList();
                    break;
                case SortMode.Difficulty:
                    filtered = filtered.OrderBy(b => b.Beatmap.Metadata.Difficulty).ToList();
                    break;
                case SortMode.DateAdded:
                    filtered = filtered.OrderByDescending(b => b.Beatmap.Metadata.CreatedAt).ToList();
                    break;
                case SortMode.DateGenerated:
                    filtered = filtered.OrderByDescending(b => b.Beatmap.Editor?.AiGenerationMetadata?.ProcessedAt ?? DateTime.MinValue).ToList();
                    break;
            }

            // Store existing panels to reuse them
            var existingPanels = flow.Children.ToDictionary(p => p.Entry);

            flow.Clear(false);

            int i = 0;
            foreach (var beatmap in filtered)
            {
                BeatmapPanel panel;
                bool isNew = false;

                if (existingPanels.TryGetValue(beatmap, out var existing))
                {
                    panel = existing;
                    existingPanels.Remove(beatmap);
                }
                else
                {
                    panel = new BeatmapPanel(beatmap)
                    {
                        OnOpenInEditor = entry => OpenInEditorRequested?.Invoke(entry),
                        OnDelete = entry => DeleteRequested?.Invoke(entry),
                        OnAddToCollection = entry => AddToCollectionRequested?.Invoke(entry)
                    };
                    panel.Action = () => select(beatmap, panel);
                    isNew = true;
                }

                if (isNew)
                {
                    // Staggered animation
                    panel.Alpha = 0;
                    panel.X = 50;
                    panel.Delay(i * 30).FadeIn(300).MoveToX(0, 500, Easing.OutQuint);
                }
                else
                {
                    // Ensure visible if it was somehow hidden, but don't replay entrance animation
                    panel.Alpha = 1;
                    panel.X = 0;
                }

                flow.Add(panel);
                i++;
            }

            // Dispose panels that are no longer needed
            foreach (var panel in existingPanels.Values)
            {
                panel.Dispose();
            }

            // Reselect if possible, or clear selection
            if (selectedBeatmap.Value != null && filtered.Contains(selectedBeatmap.Value))
            {
                // Find the panel and set it as selected visually
                var panel = flow.Children.FirstOrDefault(p => p.Entry == selectedBeatmap.Value);
                if (panel != null)
                    panel.State.Value = BeatmapPanel.PanelState.Selected;
            }
            else
            {
                selectedBeatmap.Value = null;
            }
        }

        private bool matchesFilter(BeatmapLibrary.BeatmapEntry entry, string query)
        {
            bool matchesQuery = string.IsNullOrWhiteSpace(query) ||
                entry.Beatmap.Metadata.Title.Contains(query, StringComparison.OrdinalIgnoreCase) ||
                entry.Beatmap.Metadata.Artist.Contains(query, StringComparison.OrdinalIgnoreCase) ||
                entry.Beatmap.Metadata.Creator.Contains(query, StringComparison.OrdinalIgnoreCase);

            if (!matchesQuery) return false;

            // AI Confidence Filter
            if (minConfidence > 0)
            {
                var confidence = entry.Beatmap.Editor?.AiGenerationMetadata?.Confidence ?? 0;
                if (confidence < minConfidence) return false;
            }

            // Genre Filter
            if (!string.IsNullOrEmpty(genreFilter))
            {
                if (!entry.Beatmap.Metadata.Tags.Any(t => t.Equals(genreFilter, StringComparison.OrdinalIgnoreCase)))
                    return false;
            }

            // Custom filter (e.g., favorites)
            if (customFilter != null && !customFilter(entry))
                return false;

            return true;
        }

        private void select(BeatmapLibrary.BeatmapEntry entry, BeatmapPanel panel)
        {
            if (selectedBeatmap.Value == entry)
            {
                // Double click or re-select logic could go here (e.g. start game)
                return;
            }

            // Deselect previous
            foreach (var child in flow.Children)
            {
                if (child != panel)
                    child.State.Value = BeatmapPanel.PanelState.NotSelected;
            }

            selectedBeatmap.Value = entry;
            panel.State.Value = BeatmapPanel.PanelState.Selected;
            BeatmapSelected?.Invoke(entry);
        }

        private bool selectRelative(int direction)
        {
            var panels = flow.Children.ToList();
            if (panels.Count == 0)
                return false;

            int currentIndex = -1;
            if (selectedBeatmap.Value != null)
                currentIndex = panels.FindIndex(p => p.Entry == selectedBeatmap.Value);

            int targetIndex;
            if (currentIndex < 0)
            {
                targetIndex = direction >= 0 ? 0 : panels.Count - 1;
            }
            else
            {
                targetIndex = currentIndex + direction;
                if (targetIndex < 0)
                    targetIndex = panels.Count - 1;
                else if (targetIndex >= panels.Count)
                    targetIndex = 0;
            }

            var targetPanel = panels[targetIndex];
            select(targetPanel.Entry, targetPanel);
            scroll.ScrollTo(targetPanel);
            return true;
        }

        private partial class BeatmapPanel : ClickableContainer, IHasContextMenu
        {
            private const float collapsedHeight = 96f;
            private const float expandedHeight = 112f;

            public readonly BeatmapLibrary.BeatmapEntry Entry;
            public readonly Bindable<PanelState> State = new(PanelState.NotSelected);

            /// <summary>
            /// Action to invoke when "Open in Editor" is selected from context menu.
            /// </summary>
            public Action<BeatmapLibrary.BeatmapEntry>? OnOpenInEditor;

            /// <summary>
            /// Action to invoke when "Delete" is selected from context menu.
            /// </summary>
            public Action<BeatmapLibrary.BeatmapEntry>? OnDelete;

            /// <summary>
            /// Action to invoke when "Add to Collection" is selected from context menu.
            /// </summary>
            public Action<BeatmapLibrary.BeatmapEntry>? OnAddToCollection;

            private Box background = null!;
            private Box leftBar = null!;
            private Box flash = null!;
            private Container content = null!;
            private SpriteText title = null!;
            private SpriteText artist = null!;
            private SpriteText difficulty = null!;

            public MenuItem[]? ContextMenuItems => new MenuItem[]
            {
                new MenuItem("Open in Editor", () => OnOpenInEditor?.Invoke(Entry)),
                new MenuItem("Add to Collection", () => OnAddToCollection?.Invoke(Entry)),
                new MenuItem("Delete", () => OnDelete?.Invoke(Entry))
            };

            public enum PanelState
            {
                NotSelected,
                Selected
            }

            public BeatmapPanel(BeatmapLibrary.BeatmapEntry entry)
            {
                Entry = entry;
                RelativeSizeAxes = Axes.X;
                Height = collapsedHeight;
                Masking = true;
                CornerRadius = 10;
                BorderThickness = 3;
                BorderColour = Color4.Transparent;
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Shadow,
                    Colour = Color4.Black.Opacity(0.2f),
                    Radius = 5,
                    Offset = new Vector2(0, 2),
                };

                Children = new Drawable[]
                {
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface
                    },
                    leftBar = new Box
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = 0,
                        Colour = UITheme.AccentPrimary,
                        Alpha = 0 // Hidden by default
                    },
                    content = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 25, Vertical = 14 }, // Increased left padding for bar
                        Children = new Drawable[]
                        {
                            new FillFlowContainer
                            {
                                RelativeSizeAxes = Axes.X,
                                AutoSizeAxes = Axes.Y,
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Direction = FillDirection.Vertical,
                                Spacing = new Vector2(0, 6),
                                Children = new Drawable[]
                                {
                                    title = new BeatSight.Game.UI.Components.BeatSightSpriteText
                                    {
                                        Text = entry.Beatmap.Metadata.Title,
                                        Font = BeatSightFont.Section(22f),
                                        Colour = UITheme.TextPrimary,
                                        Truncate = true,
                                        RelativeSizeAxes = Axes.X
                                    },
                                    artist = new BeatSight.Game.UI.Components.BeatSightSpriteText
                                    {
                                        Text = entry.Beatmap.Metadata.Artist,
                                        Font = BeatSightFont.Body(16f),
                                        Colour = UITheme.TextSecondary,
                                        Truncate = true,
                                        RelativeSizeAxes = Axes.X
                                    },
                                    difficulty = new BeatSight.Game.UI.Components.BeatSightSpriteText
                                    {
                                        Text = $"[{entry.Beatmap.Metadata.Difficulty:F1}] mapped by {entry.Beatmap.Metadata.Creator}",
                                        Font = BeatSightFont.Caption(14f),
                                        Colour = getDifficultyColour((float)entry.Beatmap.Metadata.Difficulty),
                                        Truncate = true,
                                        RelativeSizeAxes = Axes.X
                                    },
                                    new FillFlowContainer
                                    {
                                        RelativeSizeAxes = Axes.X,
                                        AutoSizeAxes = Axes.Y,
                                        Direction = FillDirection.Horizontal,
                                        Spacing = new Vector2(10, 0),
                                        Children = getAiInfo(entry.Beatmap)
                                    }
                                }
                            }
                        }
                    },
                    flash = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4.White,
                        Alpha = 0,
                        Blending = BlendingParameters.Additive
                    }
                };

                State.BindValueChanged(onStateChanged, true);
            }

            private void onStateChanged(ValueChangedEvent<PanelState> state)
            {
                switch (state.NewValue)
                {
                    case PanelState.Selected:
                        BorderColour = UITheme.AccentPrimary;
                        background.FadeColour(UITheme.SurfaceAlt, 200, Easing.OutQuint);
                        this.ResizeTo(new Vector2(1.0f, expandedHeight), 300, Easing.OutElastic); // Elastic expand
                        leftBar.ResizeWidthTo(8, 300, Easing.OutElastic);
                        leftBar.FadeIn(200);
                        break;

                    case PanelState.NotSelected:
                        BorderColour = Color4.Transparent;
                        background.FadeColour(UITheme.Surface, 200, Easing.OutQuint);
                        this.ResizeTo(new Vector2(1.0f, collapsedHeight), 200, Easing.OutQuint);
                        leftBar.ResizeWidthTo(0, 200, Easing.OutQuint);
                        leftBar.FadeOut(200);
                        break;
                }
            }

            private Color4 getDifficultyColour(float stars)
            {
                if (stars < 2.0f) return UITheme.AccentSuccess;
                if (stars < 4.0f) return UITheme.AccentWarning;
                if (stars < 5.5f) return UITheme.AccentError;
                return UITheme.AccentSecondary;
            }

            private Drawable[] getAiInfo(Beatmap beatmap)
            {
                var list = new List<Drawable>();
                var aiMeta = beatmap.Editor?.AiGenerationMetadata;

                if (aiMeta != null)
                {
                    // AI Badge
                    list.Add(new Container
                    {
                        AutoSizeAxes = Axes.Both,
                        Masking = true,
                        CornerRadius = 4,
                        Children = new Drawable[]
                        {
                            new Box { RelativeSizeAxes = Axes.Both, Colour = UITheme.AccentPrimary },
                            new BeatSight.Game.UI.Components.BeatSightSpriteText
                            {
                                Text = "AI Generated",
                                Font = BeatSightFont.Caption(10f),
                                Colour = Color4.White,
                                Padding = new MarginPadding { Horizontal = 5, Vertical = 2 }
                            }
                        }
                    });

                    // Confidence
                    if (aiMeta.Confidence.HasValue)
                    {
                        list.Add(new BeatSight.Game.UI.Components.BeatSightSpriteText
                        {
                            Text = $"Confidence: {aiMeta.Confidence.Value:P0}",
                            Font = BeatSightFont.Caption(12f),
                            Colour = UITheme.TextSecondary
                        });
                    }

                    // Model Version
                    if (!string.IsNullOrEmpty(aiMeta.ModelVersion))
                    {
                        list.Add(new BeatSight.Game.UI.Components.BeatSightSpriteText
                        {
                            Text = $"v{aiMeta.ModelVersion}",
                            Font = BeatSightFont.Caption(12f),
                            Colour = UITheme.TextSecondary,
                            Alpha = 0.7f
                        });
                    }
                }
                return list.ToArray();
            }

            protected override bool OnHover(HoverEvent e)
            {
                if (State.Value == PanelState.NotSelected)
                    background.FadeColour(UITheme.Emphasise(UITheme.Surface, 1.1f), 100);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                if (State.Value == PanelState.NotSelected)
                    background.FadeColour(UITheme.Surface, 100);
                base.OnHoverLost(e);
            }

            protected override bool OnClick(ClickEvent e)
            {
                flash.FadeOutFromOne(400, Easing.OutQuad);
                return base.OnClick(e);
            }
        }

        public enum SortMode
        {
            Title,
            Artist,
            Difficulty,
            DateAdded,
            DateGenerated
        }
    }
}
