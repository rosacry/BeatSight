using System;

namespace BeatSight.Game.UI.Components
{
    /// <summary>
    /// Sources implement this to signal that tooltips should be suppressed while the source is interacting.
    /// </summary>
    public interface ISettingsTooltipSuppressionSource
    {
        event Action<bool> TooltipSuppressionChanged;

        bool IsTooltipSuppressed { get; }
    }
}
