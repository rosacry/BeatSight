using System;
using BeatSight.Game.Audio;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    /// <summary>
    /// Styled button for the editor toolbar with hover effects, 
    /// visual feedback, and status tooltip support.
    /// </summary>
    public partial class EditorButton : BasicButton
    {
        private readonly Box background;
        private readonly Color4 hoverColour;
        private readonly Color4 idleColour;
        private readonly Color4 disabledColour;
        private readonly SpriteText label;
        private string baseText;

        private Box hoverGlow = null!;
        private Box flash = null!;

        [Resolved]
        private UIAudioController uiAudio { get; set; } = null!;

        /// <summary>
        /// Current status message displayed on hover.
        /// </summary>
        public string StatusMessage { get; private set; } = string.Empty;

        /// <summary>
        /// Fired when hover hint text should change.
        /// </summary>
        public event Action<string?>? HoverHintChanged;

        public EditorButton(string text, Color4 colour)
        {
            baseText = text;
            hoverColour = EditorColours.Lighten(colour, 1.15f);
            idleColour = colour;
            disabledColour = EditorColours.Lighten(colour, 0.6f);

            Masking = true;
            CornerRadius = 8;

            AddInternal(background = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = idleColour
            });

            AddInternal(hoverGlow = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = Color4.White,
                Alpha = 0,
                Blending = BlendingParameters.Additive
            });

            AddInternal(label = new SpriteText
            {
                Text = text,
                Font = BeatSightFont.Section(20f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre
            });

            AddInternal(flash = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = Color4.White,
                Alpha = 0,
                Blending = BlendingParameters.Additive
            });

            Enabled.BindValueChanged(e => updateEnabledState(e.NewValue), true);
        }

        /// <summary>
        /// Sets the button label text.
        /// </summary>
        public void SetLabel(string text)
        {
            if (string.IsNullOrWhiteSpace(text))
                text = baseText;

            baseText = text;
            label.Text = text;
            base.Text = text;
        }

        /// <summary>
        /// Updates the button state with enabled flag and tooltip message.
        /// </summary>
        public void UpdateState(bool enabled, string tooltip)
        {
            StatusMessage = tooltip;
            label.Text = baseText;
            Enabled.Value = enabled;

            if (IsHovered)
                HoverHintChanged?.Invoke(StatusMessage);
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
            HoverHintChanged?.Invoke(StatusMessage);

            if (!Enabled.Value)
                return false;

            uiAudio.PlayHover(e.ScreenSpaceMousePosition.X / GetContainingInputManager().DrawSize.X);
            background.FadeColour(hoverColour, 200, Easing.OutQuint);
            this.ScaleTo(1.05f, 400, Easing.OutElastic);
            hoverGlow.FadeTo(0.2f, 200, Easing.OutQuint);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            base.OnHoverLost(e);
            background.FadeColour(Enabled.Value ? idleColour : disabledColour, 200, Easing.OutQuint);
            this.ScaleTo(1f, 400, Easing.OutElastic);
            hoverGlow.FadeOut(200);
            HoverHintChanged?.Invoke(null);
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

        private void updateEnabledState(bool enabled)
        {
            background.FadeColour(enabled ? idleColour : disabledColour, 200, Easing.OutQuint);
            this.FadeTo(enabled ? 1f : 0.5f, 200, Easing.OutQuint);
            if (!enabled)
                this.ScaleTo(1f, 200, Easing.OutQuint);
            label.FadeColour(enabled ? EditorColours.TextPrimary : EditorColours.Lighten(EditorColours.TextPrimary, 0.8f), 200, Easing.OutQuint);
        }
    }
}
