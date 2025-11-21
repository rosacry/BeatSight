using System;
using System.Collections.Generic;
using System.Linq;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Threading;
using osu.Framework.Logging;
using osu.Framework.Utils;
using osuTK;
using osuTK.Graphics;
using osuTK.Input;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Primitives;
using osu.Framework.Graphics.Effects;
using BeatSight.Game.UI.Theming;

namespace BeatSight.Game.UI.Components
{
    public partial class Dropdown<T> : BasicDropdown<T>, ISettingsTooltipSuppressionSource
    {
        public float? MenuMaxHeight { get; set; }
        public Container? OverlayLayer { get; set; }
        public Drawable? ScrollViewport { get; set; }

        private bool searchEnabled;
        private DropdownHeader? dropdownHeader;
        private bool tooltipSuppressed;

        public event Action<bool>? TooltipSuppressionChanged;

        public bool IsTooltipSuppressed => tooltipSuppressed;

        public bool SearchEnabled
        {
            get => searchEnabled;
            set
            {
                if (searchEnabled == value)
                    return;

                searchEnabled = value;
                updateSearchState();
            }
        }

        public Dropdown()
        {
            AutoSizeAxes = Axes.Y;
            RelativeSizeAxes = Axes.None;
        }

        internal void SetTooltipSuppression(bool suppressed)
        {
            if (tooltipSuppressed == suppressed)
                return;

            tooltipSuppressed = suppressed;
            TooltipSuppressionChanged?.Invoke(suppressed);
        }

        protected override DropdownMenu CreateMenu() => new DropdownMenu(this);

        protected override DropdownHeader CreateHeader()
        {
            dropdownHeader = new DropdownHeader();
            return dropdownHeader;
        }

        internal Colour4 GetHeaderBackgroundColour()
        {
            if (dropdownHeader == null)
                return Colour4.Black;

            return (Colour4)dropdownHeader.Colour.AverageColour * dropdownHeader.GetCurrentBackgroundColour();
        }

        protected override void LoadComplete()
        {
            base.LoadComplete();

            if (Menu != null)
            {
                if (MenuMaxHeight.HasValue)
                    Menu.MaxHeight = MenuMaxHeight.Value;
            }

            updateSearchState();
        }

        private void updateSearchState()
        {
            if (Menu != null)
            {
                Menu.AllowNonContiguousMatching = searchEnabled;

                if (!searchEnabled)
                    Menu.SearchTerm = string.Empty;
            }

            dropdownHeader?.SetSearchEnabled(searchEnabled);
        }

        protected sealed partial class DropdownHeader : BasicDropdownHeader
        {
            private DropdownSearchBar? searchBar;
            private const float header_corner_radius = 8f;

            public DropdownHeader()
            {
                Masking = true;
                CornerRadius = header_corner_radius;
                MaskingSmoothness = 1.5f;
                applyBackgroundMasking();
                Foreground.Padding = new MarginPadding { Horizontal = 10, Top = 10, Bottom = 2 };
            }
            protected override void LoadComplete()
            {
                base.LoadComplete();
                foreach (var child in Foreground.Children)
                {
                    if (child is osu.Framework.Graphics.Sprites.SpriteText text)
                    {
                        text.Font = BeatSightFont.Button();
                        text.Anchor = Anchor.CentreLeft;
                        text.Origin = Anchor.CentreLeft;
                        text.UseFullGlyphHeight = false;
                        text.Truncate = true;
                    }
                }
            }

            protected override void Update()
            {
                base.Update();
                enforceRoundedMask();
            }

            private void enforceRoundedMask()
            {
                // Keep header edges rounded even when the base class toggles state-specific masks.
                if (!Masking)
                    Masking = true;

                if (!Precision.AlmostEquals(CornerRadius, header_corner_radius))
                    CornerRadius = header_corner_radius;

                applyBackgroundMasking();
            }

            private void applyBackgroundMasking()
            {
                Background.Masking = true;
                Background.CornerRadius = header_corner_radius;
                Background.MaskingSmoothness = 1.5f;
            }

            protected override DropdownSearchBar CreateSearchBar()
            {
                searchBar = new DropdownSearchBar();
                searchBar.SearchActive += active =>
                {
                    foreach (var child in Foreground.Children)
                    {
                        if (child != searchBar)
                            child.Alpha = active ? 0 : 1;
                    }
                };
                return searchBar;
            }

