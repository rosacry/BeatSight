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
using osuTK.Input;

namespace BeatSight.Game.Screens.Editor
{
    /// <summary>
    /// Toggle button for switching between editor preview modes (2D, 3D, Sheet Music).
    /// Provides visual feedback for current mode and availability state.
    /// </summary>
    public partial class PreviewToggleButton : BasicButton
    {
        private const float horizontalLabelPadding = 12f;
        private readonly Box background;
        private readonly Box border;
        private readonly Box topSheen;
        private readonly FillFlowContainer contentFlow;
        private readonly SpriteIcon icon;
        private readonly SpriteText modeLabel;
        private readonly Bindable<EditorPreviewMode> previewMode;
        private readonly Color4 colour2D = UITheme.AccentPrimary;
        private readonly Color4 colour3D = UITheme.AccentSecondary;
        private Color4 currentBaseColour;
        private string fullModeLabel = "2D View";
        private string? availabilityMessage;

        private Box hoverGlow = null!;
        private Box flash = null!;

        [Resolved]
        private UIAudioController uiAudio { get; set; } = null!;

        /// <summary>
        /// Fired when the hover hint text should change.
        /// </summary>
        public event Action<string?>? HoverHintChanged;

        /// <summary>
        /// Enables or disables scale transforms for this button.
        /// Disable when the button sits in autosized layout rows that must not reflow.
        /// </summary>
        public bool EnableScaleAnimation { get; set; } = true;

        public PreviewToggleButton(Bindable<EditorPreviewMode> previewMode)
        {
            this.previewMode = previewMode.GetBoundCopy();
            currentBaseColour = colour2D;
            availabilityMessage = "Load or create a beatmap to enable 2D/3D switching.";

            Masking = true;
            CornerRadius = 9;

            AddRange(new Drawable[]
            {
                background = new Box
                {
                    RelativeSizeAxes = Axes.Both
                },
                topSheen = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Height = 0.42f,
                    Colour = Color4.White.Opacity(0.1f)
                },
                border = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(200, 223, 255, 120),
                    Alpha = 0
                },
                hoverGlow = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = Color4.White,
                    Alpha = 0,
                    Blending = BlendingParameters.Additive
                },
                contentFlow = new FillFlowContainer
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
                            Size = new Vector2(15),
                            Colour = EditorColours.TextPrimary,
                            Icon = FontAwesome.Solid.LayerGroup
                        },
                        modeLabel = new SpriteText
                        {
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                            Font = BeatSightFont.Button(12.8f),
                            Colour = EditorColours.TextPrimary,
                            Text = "2D View",
                            Truncate = true,
                            UseFullGlyphHeight = false,
                            MaxWidth = 120
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

            Text = string.Empty;
            Action = toggleMode;
            this.previewMode.BindValueChanged(updateState, true);
            Enabled.BindValueChanged(_ => updateBackgroundForAvailability(), true);
        }

        public void SetContentDensity(float labelSize, float iconSize, float spacing, float cornerRadius)
        {
            modeLabel.Font = BeatSightFont.Button(labelSize);
            icon.Size = new Vector2(iconSize);
            contentFlow.Spacing = new Vector2(spacing, 0);
            CornerRadius = cornerRadius;
        }

        protected override void Update()
        {
            base.Update();
            modeLabel.MaxWidth = Math.Max(20f, DrawWidth - 32f - horizontalLabelPadding * 2f);
            applyResponsiveModeLabel();
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
                    fullModeLabel = "3D View";
                    currentBaseColour = colour3D;
                    break;
                case EditorPreviewMode.Manuscript:
                    icon.Icon = FontAwesome.Solid.Music;
                    fullModeLabel = "Sheet Music";
                    currentBaseColour = Color4.Goldenrod;
                    break;
                case EditorPreviewMode.Playfield2D:
                default:
                    icon.Icon = FontAwesome.Solid.LayerGroup;
                    fullModeLabel = "2D View";
                    currentBaseColour = colour2D;
                    break;
            }

            applyResponsiveModeLabel();
            updateBackgroundForAvailability();
        }

        private void applyResponsiveModeLabel()
        {
            if (previewMode.Value == EditorPreviewMode.Manuscript && DrawWidth < 124f)
            {
                modeLabel.Text = "Sheet";
                return;
            }

            modeLabel.Text = fullModeLabel;
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
                case EditorPreviewMode.Playfield3D: tooltip = "Switch to Sheet Music view"; break;
                case EditorPreviewMode.Manuscript: tooltip = "Switch to 2D flat osu!mania-style lane view"; break;
            }
            HoverHintChanged?.Invoke(tooltip);

            var targetColour = EditorColours.Lighten(currentBaseColour, 1.15f);
            background.FadeColour(targetColour, 140, Easing.OutQuint);
            if (EnableScaleAnimation)
                this.ScaleTo(1.015f, 220, Easing.OutQuint);
            border.FadeTo(0.24f, 170, Easing.OutQuint);
            hoverGlow.FadeTo(0.2f, 200, Easing.OutQuint);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            base.OnHoverLost(e);
            HoverHintChanged?.Invoke(null);
            updateBackgroundForAvailability();
            if (EnableScaleAnimation)
                this.ScaleTo(1f, 200, Easing.OutQuint);
            else
                Scale = Vector2.One;
            border.FadeOut(160, Easing.OutQuint);
            hoverGlow.FadeOut(200);
        }

        protected override bool OnMouseDown(MouseDownEvent e)
        {
            if (e.Button != MouseButton.Left)
                return base.OnMouseDown(e);

            if (EnableScaleAnimation)
                this.ScaleTo(0.95f, 50, Easing.OutQuint);
            // Consume left-button down so the preview toggle never forwards to timeline input.
            return true;
        }

        protected override void OnMouseUp(MouseUpEvent e)
        {
            if (EnableScaleAnimation)
                this.ScaleTo(IsHovered ? 1.02f : 1f, 220, Easing.OutQuint);
            else
                Scale = Vector2.One;
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
            topSheen.FadeTo(Enabled.Value ? 1f : 0.7f, 150, Easing.OutQuint);
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
