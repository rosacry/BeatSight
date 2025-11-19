using System;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Utils;
using osuTK;
using osuTK.Input;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// Slider bar with consistent keyboard and drag stepping behaviour across the game.
    /// </summary>
    public partial class BeatSightSliderBar : BasicSliderBar<double>, ISettingsTooltipSuppressionSource
    {
        private const double defaultKeyboardMultiplier = 1;
        private const double defaultDragMultiplier = 5;

        private bool pointerAdjusting;
        private bool suppressPointerSnap;

        public event Action<bool>? TooltipSuppressionChanged;
        public event Action? UserChange;

        public bool IsTooltipSuppressed => pointerAdjusting;

        public BeatSightSliderBar()
        {
            Masking = true;
            CornerRadius = 6;
        }

        public double KeyboardStepMultiplier { get; set; } = defaultKeyboardMultiplier;
        public double DragStepMultiplier { get; set; } = defaultDragMultiplier;

        protected override void LoadComplete()
        {
            base.LoadComplete();
            Current?.BindValueChanged(onCurrentValueChanged, true);
        }

        protected override bool OnMouseDown(MouseDownEvent e)
        {
            if (e.Button != MouseButton.Left)
                return base.OnMouseDown(e);

            if (Current?.Disabled == true)
                return base.OnMouseDown(e);

            setPointerAdjusting(true);
            base.OnMouseDown(e);

            adjustValueFromPointer(e.ScreenSpaceMousePosition);
            requestFocus();
            return true;
        }

        protected override void OnMouseUp(MouseUpEvent e)
        {
            base.OnMouseUp(e);
            setPointerAdjusting(false);
            snapCurrentValueIfNeeded();
        }

        protected override bool OnMouseMove(MouseMoveEvent e)
        {
            bool handled = base.OnMouseMove(e);

            if (pointerAdjusting)
            {
                adjustValueFromPointer(e.ScreenSpaceMousePosition);
                return true;
            }

            return handled;
        }

        protected override bool OnDragStart(DragStartEvent e)
        {
            setPointerAdjusting(true);
            var handled = base.OnDragStart(e);
            if (!handled)
            {
                setPointerAdjusting(false);
                return false;
            }

            requestFocus();
            return true;
        }

        protected override bool OnClick(ClickEvent e)
        {
            if (e.Button != MouseButton.Left)
                return base.OnClick(e);

            if (Current?.Disabled == true)
                return base.OnClick(e);

            // Prevent base slider from reapplying an unsnapped value after a click.
            requestFocus();
            snapCurrentValueIfNeeded();
            return true;
        }

        protected override void OnDragEnd(DragEndEvent e)
        {
            base.OnDragEnd(e);
            setPointerAdjusting(false);
            snapCurrentValueIfNeeded();
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key is Key.Left or Key.Right)
            {
                var step = getKeyboardStep();
                if (step > 0)
                {
                    var direction = e.Key == Key.Right ? 1 : -1;
                    applyKeyboardDelta(step * direction);
                    return true;
                }
            }

            return base.OnKeyDown(e);
        }

        private void onCurrentValueChanged(ValueChangedEvent<double> e)
        {
            if (!pointerAdjusting || suppressPointerSnap)
                return;

            double snapped = snapToDragStep(e.NewValue);
            if (Precision.AlmostEquals(snapped, e.NewValue))
                return;

            suppressPointerSnap = true;
            Current.Value = snapped;
            suppressPointerSnap = false;
            UserChange?.Invoke();
        }

        private void adjustValueFromPointer(Vector2 screenSpacePosition)
        {
            if (CurrentNumber == null || DrawWidth <= 0)
                return;

            double min = CurrentNumber.MinValue;
            double max = CurrentNumber.MaxValue;
            if (Precision.AlmostEquals(max, min))
                return;

            Vector2 local = ToLocalSpace(screenSpacePosition);
            double progress = Math.Clamp(local.X / DrawWidth, 0, 1);
            double target = min + progress * (max - min);

            double snapped = snapToDragStep(target);
            if (Precision.AlmostEquals(snapped, Current.Value))
                return;

            suppressPointerSnap = true;
            Current.Value = snapped;
            suppressPointerSnap = false;
            UserChange?.Invoke();
        }

        private void applyKeyboardDelta(double delta)
        {
            double min = CurrentNumber?.MinValue ?? double.MinValue;
            double max = CurrentNumber?.MaxValue ?? double.MaxValue;
            double target = Math.Clamp(Current.Value + delta, min, max);
            Current.Value = target;
            UserChange?.Invoke();
        }

        private double snapToDragStep(double value)
        {
            double min = CurrentNumber?.MinValue ?? double.MinValue;
            double max = CurrentNumber?.MaxValue ?? double.MaxValue;
            double step = getDragStep();
            if (step <= 0)
                return Math.Clamp(value, min, max);

            double snapped = Math.Round((value - min) / step) * step + min;
            return Math.Clamp(snapped, min, max);
        }

        private void snapCurrentValueIfNeeded()
        {
            if (Current == null)
                return;

            double snapped = snapToDragStep(Current.Value);
            if (Precision.AlmostEquals(snapped, Current.Value))
                return;

            suppressPointerSnap = true;
            Current.Value = snapped;
            suppressPointerSnap = false;
        }

        private double getKeyboardStep()
        {
            double precision = getPrecision();
            double step = precision * KeyboardStepMultiplier;
            return step > 0 ? step : precision;
        }

        private double getDragStep()
        {
            double precision = getPrecision();
            double step = precision * DragStepMultiplier;
            return step > 0 ? step : precision;
        }

        private double getPrecision()
        {
            double precision = CurrentNumber?.Precision ?? 0;
            return precision > 0 ? precision : 0.01;
        }


        private void requestFocus()
        {
            GetContainingFocusManager()?.ChangeFocus(this);
        }

        private void setPointerAdjusting(bool value)
        {
            if (pointerAdjusting == value)
                return;

            pointerAdjusting = value;
            TooltipSuppressionChanged?.Invoke(value);
        }
    }
}
