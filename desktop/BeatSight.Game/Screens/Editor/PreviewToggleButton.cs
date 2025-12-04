using System;
using BeatSight.Game.Audio;
using BeatSight.Game.Configuration;
using BeatSight.Game.UI.Components;
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

namespace BeatSight.Game.Screens.Editor
{
    /// <summary>
    /// Toggle button for switching between editor preview modes (2D, 3D, Manuscript).
    /// Provides visual feedback for current mode and availability state.
    /// </summary>
    public partial class PreviewToggleButton : BasicButton
    {
        private readonly Box background;
        private readonly SpriteIcon icon;
        private readonly SpriteText modeLabel;
        private readonly Bindable<EditorPreviewMode> previewMode;
        private readonly Color4 colour2D = UITheme.AccentPrimary;
        private readonly Color4 colour3D = UITheme.AccentSecondary;
        private Color4 currentBaseColour;
        private string? availabilityMessage;

        private Box hoverGlow = null!;
        private Box flash = null!;

        [Resolved]
        private UIAudioController uiAudio { get; set; } = null!;

        /// <summary>
        /// Fired when the hover hint text should change.
        /// </summary>
        public event Action<string?>? HoverHintChanged;

        public PreviewToggleButton(Bindable<EditorPreviewMode> previewMode)
        {
            this.previewMode = previewMode.GetBoundCopy();
            currentBaseColour = colour2D;
            availabilityMessage = "Load or create a beatmap to enable 2D/3D switching.";

            Masking = true;
            CornerRadius = 8;

            AddRange(new Drawable[]
            {
                background = new Box
                {
                    RelativeSizeAxes = Axes.Both
                },
                hoverGlow = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.White,
                    Alpha = 0,
                    Blending = BlendingParameters.Additive
                },
                new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Direction = FillDirection.Horizontal,
                    Spacing = new Vector2(6, 0),
                    Children = new Drawable[]
                    {
                        icon = new SpriteIcon
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Size = new Vector2(22),
                            Colour = EditorColours.TextPrimary,
                            Icon = FontAwesome.Solid.LayerGroup
                        },
                        modeLabel = new SpriteText
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Font = BeatSightFont.Title(16f),
                            Colour = EditorColours.TextPrimary,
                            Text = "2D View"
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
            });

            Action = toggleMode;
            this.previewMode.BindValueChanged(updateState, true);
            Enabled.BindValueChanged(_ => updateBackgroundForAvailability(), true);
        }

        private void toggleMode()
        {
            if (previewMode.Value == EditorPreviewMode.Playfield2D)
                previewMode.Value = EditorPreviewMode.Playfield3D;
            else if (previewMode.Value == EditorPreviewMode.Playfield3D)
                previewMode.Value = EditorPreviewMode.Manuscript;
            else
                previewMode.Value = EditorPreviewMode.Playfield2D;
        }

        private void updateState(ValueChangedEvent<EditorPreviewMode> state)
        {
            switch (state.NewValue)
            {
                case EditorPreviewMode.Playfield3D:
                    icon.Icon = FontAwesome.Solid.Cube;
                    modeLabel.Text = "3D View";
                    currentBaseColour = colour3D;
                    break;
                case EditorPreviewMode.Manuscript:
                    icon.Icon = FontAwesome.Solid.Music;
                    modeLabel.Text = "Manuscript";
                    currentBaseColour = Color4.Goldenrod;
                    break;
                case EditorPreviewMode.Playfield2D:
                default:
                    icon.Icon = FontAwesome.Solid.LayerGroup;
                    modeLabel.Text = "2D View";
                    currentBaseColour = colour2D;
                    break;
            }
            updateBackgroundForAvailability();
        }

        protected override bool OnClick(ClickEvent e)
        {
            if (Enabled.Value)
            {
                uiAudio.PlayClick();
                flash.FadeTo(0.5f).FadeOut(500, Easing.OutQuint);
            }
            return base.OnClick(e);
        }

        protected override bool OnHover(HoverEvent e)
        {
            if (!Enabled.Value)
            {
                HoverHintChanged?.Invoke(availabilityMessage ?? "Load or create a beatmap to enable view switching.");
                return base.OnHover(e);
            }

            uiAudio.PlayHover(e.ScreenSpaceMousePosition.X / GetContainingInputManager().DrawSize.X);

            string tooltip = "";
            switch (previewMode.Value)
            {
                case EditorPreviewMode.Playfield2D: tooltip = "Switch to 3D Guitar Hero-style lane view"; break;
                case EditorPreviewMode.Playfield3D: tooltip = "Switch to Manuscript view"; break;
                case EditorPreviewMode.Manuscript: tooltip = "Switch to 2D flat osu!mania-style lane view"; break;
            }
            HoverHintChanged?.Invoke(tooltip);

            var targetColour = EditorColours.Lighten(currentBaseColour, 1.15f);
            background.FadeColour(targetColour, 140, Easing.OutQuint);
            this.ScaleTo(1.05f, 400, Easing.OutElastic);
            hoverGlow.FadeTo(0.2f, 200, Easing.OutQuint);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            base.OnHoverLost(e);
            HoverHintChanged?.Invoke(null);
            updateBackgroundForAvailability();
            this.ScaleTo(1f, 400, Easing.OutElastic);
            hoverGlow.FadeOut(200);
        }

        protected override bool OnMouseDown(MouseDownEvent e)
        {
            this.ScaleTo(0.95f, 50, Easing.OutQuint);
            return base.OnMouseDown(e);
        }

        protected override void OnMouseUp(MouseUpEvent e)
        {
            this.ScaleTo(IsHovered ? 1.05f : 1f, 800, Easing.OutElastic);
            base.OnMouseUp(e);
        }

        /// <summary>
        /// Sets the availability state and reason message.
        /// </summary>
        public void SetAvailability(bool available, string? reason)
        {
            availabilityMessage = reason;
            Enabled.Value = available;
            updateBackgroundForAvailability();
        }

        private void updateBackgroundForAvailability()
        {
            var targetColour = Enabled.Value
                ? currentBaseColour
                : EditorColours.Lighten(currentBaseColour, 0.65f);

            background.FadeColour(targetColour, 180, Easing.OutQuint);
            icon.Colour = Enabled.Value ? EditorColours.TextPrimary : EditorColours.TextSecondary;
            modeLabel.Colour = Enabled.Value ? EditorColours.TextPrimary : EditorColours.TextSecondary;
        }
    }

    /// <summary>
    /// Enum defining the available preview modes in the editor.
    /// </summary>
    public enum EditorPreviewMode
    {
        Playfield2D,
        Playfield3D,
        Manuscript
    }
}
