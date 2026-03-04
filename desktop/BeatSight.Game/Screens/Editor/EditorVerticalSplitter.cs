using System;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Input.Events;
using osuTK;
using osuTK.Graphics;
using osuTK.Input;

namespace BeatSight.Game.Screens.Editor
{
    internal partial class EditorVerticalSplitter : CompositeDrawable
    {
        private readonly Box background;
        private readonly Box rail;
        private bool dragging;
        private Vector2 dragLastScreenPosition;
        private const float minimumDragDelta = 0.01f;

        public event Action<float>? DragDeltaY;
        public event Action<bool>? DraggingStateChanged;
        public override bool HandlePositionalInput => true;

        public EditorVerticalSplitter()
        {
            RelativeSizeAxes = Axes.X;
            Height = 7f;
            Alpha = 1f;
            Masking = false;
            CornerRadius = 0;

            InternalChildren = new Drawable[]
            {
                background = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(10, 17, 30, 120)
                },
                rail = new Box
                {
                    RelativeSizeAxes = Axes.X,
                    Width = 1f,
                    Height = 1.8f,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Colour = EditorColours.Lighten(EditorColours.Divider, 1.08f).Opacity(0.86f)
                }
            };
        }

        protected override bool OnHover(HoverEvent e)
        {
            updateVisualState(active: true);
            return true;
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            if (!dragging)
                updateVisualState(active: false);

            base.OnHoverLost(e);
        }

        protected override bool OnMouseDown(MouseDownEvent e)
        {
            if (e.Button != MouseButton.Left)
                return false;

            beginDragging(e.ScreenSpaceMousePosition);
            return true;
        }

        protected override bool OnDragStart(DragStartEvent e)
        {
            if (e.Button != MouseButton.Left)
                return false;

            beginDragging(e.ScreenSpaceMousePosition);
            return true;
        }

        protected override void OnDrag(DragEvent e)
        {
            if (!dragging)
            {
                base.OnDrag(e);
                return;
            }

            dispatchDragDelta(e.ScreenSpaceMousePosition);

            base.OnDrag(e);
        }

        protected override bool OnMouseMove(MouseMoveEvent e)
        {
            if (!dragging)
                return base.OnMouseMove(e);

            dispatchDragDelta(e.ScreenSpaceMousePosition);

            return true;
        }

        protected override void Update()
        {
            base.Update();

            if (!dragging)
                return;

            var input = GetContainingInputManager();
            if (input == null)
                return;

            if (!input.CurrentState.Mouse.IsPressed(MouseButton.Left))
            {
                endDragging();
                return;
            }

            dispatchDragDelta(input.CurrentState.Mouse.Position);
        }

        protected override void OnDragEnd(DragEndEvent e)
        {
            endDragging();
            base.OnDragEnd(e);
        }

        protected override void OnMouseUp(MouseUpEvent e)
        {
            if (e.Button == MouseButton.Left)
                endDragging();

            base.OnMouseUp(e);
        }

        private void beginDragging(Vector2 screenSpacePosition)
        {
            if (dragging)
            {
                dragLastScreenPosition = screenSpacePosition;
                return;
            }

            dragging = true;
            dragLastScreenPosition = screenSpacePosition;
            updateVisualState(active: true);
            DraggingStateChanged?.Invoke(true);
        }

        private void endDragging()
        {
            if (!dragging)
                return;

            dragging = false;
            DraggingStateChanged?.Invoke(false);
            updateVisualState(active: IsHovered);
        }

        private void dispatchDragDelta(Vector2 screenSpacePosition)
        {
            float deltaY = screenSpacePosition.Y - dragLastScreenPosition.Y;
            dragLastScreenPosition = screenSpacePosition;

            if (Math.Abs(deltaY) > minimumDragDelta)
                DragDeltaY?.Invoke(deltaY);
        }

        private void updateVisualState(bool active)
        {
            background.FadeColour(active
                    ? new Color4(16, 28, 50, 146)
                    : new Color4(10, 17, 30, 120),
                120,
                Easing.OutQuint);
            rail.FadeTo(active ? 0.97f : 0.82f, 120, Easing.OutQuint);
            rail.ResizeHeightTo(active || dragging ? 2.2f : 1.8f, 120, Easing.OutQuint);
        }
    }
}
