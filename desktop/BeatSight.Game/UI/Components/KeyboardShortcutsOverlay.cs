// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

using System;
using System.Collections.Generic;
using System.Linq;
using osu.Framework.Allocation;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;
using osuTK.Input;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// A beautiful overlay that displays keyboard shortcuts organized by category.
    /// </summary>
    public partial class KeyboardShortcutsOverlay : Container
    {
        private const float animation_duration = 300f;

        private Container panelContainer = null!;
        private FillFlowContainer categoriesContainer = null!;
        private SearchTextBox searchBox = null!;

        private readonly List<ShortcutCategory> categories = new();
        private string currentFilter = string.Empty;

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
                    Colour = Color4.Black.Opacity(0.8f),
                },
                panelContainer = new Container
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Width = 900,
                    Height = 600,
                    Scale = new Vector2(0.9f),
                    Masking = true,
                    CornerRadius = 20,
                    EdgeEffect = new EdgeEffectParameters
                    {
                        Type = EdgeEffectType.Shadow,
                        Colour = Color4.Black.Opacity(0.5f),
                        Radius = 40f,
                    },
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4(18, 20, 30, 250),
                        },
                        new Box
                        {
                            RelativeSizeAxes = Axes.X,
                            Height = 3,
                            Colour = ColourInfo.GradientHorizontal(
                                new Color4(0, 212, 255, 255),
                                new Color4(255, 50, 150, 255)
                            ),
                        },
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.Both,
                            Direction = FillDirection.Vertical,
                            Padding = new MarginPadding(32),
                            Spacing = new Vector2(0, 24),
                            Children = new Drawable[]
                            {
                                createHeader(),
                                new BeatSightScrollContainer
                                {
                                    RelativeSizeAxes = Axes.Both,
                                    Child = categoriesContainer = new FillFlowContainer
                                    {
                                        RelativeSizeAxes = Axes.X,
                                        AutoSizeAxes = Axes.Y,
                                        Direction = FillDirection.Full,
                                        Spacing = new Vector2(24, 24),
                                    },
                                },
                            },
                        },
                        createFooter(),
                    },
                },
            };

            searchBox.Current.BindValueChanged(e =>
            {
                currentFilter = e.NewValue?.ToLower() ?? string.Empty;
                filterShortcuts();
            });

            initializeDefaultShortcuts();
        }

        private Drawable createHeader()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 40,
                Children = new Drawable[]
                {
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(16, 0),
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Children = new Drawable[]
                        {
                            new SpriteIcon
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Size = new Vector2(28),
                                Icon = FontAwesome.Regular.Keyboard,
                                Colour = new Color4(0, 212, 255, 255),
                            },
                            new SpriteText
                            {
                                Anchor = Anchor.CentreLeft,
                                Origin = Anchor.CentreLeft,
                                Text = "Keyboard Shortcuts",
                                Font = new FontUsage("Torus", 28, "Bold"),
                                Colour = Color4.White,
                            },
                        },
                    },
                    searchBox = new SearchTextBox
                    {
                        Width = 250,
                        RelativeSizeAxes = Axes.Y,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        PlaceholderText = "Search...",
                    },
                    new ShortcutsCloseButton
                    {
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        Action = Close,
                    },
                },
            };
        }

        private Drawable createFooter()
        {
            return new Container
            {
                Anchor = Anchor.BottomCentre,
                Origin = Anchor.BottomCentre,
                AutoSizeAxes = Axes.Both,
                Padding = new MarginPadding(16),
                Child = new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Horizontal,
                    Spacing = new Vector2(8, 0),
                    Children = new Drawable[]
                    {
                        new SpriteText
                        {
                            Text = "Press",
                            Font = new FontUsage("Torus", 12),
                            Colour = new Color4(100, 100, 100, 255),
                        },
                        new KeyBadge("Esc"),
                        new SpriteText
                        {
                            Text = "to close",
                            Font = new FontUsage("Torus", 12),
                            Colour = new Color4(100, 100, 100, 255),
                        },
                    },
                },
            };
        }

        private void initializeDefaultShortcuts()
        {
            AddCategory(new ShortcutCategory("General")
            {
                Shortcuts =
                {
                    new Shortcut("Open Settings", "Ctrl", ","),
                    new Shortcut("Keyboard Shortcuts", "Ctrl", "/"),
                    new Shortcut("Toggle Fullscreen", "F11"),
                    new Shortcut("Go Back", "Escape"),
                },
            });

            AddCategory(new ShortcutCategory("Playback")
            {
                Shortcuts =
                {
                    new Shortcut("Play/Pause", "Space"),
                    new Shortcut("Stop", "Ctrl", "Space"),
                    new Shortcut("Next Track", "Ctrl", "→"),
                    new Shortcut("Previous Track", "Ctrl", "←"),
                    new Shortcut("Volume Up", "↑"),
                    new Shortcut("Volume Down", "↓"),
                    new Shortcut("Mute", "M"),
                },
            });

            AddCategory(new ShortcutCategory("Editor")
            {
                Shortcuts =
                {
                    new Shortcut("Save", "Ctrl", "S"),
                    new Shortcut("Undo", "Ctrl", "Z"),
                    new Shortcut("Redo", "Ctrl", "Y"),
                    new Shortcut("Cut", "Ctrl", "X"),
                    new Shortcut("Copy", "Ctrl", "C"),
                    new Shortcut("Paste", "Ctrl", "V"),
                    new Shortcut("Select All", "Ctrl", "A"),
                    new Shortcut("Zoom In", "Ctrl", "+"),
                    new Shortcut("Zoom Out", "Ctrl", "-"),
                },
            });

            AddCategory(new ShortcutCategory("Gameplay")
            {
                Shortcuts =
                {
                    new Shortcut("Pause", "Escape"),
                    new Shortcut("Restart", "Ctrl", "R"),
                    new Shortcut("Skip Intro", "Space"),
                },
            });

            buildCategories();
        }

        public void AddCategory(ShortcutCategory category) => categories.Add(category);

        private void buildCategories()
        {
            categoriesContainer.Clear();
            foreach (var category in categories)
            {
                categoriesContainer.Add(new ShortcutCategoryDisplay(category));
            }
        }

        private void filterShortcuts()
        {
            foreach (var child in categoriesContainer.Children)
            {
                if (child is ShortcutCategoryDisplay display)
                    display.ApplyFilter(currentFilter);
            }
        }

        public void Open()
        {
            if (IsOpen) return;
            IsOpen = true;
            this.FadeIn(animation_duration, Easing.OutQuint);
            panelContainer.ScaleTo(1f, animation_duration, Easing.OutBack);
        }

        public void Close()
        {
            if (!IsOpen) return;
            IsOpen = false;
            this.FadeOut(animation_duration, Easing.OutQuint);
            panelContainer.ScaleTo(0.9f, animation_duration, Easing.InQuint);
            OnClose?.Invoke();
        }

        public void Toggle() => _ = IsOpen ? (Action)Close : Open;

        protected override bool OnClick(ClickEvent e)
        {
            var panelBounds = panelContainer.ScreenSpaceDrawQuad;
            if (!panelBounds.Contains(e.ScreenSpaceMousePosition))
            {
                Close();
                return true;
            }
            return base.OnClick(e);
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == Key.Escape && IsOpen)
            {
                Close();
                return true;
            }
            return base.OnKeyDown(e);
        }

        // Nested UI Components
        private partial class ShortcutsCloseButton : Container
        {
            public Action? Action;
            private Box background = null!;

            [BackgroundDependencyLoader]
            private void load()
            {
                Size = new Vector2(36);
                Masking = true;
                CornerRadius = 18;

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
                        Size = new Vector2(18),
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

        private partial class KeyBadge : Container
        {
            public KeyBadge(string key)
            {
                AutoSizeAxes = Axes.Both;
                Masking = true;
                CornerRadius = 4;

                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(50, 52, 65, 255),
                    },
                    new SpriteText
                    {
                        Padding = new MarginPadding { Horizontal = 6, Vertical = 2 },
                        Text = key,
                        Font = new FontUsage("Torus", 11, "SemiBold"),
                        Colour = new Color4(180, 180, 180, 255),
                    },
                };
            }
        }

        private partial class ShortcutCategoryDisplay : Container
        {
            private readonly ShortcutCategory category;
            private FillFlowContainer shortcutsContainer = null!;

            public ShortcutCategoryDisplay(ShortcutCategory category) => this.category = category;

            [BackgroundDependencyLoader]
            private void load()
            {
                Width = 380;
                AutoSizeAxes = Axes.Y;
                Masking = true;
                CornerRadius = 12;

                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = new Color4(25, 27, 40, 200),
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Vertical,
                        Padding = new MarginPadding(16),
                        Spacing = new Vector2(0, 12),
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = category.Name,
                                Font = new FontUsage("Torus", 16, "Bold"),
                                Colour = new Color4(0, 212, 255, 255),
                            },
                            new Box
                            {
                                RelativeSizeAxes = Axes.X,
                                Height = 1,
                                Colour = new Color4(50, 52, 65, 255),
                            },
                            shortcutsContainer = new FillFlowContainer
                            {
                                RelativeSizeAxes = Axes.X,
                                AutoSizeAxes = Axes.Y,
                                Direction = FillDirection.Vertical,
                                Spacing = new Vector2(0, 8),
                            },
                        },
                    },
                };

                foreach (var shortcut in category.Shortcuts)
                    shortcutsContainer.Add(new ShortcutRow(shortcut));
            }

            public void ApplyFilter(string filter)
            {
                if (string.IsNullOrEmpty(filter))
                {
                    this.FadeIn(200);
                    foreach (var child in shortcutsContainer.Children) child.FadeIn(200);
                    return;
                }

                bool categoryVisible = false;
                foreach (var child in shortcutsContainer.Children)
                {
                    if (child is ShortcutRow row)
                    {
                        bool matches = row.Shortcut.Action.ToLower().Contains(filter) ||
                                       row.Shortcut.Keys.Any(k => k.ToLower().Contains(filter));
                        if (matches)
                        {
                            child.FadeIn(200);
                            categoryVisible = true;
                        }
                        else child.FadeOut(200);
                    }
                }
                if (categoryVisible) this.FadeIn(200);
                else this.FadeOut(200);
            }
        }

        private partial class ShortcutRow : Container
        {
            public Shortcut Shortcut { get; }

            public ShortcutRow(Shortcut shortcut) => Shortcut = shortcut;

            [BackgroundDependencyLoader]
            private void load()
            {
                RelativeSizeAxes = Axes.X;
                Height = 28;

                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Text = Shortcut.Action,
                        Font = new FontUsage("Torus", 13),
                        Colour = new Color4(200, 200, 200, 255),
                    },
                    new FillFlowContainer
                    {
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(4, 0),
                        ChildrenEnumerable = createKeyBadges(),
                    },
                };
            }

            private IEnumerable<Drawable> createKeyBadges()
            {
                for (int i = 0; i < Shortcut.Keys.Length; i++)
                {
                    if (i > 0)
                    {
                        yield return new SpriteText
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Text = "+",
                            Font = new FontUsage("Torus", 10),
                            Colour = new Color4(80, 80, 80, 255),
                        };
                    }
                    yield return new ShortcutKeyBadge(Shortcut.Keys[i]);
                }
            }
        }

        private partial class ShortcutKeyBadge : Container
        {
            public ShortcutKeyBadge(string key)
            {
                AutoSizeAxes = Axes.Both;
                Masking = true;
                CornerRadius = 6;

                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Shadow,
                    Colour = Color4.Black.Opacity(0.3f),
                    Radius = 2,
                    Offset = new Vector2(0, 1),
                };

                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = ColourInfo.GradientVertical(
                            new Color4(60, 62, 75, 255),
                            new Color4(45, 47, 60, 255)
                        ),
                    },
                    new SpriteText
                    {
                        Padding = new MarginPadding { Horizontal = 8, Vertical = 4 },
                        Text = key,
                        Font = new FontUsage("Torus", 12, "SemiBold"),
                        Colour = new Color4(220, 220, 220, 255),
                    },
                };
            }
        }
    }

    // Data models
    public class ShortcutCategory
    {
        public string Name { get; }
        public List<Shortcut> Shortcuts { get; } = new();
        public ShortcutCategory(string name) => Name = name;
    }

    public class Shortcut
    {
        public string Action { get; }
        public string[] Keys { get; }
        public Shortcut(string action, params string[] keys)
        {
            Action = action;
            Keys = keys;
        }
    }
}
