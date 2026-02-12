using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Drawing;
using BeatSight.Game.Audio;
using BeatSight.Game.Customization;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Audio;
using osu.Framework.Audio.Sample;
using osu.Framework.Allocation;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Effects;
using osu.Framework.Graphics.Shapes;
using FrameworkRectangleF = osu.Framework.Graphics.Primitives.RectangleF;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Graphics.Cursor;
using osu.Framework.Localisation;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input;
using osu.Framework.Input.Events;
using osu.Framework.IO.Stores;
using osu.Framework.Logging;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osu.Framework.Utils;
using osu.Framework.Threading;
using osuTK;
using osuTK.Graphics;
using osuTK.Input;
using BeatSight.Game.Screens;

using BeatSight.Game.UI.Overlays;

namespace BeatSight.Game.Screens.Settings
{
    public partial class SettingsScreen : BeatSightScreen
    {
        [Resolved]
        private UIScaleWizard uiScaleWizard { get; set; } = null!;

        private BeatSightConfigManager config = null!;
        private GameHost host = null!;

        private Container contentContainer = null!;
        private GridContainer mainGrid = null!;
        private Container headerContainer = null!;
        private SpriteText headerTitleText = null!;
        private FillFlowContainer sidebarButtonFlow = null!;
        private SettingsSection? currentSection;
        private BackButton backButton = null!;
        private readonly Dictionary<SettingsCategory, SettingsButton> sectionButtons = new();
        private SettingsCategory currentCategory = SettingsCategory.Playback;
        private Container dropdownOverlay = null!;
        private SettingsTooltipOverlay tooltipOverlay = null!;
        private Container overlayRoot = null!;

        private Bindable<bool> showGlobalBackground = null!;
        private Bindable<double> globalBackgroundOpacity = null!;
        private Box rightAreaBackground = null!;
        private float lastSidebarWidth = -1;
        private float lastHeaderHeight = -1;

        private enum SettingsCategory
        {
            Playback,
            Audio,
            Graphics,
            Controls,
            AI
        }

        [BackgroundDependencyLoader]
        private void load(BeatSightConfigManager configManager, GameHost gameHost)
        {
            config = configManager;
            host = gameHost;

            showGlobalBackground = config.GetBindable<bool>(BeatSightSetting.ShowGlobalBackground);
            globalBackgroundOpacity = config.GetBindable<double>(BeatSightSetting.GlobalBackgroundOpacity);

            showGlobalBackground.BindValueChanged(_ => updateBackgroundState());
            globalBackgroundOpacity.BindValueChanged(_ => updateBackgroundState(), true);

            backButton = new BackButton
            {
                Action = () => this.Exit(),
                Margin = BackButton.DefaultMargin,
                Depth = -10
            };

            dropdownOverlay = new Container
            {
                RelativeSizeAxes = Axes.Both,
                AlwaysPresent = true,
                Masking = false,
                Depth = -5
            };

            overlayRoot = new Container
            {
                RelativeSizeAxes = Axes.Both,
                AlwaysPresent = true,
                Depth = -10,
                Children = new Drawable[]
                {
                    dropdownOverlay,
                    tooltipOverlay = new SettingsTooltipOverlay
                    {
                        RelativeSizeAxes = Axes.Both,
                        AlwaysPresent = true
                    },
                    new SafeAreaContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = BackButton.DefaultMargin,
                        Child = backButton
                    }
                }
            };

