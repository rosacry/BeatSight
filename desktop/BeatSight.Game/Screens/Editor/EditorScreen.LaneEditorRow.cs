using System;
using System.Collections.Generic;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Mapping;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        // Instrument colours offered as one-click lane colours; "Auto" returns the lane to the colour of what it holds.
        private static readonly Color4[] laneSwatchColours =
        {
            DrumPalette.Crash,
            DrumPalette.HiHat,
            DrumPalette.Snare,
            DrumPalette.Kick,
            DrumPalette.Tom,
            DrumPalette.TomLow,
            DrumPalette.Ride,
            DrumPalette.RideBell,
            DrumPalette.China,
            DrumPalette.Splash,
            DrumPalette.Percussion
        };

        private FillFlowContainer timelineLaneChipFlow = null!;
        private readonly List<TimelineColourSwatch> timelineLaneSwatches = new();
        private TimelineColourSwatch timelineLaneAutoSwatch = null!;
        private string? lastLaneChipSignature;

        /// <summary>
        /// Lane setup row: pick a lane (chips match the timeline rows), rename it, recolour it, reorder, add or remove.
        /// Empty fields mean "automatic": the name and colour of the instrument the lane holds.
        /// </summary>
        private Drawable createTimelineLaneSection()
        {
            timelineLaneChipFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(4, 0),
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            timelineLaneNameInput = createLaneTextBox(140, "Name");
            timelineLaneShortNameInput = createLaneTextBox(56, "Short");
            timelineLaneColorInput = createLaneTextBox(84, "#RRGGBB");

            timelineLaneSwatches.Clear();
            var swatchFlow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(4, 0),
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            timelineLaneAutoSwatch = new TimelineColourSwatch(null, () => setTimelineLaneColour(null));
            swatchFlow.Add(timelineLaneAutoSwatch);

            foreach (var colour in laneSwatchColours)
            {
                var swatch = new TimelineColourSwatch(colour, () => setTimelineLaneColour(colour));
                timelineLaneSwatches.Add(swatch);
                swatchFlow.Add(swatch);
            }

            timelineLaneMoveLeftButton = createTimelineIconButton(FontAwesome.Solid.ChevronLeft, () => moveTimelineLane(-1));
            timelineLaneMoveRightButton = createTimelineIconButton(FontAwesome.Solid.ChevronRight, () => moveTimelineLane(1));
            timelineLaneAddButton = createTimelineMiniButton("Add lane", addTimelineLane, 84);
            timelineLaneRemoveButton = createTimelineMiniButton("Remove lane", removeTimelineLane, 100);
            foreach (var button in new Drawable[] { timelineLaneAddButton, timelineLaneRemoveButton })
            {
                button.Anchor = Anchor.CentreLeft;
                button.Origin = Anchor.CentreLeft;
            }

            var row = new FillFlowContainer
            {
                RelativeSizeAxes = Axes.X,
                Width = 1f,
                AutoSizeAxes = Axes.Y,
                Direction = FillDirection.Full,
                Spacing = new Vector2(18, 8),
                Children = new Drawable[]
                {
                    createLaneFieldGroup(null, timelineLaneChipFlow),
                    createLaneFieldGroup("Name", timelineLaneNameInput, timelineLaneShortNameInput),
                    createLaneFieldGroup("Colour", swatchFlow, timelineLaneColorInput),
                    createLaneFieldGroup("Order", timelineLaneMoveLeftButton, timelineLaneMoveRightButton),
                    createLaneFieldGroup(null, timelineLaneAddButton, timelineLaneRemoveButton)
                }
            };

            return createTimelineSection("Lane setup", row);
        }

        private BeatSightTextBox createLaneTextBox(float width, string placeholder)
        {
            var textBox = new BeatSightTextBox
            {
                Width = width,
                Height = 30,
                PlaceholderText = placeholder,
                TextSize = 11.6f,
                CommitOnFocusLost = true,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft
            };

            // Enter or leaving the field applies it, so there is no separate Save step.
            textBox.OnCommit += (_, _) => applyTimelineLaneEdits();
            return textBox;
        }

        private static Drawable createLaneFieldGroup(string? caption, params Drawable[] controls)
        {
            var flow = new FillFlowContainer
            {
                AutoSizeAxes = Axes.Both,
                Direction = FillDirection.Horizontal,
                Spacing = new Vector2(6, 0)
            };

            if (caption != null)
            {
                flow.Add(new SpriteText
                {
                    Text = caption,
                    Font = BeatSightFont.Caption(11.5f),
                    Colour = EditorColours.TextSecondary,
                    Anchor = Anchor.CentreLeft,
                    Origin = Anchor.CentreLeft,
                    Margin = new MarginPadding { Right = 2 }
                });
            }

            flow.AddRange(controls);
            return new Container
            {
                AutoSizeAxes = Axes.X,
                Height = 32,
                Child = new Container
                {
                    AutoSizeAxes = Axes.X,
                    RelativeSizeAxes = Axes.Y,
                    Child = flow.With(f =>
                    {
                        f.Anchor = Anchor.CentreLeft;
                        f.Origin = Anchor.CentreLeft;
                    })
                }
            };
        }

        private BasicButton createTimelineIconButton(IconUsage icon, Action action)
        {
            var button = new BasicButton
            {
                Size = new Vector2(32),
                BackgroundColour = UITheme.SurfaceRaised,
                Anchor = Anchor.CentreLeft,
                Origin = Anchor.CentreLeft,
                Masking = true,
                CornerRadius = 8,
                Action = action
            };
            button.Add(new SpriteIcon
            {
                Icon = icon,
                Size = new Vector2(11),
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Colour = EditorColours.TextPrimary
            });
            timelineMiniButtons.Add(button);
            return button;
        }

        private void selectTimelineLane(int laneIndex)
        {
            timelineLaneEditIndex = laneIndex;
            refreshTimelineLaneEditorControls();
        }

        private void setTimelineLaneColour(Color4? colour)
        {
            if (timelineLaneColorInput == null)
                return;

            suppressLaneEditorFieldSync = true;
            timelineLaneColorInput.Current.Value = colour.HasValue ? LaneManagement.ToColorHex(colour.Value) : string.Empty;
            suppressLaneEditorFieldSync = false;
            applyTimelineLaneEdits();
        }

        private void refreshTimelineLaneChips(IReadOnlyList<LaneIdentity> lanes)
        {
            var signature = new System.Text.StringBuilder();
            foreach (var lane in lanes)
                signature.Append(lane.ShortName).Append(':').Append(LaneManagement.ToColorHex(lane.Colour)).Append('|');
            signature.Append(timelineLaneEditIndex);

            string current = signature.ToString();
            if (current == lastLaneChipSignature)
                return;

            lastLaneChipSignature = current;
            timelineLaneChipFlow.Clear();
            for (int i = 0; i < lanes.Count; i++)
            {
                int laneIndex = i;
                timelineLaneChipFlow.Add(new TimelineLaneChip(lanes[i], i == timelineLaneEditIndex, () => selectTimelineLane(laneIndex)));
            }
        }

        /// <summary>
        /// One lane in the lane setup row: colour bar and short label, highlighted when selected.
        /// </summary>
        private partial class TimelineLaneChip : ClickableContainer
        {
            private readonly Box background;
            private readonly bool selected;

            public TimelineLaneChip(LaneIdentity lane, bool selected, Action action)
            {
                this.selected = selected;
                AutoSizeAxes = Axes.X;
                Height = 28;
                Anchor = Anchor.CentreLeft;
                Origin = Anchor.CentreLeft;
                Masking = true;
                CornerRadius = 6;
                BorderThickness = selected ? 1.5f : 0f;
                BorderColour = UITheme.AccentPrimary;
                Action = action;
                Name = lane.Name;

                Children = new Drawable[]
                {
                    background = new Box
                    {
                        RelativeSizeAxes = Axes.Both,
                        Colour = selected ? UITheme.SurfaceRaised : UITheme.Surface
                    },
                    new Box
                    {
                        RelativeSizeAxes = Axes.Y,
                        Width = 3,
                        Colour = lane.Colour
                    },
                    new SpriteText
                    {
                        Text = lane.ShortName,
                        Font = BeatSightFont.Button(12f),
                        Colour = selected ? UITheme.TextPrimary : UITheme.TextSecondary,
                        Anchor = Anchor.CentreLeft,
                        Origin = Anchor.CentreLeft,
                        Margin = new MarginPadding { Left = 11, Right = 9 }
                    }
                };
            }

            protected override bool OnHover(HoverEvent e)
            {
                if (!selected)
                    background.FadeColour(UITheme.SurfaceAlt, UITheme.MotionFast, Easing.OutQuint);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                if (!selected)
                    background.FadeColour(UITheme.Surface, UITheme.MotionFast, Easing.OutQuint);
                base.OnHoverLost(e);
            }
        }

        /// <summary>
        /// Colour choice for the selected lane; a null colour is "Auto".
        /// </summary>
        private partial class TimelineColourSwatch : ClickableContainer
        {
            public readonly string? Hex;

            public TimelineColourSwatch(Color4? colour, Action action)
            {
                Hex = colour.HasValue ? LaneManagement.ToColorHex(colour.Value) : null;
                Height = 22;
                Anchor = Anchor.CentreLeft;
                Origin = Anchor.CentreLeft;
                Masking = true;
                CornerRadius = 5;
                BorderColour = UITheme.TextPrimary;
                Action = action;

                if (colour.HasValue)
                {
                    Width = 22;
                    Child = new Box { RelativeSizeAxes = Axes.Both, Colour = colour.Value };
                }
                else
                {
                    AutoSizeAxes = Axes.X;
                    Children = new Drawable[]
                    {
                        new Box { RelativeSizeAxes = Axes.Both, Colour = UITheme.SurfaceRaised },
                        new SpriteText
                        {
                            Text = "Auto",
                            Font = BeatSightFont.Button(11f),
                            Colour = EditorColours.TextPrimary,
                            Anchor = Anchor.CentreLeft,
                            Origin = Anchor.CentreLeft,
                            Margin = new MarginPadding { Horizontal = 8 }
                        }
                    };
                }
            }

            public void SetSelected(bool selected) => BorderThickness = selected ? 2f : 0f;

            protected override bool OnHover(HoverEvent e)
            {
                this.ScaleTo(1.08f, UITheme.MotionFast, Easing.OutQuint);
                return base.OnHover(e);
            }

            protected override void OnHoverLost(HoverLostEvent e)
            {
                this.ScaleTo(1f, UITheme.MotionFast, Easing.OutQuint);
                base.OnHoverLost(e);
            }
        }
    }
}
