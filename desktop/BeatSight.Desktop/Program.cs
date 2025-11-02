using osu.Framework;
using osu.Framework.Platform;
using BeatSight.Game;

namespace BeatSight.Desktop
{
    public static class Program
    {
        public static void Main(string[] args)
        {
            using GameHost host = Host.GetSuitableDesktopHost("BeatSight");
            using osu.Framework.Game game = new BeatSightGame();
            host.Run(game);
        }
    }
}
