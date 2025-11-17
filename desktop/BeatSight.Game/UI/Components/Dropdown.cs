using System;
using System.Collections.Generic;
using System.Linq;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Sprites;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Threading;
using osu.Framework.Logging;
using osuTK;

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
            }

            protected override DropdownSearchBar CreateSearchBar()
                => searchBar = new DropdownSearchBar();

            public void SetSearchEnabled(bool enabled)
                => searchBar?.SetSearchEnabled(enabled);
        }

        protected sealed partial class DropdownSearchBar : BasicDropdownHeader.BasicDropdownSearchBar
        {
            private DropdownSearchTextBox? textBox;
            private bool searchAllowed;

            protected override TextBox CreateTextBox()
                => textBox = new DropdownSearchTextBox();

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

                public void SetTypingEnabled(bool enabled)
                {
                    typingEnabled = enabled;
                    ReadOnly = !enabled;

                    if (!enabled && HasFocus)
                        KillFocus();
                }

                public override bool AcceptsFocus => typingEnabled && base.AcceptsFocus;
                public override bool HandleNonPositionalInput => typingEnabled && base.HandleNonPositionalInput;
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
            private const float menu_corner_radius = 10f;

            public DropdownMenu(Dropdown<T> owner)
            {
                this.owner = owner;
                BypassAutoSizeAxes = Axes.Both;
                Masking = true;
                CornerRadius = menu_corner_radius;
                StateChanged += onStateChanged;
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

                var headerTopLeft = targetOverlayParent.ToLocalSpace(owner.ScreenSpaceDrawQuad.TopLeft);
                var headerTopRight = targetOverlayParent.ToLocalSpace(owner.ScreenSpaceDrawQuad.TopRight);
                var headerBottomLeft = targetOverlayParent.ToLocalSpace(owner.ScreenSpaceDrawQuad.BottomLeft);
                var headerWidth = headerTopRight.X - headerTopLeft.X;

                var menuTop = headerBottomLeft.Y;
                var availableHeight = Math.Max(0, targetOverlayParent.DrawSize.Y - menuTop);
                var menuHeight = computeOverlayMenuHeight(availableHeight, targetOverlayParent.DrawSize.Y);

                Size = new Vector2(headerWidth, menuHeight);
                forcedOverlayWidth = headerWidth;
                Position = new Vector2(headerTopLeft.X, menuTop);

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
                => new HoverStableDropdownMenuItem(item);

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

                if (viewportMaskContainer != null && overlayRoot != null)
                    updateViewportMaskBounds(overlayRoot);

                var headerQuad = owner.ScreenSpaceDrawQuad;
                var headerTopLeft = parentContainer.ToLocalSpace(headerQuad.TopLeft);
                var headerTopRight = parentContainer.ToLocalSpace(headerQuad.TopRight);
                var headerBottomLeft = parentContainer.ToLocalSpace(headerQuad.BottomLeft);

                var headerWidth = headerTopRight.X - headerTopLeft.X;
                var menuTop = headerBottomLeft.Y;
                var availableHeight = Math.Max(0, parentContainer.DrawSize.Y - menuTop);
                var menuHeight = computeOverlayMenuHeight(availableHeight, parentContainer.DrawSize.Y);

                forcedOverlayWidth = headerWidth;
                Size = new Vector2(headerWidth, menuHeight);
                Position = new Vector2(headerTopLeft.X, menuTop);
            }

            private float computeOverlayMenuHeight(float availableHeight, float overlayHeight)
            {
                var contentHeight = Math.Max(ContentContainer.BoundingBox.Height, DrawSize.Y);
                var maxHeight = owner.MenuMaxHeight ?? contentHeight;
                var desiredHeight = Math.Min(contentHeight, maxHeight);

                return Math.Clamp(Math.Min(availableHeight, desiredHeight), 0, overlayHeight);
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
                    RelativeSizeAxes = Axes.None,
                    Anchor = Anchor.TopLeft,
                    Origin = Anchor.TopLeft
                };

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

            private sealed partial class HoverStableDropdownMenuItem : DropdownMenu.DrawableDropdownMenuItem
            {
                public HoverStableDropdownMenuItem(MenuItem item)
                    : base(item)
                {
                    AutoSizeAxes = Axes.Y;
                    RelativeSizeAxes = Axes.X;
                    Width = 1;

                    Foreground.AutoSizeAxes = Axes.Y;
                    Foreground.RelativeSizeAxes = Axes.X;

                    Background.RelativeSizeAxes = Axes.Both;
                    Foreground.Padding = new MarginPadding(2);
                    BackgroundColour = FrameworkColour.BlueGreen;
                    BackgroundColourHover = FrameworkColour.Green;
                    BackgroundColourSelected = FrameworkColour.GreenDark;
                }

                protected override Drawable CreateContent() => new SpriteText
                {
                    Font = FrameworkFont.Condensed
                };

                protected override bool OnHover(HoverEvent e)
                {
                    Scheduler.AddOnce(UpdateBackgroundColour);
                    Scheduler.AddOnce(UpdateForegroundColour);

                    return false;
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
