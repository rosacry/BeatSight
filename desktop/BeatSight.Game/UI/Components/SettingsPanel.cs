// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using System.Collections.Generic;
using osu.Framework.Allocation;
using osu.Framework.Extensions.ObjectExtensions;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// A modern settings panel with categories, search, and smooth animations.
    /// </summary>
    public partial class SettingsPanel : Container
    {
        private const float panel_width = 500f;
        private const float animation_duration = 400f;
        private const float header_height = 80f;

        private Container panelContainer = null!;
        private FillFlowContainer categoriesContainer = null!;
        private FillFlowContainer settingsContainer = null!;
        private SearchTextBox searchBox = null!;
        private GridContainer contentGrid = null!;
        private float currentPanelWidth = panel_width;
        private float lastCategoryColumnWidth = -1;
        private float lastSearchHeight = -1;

        private readonly List<SettingsCategory> categories = new();
        private SettingsCategory? selectedCategory;

        public bool IsOpen { get; private set; }
        public event Action? OnClose;

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;
            Alpha = 0;

            Children = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Black.Opacity(0.7f),
                },
                panelContainer = new Container
                {
                    Width = panel_width,
                    RelativeSizeAxes = Axes.Y,
                    Anchor = Anchor.CentreRight,
                    Origin = Anchor.CentreRight,
                    X = panel_width,
                    Masking = true,
                    EdgeEffect = new EdgeEffectParameters
                    {
                        Type = EdgeEffectType.Shadow,
                        Colour = Color4.Black.Opacity(0.5f),
                        Radius = 30f,
                    },
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(18, 20, 30, 255),
                        },
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.Both,
                            Direction = FillDirection.Vertical,
                            Padding = new MarginPadding(24),
                            Spacing = new Vector2(0, 16),
                            Children = new Drawable[]
                            {
                                createHeader(),
                                searchBox = new SearchTextBox
                                {
                                    RelativeSizeAxes = Axes.X,
                                    Height = 44,
                                    PlaceholderText = "Search settings...",
                                },
                                new GridContainer
                                {
                                    Name = "SettingsPanelContentGrid",
                                    RelativeSizeAxes = Axes.Both,
                                    ColumnDimensions = new[]
                                    {
                                        new Dimension(GridSizeMode.Absolute, getInitialCategoryColumnWidth()),
                                        new Dimension(GridSizeMode.Distributed),
                                    },
                                    Content = new[]
                                    {
                                        new Drawable[]
                                        {
                                            new BeatSightScrollContainer
                                            {
                                                RelativeSizeAxes = Axes.Both,
                                                Child = categoriesContainer = new FillFlowContainer
                                                {
                                                    RelativeSizeAxes = Axes.X,
                                                    AutoSizeAxes = Axes.Y,
                                                    Direction = FillDirection.Vertical,
                                                    Spacing = new Vector2(0, 4),
                                                },
                                            },
                                            new Container
                                            {
                                                RelativeSizeAxes = Axes.Both,
                                                Masking = true,
                                                CornerRadius = 12,
                                                Children = new Drawable[]
                                                {
                                                    new Box
                                                    {
                                                        RelativeSizeAxes = Axes.Both,
                                                        Colour = new Color4(25, 27, 40, 200),
                                                    },
                                                    new BeatSightScrollContainer
                                                    {
                                                        RelativeSizeAxes = Axes.Both,
                                                        Padding = new MarginPadding(16),
                                                        Child = settingsContainer = new FillFlowContainer
                                                        {
                                                            RelativeSizeAxes = Axes.X,
                                                            AutoSizeAxes = Axes.Y,
                                                            Direction = FillDirection.Vertical,
                                                            Spacing = new Vector2(0, 12),
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    },
                                }.With(g => contentGrid = g),
                            },
                        },
                    },
                },
            };

            searchBox.Current.BindValueChanged(e => filterSettings(e.NewValue));
            initializeDefaultCategories();
            applyResponsiveLayout(force: true);
        }

        private Drawable createHeader()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 50,
                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Text = "Settings",
                        Font = new FontUsage("Torus", 28, "Bold"),
                        Colour = Color4.White,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                    },
                    new SettingsCloseButton
                    {
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        Action = Close,
                    },
                },
            };
        }

        private void initializeDefaultCategories()
        {
            AddCategory(new SettingsCategory("General", FontAwesome.Solid.Cog));
            AddCategory(new SettingsCategory("Audio", FontAwesome.Solid.VolumeUp));
            AddCategory(new SettingsCategory("Graphics", FontAwesome.Solid.Desktop));
            AddCategory(new SettingsCategory("Gameplay", FontAwesome.Solid.Gamepad));
            AddCategory(new SettingsCategory("Input", FontAwesome.Solid.Keyboard));
        }

        public void AddCategory(SettingsCategory category)
        {
            categories.Add(category);

            var button = new SettingsCategoryButton(category)
            {
                Action = () => selectCategory(category),
            };

            categoriesContainer.Add(button);

            if (selectedCategory == null)
                selectCategory(category);
        }

        public void AddSetting(string categoryName, SettingsItem item)
        {
            var category = categories.Find(c => c.Name == categoryName);
            category?.Items.Add(item);

            if (selectedCategory?.Name == categoryName)
                settingsContainer.Add(createSettingDrawable(item));
        }

        private void selectCategory(SettingsCategory category)
        {
            selectedCategory = category;

            foreach (var child in categoriesContainer.Children)
            {
                if (child is SettingsCategoryButton button)
                    button.IsSelected = button.Category == category;
            }

            settingsContainer.Clear();
            foreach (var item in category.Items)
            {
                settingsContainer.Add(createSettingDrawable(item));
            }
        }

        private Drawable createSettingDrawable(SettingsItem item)
        {
            return item.Type switch
            {
                SettingsItemType.Toggle => new SettingsToggle(item),
                SettingsItemType.Slider => new SettingsSlider(item),
                SettingsItemType.Header => new SettingsHeader(item),
                _ => new Container(),
            };
        }

        private void filterSettings(string searchText)
        {
            if (string.IsNullOrWhiteSpace(searchText))
            {
                if (selectedCategory != null) selectCategory(selectedCategory);
                return;
            }

            settingsContainer.Clear();
            foreach (var category in categories)
            {
                foreach (var item in category.Items)
                {
                    if (item.Label.ToLower().Contains(searchText.ToLower()))
                        settingsContainer.Add(createSettingDrawable(item));
                }
            }
        }

        public void Open()
        {
            if (IsOpen) return;
            IsOpen = true;
            this.FadeIn(animation_duration, Easing.OutQuint);
            panelContainer.MoveToX(0, animation_duration, Easing.OutQuint);
        }

        public void Close()
        {
            if (!IsOpen) return;
            IsOpen = false;
            this.FadeOut(animation_duration, Easing.OutQuint);
            panelContainer.MoveToX(currentPanelWidth, animation_duration, Easing.OutQuint);
            OnClose?.Invoke();
        }

        public void Toggle() => _ = IsOpen ? (Action)Close : Open;

        protected override bool OnClick(ClickEvent e)
        {
            if (e.MousePosition.X < Width - currentPanelWidth)
            {
                Close();
                return true;
            }
            return base.OnClick(e);
        }

        protected override void Update()
        {
            base.Update();
            applyResponsiveLayout();
        }

        private void applyResponsiveLayout(bool force = false)
        {
            if (panelContainer == null || DrawWidth <= 0 || DrawHeight <= 0)
                return;

            float panelWidth = getPanelWidthForViewport(DrawWidth);
            float categoryWidth = getCategoryWidthForPanel(panelWidth);
            float searchHeight = getSearchHeightForViewport(DrawHeight);

            if (force || Math.Abs(panelWidth - currentPanelWidth) > 0.2f)
            {
                currentPanelWidth = panelWidth;
                panelContainer.Width = panelWidth;
                if (!IsOpen)
                    panelContainer.X = panelWidth;
            }

            if (contentGrid != null && (force || Math.Abs(categoryWidth - lastCategoryColumnWidth) > 0.2f))
            {
                contentGrid.ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, categoryWidth),
                    new Dimension(GridSizeMode.Distributed),
                };
                lastCategoryColumnWidth = categoryWidth;
            }

            if (searchBox != null && (force || Math.Abs(searchHeight - lastSearchHeight) > 0.2f))
            {
                searchBox.Height = searchHeight;
                lastSearchHeight = searchHeight;
            }
        }

        private float getInitialCategoryColumnWidth()
        {
            float viewportWidth = DrawWidth > 0 ? DrawWidth : 1920f;
            float panelWidth = getPanelWidthForViewport(viewportWidth);
            return getCategoryWidthForPanel(panelWidth);
        }

        private static float getPanelWidthForViewport(float viewportWidth)
        {
            float width = viewportWidth > 0 ? viewportWidth : 1920f;
            return ResponsiveLayout.ClampFraction(width, 0.32f, 420f, 720f);
        }

        private static float getCategoryWidthForPanel(float panelWidth)
        {
            float width = panelWidth > 0 ? panelWidth : panel_width;
            return ResponsiveLayout.ClampFraction(width, 0.27f, 120f, 220f);
        }

        private static float getSearchHeightForViewport(float viewportHeight)
        {
            float height = viewportHeight > 0 ? viewportHeight : 1080f;
            return ResponsiveLayout.ClampFraction(height, 0.04f, 38f, 52f);
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == osuTK.Input.Key.Escape && IsOpen)
            {
                Close();
                return true;
            }
            return base.OnKeyDown(e);
        }

        // Nested classes
        private partial class SettingsCloseButton : Container
        {
            public Action? Action;
            private Box background = null!;

            [BackgroundDependencyLoader]
            private void load()
            {
                Size = new Vector2(32);
                Masking = true;
                CornerRadius = 8;

                Children = new Drawable[]
                {
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4.White.Opacity(0),
                    },
                    new SpriteIcon
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Size = new Vector2(16),
                        Icon = FontAwesome.Solid.Times,
                        Colour = new Color4(150, 150, 150, 255),
                    },
                };
            }

            protected override bool OnHover(HoverEvent e)
            {
                background.FadeColour(Color4.White.Opacity(0.1f), 150);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                background.FadeColour(Color4.White.Opacity(0), 150);
                base.OnHoverLost(e);
            }

            protected override bool OnClick(ClickEvent e)
            {
                Action?.Invoke();
                return true;
            }
        }

        private partial class SettingsCategoryButton : Container
        {
            public SettingsCategory Category { get; }
            public Action? Action;

            private Box background = null!;
            private Box activeIndicator = null!;
            private SpriteIcon icon = null!;
            private SpriteText label = null!;

            private bool isSelected;
            public bool IsSelected
            {
                get => isSelected;
                set
                {
                    if (isSelected == value) return;
                    isSelected = value;
                    updateState();
                }
            }

            public SettingsCategoryButton(SettingsCategory category) => Category = category;

            [BackgroundDependencyLoader]
            private void load()
            {
                RelativeSizeAxes = Axes.X;
                Height = 40;
                Masking = true;
                CornerRadius = 8;

                Children = new Drawable[]
                {
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4.White.Opacity(0),
                    },
                    activeIndicator = new Box
                    {
                        Width = 3,
                        RelativeSizeAxes = Axes.Y,
                        Colour = new Color4(0, 212, 255, 255),
                        Alpha = 0,
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Padding = new MarginPadding { Left = 12 },
                        Spacing = new Vector2(10, 0),
                        Children = new Drawable[]
                        {
                            icon = new SpriteIcon
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Size = new Vector2(16),
                                Icon = Category.Icon,
                                Colour = new Color4(120, 120, 120, 255),
                            },
                            label = new SpriteText
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Text = Category.Name,
                                Font = new FontUsage("Torus", 14),
                                Colour = new Color4(180, 180, 180, 255),
                            },
                        },
                    },
                };
            }

            private void updateState()
            {
                if (isSelected)
                {
                    background.FadeColour(Color4.White.Opacity(0.05f), 200);
                    activeIndicator.FadeIn(200);
                    icon.FadeColour(new Color4(0, 212, 255, 255), 200);
                    label.FadeColour(Color4.White, 200);
                }
                else
                {
                    background.FadeColour(Color4.White.Opacity(0), 200);
                    activeIndicator.FadeOut(200);
                    icon.FadeColour(new Color4(120, 120, 120, 255), 200);
                    label.FadeColour(new Color4(180, 180, 180, 255), 200);
                }
            }

            protected override bool OnHover(HoverEvent e)
            {
                if (!isSelected) background.FadeColour(Color4.White.Opacity(0.03f), 150);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                if (!isSelected) background.FadeColour(Color4.White.Opacity(0), 150);
                base.OnHoverLost(e);
            }

            protected override bool OnClick(ClickEvent e)
            {
                Action?.Invoke();
                return true;
            }
        }

        private partial class SettingsToggle : Container
        {
            private readonly SettingsItem item;
            private Box toggleBackground = null!;
            private Container toggleKnob = null!;
            private bool isOn;

            public SettingsToggle(SettingsItem item)
            {
                this.item = item;
                isOn = item.Value as bool? ?? false;
            }

            [BackgroundDependencyLoader]
            private void load()
            {
                RelativeSizeAxes = Axes.X;
                Height = 48;

                Children = new Drawable[]
                {
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.Y,
                        AutoSizeAxes = Axes.X,
                        Direction = FillDirection.Vertical,
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = item.Label,
                                Font = new FontUsage("Torus", 14, "SemiBold"),
                                Colour = Color4.White,
                            },
                            new SpriteText
                            {
                                Text = item.Description ?? "",
                                Font = new FontUsage("Torus", 12),
                                Colour = new Color4(120, 120, 120, 255),
                            },
                        },
                    },
                    new Container
                    {
                        Size = new Vector2(44, 24),
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        Masking = true,
                        CornerRadius = 12,
                        Children = new Drawable[]
                        {
                            toggleBackground = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = isOn ? new Color4(0, 212, 255, 255) : new Color4(60, 60, 70, 255),
                            },
                            toggleKnob = new Container
                            {
                                Size = new Vector2(20),
                                Position = new Vector2(isOn ? 22 : 2, 2),
                                Masking = true,
                                CornerRadius = 10,
                                Child = new Box
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Colour = Color4.White,
                                },
                            },
                        },
                    },
                };
            }

            protected override bool OnClick(ClickEvent e)
            {
                isOn = !isOn;
                toggleBackground.FadeColour(isOn ? new Color4(0, 212, 255, 255) : new Color4(60, 60, 70, 255), 200);
                toggleKnob.MoveTo(new Vector2(isOn ? 22 : 2, 2), 200, Easing.OutQuint);
                item.OnValueChanged?.Invoke(isOn);
                return true;
            }
        }

        private partial class SettingsSlider : Container
        {
            private readonly SettingsItem item;
            private Box progressBar = null!;
            private SpriteText valueText = null!;
            private float currentValue;
            private readonly float minValue;
            private readonly float maxValue;

            public SettingsSlider(SettingsItem item)
            {
                this.item = item;
                currentValue = Convert.ToSingle(item.Value ?? 0.5f);
                minValue = Convert.ToSingle(item.MinValue ?? 0f);
                maxValue = Convert.ToSingle(item.MaxValue ?? 1f);
            }

            [BackgroundDependencyLoader]
            private void load()
            {
                RelativeSizeAxes = Axes.X;
                Height = 60;

                Children = new Drawable[]
                {
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 8),
                        Children = new Drawable[]
                        {
                            new Container
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 20,
                                Children = new Drawable[]
                                {
                                    new SpriteText
                                    {
                                        Text = item.Label,
                                        Font = new FontUsage("Torus", 14, "SemiBold"),
                                        Colour = Color4.White,
                                    },
                                    valueText = new SpriteText
                                    {
                                        Anchor = Anchor.CentreRight,
                                        Origin = Anchor.CentreRight,
                                        Text = formatValue(currentValue),
                                        Font = new FontUsage("Torus", 14),
                                        Colour = new Color4(0, 212, 255, 255),
                                    },
                                },
                            },
                            new Container
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 6,
                                Masking = true,
                                CornerRadius = 3,
                                Children = new Drawable[]
                                {
                                    new Box
                                    {
                                        RelativeSizeAxes = Axes.Both,
                                        Colour = new Color4(40, 42, 55, 255),
                                    },
                                    progressBar = new Box
                                    {
                                        RelativeSizeAxes = Axes.Y,
                                        Width = 0,
                                        Colour = ColourInfo.GradientHorizontal(
                                            new Color4(0, 212, 255, 255),
                                            new Color4(255, 50, 150, 255)
                                        ),
                                    },
                                },
                            },
                        },
                    },
                };
            }

            protected override void LoadComplete()
            {
                base.LoadComplete();
                updateProgress();
            }

            private void updateProgress()
            {
                float progress = (currentValue - minValue) / (maxValue - minValue);
                progressBar.ResizeWidthTo(progress, 50);
            }

            private string formatValue(float value)
            {
                return maxValue <= 1 ? $"{(int)(value * 100)}%" : value.ToString("F1");
            }

            protected override bool OnDragStart(DragStartEvent e) => true;

            protected override void OnDrag(DragEvent e) => updateValue(e.MousePosition.X);

            protected override bool OnClick(ClickEvent e)
            {
                updateValue(e.MousePosition.X);
                return true;
            }

            private void updateValue(float mouseX)
            {
                float progress = Math.Clamp(mouseX / DrawWidth, 0, 1);
                currentValue = minValue + (maxValue - minValue) * progress;
                updateProgress();
                valueText.Text = formatValue(currentValue);
                item.OnValueChanged?.Invoke(currentValue);
            }
        }

        private partial class SettingsHeader : Container
        {
            public SettingsHeader(SettingsItem item)
            {
                RelativeSizeAxes = Axes.X;
                Height = 40;
                Padding = new MarginPadding { Top = 16 };

                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Text = item.Label,
                        Font = new FontUsage("Torus", 16, "Bold"),
                        Colour = Color4.White,
                    },
                    new Box
                    {
                        Anchor = Anchor.BottomLeft,
                        Origin = Anchor.BottomLeft,
                        RelativeSizeAxes = Axes.X,
                        Height = 1,
                        Colour = new Color4(50, 52, 65, 255),
                    },
                };
            }
        }
    }

    // Data models - outside the class but in same namespace
    public class SettingsCategory
    {
        public string Name { get; }
        public IconUsage Icon { get; }
        public List<SettingsItem> Items { get; } = new();

        public SettingsCategory(string name, IconUsage icon)
        {
            Name = name;
            Icon = icon;
        }
    }

    public class SettingsItem
    {
        public string Label { get; set; } = string.Empty;
        public string? Description { get; set; }
        public SettingsItemType Type { get; set; }
        public object? Value { get; set; }
        public object? MinValue { get; set; }
        public object? MaxValue { get; set; }
        public string[]? Options { get; set; }
        public Action? OnClick { get; set; }
        public Action<object>? OnValueChanged { get; set; }
    }

    public enum SettingsItemType
    {
        Toggle,
        Slider,
        Dropdown,
        Button,
        Header,
        Text,
    }
}
