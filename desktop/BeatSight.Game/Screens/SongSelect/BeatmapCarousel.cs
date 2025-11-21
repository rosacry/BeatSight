using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
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

        private readonly Bindable<BeatmapLibrary.BeatmapEntry?> selectedBeatmap = new();
        private FillFlowContainer<BeatmapPanel> flow = null!;
        private BasicScrollContainer scroll = null!;

        private List<BeatmapLibrary.BeatmapEntry> allBeatmaps = new();
        private string currentFilter = string.Empty;
        private SortMode currentSortMode = SortMode.Title;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;

            InternalChild = scroll = new BasicScrollContainer
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

        public void Sort(SortMode mode)
        {
            currentSortMode = mode;
            Filter(currentFilter);
        }

        public void Filter(string query)
        {
            currentFilter = query;
            var filtered = string.IsNullOrWhiteSpace(query)
                ? allBeatmaps
                : allBeatmaps.Where(b => matchesFilter(b, query)).ToList();

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
            }

            flow.Clear();

            foreach (var beatmap in filtered)
            {
                var panel = new BeatmapPanel(beatmap);
                panel.Action = () => select(beatmap, panel);
                flow.Add(panel);
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

        public void SelectRandom()
        {
            if (flow.Children.Count == 0) return;
            var random = new Random();
            var panel = flow.Children[random.Next(flow.Children.Count)];
            panel.TriggerClick();
        }

        private bool matchesFilter(BeatmapLibrary.BeatmapEntry entry, string query)
        {
            return entry.Beatmap.Metadata.Title.Contains(query, StringComparison.OrdinalIgnoreCase)
                || entry.Beatmap.Metadata.Artist.Contains(query, StringComparison.OrdinalIgnoreCase)
                || entry.Beatmap.Metadata.Creator.Contains(query, StringComparison.OrdinalIgnoreCase);
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

        private partial class BeatmapPanel : ClickableContainer
        {
            public readonly BeatmapLibrary.BeatmapEntry Entry;
            public readonly Bindable<PanelState> State = new(PanelState.NotSelected);

            private Box background = null!;
            private Box leftBar = null!;
            private Box flash = null!;
            private Container content = null!;
            private SpriteText title = null!;
            private SpriteText artist = null!;
            private SpriteText difficulty = null!;

            public enum PanelState
            {
                NotSelected,
                Selected
            }

            public BeatmapPanel(BeatmapLibrary.BeatmapEntry entry)
            {
                Entry = entry;
                RelativeSizeAxes = Axes.X;
                Height = 80;
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
                        Width = 8,
                        Colour = UITheme.AccentPrimary,
                        Alpha = 0 // Hidden by default
                    },
                    content = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 25, Vertical = 10 }, // Increased left padding for bar
                        Children = new Drawable[]
                        {
                            new FillFlowContainer
                            {
                                RelativeSizeAxes = Axes.X,
                                AutoSizeAxes = Axes.Y,
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Direction = FillDirection.Vertical,
                                Spacing = new Vector2(0, 10),
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
                                        Text = $"[{entry.Beatmap.Metadata.Difficulty:F1}★] mapped by {entry.Beatmap.Metadata.Creator}",
                                        Font = BeatSightFont.Caption(14f),
                                        Colour = UITheme.TextMuted,
                                        Truncate = true,
                                        RelativeSizeAxes = Axes.X
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
                        this.ResizeTo(new Vector2(1.02f, 100), 300, Easing.OutElastic); // Elastic expand
                        leftBar.FadeIn(200);
                        break;

                    case PanelState.NotSelected:
                        BorderColour = Color4.Transparent;
                        background.FadeColour(UITheme.Surface, 200, Easing.OutQuint);
                        this.ResizeTo(new Vector2(1.0f, 80), 200, Easing.OutQuint);
                        leftBar.FadeOut(200);
                        break;
                }
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
            DateAdded
        }
    }
}