            public void SetSearchEnabled(bool enabled)
                => searchBar?.SetSearchEnabled(enabled);

            public Colour4 GetCurrentBackgroundColour() => Background.Colour;

            public Quad BackgroundScreenSpaceDrawQuad => Background.ScreenSpaceDrawQuad;
        }

        protected sealed partial class DropdownSearchBar : BasicDropdownHeader.BasicDropdownSearchBar
        {
            private DropdownSearchTextBox? textBox;
            private bool searchAllowed;
            private const float search_corner_radius = 8f;
            private readonly Box background;

            public Action<bool>? SearchActive;

            public DropdownSearchBar()
            {
                Masking = true;
                CornerRadius = search_corner_radius;
                MaskingSmoothness = 1.5f;

                AddInternal(background = new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = UITheme.Surface,
                    Depth = 1
                });
            }

            protected override void Update()
            {
                base.Update();
                enforceRoundedMask();
            }

            private void enforceRoundedMask()
            {
                if (!Masking)
                    Masking = true;

                if (!Precision.AlmostEquals(CornerRadius, search_corner_radius))
                    CornerRadius = search_corner_radius;
            }

            protected override TextBox CreateTextBox()
            {
                textBox = new DropdownSearchTextBox();
                textBox.OnFocusAction = () => SearchActive?.Invoke(true);
                textBox.OnFocusLostAction = () => SearchActive?.Invoke(false);
                return textBox;
            }

            public void SetSearchEnabled(bool enabled)
            {
                searchAllowed = enabled;
                AlwaysDisplayOnFocus = enabled;
                Alpha = enabled ? 1 : 0;
                Width = enabled ? 1 : 0;
                AlwaysPresent = enabled;
                if (enabled)
                    Show();
                else
                    Hide();

                if (textBox == null)
                    return;

                textBox.SetTypingEnabled(enabled);

                if (!enabled)
                    SearchTerm.Value = string.Empty;
            }

            public override bool HandlePositionalInput => searchAllowed && base.HandlePositionalInput;
            public override bool HandleNonPositionalInput => searchAllowed && base.HandleNonPositionalInput;
            public override bool PropagateNonPositionalInputSubTree => searchAllowed && base.PropagateNonPositionalInputSubTree;
            public override bool PropagatePositionalInputSubTree => searchAllowed && base.PropagatePositionalInputSubTree;

            private sealed partial class DropdownSearchTextBox : BasicTextBox
            {
                private bool typingEnabled = true;

                public Action? OnFocusAction;
                public Action? OnFocusLostAction;

                public DropdownSearchTextBox()
                {
                    BackgroundUnfocused = Color4.Transparent;
                    BackgroundFocused = Color4.Transparent;
                }

                public void SetTypingEnabled(bool enabled)
                {
                    typingEnabled = enabled;
                    ReadOnly = !enabled;

                    if (!enabled && HasFocus)
                        KillFocus();
                }

                public override bool AcceptsFocus => typingEnabled && base.AcceptsFocus;
                public override bool HandleNonPositionalInput => typingEnabled && base.HandleNonPositionalInput;

                protected override void OnFocus(FocusEvent e)
                {
                    base.OnFocus(e);
                    OnFocusAction?.Invoke();
                    if (typingEnabled)
                        Schedule(() => Text = string.Empty);
                }

                protected override void OnFocusLost(FocusLostEvent e)
                {
                    base.OnFocusLost(e);
                    OnFocusLostAction?.Invoke();
                }
            }
        }

