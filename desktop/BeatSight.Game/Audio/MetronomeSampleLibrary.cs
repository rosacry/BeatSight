using System.Collections.Generic;
using BeatSight.Game.Configuration;

namespace BeatSight.Game.Audio
{
    /// <summary>
    /// Provides centralised lookup helpers for metronome sample assets.
    /// </summary>
    public static class MetronomeSampleLibrary
    {
        private const string default_base_name = "Perc_MetronomeQuartz";

        /// <summary>
        /// Resolves the resource paths used for the accent and regular variants of a metronome sound option.
        /// </summary>
        public static (string AccentPath, string RegularPath) GetSamplePaths(MetronomeSoundOption option)
        {
            string baseName = GetBaseName(option);
            return ($"Samples/Metronome/{baseName}_hi.wav", $"Samples/Metronome/{baseName}_lo.wav");
        }

        /// <summary>
        /// Returns an ordered list of fallback sample resource names to attempt when the preferred sample is missing.
        /// </summary>
        public static IEnumerable<string> GetFallbackCandidates(bool accent)
        {
            string suffix = accent ? "_hi" : "_lo";

            yield return $"Samples/Metronome/Synth_Tick_A{suffix}.wav";
            yield return $"Samples/Metronome/Perc_ClickToy{suffix}.wav";
            yield return "Gameplay/normal-hitnormal";
            yield return "UI/click-short";
            yield return "UI/click";
        }

        /// <summary>
        /// Maps a metronome sound option to its base resource name.
        /// </summary>
        public static string GetBaseName(MetronomeSoundOption option)
        {
            return option switch
            {
                MetronomeSoundOption.PercCan => "Perc_Can",
                MetronomeSoundOption.PercCastanet => "Perc_Castanet",
                MetronomeSoundOption.PercChair => "Perc_Chair",
                MetronomeSoundOption.PercClackhead => "Perc_Clackhead",
                MetronomeSoundOption.PercClap => "Perc_Clap",
                MetronomeSoundOption.PercClickToy => "Perc_ClickToy",
                MetronomeSoundOption.PercGlass => "Perc_Glass",
                MetronomeSoundOption.PercHeadKnock => "Perc_HeadKnock",
                MetronomeSoundOption.PercKeyboard => "Perc_Keyboard",
                MetronomeSoundOption.PercMetal => "Perc_Metal",
                MetronomeSoundOption.PercMetronomeQuartz => default_base_name,
                MetronomeSoundOption.PercMouthPop => "Perc_MouthPop",
                MetronomeSoundOption.PercMusicStand => "Perc_MusicStand",
                MetronomeSoundOption.PercPracticePad => "Perc_PracticePad",
                MetronomeSoundOption.PercSnap => "Perc_Snap",
                MetronomeSoundOption.PercSqueak => "Perc_Squeak",
                MetronomeSoundOption.PercStick => "Perc_Stick",
                MetronomeSoundOption.PercTambA => "Perc_Tamb_A",
                MetronomeSoundOption.PercTambB => "Perc_Tamb_B",
                MetronomeSoundOption.PercTambC => "Perc_Tamb_C",
                MetronomeSoundOption.PercTambD => "Perc_Tamb_D",
                MetronomeSoundOption.PercTeeth => "Perc_Teeth",
                MetronomeSoundOption.PercTongue => "Perc_Tongue",
                MetronomeSoundOption.PercTrashCan => "Perc_TrashCan",
                MetronomeSoundOption.PercWhistleParty => "Perc_WhistleParty",
                MetronomeSoundOption.PercWhistleRef => "Perc_WhistleRef",
                MetronomeSoundOption.SynthBellA => "Synth_Bell_A",
                MetronomeSoundOption.SynthBellB => "Synth_Bell_B",
                MetronomeSoundOption.SynthBlockA => "Synth_Block_A",
                MetronomeSoundOption.SynthBlockB => "Synth_Block_B",
                MetronomeSoundOption.SynthBlockC => "Synth_Block_C",
                MetronomeSoundOption.SynthBlockD => "Synth_Block_D",
                MetronomeSoundOption.SynthBlockE => "Synth_Block_E",
                MetronomeSoundOption.SynthBlockF => "Synth_Block_F",
                MetronomeSoundOption.SynthBlockG => "Synth_Block_G",
                MetronomeSoundOption.SynthBlockH => "Synth_Block_H",
                MetronomeSoundOption.SynthSineA => "Synth_Sine_A",
                MetronomeSoundOption.SynthSineB => "Synth_Sine_B",
                MetronomeSoundOption.SynthSineC => "Synth_Sine_C",
                MetronomeSoundOption.SynthSineD => "Synth_Sine_D",
                MetronomeSoundOption.SynthSineE => "Synth_Sine_E",
                MetronomeSoundOption.SynthSineF => "Synth_Sine_F",
                MetronomeSoundOption.SynthSquareA => "Synth_Square_A",
                MetronomeSoundOption.SynthSquareB => "Synth_Square_B",
                MetronomeSoundOption.SynthSquareC => "Synth_Square_C",
                MetronomeSoundOption.SynthSquareD => "Synth_Square_D",
                MetronomeSoundOption.SynthSquareE => "Synth_Square_E",
                MetronomeSoundOption.SynthTickA => "Synth_Tick_A",
                MetronomeSoundOption.SynthTickB => "Synth_Tick_B",
                MetronomeSoundOption.SynthTickC => "Synth_Tick_C",
                MetronomeSoundOption.SynthTickD => "Synth_Tick_D",
                MetronomeSoundOption.SynthTickE => "Synth_Tick_E",
                MetronomeSoundOption.SynthTickF => "Synth_Tick_F",
                MetronomeSoundOption.SynthTickG => "Synth_Tick_G",
                MetronomeSoundOption.SynthTickH => "Synth_Tick_H",
                MetronomeSoundOption.SynthWeirdA => "Synth_Weird_A",
                MetronomeSoundOption.SynthWeirdB => "Synth_Weird_B",
                MetronomeSoundOption.SynthWeirdC => "Synth_Weird_C",
                MetronomeSoundOption.SynthWeirdD => "Synth_Weird_D",
                MetronomeSoundOption.SynthWeirdE => "Synth_Weird_E",
                _ => default_base_name
            };
        }
    }
}