            mainGrid = new GridContainer
            {
                Name = "SettingsLayoutGrid",
                RelativeSizeAxes = Axes.Both,
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, getSidebarWidthForViewport(DrawWidth)),
                    new Dimension()
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        createSidebar(),
                        createRightArea()
                    }
                }
            };

            InternalChildren = new Drawable[]
            {
                // Background matching SongSelectScreen
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Black,
                    Alpha = 0.3f
                },
                new SafeAreaContainer
                {
                    RelativeSizeAxes = Axes.Both,
                    Children = new Drawable[]
                    {
                        mainGrid,
                        createHeader()
                    }
                },
                overlayRoot
            };


            // Show playback settings by default
            showSection(SettingsCategory.Playback);

            updateBackgroundState();
            applyResponsiveLayout(force: true);
        }


        private Drawable createSidebar()
        {
            sidebarButtonFlow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 4),
                Padding = new MarginPadding { Top = 110, Left = 20, Right = 20, Bottom = 40 },
                Children = new Drawable[]
                {
                    createSectionButton(SettingsCategory.Playback, "Playback"),
                    createSectionButton(SettingsCategory.Audio, "Audio"),
                    createSectionButton(SettingsCategory.Graphics, "Graphics"),
                    createSectionButton(SettingsCategory.Controls, "Controls"),
                    createSectionButton(SettingsCategory.AI, "AI Tools")
                }
            };

            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.SurfaceAlt
                    },
                    new BeatSightScrollContainer
                    {
                        RelativeSizeAxes = Axes.Both,
                        ClampExtension = 0,
                        Child = sidebarButtonFlow
                    }
                }
            };
        }

        private SettingsButton createSectionButton(SettingsCategory category, string text)
        {
            var button = new SettingsButton(text, () => showSection(category));
            sectionButtons[category] = button;
            if (category == currentCategory)
                button.SetSelected(true);
            return button;
        }

        private void showSection(SettingsCategory category)
        {
            if (currentCategory == category && currentSection != null && contentContainer.Child == currentSection)
                return;

            // Ensure any dropdown menus currently hosted in the shared overlay are disposed
            // before tearing down the owning section. This prevents orphaned menus from
            // lingering at the screen origin when the source control disappears.
            dropdownOverlay.Clear(disposeChildren: true);

            currentCategory = category;
            currentSection = createSectionInstance(category);
            contentContainer.Child = currentSection;

            foreach (var entry in sectionButtons)
                entry.Value.SetSelected(entry.Key == category);
        }

        private SettingsSection createSectionInstance(SettingsCategory category)
        {
            switch (category)
            {
                case SettingsCategory.Playback:
                    return new PlaybackSettingsSection(config, host, dropdownOverlay, tooltipOverlay);
                case SettingsCategory.Audio:
                    return new AudioSettingsSection(config, host, dropdownOverlay, tooltipOverlay);
                case SettingsCategory.Graphics:
                    return new GraphicsSettingsSection(config, host, dropdownOverlay, tooltipOverlay, uiScaleWizard, openSkinEditor);
                case SettingsCategory.Controls:
                    return new ControlsSettingsSection(config, host, dropdownOverlay, tooltipOverlay);
                case SettingsCategory.AI:
                    return new AISettingsSection(config, host, dropdownOverlay, tooltipOverlay);
                default:
                    throw new ArgumentOutOfRangeException(nameof(category), category, null);
            }
        }

        private void updateBackgroundState()
        {
            if (rightAreaBackground == null) return;

            if (showGlobalBackground.Value)
            {
                // Invert opacity: 100% background opacity = 0% overlay opacity
                rightAreaBackground.Alpha = 1.0f - (float)globalBackgroundOpacity.Value;
            }
            else
            {
                rightAreaBackground.Alpha = 1.0f;
            }
        }

        private Drawable createRightArea()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    rightAreaBackground = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.BackgroundLayer
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Top = 100 },
                        Child = contentContainer = new Container
                        {
                            RelativeSizeAxes = Axes.Both,
                            Padding = UITheme.ScreenPadding
                        }
                    }
                }
            };
        }

        private Drawable createFooter()
        {
            return new Container
            {
                RelativeSizeAxes = Axes.Both,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.SurfaceAlt
                    }
                }
            };
        }

        private Drawable createHeader()
        {
            return headerContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 100,
                Children = new Drawable[]
                {
                    new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface,
                        Alpha = 1f
                    },
                    new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Padding = new MarginPadding { Horizontal = 40 },
                        Children = new Drawable[]
                        {
                            headerTitleText = new SpriteText
                            {
                                Text = AppCopy.SettingsHeader,
                                Font = BeatSightFont.Title(40f),
                                Colour = UITheme.AccentPrimary,
                                Anchor = Anchor.Centre,
                                Origin = Anchor.Centre,
                            }
                        }
                    }
                }
            };
        }

        protected override void Update()
        {
            base.Update();
            applyResponsiveLayout();
        }

        private void applyResponsiveLayout(bool force = false)
        {
            if (mainGrid == null || headerContainer == null || sidebarButtonFlow == null)
                return;

            var viewport = resolveResponsiveViewport();
            if (viewport.X <= 0 || viewport.Y <= 0)
                return;

            float sidebarWidth = getSidebarWidthForViewport(viewport.X);
            float headerHeight = getHeaderHeightForViewport(viewport.Y);

            if (force || Math.Abs(sidebarWidth - lastSidebarWidth) > 0.2f)
            {
                mainGrid.ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Absolute, sidebarWidth),
                    new Dimension()
                };
                lastSidebarWidth = sidebarWidth;
            }

            if (force || Math.Abs(headerHeight - lastHeaderHeight) > 0.2f)
            {
                headerContainer.Height = headerHeight;
                lastHeaderHeight = headerHeight;
            }

            float horizontalInset = ResponsiveLayout.ClampFraction(viewport.X, 0.012f, 14f, 32f);
            float topInset = headerHeight + ResponsiveLayout.ClampFraction(viewport.Y, 0.012f, 8f, 20f);
            float bottomInset = ResponsiveLayout.ClampFraction(viewport.Y, 0.038f, 24f, 56f);

            sidebarButtonFlow.Padding = new MarginPadding
            {
                Top = topInset,
                Left = horizontalInset,
                Right = horizontalInset,
                Bottom = bottomInset
            };
            sidebarButtonFlow.Spacing = new Vector2(0, ResponsiveLayout.ClampFraction(viewport.Y, 0.0052f, 3f, 7f));

            if (headerTitleText != null)
                headerTitleText.Font = BeatSightFont.Title(ResponsiveLayout.ClampFraction(viewport.Y, 0.041f, 28f, 42f));
        }

        private Vector2 resolveResponsiveViewport()
            => ResponsiveLayout.ResolveViewport(
                this,
                DrawWidth > 0 ? DrawWidth : 1366f,
                DrawHeight > 0 ? DrawHeight : 768f);

        private static float getSidebarWidthForViewport(float viewportWidth)
        {
            float width = viewportWidth > 0 ? viewportWidth : 1366f;
            return ResponsiveLayout.ClampFraction(width, 0.19f, 210f, 370f);
        }

        private static float getHeaderHeightForViewport(float viewportHeight)
        {
            float height = viewportHeight > 0 ? viewportHeight : 768f;
            return ResponsiveLayout.ClampFraction(height, 0.11f, 82f, 130f);
        }

        internal static void OpenDirectoryExternally(GameHost host, string relativePath)
        {
            try
            {
                string fullPath = host.Storage.GetFullPath(relativePath);
                Directory.CreateDirectory(fullPath);
                launchFileBrowser(fullPath);
            }
            catch (Exception ex)
            {
                Logger.Log($"[Settings] Failed to open directory '{relativePath}': {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        private void openSkinEditor()
        {
            var editor = new SkinEditorScreen
            {
                OnClose = () =>
                {
                    // Refresh skin settings if needed
                }
            };
            AddInternal(editor);
        }

        private static void launchFileBrowser(string path)
        {
            try
            {
                if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = "explorer.exe",
                        Arguments = $"\"{path}\"",
                        UseShellExecute = true
                    });
                }
                else if (RuntimeInformation.IsOSPlatform(OSPlatform.OSX))
                {
                    Process.Start("open", path);
                }
                else
                {
                    Process.Start("xdg-open", path);
                }
            }
            catch (Exception ex)
            {
                Logger.Log($"[Settings] Failed to launch file browser for '{path}': {ex.Message}", LoggingTarget.Runtime, LogLevel.Debug);
            }
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == osuTK.Input.Key.Escape)
            {
                this.Exit();
                return true;
            }

            return base.OnKeyDown(e);
        }

        private partial class SettingsButton : CompositeDrawable
        {
            private const float button_corner_radius = 10f;
            private const float button_hover_scale = 1.05f;
            private const float button_masking_smoothness = 1.5f;

            private readonly Box background;
            private readonly Box accentBar;
            private readonly Container highlightOverlay;
            private readonly SpriteText label;
            private readonly Action action;
            private bool isSelected;
            private readonly Container buttonBody;
            private Box flash = null!;
            private float lastAppliedHeight = -1f;
            private float lastAppliedWidth = -1f;

            [Resolved]
            private UIAudioController uiAudio { get; set; } = null!;

            public SettingsButton(string text, Action action)
            {
                this.action = action;

                RelativeSizeAxes = Axes.X;
                Height = 50;
                Padding = new MarginPadding { Horizontal = 10 };

                InternalChild = buttonBody = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = button_corner_radius,
                    MaskingSmoothness = button_masking_smoothness
                };

                buttonBody.AddRange(new Drawable[]
                {
                    accentBar = new Box
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = 6,
                        Colour = UITheme.AccentPrimary,
                        Alpha = 0,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft
                    },
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = UITheme.Surface
                    },
                    highlightOverlay = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Alpha = 0,
                        Masking = true,
                        CornerRadius = button_corner_radius,
                        EdgeEffect = new EdgeEffectParameters
                        {
                            Type = EdgeEffectType.Glow,
                            Colour = UITheme.AccentPrimary.Opacity(0.35f),
                            Radius = 12,
                            Roundness = button_corner_radius,
                            Hollow = true
                        },
                        Child = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = UITheme.AccentPrimary.Opacity(0.18f)
                        }
                    },
                    label = new SpriteText
                    {
                        Text = text,
                        Font = BeatSightFont.Subtitle(20f),
                        Colour = UITheme.TextSecondary,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Padding = new MarginPadding { Left = 24 }
                    },
                    flash = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = Color4.White,
                        Alpha = 0,
                        Blending = BlendingParameters.Additive
                    }
                });
            }

            protected override void Update()
            {
                base.Update();

                if (Parent == null)
                    return;

                float targetHeight = ResponsiveLayout.ClampFraction(Parent.DrawHeight, 0.062f, 42f, 56f);
                float targetAccentWidth = ResponsiveLayout.ClampFraction(Parent.DrawWidth, 0.0045f, 4f, 7f);
                float targetLabelLeft = ResponsiveLayout.ClampFraction(Parent.DrawWidth, 0.018f, 16f, 28f);
                float targetLabelSize = System.Math.Clamp(targetHeight * 0.4f, 15f, 22f);

                if (System.Math.Abs(targetHeight - lastAppliedHeight) > 0.2f)
                {
                    Height = targetHeight;
                    label.Font = BeatSightFont.Subtitle(targetLabelSize);
                    lastAppliedHeight = targetHeight;
                }

                if (System.Math.Abs(targetAccentWidth - lastAppliedWidth) > 0.2f)
                {
                    accentBar.Width = targetAccentWidth;
                    label.Padding = new MarginPadding { Left = targetLabelLeft };
                    lastAppliedWidth = targetAccentWidth;
                }
            }

            public void SetSelected(bool selected)
            {
                if (isSelected == selected)
                {
                    updateVisualState();
                    return;
                }

                isSelected = selected;
                updateVisualState();
            }

            protected override bool OnClick(ClickEvent e)
            {
                uiAudio.PlayClick();
                flash.FadeTo(0.5f).FadeOut(500, Easing.OutQuint);
                action?.Invoke();
                return true;
            }

            protected override bool OnHover(HoverEvent e)
            {
                uiAudio.PlayHover(e.ScreenSpaceMousePosition.X / GetContainingInputManager().DrawSize.X);
                updateVisualState(true);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                base.OnHoverLost(e);
                updateVisualState();
            }

            protected override bool OnMouseDown(MouseDownEvent e)
            {
                buttonBody.ScaleTo(0.95f, 50, Easing.OutQuint);
                return base.OnMouseDown(e);
            }

            protected override void OnMouseUp(MouseUpEvent e)
            {
                updateVisualState(IsHovered);
                base.OnMouseUp(e);
            }

            private void updateVisualState(bool hovering = false)
            {
                Colour4 baseColour = UITheme.Surface;

                if (isSelected)
                    baseColour = UITheme.Emphasise(baseColour, 1.2f);

                if (hovering)
                    baseColour = UITheme.Emphasise(baseColour, 1.08f);

                background.FadeColour(baseColour, 200, Easing.OutQuint);

                float accentAlpha = isSelected ? 1f : hovering ? 0.45f : 0f;
                accentBar.FadeTo(accentAlpha, 200, Easing.OutQuint);

                float highlightAlpha = isSelected ? 1f : hovering ? 0.6f : 0f;
                highlightOverlay.FadeTo(highlightAlpha, 200, Easing.OutQuint);

                var targetLabelColour = (isSelected || hovering) ? UITheme.TextPrimary : UITheme.TextSecondary;
                label.FadeColour(targetLabelColour, 200, Easing.OutQuint);

                buttonBody.ScaleTo(hovering ? button_hover_scale : 1f, 400, Easing.OutElastic);
            }
        }
    }

    public abstract partial class SettingsSection : CompositeDrawable
    {
        private readonly string title;
        protected Container DropdownOverlay { get; }
        private BeatSightScrollContainer sectionScrollContainer = null!;
        private FillFlowContainer contentFlow = null!;
        private FillFlowContainer sectionBody = null!;
        private SpriteText sectionTitleText = null!;
        private readonly List<Action<float, float>> responsiveReflowActions = new();
        private float lastResponsiveWidth = -1f;
        private float lastResponsiveHeight = -1f;
        protected SettingsTooltipOverlay TooltipOverlay { get; }
        protected const float dropdown_menu_max_height = 240;
        protected BeatSightScrollContainer ScrollViewport => sectionScrollContainer;
        protected enum SliderToggleMode
        {
            DisableSlider,
            ZeroValue
        }

        protected SettingsSection(string title, Container dropdownOverlay, SettingsTooltipOverlay tooltipOverlay)
        {
            this.title = title;
            RelativeSizeAxes = Axes.Both;
            DropdownOverlay = dropdownOverlay;
            TooltipOverlay = tooltipOverlay;
        }

        [BackgroundDependencyLoader]
        private void loadSection()
        {
            contentFlow = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 30)
            };

            sectionBody = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 30)
            };

            contentFlow.AddRange(new Drawable[]
            {
                sectionTitleText = new SpriteText
                {
                    Text = title,
                    Font = BeatSightFont.Section(28f),
                    Colour = UITheme.TextPrimary,
                    Margin = new MarginPadding { Bottom = 10 }
                },
                sectionBody
            });

            sectionScrollContainer = new BeatSightScrollContainer
            {
                RelativeSizeAxes = Axes.Both,
                ClampExtension = 0,
                Child = contentFlow
            };

            InternalChild = sectionScrollContainer;

            rebuildContent();
            applyResponsiveControlSizing(force: true);
        }

        protected void rebuildContent()
        {
            if (sectionBody == null)
                return;

            responsiveReflowActions.Clear();
            sectionBody.Clear(false);
            sectionBody.Add(createContent());
            applyResponsiveControlSizing(force: true);
        }

        protected abstract Drawable createContent();

        protected override void Update()
        {
            base.Update();
            applyResponsiveControlSizing();
        }

        private void registerResponsiveReflow(Action<float, float> action)
        {
            if (action == null)
                return;

            responsiveReflowActions.Add(action);
        }

        private void applyResponsiveControlSizing(bool force = false)
        {
            var viewport = resolveResponsiveViewport();
            float width = viewport.X;
            float height = viewport.Y;

            if (!force
                && System.Math.Abs(width - lastResponsiveWidth) < 0.2f
                && System.Math.Abs(height - lastResponsiveHeight) < 0.2f)
            {
                return;
            }

            float sectionSpacing = ResponsiveLayout.ClampFraction(height, 0.039f, 20f, 34f);
            if (contentFlow != null)
                contentFlow.Spacing = new Vector2(0, sectionSpacing);
            if (sectionBody != null)
                sectionBody.Spacing = new Vector2(0, sectionSpacing);

            if (sectionTitleText != null)
            {
                sectionTitleText.Font = BeatSightFont.Section(ResponsiveLayout.ClampFraction(height, 0.032f, 22f, 30f));
                sectionTitleText.Margin = new MarginPadding
                {
                    Bottom = ResponsiveLayout.ClampFraction(height, 0.011f, 6f, 14f)
                };
            }

            foreach (var action in responsiveReflowActions)
                action(width, height);

            lastResponsiveWidth = width;
            lastResponsiveHeight = height;
        }

        private Vector2 resolveResponsiveViewport()
            => ResponsiveLayout.ResolveViewport(
                this,
                DrawWidth > 0 ? DrawWidth : 1366f,
                DrawHeight > 0 ? DrawHeight : 768f);

        protected SettingItem CreateSettingItem(string label, string? description, Drawable control, params ISettingsTooltipSuppressionSource[] suppressionSources)
        {
            var item = new SettingItem(label, description, control, TooltipOverlay);

            if (control is ISettingsTooltipSuppressionSource controlSuppressor)
                item.TrackTooltipSuppressor(controlSuppressor);

            if (suppressionSources != null)
            {
                foreach (var source in suppressionSources)
                {
                    if (source != null)
                        item.TrackTooltipSuppressor(source);
                }
            }

            return item;
        }

        protected SettingItem CreateCheckbox(string label, Bindable<bool> bindable, string? description = null)
        {
            var checkbox = new BeatSightCheckbox
            {
                Current = bindable,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre
            };

            var checkboxContainer = new Container
            {
                Size = new Vector2(24, 24),
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Child = checkbox
            };

            var controlContainer = new Container
            {
                RelativeSizeAxes = Axes.X,
                Height = 24,
                Child = checkboxContainer
            };

            registerResponsiveReflow((width, height) =>
            {
                float checkboxSize = ResponsiveLayout.ClampFraction(height, 0.031f, 20f, 26f);
                controlContainer.Height = checkboxSize;
                checkboxContainer.Size = new Vector2(checkboxSize, checkboxSize);
            });

            var setting = CreateSettingItem(label, description, controlContainer);

            setting.SetDefaultValue(bindable.Default ? "Enabled" : "Disabled");
            bindable.BindValueChanged(_ => setting.SetModified(!bindable.IsDefault), true);

            setting.EnableRowToggle(bindable);
            return setting;
        }

        protected SettingItem CreateEnumDropdown<T>(string label, Bindable<T> bindable, string? description = null, Func<T, string>? formatter = null, bool enableSearch = false) where T : struct, Enum
        {
            if (formatter == null)
            {
                var directDropdown = new SettingsDropdown<T>(dropdown_menu_max_height)
                {
                    Width = 220,
                    Anchor = Anchor.CentreRight,
                    Origin = Anchor.CentreRight,
                    SearchEnabled = enableSearch
                };

                registerResponsiveReflow((width, height) =>
                {
                    directDropdown.Width = ResponsiveLayout.ClampFraction(width, 0.17f, 176f, 264f);
                });

                directDropdown.OverlayLayer = DropdownOverlay;
                directDropdown.ScrollViewport = ScrollViewport;
                directDropdown.Current = bindable;
                directDropdown.Items = Enum.GetValues(typeof(T)).Cast<T>().ToArray();

                var directSetting = CreateSettingItem(label, description, directDropdown);
                directSetting.SetDefaultValue(bindable.Default.ToString());
                bindable.BindValueChanged(_ => directSetting.SetModified(!bindable.IsDefault), true);
                return directSetting;
            }

            var items = Enum.GetValues(typeof(T)).Cast<T>().Select(value => new EnumChoice<T>(formatter(value), value)).ToArray();

            var mappedDropdown = new SettingsDropdown<EnumChoice<T>>(dropdown_menu_max_height)
            {
                Width = 220,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Items = items,
                SearchEnabled = enableSearch
            };

            registerResponsiveReflow((width, height) =>
            {
                mappedDropdown.Width = ResponsiveLayout.ClampFraction(width, 0.17f, 176f, 264f);
            });

            mappedDropdown.OverlayLayer = DropdownOverlay;
            mappedDropdown.ScrollViewport = ScrollViewport;
            mappedDropdown.Current.BindValueChanged(e =>
            {
                if (!EqualityComparer<T>.Default.Equals(bindable.Value, e.NewValue.Value))
                    bindable.Value = e.NewValue.Value;
            });

            bindable.BindValueChanged(e =>
            {
                var target = items.FirstOrDefault(choice => EqualityComparer<T>.Default.Equals(choice.Value, e.NewValue));
                if (!target.Equals(default(EnumChoice<T>)) && !mappedDropdown.Current.Value.Equals(target))
                    mappedDropdown.Current.Value = target;
            }, true);

            var setting = CreateSettingItem(label, description, mappedDropdown);
            setting.SetDefaultValue(formatter(bindable.Default));
            bindable.BindValueChanged(_ => setting.SetModified(!bindable.IsDefault), true);
            return setting;
        }

        protected SettingItem CreateSlider(string label, Bindable<double> bindable, double min, double max, double precision, string? description = null, Func<double, string>? valueFormatter = null, Bindable<bool>? toggleBindable = null, Action<bool>? toggleStateChanged = null, string? toggleLabelText = null, SliderToggleMode toggleMode = SliderToggleMode.DisableSlider)
        {
            var sliderBindable = new BindableDouble
            {
                MinValue = min,
                MaxValue = max,
                Precision = precision
            };

            sliderBindable.BindTo(bindable);

            var sliderBar = new BeatSightSliderBar
            {
                RelativeSizeAxes = Axes.X,
                Height = 16,
                Current = sliderBindable,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            var valueText = new SpriteText
            {
                Font = BeatSightFont.Label(16f),
                Colour = UITheme.TextSecondary,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight
            };

            var formatter = valueFormatter ?? createDefaultSliderFormatter(precision);
            sliderBindable.BindValueChanged(e => valueText.Text = formatter(e.NewValue), true);

            var valueContainer = new Container
            {
                Width = 64,
                Height = 24,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Child = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Anchor = Anchor.CentreRight,
                    Origin = Anchor.CentreRight,
                    Child = valueText
                }
            };

            const float initialControlWidthWithoutToggle = 320f;
            const float initialControlWidthWithToggle = 360f;
            float controlWidth = toggleBindable != null ? initialControlWidthWithToggle : initialControlWidthWithoutToggle;

            var sliderContainerChildren = new List<Drawable> { sliderBar };
            SliderInputBlocker? sliderInputBlocker = null;

            if (toggleMode == SliderToggleMode.DisableSlider)
            {
                sliderInputBlocker = new SliderInputBlocker
                {
                    RelativeSizeAxes = Axes.Both,
                    Blocking = false
                };
                sliderContainerChildren.Add(sliderInputBlocker);
            }

            Container sliderContainer = new Container
            {
                Width = 220,
                Height = 18,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Children = sliderContainerChildren.ToArray()
            };

            var sliderCluster = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Horizontal,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Spacing = new Vector2(16, 0)
            };

            sliderCluster.Add(sliderContainer);

            var rowFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(8, 0),
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight
            };

            rowFlow.AddRange(new Drawable[] { valueContainer, sliderCluster });

            Container? toggleContainer = null;
            SpriteText? toggleLabelSprite = null;

            if (toggleBindable != null)
            {
                const float checkboxWidth = 24;
                float toggleAreaWidth = string.IsNullOrEmpty(toggleLabelText) ? checkboxWidth : 132;
                float sliderWidth = Math.Max(120, controlWidth - valueContainer.Width - rowFlow.Spacing.X - toggleAreaWidth - sliderCluster.Spacing.X);
                sliderContainer.Width = sliderWidth;

                var checkbox = new BeatSightCheckbox
                {
                    Anchor = Anchor.CentreRight,
                    Origin = Anchor.CentreRight,
                    Current = toggleBindable
                };

                Drawable toggleDrawable = checkbox;

                if (!string.IsNullOrEmpty(toggleLabelText))
                {
                    toggleDrawable = new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(4, 0),
                        Children = new Drawable[]
                        {
                            toggleLabelSprite = new SpriteText
                            {
                                Text = toggleLabelText!,
                                Font = BeatSightFont.Caption(14f),
                                Colour = UITheme.TextSecondary,
                                Anchor = Anchor.CentreRight,
                                Origin = Anchor.CentreRight
                            },
                            checkbox
                        }
                    };
                }

                toggleContainer = new Container
                {
                    Width = toggleAreaWidth,
                    Height = 24,
                    Anchor = Anchor.CentreLeft,
                    Origin = Anchor.CentreLeft,
                    Child = new Container
                    {
                        RelativeSizeAxes = Axes.Both,
                        Anchor = Anchor.CentreRight,
                        Origin = Anchor.CentreRight,
                        Child = toggleDrawable
                    }
                };

                sliderCluster.Add(toggleContainer);

                if (toggleMode == SliderToggleMode.DisableSlider && sliderInputBlocker != null)
                {
                    void applyToggleState(bool enabled, bool instant)
                    {
                        sliderInputBlocker.Blocking = !enabled;
                        if (instant)
                        {
                            sliderBar.Alpha = enabled ? 1f : 0.45f;
                            valueText.Colour = enabled ? UITheme.TextSecondary : UITheme.TextMuted;
                        }
                        else
                        {
                            sliderBar.FadeTo(enabled ? 1f : 0.45f, 200, Easing.OutQuint);
                            valueText.FadeColour(enabled ? UITheme.TextSecondary : UITheme.TextMuted, 200, Easing.OutQuint);
                        }
                    }

                    applyToggleState(toggleBindable.Value, true);

                    toggleBindable.BindValueChanged(e =>
                    {
                        applyToggleState(e.NewValue, false);
                        toggleStateChanged?.Invoke(e.NewValue);
                    }, true);
                }
                else if (toggleMode == SliderToggleMode.ZeroValue)
                {
                    double sliderMin = sliderBindable.MinValue;
                    double sliderMax = sliderBindable.MaxValue;

                    bool suppressSliderToToggleSync = false;
                    bool suppressToggleToSliderSync = false;

                    toggleBindable.BindValueChanged(e =>
                    {
                        if (suppressToggleToSliderSync)
                        {
                            toggleStateChanged?.Invoke(e.NewValue);
                            return;
                        }

                        if (!e.NewValue)
                        {
                            suppressSliderToToggleSync = true;
                            sliderBindable.Value = sliderMin;
                            suppressSliderToToggleSync = false;
                        }
                        else
                        {
                            suppressSliderToToggleSync = true;
                            sliderBindable.Value = sliderMax;
                            suppressSliderToToggleSync = false;
                        }

                        toggleStateChanged?.Invoke(e.NewValue);
                    });

                    sliderBindable.BindValueChanged(e =>
                    {
                        if (suppressSliderToToggleSync)
                            return;

                        bool hasValue = !Precision.AlmostEquals(e.NewValue, sliderMin);
                        if (toggleBindable.Value != hasValue)
                        {
                            suppressToggleToSliderSync = true;
                            toggleBindable.Value = hasValue;
                            suppressToggleToSliderSync = false;
                        }
                    });
                }
            }

            rowFlow.Width = controlWidth;

            var controlContainer = new Container
            {
                Width = controlWidth,
                AutoSizeAxes = Axes.Y,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Child = rowFlow
            };

            void applySliderResponsiveSizing(float viewportWidth, float viewportHeight)
            {
                float rowSpacing = ResponsiveLayout.ClampFraction(viewportWidth, 0.006f, 6f, 10f);
                float sliderToggleSpacing = ResponsiveLayout.ClampFraction(viewportWidth, 0.011f, 10f, 18f);
                float controlWidthWithoutToggle = ResponsiveLayout.ClampFraction(viewportWidth, 0.275f, 268f, 348f);
                float controlWidthWithToggle = ResponsiveLayout.ClampFraction(viewportWidth, 0.315f, 300f, 392f);
                float valueWidth = ResponsiveLayout.ClampFraction(viewportWidth, 0.047f, 56f, 74f);
                float valueHeight = ResponsiveLayout.ClampFraction(viewportHeight, 0.031f, 22f, 28f);
                float sliderHeight = ResponsiveLayout.ClampFraction(viewportHeight, 0.021f, 14f, 18f);
                float sliderContainerHeight = ResponsiveLayout.ClampFraction(viewportHeight, 0.024f, 16f, 20f);
                float toggleLabelSize = ResponsiveLayout.ClampFraction(viewportHeight, 0.017f, 12f, 15f);

                rowFlow.Spacing = new Vector2(rowSpacing, 0);
                sliderCluster.Spacing = new Vector2(sliderToggleSpacing, 0);
                valueContainer.Width = valueWidth;
                valueContainer.Height = valueHeight;
                sliderBar.Height = sliderHeight;
                sliderContainer.Height = sliderContainerHeight;
                valueText.Font = BeatSightFont.Label(System.Math.Clamp(valueHeight * 0.66f, 12f, 17f));

                if (toggleLabelSprite != null)
                    toggleLabelSprite.Font = BeatSightFont.Caption(toggleLabelSize);

                float effectiveControlWidth = toggleBindable != null ? controlWidthWithToggle : controlWidthWithoutToggle;
                controlContainer.Width = effectiveControlWidth;
                rowFlow.Width = effectiveControlWidth;

                if (toggleBindable != null)
                {
                    float checkboxWidth = ResponsiveLayout.ClampFraction(viewportHeight, 0.031f, 20f, 26f);
                    float toggleAreaWidth = string.IsNullOrEmpty(toggleLabelText)
                        ? checkboxWidth
                        : ResponsiveLayout.ClampFraction(viewportWidth, 0.11f, 110f, 150f);

                    if (toggleContainer != null)
                    {
                        toggleContainer.Width = toggleAreaWidth;
                        toggleContainer.Height = valueHeight;
                    }

                    sliderContainer.Width = System.Math.Max(120f, effectiveControlWidth - valueContainer.Width - rowFlow.Spacing.X - toggleAreaWidth - sliderCluster.Spacing.X);
                }
                else
                {
                    sliderContainer.Width = System.Math.Max(120f, effectiveControlWidth - valueContainer.Width - rowFlow.Spacing.X);
                }
            }

            registerResponsiveReflow(applySliderResponsiveSizing);
            applySliderResponsiveSizing(DrawWidth > 0 ? DrawWidth : 1366f, DrawHeight > 0 ? DrawHeight : 768f);

            var setting = CreateSettingItem(label, description, controlContainer, sliderBar);

            setting.SetDefaultValue(formatter(bindable.Default));
            bindable.BindValueChanged(_ => setting.SetModified(!bindable.IsDefault), true);

            if (toggleBindable != null)
                setting.EnableRowToggle(toggleBindable);

            return setting;
        }

        protected static Func<double, string> PercentageFormatter(int decimalPlaces = 0)
        {
            int places = Math.Max(0, decimalPlaces);
            string format = $"F{places}";
            return value => $"{(value * 100).ToString(format, CultureInfo.InvariantCulture)}%";
        }

        protected static Func<double, string> MillisecondsFormatter(int decimalPlaces = 0)
        {
            int places = Math.Max(0, decimalPlaces);
            string format = $"F{places}";
            return value => $"{value.ToString(format, CultureInfo.InvariantCulture)} ms";
        }

        protected static Func<double, string> MultiplierFormatter(int decimalPlaces = 2)
        {
            int places = Math.Max(0, decimalPlaces);
            string format = $"F{places}";
            return value => $"{value.ToString(format, CultureInfo.InvariantCulture)}x";
        }

        private static Func<double, string> createDefaultSliderFormatter(double precision)
        {
            int decimalPlaces = determineDecimalPlaces(precision);
            string format = $"F{decimalPlaces}";
            return value => value.ToString(format, CultureInfo.InvariantCulture);
        }

        private static int determineDecimalPlaces(double precision)
        {
            if (precision <= 0)
                return 2;

            double places = -Math.Log10(precision);
            if (double.IsNaN(places) || double.IsInfinity(places))
                return 2;

            return Math.Clamp((int)Math.Ceiling(places), 0, 4);
        }

        protected partial class SliderInputBlocker : Container
        {
            public bool Blocking { get; set; }

            public override bool HandlePositionalInput => Blocking || base.HandlePositionalInput;
            public override bool HandleNonPositionalInput => Blocking || base.HandleNonPositionalInput;

            protected override bool OnMouseDown(MouseDownEvent e)
            {
                if (Blocking)
                    return true;

                return base.OnMouseDown(e);
            }

            protected override bool OnDragStart(DragStartEvent e)
            {
                if (Blocking)
                    return true;

                return base.OnDragStart(e);
            }

            protected override bool OnScroll(ScrollEvent e)
            {
                if (Blocking)
                    return true;

                return base.OnScroll(e);
            }
        }

        protected sealed partial class SettingsDropdown<T> : BeatSight.Game.UI.Components.Dropdown<T>
        {
            public SettingsDropdown(float menuMaxHeight)
            {
                MenuMaxHeight = menuMaxHeight;
            }
        }

        private readonly struct EnumChoice<T> : IEquatable<EnumChoice<T>> where T : struct, Enum
        {
            public EnumChoice(string label, T value)
            {
                Label = label;
                Value = value;
            }

            public string Label { get; }
            public T Value { get; }
            public override string ToString() => Label;
            public bool Equals(EnumChoice<T> other) => EqualityComparer<T>.Default.Equals(Value, other.Value) && Label == other.Label;
            public override bool Equals(object? obj) => obj is EnumChoice<T> other && Equals(other);
            public override int GetHashCode() => HashCode.Combine(Label, Value);
        }
    }

    public partial class SettingItem : CompositeDrawable
    {
        private const double hover_transition_duration = 200;

        private readonly bool hasDescription;
        private readonly string? descriptionText;
        private readonly SettingsTooltipOverlay? tooltipOverlay;
        private readonly Box backgroundBox;
        private readonly Container hoverHighlight;
        private Bindable<bool>? rowToggleBindable;
        private readonly List<(ISettingsTooltipSuppressionSource source, Action<bool> handler)> suppressionSubscriptions = new();
        private readonly Circle modifiedIndicator;
        private LabelTooltipContainer labelContainer = null!;
        private SpriteText labelText = null!;
        private string? defaultValueText;
        private string? currentTooltipText;

        public SettingItem(string label, string? description, Drawable control, SettingsTooltipOverlay? tooltipOverlay)
        {
            hasDescription = !string.IsNullOrWhiteSpace(description);
            descriptionText = description;
            this.tooltipOverlay = tooltipOverlay;

            RelativeSizeAxes = Axes.X;
            AutoSizeAxes = Axes.Y;

            modifiedIndicator = new Circle
            {
                Size = new Vector2(6),
                Colour = UITheme.AccentPrimary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreRight,
                Margin = new MarginPadding { Right = 8 },
                Alpha = 0
            };

            backgroundBox = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = UITheme.Surface
            };

            hoverHighlight = new Container
            {
                RelativeSizeAxes = Axes.Both,
                Alpha = 0,
                Masking = true,
                CornerRadius = 8,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Glow,
                    Colour = UITheme.AccentPrimary.Opacity(0.32f),
                    Radius = 14,
                    Roundness = 8
                },
                Child = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.AccentPrimary.Opacity(0.08f)
                }
            };

            var textColumn = createTextColumn(label);

            InternalChildren = new Drawable[]
            {
                new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Masking = true,
                    CornerRadius = 8,
                    Children = new Drawable[]
                    {
                        backgroundBox,
                        hoverHighlight
                    }
                },
                new Container
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Padding = new MarginPadding(24),
                    Child = createRowContent(textColumn, control)
                }
            };
        }

        public void SetModified(bool modified)
        {
            modifiedIndicator.Alpha = modified ? 1 : 0;
        }

        public void SetDefaultValue(string text)
        {
            defaultValueText = $"Default: {text}";
        }

        private partial class LabelTooltipContainer : FillFlowContainer
        {
        }

        private Drawable createTextColumn(string label)
        {
            labelText = new SpriteText
            {
                Text = label,
                Font = BeatSightFont.Section(26f),
                Colour = UITheme.TextPrimary,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            labelContainer = new LabelTooltipContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Spacing = new Vector2(0, 6),
                Children = new Drawable[]
                {
                    new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Horizontal,
                        Spacing = new Vector2(8, 0),
                        Children = new Drawable[]
                        {
                            modifiedIndicator,
                            labelText
                        }
                    }
                }
            };

            return labelContainer;
        }

        private Drawable createRowContent(Drawable textColumn, Drawable control)
        {
            const float textColumnWeight = 0.6f;

            var controlWrapper = new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Anchor = Anchor.CentreRight,
                Origin = Anchor.CentreRight,
                Child = new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Anchor = Anchor.CentreRight,
                    Origin = Anchor.CentreRight,
                    Child = control
                }
            };

            return new GridContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                ColumnDimensions = new[]
                {
                    new Dimension(GridSizeMode.Distributed, textColumnWeight),
                    new Dimension(GridSizeMode.AutoSize)
                },
                Content = new[]
                {
                    new Drawable[]
                    {
                        new Container
                        {
                            RelativeSizeAxes = Axes.Both,
                            Padding = new MarginPadding { Right = 28 },
                            Anchor = Anchor.CentreLeft,
                            Origin = Anchor.CentreLeft,
                            Child = textColumn
                        },
                        controlWrapper
                    }
                }
            };
        }

        public void TrackTooltipSuppressor(ISettingsTooltipSuppressionSource source)
        {
            if (tooltipOverlay == null)
                return;

            void handler(bool suppressed) => tooltipOverlay.SetSuppressed(source, suppressed);
            source.TooltipSuppressionChanged += handler;
            suppressionSubscriptions.Add((source, handler));

            if (source.IsTooltipSuppressed)
                tooltipOverlay.SetSuppressed(source, true);
        }

        protected override bool OnHover(HoverEvent e)
        {
            backgroundBox.FadeColour(UITheme.Emphasise(UITheme.Surface, 1.12f), hover_transition_duration, Easing.OutQuint);
            hoverHighlight.FadeTo(0.85f, hover_transition_duration, Easing.OutQuint);
            hoverHighlight.ScaleTo(1f, hover_transition_duration, Easing.OutQuint);

            updateTooltip(e.ScreenSpaceMousePosition);

            return base.OnHover(e);
        }

        protected override bool OnMouseMove(MouseMoveEvent e)
        {
            updateTooltip(e.ScreenSpaceMousePosition);
            return base.OnMouseMove(e);
        }

        private void updateTooltip(Vector2 screenSpacePosition)
        {
            bool hoveringIndicator = screenSpacePosition.X < labelText.ScreenSpaceDrawQuad.TopLeft.X;
            bool isModified = modifiedIndicator.Alpha > 0;

            string? targetText = null;

            if (hoveringIndicator && isModified)
                targetText = defaultValueText;
            else if (hasDescription)
                targetText = descriptionText;

            if (targetText != currentTooltipText)
            {
                if (!string.IsNullOrEmpty(targetText))
                    tooltipOverlay?.BeginHover(this, targetText!, screenSpacePosition);
                else
                    tooltipOverlay?.EndHover(this);

                currentTooltipText = targetText;
            }

            if (!string.IsNullOrEmpty(targetText))
                tooltipOverlay?.UpdateHoverPosition(this, screenSpacePosition);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            base.OnHoverLost(e);
            tooltipOverlay?.EndHover(this);
            currentTooltipText = null;
            backgroundBox.FadeColour(UITheme.Surface, hover_transition_duration, Easing.OutQuint);
            hoverHighlight.FadeOut(hover_transition_duration, Easing.OutQuint);
        }

        public void EnableRowToggle(Bindable<bool> toggleBindable)
        {
            rowToggleBindable = toggleBindable ?? throw new ArgumentNullException(nameof(toggleBindable));
        }

        protected override bool OnClick(ClickEvent e)
        {
            if (rowToggleBindable != null && !rowToggleBindable.Disabled && e.Button == MouseButton.Left)
            {
                rowToggleBindable.Value = !rowToggleBindable.Value;
                return true;
            }

            return base.OnClick(e);
        }

        protected override void Dispose(bool isDisposing)
        {
            tooltipOverlay?.EndHover(this);

            foreach (var (source, handler) in suppressionSubscriptions)
            {
                source.TooltipSuppressionChanged -= handler;
                tooltipOverlay?.SetSuppressed(source, false);
            }

            suppressionSubscriptions.Clear();
            base.Dispose(isDisposing);
        }
    }

    // Shared tooltip overlay that mimics osu!'s delayed hover descriptions.
    public sealed partial class SettingsTooltipOverlay : CompositeDrawable
    {
        private const double appear_delay = 450;
        private const double fade_duration = 180;
        private const float tooltip_margin = 10;
        private const float tooltip_offset_x = 18;
        private const float tooltip_offset_y = 12;
        private const float tooltip_max_width = 320;

        private readonly Container tooltipBody;
        private readonly TooltipTextFlow tooltipText;
        private SettingItem? currentOwner;
        private ScheduledDelegate? showSchedule;
        private Vector2 pendingPosition;
        private string? pendingDescription;
        private readonly HashSet<object> suppressionTokens = new();
        private Vector2 lastTooltipSize;
        private Vector2? lastTrackedMousePosition;

        public SettingsTooltipOverlay()
        {
            RelativeSizeAxes = Axes.Both;
            AlwaysPresent = true;
            Alpha = 0;

            InternalChild = tooltipBody = new Container
            {
                AutoSizeAxes = Axes.Both,
                Anchor = Anchor.TopLeft,
                Origin = Anchor.TopLeft,
                Masking = true,
                CornerRadius = 6,
                Alpha = 0,
                EdgeEffect = new EdgeEffectParameters
                {
                    Type = EdgeEffectType.Glow,
                    Colour = UITheme.AccentPrimary.Opacity(0.2f),
                    Radius = 10,
                    Roundness = 6
                },
                Child = new Container
                {
                    AutoSizeAxes = Axes.Both,
                    Padding = new MarginPadding { Horizontal = 12, Vertical = 10 },
                    Child = tooltipText = new TooltipTextFlow(tooltip_max_width)
                    {
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre
                    }
                }
            };
        }

        public void BeginHover(SettingItem source, string description, Vector2 screenSpacePosition)
        {
            pendingPosition = screenSpacePosition;
            lastTrackedMousePosition = screenSpacePosition;

            if (string.IsNullOrWhiteSpace(description))
                return;

            pendingDescription = description;

            if (currentOwner != source)
            {
                hideTooltip();
                currentOwner = source;
            }

            scheduleShow();
        }

        public void UpdateHoverPosition(SettingItem source, Vector2 screenSpacePosition)
        {
            pendingPosition = screenSpacePosition;
            lastTrackedMousePosition = screenSpacePosition;

            if (currentOwner != source)
                return;

            if (tooltipBody.Alpha <= 0 || TooltipsSuppressed)
                return;

            moveTooltip(false);
        }

        public void EndHover(SettingItem source)
        {
            if (currentOwner != source)
                return;

            currentOwner = null;
            pendingDescription = null;
            showSchedule?.Cancel();
            showSchedule = null;
            lastTrackedMousePosition = null;
            hideTooltip();
        }

        public void SetSuppressed(object token, bool suppressed)
        {
            if (suppressed)
            {
                if (suppressionTokens.Add(token))
                {
                    showSchedule?.Cancel();
                    hideTooltip();
                }
            }
            else
            {
                if (suppressionTokens.Remove(token) && !TooltipsSuppressed)
                    scheduleShow();
            }
        }

        private void scheduleShow()
        {
            showSchedule?.Cancel();

            if (TooltipsSuppressed || currentOwner == null || string.IsNullOrWhiteSpace(pendingDescription))
                return;

            showSchedule = Scheduler.AddDelayed(() => showTooltip(pendingDescription!), appear_delay);
        }

        private void showTooltip(string description)
        {
            if (TooltipsSuppressed)
                return;

            tooltipText.SetText(description);
            moveTooltip(true);
            tooltipBody.FadeIn(fade_duration, Easing.OutQuint);
            this.FadeIn(fade_duration, Easing.OutQuint);
        }

        private void moveTooltip(bool instant)
        {
            Vector2 local = ToLocalSpace(pendingPosition) + new Vector2(tooltip_offset_x, tooltip_offset_y);
            Vector2 tooltipSize = tooltipBody.BoundingBox.Size;

            if (Precision.AlmostEquals(tooltipSize.X, 0) || Precision.AlmostEquals(tooltipSize.Y, 0))
                tooltipSize = tooltipBody.DrawSize;

            var ownerBounds = getCurrentOwnerBounds();
            if (ownerBounds.HasValue)
            {
                float belowY = ownerBounds.Value.Bottom + tooltip_margin;
                float aboveY = ownerBounds.Value.Top - tooltip_margin - tooltipSize.Y;
                bool canPlaceBelow = belowY + tooltipSize.Y <= DrawHeight - tooltip_margin;
                bool canPlaceAbove = aboveY >= tooltip_margin;

                // Prefer placing above or below, centered horizontally
                bool placedVertically = false;
                if (canPlaceAbove)
                {
                    local.Y = aboveY;
                    placedVertically = true;
                }
                else if (canPlaceBelow)
                {
                    local.Y = belowY;
                    placedVertically = true;
                }

                if (placedVertically)
                {
                    // Center horizontally relative to owner
                    float ownerCentreX = ownerBounds.Value.Centre.X;
                    float centeredX = ownerCentreX - tooltipSize.X / 2;

                    // Clamp to screen bounds
                    centeredX = Math.Clamp(centeredX, tooltip_margin, DrawWidth - tooltip_margin - tooltipSize.X);
                    local.X = centeredX;
                }
                else
                {
                    // Fallback to side placement if vertical space is tight
                    float rightAlignedX = ownerBounds.Value.Right + tooltip_margin;
                    float leftAlignedX = ownerBounds.Value.Left - tooltip_margin - tooltipSize.X;

                    bool canPlaceRight = rightAlignedX + tooltipSize.X <= DrawWidth - tooltip_margin;
                    bool canPlaceLeft = leftAlignedX >= tooltip_margin;

                    if (canPlaceRight)
                        local.X = rightAlignedX;
                    else if (canPlaceLeft)
                        local.X = leftAlignedX;

                    // Align Y with top of owner, clamped
                    local.Y = Math.Clamp(ownerBounds.Value.Top, tooltip_margin, DrawHeight - tooltip_margin - tooltipSize.Y);
                }
            }
            else
            {
                // No owner, just clamp to screen
                local.X = Math.Clamp(local.X, tooltip_margin, DrawWidth - tooltip_margin - tooltipSize.X);
                local.Y = Math.Clamp(local.Y, tooltip_margin, DrawHeight - tooltip_margin - tooltipSize.Y);
            }

            if (instant)
                tooltipBody.Position = local;
            else
                tooltipBody.MoveTo(local, 200, Easing.OutQuint);
        }

        private void hideTooltip()
        {
            tooltipBody.FadeOut(fade_duration, Easing.OutQuint);
            this.FadeOut(fade_duration, Easing.OutQuint);
        }

        private sealed partial class TooltipTextFlow : TextFlowContainer
        {
            private readonly FontUsage fontUsage = BeatSightFont.Body(16f);
            private readonly float maxWidth;

            public TooltipTextFlow(float maxWidth)
            {
                this.maxWidth = maxWidth;
                AutoSizeAxes = Axes.Y;
                RelativeSizeAxes = Axes.None;
                Width = maxWidth;
                TextAnchor = Anchor.Centre;
            }

            public void SetText(string text)
            {
                Clear();

                // Heuristic: if text is short, use AutoSize.
                if (text.Length < 65 && !text.Contains('\n'))
                {
                    AutoSizeAxes = Axes.Both;
                    TextAnchor = Anchor.TopCentre;
                }
                else
                {
                    AutoSizeAxes = Axes.Y;
                    Width = maxWidth;
                    TextAnchor = Anchor.TopCentre;
                }

                AddParagraph(text, t =>
                {
                    t.Font = fontUsage;
                    t.Colour = UITheme.TextPrimary;
                });
            }

            protected override osu.Framework.Graphics.Sprites.SpriteText CreateSpriteText()
                => new BeatSightSpriteText
                {
                    UseFullGlyphHeight = false,
                    Shadow = false
                };
        }

        protected override void Update()
        {
            base.Update();

            if (currentOwner == null)
                return;

            var inputManager = GetContainingInputManager();
            if (inputManager == null)
                return;

            Vector2 cursorPosition = inputManager.CurrentState.Mouse.Position;

            if (lastTrackedMousePosition.HasValue
                && Precision.AlmostEquals(lastTrackedMousePosition.Value.X, cursorPosition.X)
                && Precision.AlmostEquals(lastTrackedMousePosition.Value.Y, cursorPosition.Y))
            {
                return;
            }

            lastTrackedMousePosition = cursorPosition;
            pendingPosition = cursorPosition;

            if (tooltipBody.Alpha <= 0 || TooltipsSuppressed)
                return;

            moveTooltip(false);
        }

        private bool TooltipsSuppressed => suppressionTokens.Count > 0;

        private FrameworkRectangleF? getCurrentOwnerBounds()
        {
            if (currentOwner == null)
                return null;

            var quad = currentOwner.ScreenSpaceDrawQuad;
            var topLeft = ToLocalSpace(quad.TopLeft);
            var bottomRight = ToLocalSpace(quad.BottomRight);

            float left = Math.Min(topLeft.X, bottomRight.X);
            float right = Math.Max(topLeft.X, bottomRight.X);
            float top = Math.Min(topLeft.Y, bottomRight.Y);
            float bottom = Math.Max(topLeft.Y, bottomRight.Y);

            return new FrameworkRectangleF(left, top, right - left, bottom - top);
        }

        private static bool rectanglesOverlap(FrameworkRectangleF a, FrameworkRectangleF b)
            => a.Right > b.Left && a.Left < b.Right && a.Bottom > b.Top && a.Top < b.Bottom;

        protected override void UpdateAfterChildren()
        {
            base.UpdateAfterChildren();

            var currentSize = tooltipBody.BoundingBox.Size;

            if (Precision.AlmostEquals(currentSize.X, lastTooltipSize.X) && Precision.AlmostEquals(currentSize.Y, lastTooltipSize.Y))
                return;

            lastTooltipSize = currentSize;

            if (currentOwner == null || pendingDescription == null || TooltipsSuppressed)
                return;

            moveTooltip(true);
        }
    }
}
