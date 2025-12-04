// Copyright (c) BeatSight. Licensed under the MIT Licence.
// Extracted from SettingsScreen.cs on December 3, 2025 for maintainability.
// See ENGINEERING_ACTION_TRACKER.md item 2.2

using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Platform;
using osuTK;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;

namespace BeatSight.Game.Screens.Settings
{
    /// <summary>
    /// Settings section displaying keyboard shortcuts reference.
    /// This is a read-only informational section.
    /// </summary>
    public partial class ControlsSettingsSection : SettingsSection
    {
        public ControlsSettingsSection(BeatSightConfigManager config, GameHost host, Container dropdownOverlay, SettingsTooltipOverlay tooltipOverlay)
            : base("Keyboard Shortcuts", dropdownOverlay, tooltipOverlay)
        {
        }

        protected override Drawable createContent()
        {
            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 24),
                Children = new Drawable[]
                {
                    createShortcutSection("Global", new[]
                    {
                        ("Escape", "Go back / Close overlay"),
                        ("F1 or Shift+?", "Toggle help overlay"),
                    }),
                    createShortcutSection("Playback Screen", new[]
                    {
                        ("Space", "Play / Pause"),
                        ("R", "Restart from beginning"),
                        ("[", "Set loop start point"),
                        ("]", "Set loop end point"),
                        ("Backspace", "Clear loop points"),
                    }),
                    createShortcutSection("Editor Screen", new[]
                    {
                        ("Space", "Play / Pause"),
                        ("Shift+Space", "Rewind to start"),
                        ("Left Arrow", "Seek backward 5 seconds"),
                        ("Right Arrow", "Seek forward 5 seconds"),
                        ("Alt+Left", "Nudge selected note earlier"),
                        ("Alt+Right", "Nudge selected note later"),
                        (",", "Jump to previous note"),
                        (".", "Jump to next note"),
                        ("Delete / Backspace", "Delete selected note"),
                        ("[ / ]", "Adjust snap divisor"),
                        ("Ctrl++ / Ctrl+-", "Zoom timeline"),
                        ("Ctrl+Alt++ / Ctrl+Alt+-", "Scale waveform"),
                    }),
                }
            };
        }

        private Drawable createShortcutSection(string title, (string key, string action)[] shortcuts)
        {
            var rows = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 6)
            };

            foreach (var (key, action) in shortcuts)
            {
                rows.Add(createShortcutRow(key, action));
            }

            return new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Vertical,
                Spacing = new Vector2(0, 10),
                Children = new Drawable[]
                {
                    new SpriteText
                    {
                        Text = title,
                        Font = BeatSightFont.Caption(16f),
                        Colour = UITheme.AccentPrimary
                    },
                    rows
                }
            };
        }

        private Drawable createShortcutRow(string key, string action)
        {
            return new Container
            {
                RelativeSizeAxes = Axes.X,
                AutoSizeAxes = Axes.Y,
                Children = new Drawable[]
                {
                    new Container
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
                                Font = BeatSightFont.Caption(12f),
                                Colour = UITheme.TextPrimary,
                                Padding = new MarginPadding { Horizontal = 8, Vertical = 4 }
                            }
                        }
                    },
                    new SpriteText
                    {
                        Text = action,
                        Font = BeatSightFont.Caption(13f),
                        Colour = UITheme.TextSecondary,
                        X = 180,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft
                    }
                }
            };
        }
    }
}
