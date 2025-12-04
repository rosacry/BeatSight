using System;
using System.Collections.Generic;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Extensions.Color4Extensions;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Colour;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Input.Events;
using osu.Framework.Platform;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Settings
{
    /// <summary>
    /// A screen for previewing and managing note skins.
    /// </summary>
    internal partial class SkinEditorScreen : BeatSightScreen
    {
        private const float panel_width = 900;
        private const float panel_height = 600;
        private const float header_height = 60;
        private const float sidebar_width = 200;

        [Resolved]
        private BeatSightConfigManager config { get; set; } = null!;

        [Resolved]
        private GameHost host { get; set; } = null!;

        private readonly Bindable<NoteSkinOption> selectedSkin = new();
        private Container previewArea = null!;
        private FillFlowContainer skinListContainer = null!;
        private SpriteText skinNameText = null!;
        private SpriteText skinDescriptionText = null!;
        private Box dimBackground = null!;

        public Action? OnClose;

        public SkinEditorScreen()
        {
            RelativeSizeAxes = Axes.Both;
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            selectedSkin.BindTo(config.GetBindable<NoteSkinOption>(BeatSightSetting.NoteSkin));

            InternalChildren = new Drawable[]
            {
                dimBackground = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Opacity(Color4.Black, 0.7f)
                },
                new Container
                {
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Size = new Vector2(panel_width, panel_height),
                    Masking = true,
                    CornerRadius = 12,
                    BorderColour = UITheme.Opacity(UITheme.AccentPrimary, 0.5f),
                    BorderThickness = 2,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = UITheme.Background
                        },
                        createHeader(),
                        createContent()
                    }
                }
            };

            selectedSkin.BindValueChanged(onSkinChanged, true);
        }

        private Drawable createHeader()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = header_height,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.BackgroundLayer
                    },
                    new SpriteText
                    {
                        Text = "Skin Editor",
                        Font = FrameworkFont.Regular.With(size: 24),
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Padding = new MarginPadding { Left = 20 },
                        Colour = Color4.White
                    },
                    new BeatSightButton
                    {
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        Size = new Vector2(40),
                        Margin = new MarginPadding { Right = 10 },
                        Text = "✕",
                        Action = closeEditor
                    }
                }
            };
        }

        private Drawable createContent()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Top = header_height },
                Children = new Drawable[]
                {
                    createSidebar(),
                    createMainArea()
                }
            };
        }

        private Drawable createSidebar()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.Y,
                Width = sidebar_width,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface
                    },
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Direction = FillDirection.Vertical,
                        Padding = new MarginPadding(10),
                        Spacing = new Vector2(0, 10),
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = "Available Skins",
                                Font = FrameworkFont.Regular.With(size: 16),
                                Colour = UITheme.TextSecondary
                            },
                            skinListContainer = new FillFlowContainer
                            {
                                RelativeSizeAxes = Axes.X,
                                AutoSizeAxes = Axes.Y,
                                Direction = FillDirection.Vertical,
                                Spacing = new Vector2(0, 5)
                            }
                        }
                    }
                }
            };
        }

        private void populateSkinList()
        {
            skinListContainer?.Clear();

            foreach (NoteSkinOption skin in Enum.GetValues<NoteSkinOption>())
            {
                skinListContainer?.Add(new SkinListItem(skin, selectedSkin));
            }
        }

        private Drawable createMainArea()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Padding = new MarginPadding { Left = sidebar_width },
                Children = new Drawable[]
                {
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Direction = FillDirection.Vertical,
                        Padding = new MarginPadding(20),
                        Spacing = new Vector2(0, 15),
                        Children = new Drawable[]
                        {
                            createSkinInfoPanel(),
                            createPreviewPanel(),
                            createActionsPanel()
                        }
                    }
                }
            };
        }

        private Drawable createSkinInfoPanel()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 80,
                Children = new Drawable[]
                {
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Direction = FillDirection.Vertical,
                        Spacing = new Vector2(0, 8),
                        Children = new Drawable[]
                        {
                            skinNameText = new SpriteText
                            {
                                Font = FrameworkFont.Regular.With(size: 28),
                                Colour = Color4.White
                            },
                            skinDescriptionText = new SpriteText
                            {
                                Font = FrameworkFont.Regular.With(size: 14),
                                Colour = UITheme.TextSecondary
                            }
                        }
                    }
                }
            };
        }

        private Drawable createPreviewPanel()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 300,
                Masking = true,
                CornerRadius = 8,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Opacity(Color4.Black, 0.4f)
                    },
                    previewArea = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding(20)
                    },
                    new SpriteText
                    {
                        Text = "Preview",
                        Font = FrameworkFont.Regular.With(size: 12),
                        Colour = UITheme.Opacity(UITheme.TextSecondary, 0.5f),
                        Anchor = Anchor.TopLeft,
                        Origin = Anchor.TopLeft,
                        Padding = new MarginPadding(8)
                    }
                }
            };
        }

        private Drawable createActionsPanel()
        {
            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(10, 0),
                Children = new Drawable[]
                {
                    new BeatSightButton
                    {
                        Width = 140,
                        Height = 36,
                        Text = "Open Folder",
                        Action = openSkinsFolder
                    },
                    new BeatSightButton
                    {
                        Width = 140,
                        Height = 36,
                        Text = "Apply Skin",
                        Action = applySkin
                    }
                }
            };
        }

        private void onSkinChanged(ValueChangedEvent<NoteSkinOption> e)
        {
            updateSkinInfo(e.NewValue);
            updatePreview(e.NewValue);
        }

        private void updateSkinInfo(NoteSkinOption skin)
        {
            skinNameText.Text = skin.ToString();
            skinDescriptionText.Text = getSkinDescription(skin);
        }

        private static string getSkinDescription(NoteSkinOption skin)
        {
            return skin switch
            {
                NoteSkinOption.Classic => "A clean, traditional look with sharp edges and solid colors. Great for readability.",
                NoteSkinOption.Neon => "Vibrant glowing notes with electric colors. Perfect for a modern aesthetic.",
                NoteSkinOption.Carbon => "Dark, sleek design with subtle metallic accents. Minimalist and professional.",
                _ => "A custom note skin."
            };
        }

        private void updatePreview(NoteSkinOption skin)
        {
            previewArea.Clear();

            // Create a mock lane preview with sample notes
            var laneColors = getLaneColors(skin);
            float laneWidth = 80;
            float spacing = 20;
            float startX = (previewArea.DrawWidth - (laneColors.Length * laneWidth + (laneColors.Length - 1) * spacing)) / 2;

            for (int i = 0; i < laneColors.Length; i++)
            {
                float x = startX + i * (laneWidth + spacing);
                previewArea.Add(createPreviewLane(x, laneWidth, laneColors[i], getNoteLabelForLane(i)));
            }
        }

        private static Color4[] getLaneColors(NoteSkinOption skin)
        {
            return skin switch
            {
                NoteSkinOption.Classic => new[]
                {
                    new Color4(64, 156, 255, 255),   // Blue - Snare
                    new Color4(255, 221, 89, 255),  // Gold - Hihat
                    new Color4(138, 201, 38, 255),  // Green - Tom
                    new Color4(255, 159, 243, 255)  // Pink - Crash
                },
                NoteSkinOption.Neon => new[]
                {
                    new Color4(0, 255, 255, 255),   // Cyan
                    new Color4(255, 0, 255, 255),   // Magenta
                    new Color4(0, 255, 0, 255),     // Lime
                    new Color4(255, 128, 0, 255)    // Orange
                },
                NoteSkinOption.Carbon => new[]
                {
                    new Color4(100, 100, 120, 255), // Steel blue
                    new Color4(90, 90, 90, 255),    // Dark gray
                    new Color4(120, 120, 100, 255), // Bronze
                    new Color4(80, 80, 80, 255)     // Charcoal
                },
                _ => new[]
                {
                    Color4.White,
                    Color4.White,
                    Color4.White,
                    Color4.White
                }
            };
        }

        private static string getNoteLabelForLane(int index)
        {
            return index switch
            {
                0 => "Snare",
                1 => "Hi-Hat",
                2 => "Tom",
                3 => "Crash",
                _ => $"Lane {index + 1}"
            };
        }

        private Drawable createPreviewLane(float x, float width, Color4 color, string label)
        {
            return new Container
            {
                Position = new Vector2(x, 0),
                Size = new Vector2(width, 260),
                Children = new Drawable[]
                {
                    // Lane background
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = ColourInfo.GradientVertical(
                            UITheme.Opacity(color, 0.1f),
                            UITheme.Opacity(color, 0.3f)
                        )
                    },
                    // Sample notes at different heights
                    createPreviewNote(color, 40, width),
                    createPreviewNote(color, 100, width),
                    createPreviewNote(color, 180, width),
                    // Lane label
                    new SpriteText
                    {
                        Text = label,
                        Font = FrameworkFont.Regular.With(size: 12),
                        Colour = color,
                        Anchor = Anchor.BottomCentre,
                        Origin = Anchor.BottomCentre,
                        Padding = new MarginPadding { Bottom = 5 }
                    }
                }
            };
        }

        private Drawable createPreviewNote(Color4 color, float y, float laneWidth)
        {
            float noteWidth = laneWidth * 0.7f;
            float noteHeight = 20;

            return new Container
            {
                Anchor = Anchor.TopCentre,
                Origin = Anchor.Centre,
                Position = new Vector2(0, y),
                Size = new Vector2(noteWidth, noteHeight),
                Masking = true,
                CornerRadius = 4,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = color
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = ColourInfo.GradientVertical(
                            UITheme.Opacity(Color4.White, 0.3f),
                            Color4.Transparent
                        ),
                        Height = 0.5f
                    }
                }
            };
        }

        private void openSkinsFolder()
        {
            try
            {
                string skinsPath = host.Storage.GetFullPath(UserAssetDirectories.Skins);
                host.OpenFileExternally(skinsPath);
            }
            catch
            {
                // Folder open failed - silently ignore
            }
        }

        private void applySkin()
        {
            config.SetValue(BeatSightSetting.NoteSkin, selectedSkin.Value);
        }

        private void closeEditor()
        {
            OnClose?.Invoke();
            this.FadeOut(200, Easing.OutQuad).Expire();
        }

        protected override bool OnClick(ClickEvent e)
        {
            // Close if clicking outside the panel
            return true;
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();
            this.FadeInFromZero(200, Easing.OutQuad);

            // Delayed population after layout
            Schedule(populateSkinList);
            Schedule(() => updatePreview(selectedSkin.Value));
        }

        /// <summary>
        /// A selectable item in the skin list.
        /// </summary>
        private partial class SkinListItem : CompositeDrawable
        {
            private readonly NoteSkinOption skin;
            private readonly Bindable<NoteSkinOption> selectedSkin;
            private Box background = null!;
            private Box selectionIndicator = null!;

            public SkinListItem(NoteSkinOption skin, Bindable<NoteSkinOption> selectedSkin)
            {
                this.skin = skin;
                this.selectedSkin = selectedSkin;

                RelativeSizeAxes = Axes.X;
                Height = 36;
            }

            [BackgroundDependencyLoader]
            private void load()
            {
                InternalChildren = new Drawable[]
                {
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4.Transparent
                    },
                    selectionIndicator = new Box
                    {
                        Width = 3,
                        RelativeSizeAxes = Axes.Y,
                        Colour = UITheme.AccentPrimary,
                        Alpha = 0
                    },
                    new SpriteText
                    {
                        Text = skin.ToString(),
                        Font = FrameworkFont.Regular.With(size: 14),
                        Colour = Color4.White,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Padding = new MarginPadding { Left = 12 }
                    }
                };

                selectedSkin.BindValueChanged(onSelectionChanged, true);
            }

            private void onSelectionChanged(ValueChangedEvent<NoteSkinOption> e)
            {
                bool isSelected = e.NewValue == skin;
                selectionIndicator.FadeTo(isSelected ? 1 : 0, 150);
                background.FadeTo(isSelected ? 0.15f : 0, 150);
                background.Colour = isSelected ? UITheme.AccentPrimary : Color4.White;
            }

            protected override bool OnHover(HoverEvent e)
            {
                if (selectedSkin.Value != skin)
                    background.FadeTo(0.08f, 100);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                if (selectedSkin.Value != skin)
                    background.FadeOut(100);
                base.OnHoverLost(e);
            }

            protected override bool OnClick(ClickEvent e)
            {
                selectedSkin.Value = skin;
                return true;
            }
        }
    }
}
