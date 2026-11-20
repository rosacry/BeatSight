using System;
using BeatSight.Game.UI.Theming;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Utils;
using osuTK;
using osuTK.Input;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// Slider bar with consistent keyboard and drag stepping behaviour across the game, drawn as a slim track with a knob.
    /// </summary>
    public partial class BeatSightSliderBar : BasicSliderBar<double>, ISettingsTooltipSuppressionSource
    {
        private const double defaultKeyboardMultiplier = 1;
        private const double defaultDragMultiplier = 5;

        private bool pointerAdjusting;
        private bool suppressPointerSnap;

        public event Action<bool>? TooltipSuppressionChanged;
        public event Action<bool>? PointerAdjustingChanged;
        public event Action? UserChange;

        public bool IsTooltipSuppressed => pointerAdjusting;
        public bool IsPointerAdjusting => pointerAdjusting;

        // The control's full height stays the click target; a slim rounded track with a knob is drawn in its middle.
        private const float maxKnobSize = 14f;
        private const float minKnobSize = 10f;
        private const float maxTrackHeight = 6f;
        private const float minTrackHeight = 4f;

        private readonly Container trackArea;
        private readonly Container track;
        private readonly Box trackBackground;
        private readonly Box trackFill;
        private readonly CircularContainer knob;

        public BeatSightSliderBar()
        {
            // The framework's full-height boxes only hold the colours now.
            Box.Alpha = 0;
            SelectionBox.Alpha = 0;

            AddRange(new Drawable[]
            {
                trackArea = new Container
                {
                    RelativeSizeAxes = Axes.Both,
                    Children = new Drawable[]
                    {
                        track = new Container
                        {
                            RelativeSizeAxes = Axes.X,
                            Anchor = Anchor.CentreLeft,
                            Origin = Anchor.CentreLeft,
                            Masking = true,
                            Children = new Drawable[]
                            {
                                trackBackground = new Box { RelativeSizeAxes = Axes.Both },
                                trackFill = new Box { RelativeSizeAxes = Axes.Both, Width = 0 }
                            }
                        },
                        knob = new CircularContainer
                        {
                            Anchor = Anchor.CentreLeft,
                            Origin = Anchor.Centre,
                            RelativePositionAxes = Axes.X,
                            Masking = true,
                            BorderColour = UITheme.AccentPrimary,
                            Child = new Box
                            {
                                RelativeSizeAxes = Axes.Both,
                                Colour = UITheme.TextPrimary
                            }
                        }
                    }
                }
            });
        }

        /// <summary>
        /// Horizontal space kept free at each end so the knob stays inside the control at 0 and 1. Content drawn in
        /// line with the track (such as the practice heatmap) should be inset by the same amount.
        /// </summary>
        public float TrackInset => knobSizeFor(DrawHeight > 0 ? DrawHeight : Height) / 2f;

        private static float knobSizeFor(float height) => Math.Clamp(height, minKnobSize, maxKnobSize);

        [osu.Framework.Allocation.BackgroundDependencyLoader]
        private void load()
        {
            BackgroundColour = UITheme.Border;
            SelectionColour = UITheme.AccentPrimary;
        }

        protected override void Update()
        {
            base.Update();

            float knobSize = knobSizeFor(DrawHeight);
            float trackHeight = Math.Clamp(DrawHeight * 0.4f, minTrackHeight, maxTrackHeight);
            float inset = knobSize / 2f;

            // Pointer mapping (base class and adjustValueFromPointer) uses the same inset as the drawing.
            if (RangePadding != inset)
                RangePadding = inset;

            trackArea.Padding = new MarginPadding { Horizontal = inset };
            track.Height = trackHeight;
            track.CornerRadius = trackHeight / 2f;
            knob.Size = new Vector2(knobSize);

            trackBackground.Colour = BackgroundColour;
            trackFill.Colour = SelectionColour;
        }

        protected override void UpdateValue(float value)
        {
            // Follow the pointer directly while dragging; ease programmatic jumps.
            double duration = pointerAdjusting ? 0 : UITheme.MotionFast;
            trackFill.ResizeWidthTo(value, duration, Easing.OutQuint);
            knob.MoveToX(value, duration, Easing.OutQuint);
        }

        protected override bool OnHover(HoverEvent e)
        {
            knob.ScaleTo(1.15f, UITheme.MotionFast, Easing.OutQuint);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            knob.ScaleTo(1f, UITheme.MotionFast, Easing.OutQuint);
            base.OnHoverLost(e);
        }

        protected override void OnFocus(FocusEvent e)
        {
            base.OnFocus(e);
            knob.BorderThickness = 3;
        }

        protected override void OnFocusLost(FocusLostEvent e)
        {
            base.OnFocusLost(e);
            knob.BorderThickness = 0;
            setPointerAdjusting(false);
        }

        public double KeyboardStepMultiplier { get; set; } = defaultKeyboardMultiplier;
        public double DragStepMultiplier { get; set; } = defaultDragMultiplier;

        protected override void LoadComplete()
        {
            base.LoadComplete();
            Current?.BindValueChanged(onCurrentValueChanged, true);
            Current?.BindDisabledChanged(disabled => this.FadeTo(disabled ? 0.45f : 1f, UITheme.MotionFast, Easing.OutQuint), true);
        }

        protected override bool OnMouseDown(MouseDownEvent e)
        {
            if (e.Button != MouseButton.Left)
                return base.OnMouseDown(e);

            if (Current?.Disabled == true)
                return base.OnMouseDown(e);

            setPointerAdjusting(true);
            adjustValueFromPointer(e);
            bool handled = base.OnMouseDown(e);

            if (handled)
                snapCurrentValueIfNeeded();
            requestFocus();
            return true;
        }

        protected override void OnMouseUp(MouseUpEvent e)
        {
            base.OnMouseUp(e);
            setPointerAdjusting(false);
            snapCurrentValueIfNeeded();
        }

        protected override bool OnDragStart(DragStartEvent e)
        {
            setPointerAdjusting(true);
            base.OnDragStart(e);

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
            adjustValueFromPointer(e);
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

        private void applyKeyboardDelta(double delta)
        {
            double min = CurrentNumber?.MinValue ?? double.MinValue;
            double max = CurrentNumber?.MaxValue ?? double.MaxValue;
            double target = Math.Clamp(Current.Value + delta, min, max);
            Current.Value = target;
            UserChange?.Invoke();
        }

        private void adjustValueFromPointer(MouseEvent e)
        {
            if (CurrentNumber == null || DrawWidth <= 0)
                return;

            double min = CurrentNumber.MinValue;
            double max = CurrentNumber.MaxValue;
            if (Precision.AlmostEquals(max, min))
                return;

            float localX = e.MousePosition.X;
            if (!float.IsFinite(localX) || localX < -DrawWidth * 2f || localX > DrawWidth * 3f)
                localX = ToLocalSpace(e.ScreenSpaceMousePosition).X;

            float usableWidth = Math.Max(1f, DrawWidth - RangePadding * 2f);
            double progress = Math.Clamp((localX - RangePadding) / usableWidth, 0, 1);
            double target = min + progress * (max - min);
            double snapped = snapToDragStep(target);
            if (Precision.AlmostEquals(snapped, Current.Value))
                return;

            suppressPointerSnap = true;
            Current.Value = snapped;
            suppressPointerSnap = false;
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
            PointerAdjustingChanged?.Invoke(value);
        }
    }
}
