using System;
using System.Collections.Generic;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;
using osuTK.Input;

namespace BeatSight.Game.UI.Overlays
{
    /// <summary>
    /// Context-aware help overlay that displays relevant keyboard shortcuts
    /// and tips based on the current screen context.
    /// Press F1 or '?' to toggle.
    /// </summary>
    public partial class HelpOverlay : VisibilityContainer
    {
        private const float panel_width = 600;
        private const float panel_max_height = 700;

        private Box backgroundDim = null!;
        private Container panel = null!;
        private FillFlowContainer<HelpSection> sectionsContainer = null!;
        private SpriteText contextLabel = null!;

        private HelpContext currentContext = HelpContext.General;

        protected override bool StartHidden => true;

        public enum HelpContext
        {
            General,
            SongSelect,
            Playback,
            Editor,
            Settings
        }

        [BackgroundDependencyLoader]
        private void load()
        {
            RelativeSizeAxes = Axes.Both;

            Children = new Drawable[]
            {
                backgroundDim = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.Black,
                    Alpha = 0.7f
                },
                panel = new Container
                {
                    Width = panel_width,
                    AutoSizeAxes = Axes.Y,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Masking = true,
                    CornerRadius = 16,
                    Children = new Drawable[]
                    {
                        new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = UITheme.Surface
                        },
                        new FillFlowContainer
                        {
                            RelativeSizeAxes = Axes.X,
                            AutoSizeAxes = Axes.Y,
                            Direction = FillDirection.Vertical,
                            Padding = new MarginPadding(24),
                            Spacing = new Vector2(0, 16),
                            Children = new Drawable[]
                            {
                                createHeader(),
                                new BasicScrollContainer
                                {
                                    RelativeSizeAxes = Axes.X,
                                    Height = panel_max_height - 120,
                                    Child = sectionsContainer = new FillFlowContainer<HelpSection>
                                    {
                                        RelativeSizeAxes = Axes.X,
                                        AutoSizeAxes = Axes.Y,
                                        Direction = FillDirection.Vertical,
                                        Spacing = new Vector2(0, 20)
                                    }
                                }
                            }
                        }
                    }
                }
            };

