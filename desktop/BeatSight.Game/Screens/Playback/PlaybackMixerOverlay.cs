// Copyright (c) BeatSight. Licensed under the MIT Licence.
// Extracted from PlaybackScreen.cs on December 3, 2025 for maintainability.
// See ENGINEERING_ACTION_TRACKER.md item 2.3

using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osuTK.Graphics;

namespace BeatSight.Game.Screens.Playback
{
    /// <summary>
    /// Overlay for mixing backing track and drum stem audio volumes.
    /// Provides quick access to mute, solo drums, and reset volume levels.
    /// </summary>
    public partial class PlaybackMixerOverlay : VisibilityContainer
    {
        public PlaybackMixerOverlay(BindableDouble backingVol, BindableDouble drumVol)
        {
            RelativeSizeAxes = Axes.Both;
            Anchor = Anchor.Centre;
            Origin = Anchor.Centre;
            Alpha = 0;

            Children = new Drawable[]
            {
                new Box { RelativeSizeAxes = Axes.Both, Colour = Color4.Black.Opacity(0.8f) },
                new FillFlowContainer
                {
                    AutoSizeAxes = Axes.Both,
                    Direction = FillDirection.Vertical,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Spacing = new osuTK.Vector2(0, 20),
                    Children = new Drawable[]
                    {
                        new BeatSightSpriteText { Text = "Audio Mixer", Font = BeatSightFont.Title(24), Anchor = Anchor.TopCentre, Origin = Anchor.TopCentre },
                        new BeatSightSpriteText { Text = "Backing Track", Font = BeatSightFont.Body(16), Anchor = Anchor.TopCentre, Origin = Anchor.TopCentre },
                        new BeatSightSliderBar
                        {
                            Current = backingVol,
                            Width = 300,
                            Height = 20,
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre
                        },
                        new BeatSightSpriteText { Text = "Drum Stem", Font = BeatSightFont.Body(16), Anchor = Anchor.TopCentre, Origin = Anchor.TopCentre },
                        new BeatSightSliderBar
                        {
                            Current = drumVol,
                            Width = 300,
                            Height = 20,
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre
                        },
                        new FillFlowContainer
                        {
                            AutoSizeAxes = Axes.Both,
                            Direction = FillDirection.Horizontal,
                            Spacing = new osuTK.Vector2(10, 0),
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre,
                            Children = new Drawable[]
                            {
                                new BeatSightButton { Text = "Mute Backing", Width = 100, Height = 30, Action = () => backingVol.Value = 0 },
                                new BeatSightButton { Text = "Solo Drums", Width = 100, Height = 30, Action = () => { backingVol.Value = 0; drumVol.Value = 1; } },
                                new BeatSightButton { Text = "Reset", Width = 100, Height = 30, Action = () => { backingVol.Value = 1; drumVol.Value = 1; } }
                            }
                        },
                        new BeatSightButton
                        {
                            Text = "Close",
                            Width = 100,
                            Height = 40,
                            Action = Hide,
                            Anchor = Anchor.TopCentre,
                            Origin = Anchor.TopCentre
                        }
                    }
                }
            };
        }

        protected override void PopIn() => this.FadeIn(200);
        protected override void PopOut() => this.FadeOut(200);
    }
}
