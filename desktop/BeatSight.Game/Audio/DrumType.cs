namespace BeatSight.Game.Audio
{
    /// <summary>
    /// Represents coarse instrument classifications emitted by the detection pipeline.
    /// These values intentionally capture common kit variations (left/right cymbals,
    /// multiple floor toms, etc.) so downstream heuristics can pick sensible lanes.
    /// </summary>
    public enum DrumType
    {
        Unknown = 0,

        Kick,

        Snare,
        SnareRimshot,
        SnareCrossStick,
        SnareGhost,

        HiHatClosed,
        HiHatOpen,
        HiHatPedal,
        HiHatFootSplash,

        RideBow,
        RideBell,

        CrashHigh,
        CrashLow,
        CrashStack,

        SplashHigh,
        SplashLow,

        ChinaHigh,
        ChinaLow,
        ChinaStack,

        TomRackHigh,
        TomRackMid,
        TomRackLow,
        TomFloorHigh,
        TomFloorLow,

        Cowbell,
        Percussion
    }
}
