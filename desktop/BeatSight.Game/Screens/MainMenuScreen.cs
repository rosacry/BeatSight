using BeatSight.Game.Screens.Editor;
using BeatSight.Game.Screens.Playback;
using BeatSight.Game.Screens.Settings;
using BeatSight.Game.Screens.SongSelect;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Allocation;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osu.Framework.Graphics.Shapes;
using osu.Framework.Graphics.Sprites;
using SpriteText = BeatSight.Game.UI.Components.BeatSightSpriteText;
using osu.Framework.Graphics.UserInterface;
using osu.Framework.Input.Events;
using osu.Framework.Platform;
using osu.Framework.Screens;
using osuTK;
using osuTK.Graphics;

namespace BeatSight.Game.Screens
{
    public partial class MainMenuScreen : Screen
    {
        private GameHost host = null!;

        [BackgroundDependencyLoader]
        private void load(GameHost host)
        {
            this.host = host;
        }

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(20, 20, 30, 255)
                },
                new ScreenEdgeContainer(scrollable: false)
                {
                    Content = new FillFlowContainer
                    {
                        AutoSizeAxes = Axes.Both,
                        Direction = FillDirection.Vertical,
                        Anchor = Anchor.Centre,
                        Origin = Anchor.Centre,
                        Spacing = new Vector2(0, 20),
                        Children = new Drawable[]
                        {
                            new SpriteText
                            {
                                Text = "BeatSight",
                                Font = BeatSightFont.Title(60f),
                                Colour = Color4.White,
                                Anchor = Anchor.TopCentre,
                                Origin = Anchor.TopCentre,
                                Shadow = false
                            },
                            new SpriteText
                            {
                                Text = "Drag and drop a song to jump straight into playback.",
                                Font = BeatSightFont.Subtitle(24f),
                                Colour = new Color4(195, 205, 220, 255),
                                Anchor = Anchor.TopCentre,
                                Origin = Anchor.TopCentre,
                                Shadow = false
                            },
                            new SpriteText
                            {
                                Text = "Or use the menu below to browse, edit, or tweak your setup.",
                                Font = BeatSightFont.Body(18f),
                                Colour = new Color4(160, 170, 190, 255),
                                Anchor = Anchor.TopCentre,
                                Origin = Anchor.TopCentre,
                                Shadow = false
                            },
                            new Container
                            {
                                Height = 40
                            },
                            new MenuButton("Play", Color4.Green)
                            {
                                Action = () => this.Push(new SongSelectScreen(SongSelectDestination.Gameplay))
                            },
                            new MenuButton("Editor", Color4.Blue)
                            {
                                Action = () => this.Push(new EditorScreen())
                            },
                            new MenuButton("Settings", Color4.Orange)
                            {
                                Action = () => this.Push(new SettingsScreen())
                            },
                            new MenuButton("Exit", Color4.Red)
                            {
                                Action = exitGame
                            },
                        }
                    }
                }
            };
        }

        private void exitGame()
        {
            if (host != null)
                host.Exit();
        }
    }

    public partial class MenuButton : Button
    {
        private readonly Color4 baseColour;
        private readonly Container content;
        private readonly Box background;

        public MenuButton(string text, Color4 colour)
        {
            AutoSizeAxes = Axes.Both;
            Anchor = Anchor.TopCentre;
            Origin = Anchor.TopCentre;

            baseColour = colour;

            AddRangeInternal(new Drawable[]
            {
                content = new Container
                {
                    Width = 300,
                    Height = 60,
                    Masking = true,
                    CornerRadius = 10,
                    Children = new Drawable[]
                    {
                        background = new Box
                        {
                            RelativeSizeAxes = Axes.Both,
                            Colour = new Color4((byte)(colour.R * 0.6f), (byte)(colour.G * 0.6f), (byte)(colour.B * 0.6f), colour.A)
                        },
                        new SpriteText
                        {
                            Text = text,
                            Font = BeatSightFont.Button(28f),
                            Colour = Color4.White,
                            Anchor = Anchor.Centre,
                            Origin = Anchor.Centre,
                        }
                    }
                }
            });
        }

        protected override bool OnHover(HoverEvent e)
        {
            background.FadeColour(baseColour, 200, Easing.OutQuint);
            content.ScaleTo(1.03f, 200, Easing.OutQuint);
            return base.OnHover(e);
        }

        protected override void OnHoverLost(HoverLostEvent e)
        {
            base.OnHoverLost(e);
            background.FadeColour(new Color4((byte)(baseColour.R * 0.6f), (byte)(baseColour.G * 0.6f), (byte)(baseColour.B * 0.6f), baseColour.A), 200, Easing.OutQuint);
            content.ScaleTo(1f, 200, Easing.OutQuint);
        }

        protected override bool OnClick(ClickEvent e)
        {
            content.ScaleTo(0.97f, 80, Easing.OutQuad).Then().ScaleTo(1.02f, 120, Easing.OutQuad);
            return base.OnClick(e);
        }
    }

    public partial class PlaceholderScreen : Screen
    {
        private readonly string title;

        public PlaceholderScreen(string title)
        {
            this.title = title;
        }

        public override void OnEntering(ScreenTransitionEvent e)
        {
            base.OnEntering(e);

            InternalChildren = new Drawable[]
            {
                new Box
                {
                    RelativeSizeAxes = Axes.Both,
                    Colour = new Color4(15, 15, 25, 255)
                },
                new SpriteText
                {
                    Text = $"{title} screen coming soon",
                    Font = BeatSightFont.Title(48f),
                    Colour = Color4.White,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre
                },
                new SpriteText
                {
                    Text = "Press Esc to return",
                    Font = BeatSightFont.Subtitle(24f),
                    Colour = Color4.Gray,
                    Anchor = Anchor.Centre,
                    Origin = Anchor.Centre,
                    Y = 80
                }
            };
        }

        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (e.Key == osuTK.Input.Key.Escape)
            {
                this.Exit();
                return true;
            }

            return base.OnKeyDown(e);
        }
    }
}