        protected new sealed partial class DropdownMenu : BasicDropdown<T>.BasicDropdownMenu
        {
            private readonly Dropdown<T> owner;
            private int pendingScrollFrames;
            private bool isOpen;
            private bool scrollCompleted;
            private Drawable? originalParent;
            private Container? overlayParent;
            private Container? overlayRoot;
            private Container? viewportMaskContainer;
            private IContainerCollection<Drawable>? originalParentCollection;
            private Vector2 originalPosition;
            private Axes originalRelativePositionAxes;
            private Axes originalRelativeSizeAxes;
            private Vector2 originalSize;
            private Anchor originalAnchor;
            private Anchor originalOrigin;
            private bool usingOverlay;
            private float originalDepth;
            private bool suppressNextClose;
            private float? forcedOverlayWidth;
            private const float menu_corner_radius = 8f;
            private bool pointerButtonHeld;

            public DropdownMenu(Dropdown<T> owner)
            {
                this.owner = owner;
                BypassAutoSizeAxes = Axes.Both;

                // Match the header's masking settings to ensure visual width alignment
                Masking = true;
                CornerRadius = 0;
                MaskingSmoothness = 1.5f;
                BorderThickness = 0;

                StateChanged += onStateChanged;
                MaskingContainer.CornerRadius = menu_corner_radius;
                MaskingContainer.Masking = true;
                MaskingContainer.MaskingSmoothness = 1.5f;
                MaskingContainer.EdgeEffect = new EdgeEffectParameters { Type = EdgeEffectType.None };
            }

            protected override void Update()
            {
                // Lock scroll position to prevent hover-based scrolling
                if (scrollCompleted && isOpen)
                {
                    var scrollBefore = ContentContainer.Current;
                    base.Update();

                    // Restore locked scroll position if it changed
                    if (!Precision.AlmostEquals(ContentContainer.Current, scrollBefore))
                        ContentContainer.ScrollTo((float)scrollBefore, false);
                }
                else
                {
                    base.Update();
                }

                enforceRoundedMask();
            }

            private void enforceRoundedMask()
            {
                // Maintain rounded list edges regardless of overlay parenting or framework state changes.
                if (!Masking)
                    Masking = true;
                if (CornerRadius != 0)
                    CornerRadius = 0;
                MaskingSmoothness = 1.5f;

                if (!Precision.AlmostEquals(MaskingContainer.CornerRadius, menu_corner_radius))
                    MaskingContainer.CornerRadius = menu_corner_radius;
                if (!MaskingContainer.Masking)
                    MaskingContainer.Masking = true;
                MaskingContainer.MaskingSmoothness = 1.5f;
            }

            private void onStateChanged(MenuState state)
            {
                Logger.Log($"DropdownMenu state -> {state}", LoggingTarget.Runtime, LogLevel.Verbose);

                if (state != MenuState.Open)
                {
                    if (usingOverlay && suppressNextClose)
                    {
                        Logger.Log("DropdownMenu ignoring close triggered during overlay transfer", LoggingTarget.Runtime, LogLevel.Verbose);
                        suppressNextClose = false;
                        Scheduler.AddOnce(Open);
                        return;
                    }

                    if (usingOverlay)
                        Logger.Log("DropdownMenu closed while using overlay", LoggingTarget.Runtime, LogLevel.Verbose);
                    isOpen = false;
                    pendingScrollFrames = 0;
                    scrollCompleted = false;
                    pointerButtonHeld = false;
                    restoreParent();
                    owner.SetTooltipSuppression(false);
                    return;
                }

                isOpen = true;
                pendingScrollFrames = 5;
                scrollCompleted = false;
                Scheduler.AddOnce(() =>
                {
                    suppressNextClose = true;
                    moveToOverlay();
                });
                owner.SetTooltipSuppression(true);
            }

            private void moveToOverlay()
            {
                var overlay = owner.OverlayLayer;
                if (overlay == null)
                    return;

                Logger.Log($"DropdownMenu moving to overlay (Parent={Parent?.GetType().Name}, usingOverlay={usingOverlay})", LoggingTarget.Runtime, LogLevel.Verbose);

                if (usingOverlay && Parent == overlayParent)
                    return;

                var parent = Parent;
                if (parent == null)
                    return;

                if (parent is not IContainerCollection<Drawable> parentCollection)
                    return;

                originalParent = parent;
                originalParentCollection = parentCollection;
                originalPosition = Position;
                originalRelativePositionAxes = RelativePositionAxes;
                originalRelativeSizeAxes = RelativeSizeAxes;
                originalSize = Size;
                originalAnchor = Anchor;
                originalOrigin = Origin;
                originalDepth = Depth;

                // Ensure any in-flight open animations reach their final state before re-parenting.
                FinishTransforms(propagateChildren: true);

                var targetOverlayParent = getOverlayParent(overlay);

                parentCollection.Remove(this, false);
                targetOverlayParent.Add(this);

                if (targetOverlayParent == overlay)
                    overlay.ChangeChildDepth(this, -9);
                else
                    overlay.ChangeChildDepth(targetOverlayParent, -9);
                RelativePositionAxes = Axes.None;
                RelativeSizeAxes = Axes.None;
                Anchor = Anchor.TopLeft;
                Origin = Anchor.TopLeft;
                AlwaysPresent = false;
                Alpha = 1;
                Scale = Vector2.One;
                overlayRoot = overlay;
                overlayParent = targetOverlayParent;

                applyMenuPlacement(targetOverlayParent);

                usingOverlay = true;
                updateOverlayBounds();
                GetContainingFocusManager()?.ChangeFocus(this);
                Logger.Log("DropdownMenu overlay placement complete", LoggingTarget.Runtime, LogLevel.Verbose);
                suppressNextClose = false;
            }

            private void restoreParent()
            {
                if (!usingOverlay || originalParent == null)
                    return;

                Logger.Log($"DropdownMenu restoring parent (ParentBefore={Parent?.GetType().Name})", LoggingTarget.Runtime, LogLevel.Verbose);

                originalParent = null;
                var parentCollection = originalParentCollection;
                originalParentCollection = null;
                usingOverlay = false;

                if (parentCollection == null)
                    return;

                AlwaysPresent = true;

                overlayParent?.Remove(this, false);
                overlayParent = null;

                if (viewportMaskContainer != null)
                {
                    if (overlayRoot is IContainerCollection<Drawable> overlayCollection)
                        overlayCollection.Remove(viewportMaskContainer, false);
                    else
                        viewportMaskContainer.Clear(false);

                    viewportMaskContainer = null;
                }

                overlayRoot = null;

                Depth = originalDepth;

                parentCollection.Add(this);
                Logger.Log("DropdownMenu parent restored", LoggingTarget.Runtime, LogLevel.Verbose);
                forcedOverlayWidth = null;
                RelativePositionAxes = originalRelativePositionAxes;
                RelativeSizeAxes = originalRelativeSizeAxes;
                Anchor = originalAnchor;
                Origin = originalOrigin;
                Size = originalSize;
                Position = originalPosition;
            }

            protected override void Dispose(bool isDisposing)
            {
                if (isDisposing)
                    restoreParent();

                base.Dispose(isDisposing);
            }

            protected override void UpdateAfterChildren()
            {
                base.UpdateAfterChildren();

                if (isOpen)
                {
                    ensureOverlayAttachment();
                    updateOverlayBounds();
                }

                if (!isOpen || scrollCompleted)
                    return;

                if (pendingScrollFrames > 0)
                {
                    pendingScrollFrames--;
                    if (tryScrollSelectedIntoView(false))
                        scrollCompleted = true;
                    return;
                }

                if (tryScrollSelectedIntoView(true))
                    scrollCompleted = true;
            }

            private bool tryScrollSelectedIntoView(bool allowFallback)
            {
                var visibleItems = VisibleMenuItems.ToList();

                if (visibleItems.Count == 0)
                    return false;

                DropdownMenu.DrawableDropdownMenuItem? target = null;
                var currentValue = owner.Current.Value;

                foreach (var item in visibleItems)
                {
                    if (item.Item is DropdownMenuItem<T> dropdownItem && EqualityComparer<T>.Default.Equals(dropdownItem.Value, currentValue))
                    {
                        target = item;
                        break;
                    }
                }

                if (target == null && allowFallback)
                    target = visibleItems.FirstOrDefault(i => i.IsSelected) ?? PreselectedItem;

                if (target == null)
                    return false;

                ContentContainer.ScrollIntoView(target);
                return true;
            }

            protected override void OnFocusLost(FocusLostEvent e) => base.OnFocusLost(e);

            protected override DrawableDropdownMenuItem CreateDrawableDropdownMenuItem(MenuItem item)
                => new HoverStableDropdownMenuItem(this, item);

            protected override bool OnHover(HoverEvent e)
            {
                // Capture scroll position before hover handling
                var scrollBefore = ContentContainer.Current;
                cancelPendingAutoScrollFromPointer();
                var handled = base.OnHover(e);

                // Restore scroll position if it changed due to hover
                if (!Precision.AlmostEquals(ContentContainer.Current, scrollBefore))
                    ContentContainer.ScrollTo((float)scrollBefore, false);

                return handled;
            }

            protected override bool OnMouseMove(MouseMoveEvent e)
            {
                var scrollBefore = ContentContainer.Current;
                cancelPendingAutoScrollFromPointer();
                var handled = base.OnMouseMove(e);

                // Always restore scroll position after mouse movement to prevent hover-induced scrolling
                if (!Precision.AlmostEquals(ContentContainer.Current, scrollBefore))
                    ContentContainer.ScrollTo((float)scrollBefore, false);

                return handled;
            }

            protected override bool OnScroll(ScrollEvent e)
            {
                cancelPendingAutoScrollFromPointer();
                return base.OnScroll(e);
            }

            protected override bool OnMouseDown(MouseDownEvent e)
            {
                if (isManualScrollButton(e.Button))
                    pointerButtonHeld = true;

                cancelPendingAutoScrollFromPointer();
                return base.OnMouseDown(e);
            }

            protected override void OnMouseUp(MouseUpEvent e)
            {
                if (isManualScrollButton(e.Button))
                    pointerButtonHeld = false;

                base.OnMouseUp(e);
            }

            private bool shouldBlockHoverEdgeScroll(double priorScrollPosition)
            {
                if (!isOpen || pointerButtonHeld)
                    return false;

                return !Precision.AlmostEquals(ContentContainer.Current, priorScrollPosition);
            }

            private static bool isManualScrollButton(MouseButton button)
                => button is MouseButton.Left or MouseButton.Middle or MouseButton.Right;

            private void cancelPendingAutoScrollFromPointer()
            {
                if (!isOpen || scrollCompleted)
                    return;

                pendingScrollFrames = 0;
                scrollCompleted = true;
            }

            private void ensureOverlayAttachment()
            {
                var overlay = owner.OverlayLayer;

                if (overlay == null)
                    return;

                if (usingOverlay && Parent == overlayParent)
                    return;

                Logger.Log("DropdownMenu overlay attachment missing; retrying", LoggingTarget.Runtime, LogLevel.Verbose);

                usingOverlay = false;
                moveToOverlay();
            }

            private void updateOverlayBounds()
            {
                if (!usingOverlay)
                    return;

                var parentContainer = overlayParent ?? owner.OverlayLayer;
                if (parentContainer == null)
                    return;

                enforceViewportMaskRounding();

                if (viewportMaskContainer != null && overlayRoot != null)
                    updateViewportMaskBounds(overlayRoot);

                applyMenuPlacement(parentContainer);
            }

            private float computeOverlayMenuHeight(float availableHeight, float overlayHeight)
            {
                var contentHeight = getActualContentHeight();
                var maxHeight = owner.MenuMaxHeight ?? contentHeight;
                var desiredHeight = Math.Min(contentHeight, maxHeight);
                var height = Math.Min(availableHeight, desiredHeight);

                return Math.Clamp(height, 0, overlayHeight);
            }

            private float getActualContentHeight()
            {
                float totalHeight = ContentContainer.Padding.Top + ContentContainer.Padding.Bottom;

                foreach (var child in ContentContainer.Children)
                    totalHeight += child.BoundingBox.Height;

                // When the menu has fewer items than the maximum displayable count we want to
                // collapse the container to match the visible content rather than keeping the
                // previous (larger) scrollable height, which manifests as the black block seen in
                // the attached screenshot. Fall back to the bounding box only when no content has
                // been computed yet so the caller still gets a sensible non-zero value.
                if (Precision.AlmostEquals(totalHeight, 0))
                    totalHeight = ContentContainer.BoundingBox.Height;

                return totalHeight;
            }

            private void applyMenuPlacement(Container parentContainer)
            {
                var header = owner.dropdownHeader;
                if (header == null)
                    return;

                var headerQuad = header.BackgroundScreenSpaceDrawQuad;
                var headerTopLeft = parentContainer.ToLocalSpace(headerQuad.TopLeft);
                var headerTopRight = parentContainer.ToLocalSpace(headerQuad.TopRight);
                var headerBottomLeft = parentContainer.ToLocalSpace(headerQuad.BottomLeft);
                var headerWidth = headerTopRight.X - headerTopLeft.X;

                var menuTop = headerBottomLeft.Y;
                var availableHeight = Math.Max(0, parentContainer.DrawSize.Y - menuTop);
                var menuHeight = computeOverlayMenuHeight(availableHeight, parentContainer.DrawSize.Y);

                forcedOverlayWidth = headerWidth;
                Size = new Vector2(forcedOverlayWidth.Value, menuHeight);
                Position = new Vector2(headerTopLeft.X, menuTop);
            }
            private Container getOverlayParent(Container overlay)
            {
                if (owner.ScrollViewport == null)
                {
                    if (viewportMaskContainer != null)
                    {
                        if (overlay is IContainerCollection<Drawable> overlayCollection)
                            overlayCollection.Remove(viewportMaskContainer, false);
                        else
                            viewportMaskContainer.Clear(false);

                        viewportMaskContainer = null;
                    }

                    return overlay;
                }

                viewportMaskContainer ??= new Container
                {
                    Masking = true,
                    CornerRadius = menu_corner_radius,
                    MaskingSmoothness = 1.5f,
                    RelativeSizeAxes = Axes.None,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft
                };
                enforceViewportMaskRounding();

                if (viewportMaskContainer.Parent != overlay)
                    overlay.Add(viewportMaskContainer);

                updateViewportMaskBounds(overlay);

                return viewportMaskContainer;
            }

            private void updateViewportMaskBounds(Container overlay)
            {
                if (viewportMaskContainer == null)
                    return;

                var viewport = owner.ScrollViewport;
                if (viewport == null)
                {
                    viewportMaskContainer.Position = Vector2.Zero;
                    viewportMaskContainer.Size = overlay.DrawSize;
                    return;
                }

                var viewportQuad = viewport.ScreenSpaceDrawQuad;
                var viewportTopLeft = overlay.ToLocalSpace(viewportQuad.TopLeft);
                var clipTop = viewportTopLeft.Y;
                var overlaySize = overlay.DrawSize;

                var height = Math.Max(0, overlaySize.Y - clipTop);
                viewportMaskContainer.Position = new Vector2(0, clipTop);
                viewportMaskContainer.Size = new Vector2(overlaySize.X, height);
            }

            private void enforceViewportMaskRounding()
            {
                if (viewportMaskContainer == null)
                    return;

                if (!viewportMaskContainer.Masking)
                    viewportMaskContainer.Masking = true;

                if (!Precision.AlmostEquals(viewportMaskContainer.CornerRadius, menu_corner_radius))
                    viewportMaskContainer.CornerRadius = menu_corner_radius;

                viewportMaskContainer.MaskingSmoothness = 1.5f;
            }

            private sealed partial class HoverStableDropdownMenuItem : DropdownMenu.DrawableDropdownMenuItem
            {
                private readonly DropdownMenu menu;

                public HoverStableDropdownMenuItem(DropdownMenu menu, MenuItem item)
                    : base(item)
                {
                    this.menu = menu;
                    AutoSizeAxes = Axes.Y;
                    RelativeSizeAxes = Axes.X;
                    Width = 1;

                    Foreground.AutoSizeAxes = Axes.Y;
                    Foreground.RelativeSizeAxes = Axes.X;

                    Background.RelativeSizeAxes = Axes.Both;
                    Foreground.Padding = new MarginPadding { Horizontal = 10, Vertical = 5 };
                    BackgroundColour = FrameworkColour.BlueGreen;
                    BackgroundColourHover = FrameworkColour.Green;
                    BackgroundColourSelected = FrameworkColour.GreenDark;
                }

                protected override Drawable CreateContent() => new SpriteText
                {
                    Font = BeatSightFont.Button()
                };

                protected override bool OnHover(HoverEvent e)
                {
                    // Capture scroll position before hover handling to prevent automatic scrolling
                    var scrollBefore = menu.ContentContainer.Current;
                    menu.cancelPendingAutoScrollFromPointer();
                    var handled = base.OnHover(e);

                    // Restore scroll position if it changed due to hover
                    if (!Precision.AlmostEquals(menu.ContentContainer.Current, scrollBefore))
                        menu.ContentContainer.ScrollTo((float)scrollBefore, false);

                    Scheduler.AddOnce(UpdateBackgroundColour);
                    Scheduler.AddOnce(UpdateForegroundColour);

                    return handled;
                }

                protected override void OnHoverLost(HoverLostEvent e)
                {
                    menu.cancelPendingAutoScrollFromPointer();
                    base.OnHoverLost(e);
                    Scheduler.AddOnce(UpdateBackgroundColour);
                    Scheduler.AddOnce(UpdateForegroundColour);
                }
            }

            protected override void UpdateSize(Vector2 newSize)
            {
                if (forcedOverlayWidth.HasValue)
                    newSize.X = forcedOverlayWidth.Value;

                base.UpdateSize(newSize);
            }


        }
    }
}
