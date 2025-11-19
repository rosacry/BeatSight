using System;
using System.Collections.Generic;
using System.Linq;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;

namespace BeatSight.Game.Mapping
{
    public static class DynamicLaneLayoutBuilder
    {
        public static LaneLayout CreateForBeatmap(Beatmap? beatmap, LanePreset fallbackPreset)
        {
            var descriptors = collectInstrumentDescriptors(beatmap);
            if (descriptors.Count == 0)
                return LaneLayoutFactory.Create(fallbackPreset);

            var categoryMap = buildCategoryMap(descriptors);
            return LaneLayoutFactory.CreateCustom(LanePreset.AutoDynamic, descriptors.Count, categoryMap);
        }

        private static IReadOnlyList<InstrumentDescriptor> collectInstrumentDescriptors(Beatmap? beatmap)
        {
            var unique = new Dictionary<string, InstrumentDescriptor>(StringComparer.OrdinalIgnoreCase);

            void addInstrument(string? component)
            {
                if (string.IsNullOrWhiteSpace(component))
                    return;

                string token = component.Trim();
                if (unique.ContainsKey(token))
                    return;

                var classification = DrumLaneHeuristics.ClassifyComponent(token);
                unique[token] = new InstrumentDescriptor(token, classification.PrimaryCategory, classification.Side, classification.Categories);
            }

            if (beatmap?.DrumKit?.Components != null)
            {
                foreach (var component in beatmap.DrumKit.Components)
                    addInstrument(component);
            }

            if (unique.Count == 0 && beatmap?.HitObjects != null)
            {
                foreach (var hit in beatmap.HitObjects)
                    addInstrument(hit.Component);
            }

            if (unique.Count == 0)
                addInstrument("kick");

            return unique.Values
                .OrderBy(descriptor => computeSortKey(descriptor))
                .ThenBy(descriptor => descriptor.Name, StringComparer.OrdinalIgnoreCase)
                .ToList();
        }

        private static Dictionary<DrumComponentCategory, int[]> buildCategoryMap(IReadOnlyList<InstrumentDescriptor> descriptors)
        {
            var map = new Dictionary<DrumComponentCategory, List<int>>();

            for (int i = 0; i < descriptors.Count; i++)
            {
                foreach (var category in descriptors[i].Categories)
                {
                    if (!map.TryGetValue(category, out var list))
                    {
                        list = new List<int>();
                        map[category] = list;
                    }

                    if (!list.Contains(i))
                        list.Add(i);
                }
            }

            return map.ToDictionary(pair => pair.Key, pair => pair.Value.OrderBy(index => index).ToArray());
        }

        private static int computeSortKey(in InstrumentDescriptor descriptor)
        {
            int baseRank = descriptor.PrimaryCategory switch
            {
                DrumComponentCategory.HiHatClosed or DrumComponentCategory.HiHatOpen or DrumComponentCategory.HiHatPedal => -40,
                DrumComponentCategory.Snare or DrumComponentCategory.CrossStick or DrumComponentCategory.Rimshot => -5,
                DrumComponentCategory.Kick => 0,
                DrumComponentCategory.TomHigh or DrumComponentCategory.TomMid => 10,
                DrumComponentCategory.TomLow => 15,
                DrumComponentCategory.Ride => 25,
                DrumComponentCategory.Crash => 30,
                DrumComponentCategory.China or DrumComponentCategory.Splash => 32,
                DrumComponentCategory.Cowbell or DrumComponentCategory.Percussion => 40,
                _ => 50
            };

            int sideOffset = descriptor.Side switch
            {
                SidePreference.Left => -6,
                SidePreference.Right => 6,
                _ => 0
            };

            return baseRank + sideOffset;
        }

        private readonly record struct InstrumentDescriptor(string Name, DrumComponentCategory PrimaryCategory, SidePreference Side, DrumComponentCategory[] Categories);
    }
}
