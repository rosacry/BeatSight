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
using osuTK;
using osuTK.Input;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Editor
{
    /// <summary>
    /// Styled button for the editor toolbar with hover effects, 
    /// visual feedback, and status tooltip support.
    /// </summary>
    public partial class EditorButton : BasicButton
    {
        private const float horizontalLabelPadding = 10f;
        private readonly Box background;
        private readonly Box border;
        private readonly Box topSheen;
        private readonly Color4 hoverColour;
        private readonly Color4 idleColour;
        private readonly Color4 disabledColour;
        private readonly Color4 borderColour;
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

        /// <summary>
        /// Enables or disables scale transforms for this button.
        /// Disable when the button sits in autosized layout rows that must not reflow.
        /// </summary>
        public bool EnableScaleAnimation { get; set; } = true;

        public EditorButton(string text, Color4 colour)
        {
            baseText = text;
            hoverColour = EditorColours.Lighten(colour, 1.1f);
            idleColour = colour;
            disabledColour = EditorColours.Lighten(colour, 0.68f);
            borderColour = EditorColours.Mix(colour, Color4.White, 0.24f).Opacity(0.85f);

            Masking = true;
            CornerRadius = 9;

            AddInternal(background = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = idleColour
            });

            AddInternal(topSheen = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Height = 0.42f,
                Colour = Color4.White.Opacity(0.09f)
            });

            AddInternal(border = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Alpha = 0,
                Colour = borderColour
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
                Font = BeatSightFont.Button(13.4f),
                Colour = EditorColours.TextPrimary,
                Anchor = Anchor.Centre,
                Origin = Anchor.Centre,
                Truncate = true,
                UseFullGlyphHeight = false,
                MaxWidth = 120
            });

            AddInternal(flash = new Box
            {
                RelativeSizeAxes = Axes.Both,
                Colour = Color4.White,
                Alpha = 0,
                Blending = BlendingParameters.Additive
            });

            SetLabel(text);
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
            // We draw our own label sprite to keep styling/animation consistent.
            // Keep base text empty to avoid duplicate captions.
            base.Text = string.Empty;
        }

        public void SetContentDensity(float labelSize, float cornerRadius)
        {
            label.Font = BeatSightFont.Button(labelSize);
            CornerRadius = cornerRadius;
        }

        protected override void Update()
        {
            base.Update();
            label.MaxWidth = Math.Max(20f, DrawWidth - horizontalLabelPadding * 2f);
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
            if (EnableScaleAnimation)
                this.ScaleTo(1.015f, 220, Easing.OutQuint);
            border.FadeTo(0.2f, 180, Easing.OutQuint);
            hoverGlow.FadeTo(0.2f, 200, Easing.OutQuint);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            base.OnHoverLost(e);
            background.FadeColour(Enabled.Value ? idleColour : disabledColour, 200, Easing.OutQuint);
            if (EnableScaleAnimation)
                this.ScaleTo(1f, 200, Easing.OutQuint);
            else
                Scale = Vector2.One;
            border.FadeOut(180, Easing.OutQuint);
            hoverGlow.FadeOut(200);
            HoverHintChanged?.Invoke(null);
        }

        protected override bool OnMouseDown(MouseDownEvent e)
        {
            if (e.Button != MouseButton.Left)
                return base.OnMouseDown(e);

            if (EnableScaleAnimation)
                this.ScaleTo(0.95f, 50, Easing.OutQuint);
            // Consume left-button down so toolbar clicks never leak to timeline hit targets underneath.
            return true;
        }

        protected override void OnMouseUp(MouseUpEvent e)
        {
            if (EnableScaleAnimation)
                this.ScaleTo(IsHovered ? 1.02f : 1f, 250, Easing.OutQuint);
            else
                Scale = Vector2.One;
            base.OnMouseUp(e);
        }

        private void updateEnabledState(bool enabled)
        {
            background.FadeColour(enabled ? idleColour : disabledColour, 200, Easing.OutQuint);
            this.FadeTo(enabled ? 1f : 0.56f, 200, Easing.OutQuint);
            if (!enabled)
            {
                if (EnableScaleAnimation)
                    this.ScaleTo(1f, 200, Easing.OutQuint);
                else
                    Scale = Vector2.One;
            }
            label.FadeColour(enabled ? EditorColours.TextPrimary : EditorColours.Lighten(EditorColours.TextPrimary, 0.84f), 200, Easing.OutQuint);
            topSheen.FadeTo(enabled ? 1f : 0.75f, 160, Easing.OutQuint);
        }
    }
}
