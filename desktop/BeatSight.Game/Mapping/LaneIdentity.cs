using System;
using System.Collections.Generic;
using BeatSight.Game.UI.Theming;
using osuTK.Graphics;

namespace BeatSight.Game.Mapping
{
    /// <summary>
    /// What a visual lane represents: one name, short label and colour used by every practice view.
    /// </summary>
    public readonly record struct LaneIdentity(string Name, string ShortName, Color4 Colour);

    public static class LaneIdentityResolver
    {
        // Label priority when several categories share a lane. Secondary crashes come after china and splash
        // so a china lane that also catches second crashes is still named after its own cymbal.
        private static readonly DrumComponentCategory[] priority =
        {
            DrumComponentCategory.Kick,
            DrumComponentCategory.Snare,
            DrumComponentCategory.SnareCenter,
            DrumComponentCategory.SnareRimshot,
            DrumComponentCategory.Rimshot,
            DrumComponentCategory.SnareCrossStick,
            DrumComponentCategory.CrossStick,
            DrumComponentCategory.HiHatClosed,
            DrumComponentCategory.HiHatOpen,
            DrumComponentCategory.HiHatPedal,
            DrumComponentCategory.HiHatFootSplash,
            DrumComponentCategory.HiHatSplash,
            DrumComponentCategory.Ride,
            DrumComponentCategory.RideBow,
            DrumComponentCategory.RideBell,
            DrumComponentCategory.Crash,
            DrumComponentCategory.China,
            DrumComponentCategory.Splash,
            DrumComponentCategory.Crash2,
            DrumComponentCategory.CymbalChoke,
            DrumComponentCategory.TomHigh,
            DrumComponentCategory.TomMid,
            DrumComponentCategory.TomLow,
            DrumComponentCategory.Cowbell,
            DrumComponentCategory.AuxPercussion,
            DrumComponentCategory.Percussion,
        };

        private static readonly DrumComponentCategory[] toms =
        {
            DrumComponentCategory.TomHigh,
            DrumComponentCategory.TomMid,
            DrumComponentCategory.TomLow,
        };

        /// <summary>
        /// Resolves the identity of <paramref name="lane"/>. A category "belongs" to the first lane it maps to;
        /// categories at home in this lane win over categories that only spill into it.
        /// </summary>
        public static LaneIdentity Resolve(LaneLayout layout, int lane)
        {
            DrumComponentCategory? best = pick(layout, lane, homeOnly: true) ?? pick(layout, lane, homeOnly: false);
            if (best == null)
                return new LaneIdentity($"Lane {lane + 1}", $"L{lane + 1}", DrumPalette.Percussion);

            var category = best.Value;
            if (Array.IndexOf(toms, category) >= 0 && countHomeToms(layout, lane) > 1)
                return new LaneIdentity("Toms", "TM", DrumPalette.Tom);

            return describe(category);
        }

        /// <summary>
        /// The component a new note placed in <paramref name="lane"/> should get when nothing more specific is known.
        /// </summary>
        public static string ComponentKey(LaneLayout layout, int lane)
        {
            DrumComponentCategory? best = pick(layout, lane, homeOnly: true) ?? pick(layout, lane, homeOnly: false);
            return best switch
            {
                DrumComponentCategory.Kick => "kick",
                DrumComponentCategory.Snare or DrumComponentCategory.SnareCenter or DrumComponentCategory.SnareRimshot
                    or DrumComponentCategory.Rimshot or DrumComponentCategory.SnareCrossStick or DrumComponentCategory.CrossStick => "snare",
                DrumComponentCategory.HiHatClosed or DrumComponentCategory.HiHatSplash => "hihat_closed",
                DrumComponentCategory.HiHatOpen => "hihat_open",
                DrumComponentCategory.HiHatPedal or DrumComponentCategory.HiHatFootSplash => "hihat_pedal",
                DrumComponentCategory.Ride or DrumComponentCategory.RideBow => "ride",
                DrumComponentCategory.RideBell => "ride_bell",
                DrumComponentCategory.Crash or DrumComponentCategory.Crash2 or DrumComponentCategory.CymbalChoke => "crash",
                DrumComponentCategory.China => "china",
                DrumComponentCategory.Splash => "splash",
                DrumComponentCategory.TomHigh => "tom_high",
                DrumComponentCategory.TomMid => "tom_mid",
                DrumComponentCategory.TomLow => "tom_low",
                DrumComponentCategory.Cowbell => "cowbell",
                _ => "percussion",
            };
        }

        private static DrumComponentCategory? pick(LaneLayout layout, int lane, bool homeOnly)
        {
            foreach (var category in priority)
            {
                IReadOnlyList<int> lanes = layout.GetLanesFor(category);
                if (lanes.Count == 0)
                    continue;

                bool matches = homeOnly ? lanes[0] == lane : contains(lanes, lane);
                if (matches)
                    return category;
            }

            return null;
        }

        private static int countHomeToms(LaneLayout layout, int lane)
        {
            int count = 0;
            foreach (var tom in toms)
            {
                var lanes = layout.GetLanesFor(tom);
                if (lanes.Count > 0 && lanes[0] == lane)
                    count++;
            }

            return count;
        }

        private static bool contains(IReadOnlyList<int> lanes, int lane)
        {
            for (int i = 0; i < lanes.Count; i++)
            {
                if (lanes[i] == lane)
                    return true;
            }

            return false;
        }

        private static LaneIdentity describe(DrumComponentCategory category) => category switch
        {
            DrumComponentCategory.Kick => new LaneIdentity("Kick", "K", DrumPalette.Kick),
            DrumComponentCategory.Snare or DrumComponentCategory.SnareCenter or DrumComponentCategory.SnareRimshot
                or DrumComponentCategory.Rimshot or DrumComponentCategory.SnareCrossStick or DrumComponentCategory.CrossStick
                => new LaneIdentity("Snare", "SN", DrumPalette.Snare),
            DrumComponentCategory.HiHatOpen => new LaneIdentity("Open hi-hat", "OH", DrumPalette.HiHatOpen),
            DrumComponentCategory.HiHatPedal or DrumComponentCategory.HiHatFootSplash
                => new LaneIdentity("Hi-hat pedal", "HP", DrumPalette.HiHatPedal),
            DrumComponentCategory.HiHatClosed or DrumComponentCategory.HiHatSplash
                => new LaneIdentity("Hi-hat", "HH", DrumPalette.HiHat),
            DrumComponentCategory.Ride or DrumComponentCategory.RideBow => new LaneIdentity("Ride", "RD", DrumPalette.Ride),
            DrumComponentCategory.RideBell => new LaneIdentity("Ride bell", "RB", DrumPalette.RideBell),
            DrumComponentCategory.China => new LaneIdentity("China", "CH", DrumPalette.China),
            DrumComponentCategory.Splash => new LaneIdentity("Splash", "SP", DrumPalette.Splash),
            DrumComponentCategory.Crash or DrumComponentCategory.Crash2 or DrumComponentCategory.CymbalChoke
                => new LaneIdentity("Crash", "CR", DrumPalette.Crash),
            DrumComponentCategory.TomHigh => new LaneIdentity("High tom", "T1", DrumPalette.TomHigh),
            DrumComponentCategory.TomMid => new LaneIdentity("Mid tom", "T2", DrumPalette.TomMid),
            DrumComponentCategory.TomLow => new LaneIdentity("Floor tom", "T3", DrumPalette.TomLow),
            _ => new LaneIdentity("Percussion", "PC", DrumPalette.Percussion),
        };
    }
}