            updateContent();
        }

        private Drawable createHeader()
        {
            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 8),
                Children = new Drawable[]
                {
                    new FillFlowContainer
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Direction = FillDirection.Horizontal,
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = "Keyboard Shortcuts",
                                Font = BeatSightFont.Title(28),
                                Colour = UITheme.TextPrimary
                            },
                            new SpriteText
                            {
                                Text = " (F1 to close)",
                                Font = BeatSightFont.Body(16),
                                Colour = UITheme.TextSecondary,
                                Anchor = Anchor.BottomLeft,
                                Origin = Anchor.BottomLeft,
                                Margin = new MarginPadding { Bottom = 4 }
                            }
                        }
                    },
                    contextLabel = new SpriteText
                    {
                        Font = BeatSightFont.Body(14),
                        Colour = UITheme.AccentPrimary
                    }
                }
            };
        }

        /// <summary>
        /// Set the current context to show relevant shortcuts.
        /// </summary>
        public void SetContext(HelpContext context)
        {
            if (currentContext == context)
                return;

            currentContext = context;
            updateContent();
        }

        private void updateContent()
        {
            sectionsContainer.Clear();

            var sections = GetHelpSections(currentContext);
            foreach (var section in sections)
            {
                sectionsContainer.Add(section);
            }

            contextLabel.Text = $"Context: {currentContext}";
        }

        private static List<HelpSection> GetHelpSections(HelpContext context)
        {
            var sections = new List<HelpSection>();

            // Always show global shortcuts
            sections.Add(new HelpSection("Global", new[]
            {
                ("F1 / ?", "Toggle this help overlay"),
                ("Escape", "Go back / Close overlay"),
                ("F11", "Toggle fullscreen"),
                ("Ctrl+S", "Save (in editor)"),
                ("Ctrl+Q", "Quit application")
            }));

            switch (context)
            {
                case HelpContext.SongSelect:
                    sections.Add(new HelpSection("Song Select", new[]
                    {
                        ("↑ / ↓", "Navigate beatmaps"),
                        ("Enter", "Select beatmap / Start"),
                        ("R", "Select random beatmap"),
                        ("Ctrl+F", "Focus search box"),
                        ("Delete", "Delete selected beatmap")
                    }));
                    break;

                case HelpContext.Playback:
                    sections.Add(new HelpSection("Playback Controls", new[]
                    {
                        ("Space", "Pause / Resume"),
                        ("← / →", "Seek backward / forward"),
                        ("[ / ]", "Slow down / Speed up"),
                        ("Ctrl+← / Ctrl+→", "Jump to section"),
                        ("Home / End", "Jump to start / end")
                    }));
                    sections.Add(new HelpSection("View Modes", new[]
                    {
                        ("1", "2D Lane View"),
                        ("2", "3D Highway View"),
                        ("3", "Manuscript View"),
                        ("Z", "Toggle zoom"),
                        ("Tab", "Toggle HUD")
                    }));
                    sections.Add(new HelpSection("Drum Input", new[]
                    {
                        ("D / F / J / K", "4-lane drum input"),
                        ("S / D / F / J / K", "5-lane drum input"),
                        ("A / S / D / F / J / K / L", "7-lane drum input"),
                        ("Customizable in Settings", "")
                    }));
                    break;

                case HelpContext.Editor:
                    sections.Add(new HelpSection("Editor Navigation", new[]
                    {
                        ("Space", "Play / Pause preview"),
                        ("← / →", "Move by grid snap"),
                        ("Shift + ← / →", "Fine movement"),
                        ("Ctrl + Scroll", "Zoom timeline"),
                        ("Mouse Drag", "Pan timeline")
                    }));
                    sections.Add(new HelpSection("Note Editing", new[]
                    {
                        ("Click", "Place note at cursor"),
                        ("Delete / Backspace", "Delete selected note"),
                        ("Ctrl+A", "Select all notes"),
                        ("Ctrl+C / Ctrl+V", "Copy / Paste notes"),
                        ("Ctrl+Z / Ctrl+Y", "Undo / Redo")
                    }));
                    sections.Add(new HelpSection("Editor Tools", new[]
                    {
                        ("1-9", "Select lane / drum type"),
                        ("Q / W / E", "Quantization: 1/4, 1/8, 1/16"),
                        ("G", "Toggle grid snap"),
                        ("M", "Toggle metronome"),
                        ("B", "Set bookmark")
                    }));
                    break;

                case HelpContext.Settings:
                    sections.Add(new HelpSection("Settings Navigation", new[]
                    {
                        ("↑ / ↓", "Navigate options"),
                        ("← / →", "Adjust value"),
                        ("Enter", "Toggle / Select"),
                        ("Escape", "Close settings"),
                        ("Ctrl+R", "Reset to defaults")
                    }));
                    break;

                default:
                    sections.Add(new HelpSection("Getting Started", new[]
                    {
                        ("Enter Song Select", "Browse and play beatmaps"),
                        ("Generate from Audio", "AI creates beatmap from any song"),
                        ("Practice Mode", "Slow down, loop sections"),
                        ("Editor", "Create and edit beatmaps manually")
                    }));
                    break;
            }

            // Tips section
            sections.Add(new HelpSection("💡 Tips", new[]
            {
                ("Slow Practice", "Use speed controls to master difficult sections"),
                ("High Confidence", "Filter by AI confidence for better beatmaps"),
                ("Custom Keys", "Rebind keys in Settings → Controls"),
                ("View Modes", "Try different views to find what works for you")
            }));

            return sections;
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == Key.Escape || e.Key == Key.F1)
            {
                Hide();
                return true;
            }

            return base.OnKeyDown(e);
        }

        protected override bool OnClick(ClickEvent e)
        {
            // Click outside panel to close
            if (!panel.ReceivePositionalInputAt(e.ScreenSpaceMousePosition))
            {
                Hide();
                return true;
            }

            return base.OnClick(e);
        }

        protected override void PopIn()
        {
            backgroundDim.FadeIn(200);
            panel.ScaleTo(0.9f).ScaleTo(1f, 300, Easing.OutQuint);
            panel.FadeIn(200);
        }

        protected override void PopOut()
        {
            backgroundDim.FadeOut(200);
            panel.ScaleTo(0.9f, 200, Easing.InQuint);
            panel.FadeOut(200);
        }

        /// <summary>
        /// A section of help content with a title and list of shortcuts.
        /// </summary>
        private partial class HelpSection : CompositeDrawable
        {
            public HelpSection(string title, (string key, string description)[] shortcuts)
            {
                RelativeSizeAxes = Axes.X;
                AutoSizeAxes = Axes.Y;

                var content = new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Direction = FillDirection.Vertical,
                    Spacing = new Vector2(0, 8)
                };

                // Section title
                content.Add(new SpriteText
                {
                    Text = title,
                    Font = BeatSightFont.Section(18),
                    Colour = UITheme.AccentPrimary
                });

                // Shortcuts grid
                foreach (var (key, description) in shortcuts)
                {
                    if (string.IsNullOrEmpty(key))
                        continue;

                    content.Add(new Container
                    {
                        RelativeSizeAxes = Axes.X,
                        AutoSizeAxes = Axes.Y,
                        Children = new Drawable[]
                        {
                            new Container
                            {
                                Width = 180,
                                AutoSizeAxes = Axes.Y,
                                Child = new Container
                                {
                                    AutoSizeAxes = Axes.Both,
                                    Masking = true,
                                    CornerRadius = 4,
                                    Children = new Drawable[]
                                    {
                                        new Box
                                        {
                                            RelativeSizeAxes = Axes.Both,
                                            Colour = UITheme.SurfaceAlt
                                        },
                                        new SpriteText
                                        {
                                            Text = key,
                                            Font = BeatSightFont.Button(14),
                                            Colour = UITheme.TextPrimary,
                                            Padding = new MarginPadding { Horizontal = 8, Vertical = 4 }
                                        }
                                    }
                                }
                            },
                            new SpriteText
                            {
                                X = 190,
                                Text = description,
                                Font = BeatSightFont.Body(14),
                                Colour = UITheme.TextSecondary
                            }
                        }
                    });
                }

                InternalChild = content;
            }
        }
    }
}
