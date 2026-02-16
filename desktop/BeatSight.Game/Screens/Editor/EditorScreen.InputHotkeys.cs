using System;
using System.Globalization;
using System.Linq;
using BeatSight.Game.Configuration;
using BeatSight.Game.Mapping;
using osu.Framework.Input.Events;
using osu.Framework.Screens;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        protected override bool OnKeyDown(KeyDownEvent e)
        {
            if (!e.ControlPressed && !e.SuperPressed && !e.AltPressed && e.Key == osuTK.Input.Key.F1)
            {
                toggleFooterShortcutsCollapsed();
                return true;
            }

            if (isTimingSetupOverlayVisible())
            {
                if (e.Key == osuTK.Input.Key.Escape)
                {
                    closeTimingSetupOverlay();
                    return true;
                }

                if (e.Key == osuTK.Input.Key.Enter || e.Key == osuTK.Input.Key.KeypadEnter)
                {
                    applyTimingSetupChanges();
                    return true;
                }

                if (e.Key == osuTK.Input.Key.Space)
                {
                    togglePlayback();
                    return true;
                }

                if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.BracketLeft)
                {
                    setTimingPlaybackRate(playbackRate - 0.05);
                    return true;
                }

                if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.BracketRight)
                {
                    setTimingPlaybackRate(playbackRate + 0.05);
                    return true;
                }

                if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.Number0)
                {
                    setTimingPlaybackRate(1.0);
                    return true;
                }

                return base.OnKeyDown(e);
            }

            bool textInputFocused = isTextInputFocused();
            if (textInputFocused)
            {
                if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.S)
                {
                    saveBeatmap();
                    return true;
                }

                return base.OnKeyDown(e);
            }

            if (e.Key == osuTK.Input.Key.Escape)
            {
                if (selectedHitObject != null || tryGetSelectionRange(out _, out _))
                {
                    selectedHitObject = null;
                    timeline?.ClearSelection();
                    updateSelectionSummary();
                    appendStatusDetail("Selection cleared");
                    return true;
                }

                this.Exit();
                return true;
            }

            if (e.Key == osuTK.Input.Key.Space)
            {
                if (e.ShiftPressed)
                    rewindToStart();
                else
                    togglePlayback();
                return true;
            }

            if (!e.ControlPressed && !e.SuperPressed && !e.AltPressed && e.Key == osuTK.Input.Key.I)
            {
                toggleInspectorCollapsed();
                return true;
            }

            if (e.AltPressed)
            {
                if (e.Key == osuTK.Input.Key.Left)
                {
                    nudgeSelectedNote(false);
                    return true;
                }

                if (e.Key == osuTK.Input.Key.Right)
                {
                    nudgeSelectedNote(true);
                    return true;
                }
            }

            if (e.Key == osuTK.Input.Key.Home)
            {
                jumpToFirstNote();
                return true;
            }

            if (e.Key == osuTK.Input.Key.End)
            {
                jumpToLastNote();
                return true;
            }

            switch (getNotationHotkeyAction(e.Key, e.ControlPressed, e.AltPressed, e.SuperPressed))
            {
                case NotationHotkeyAction.ArticulationUp:
                    cycleNotationArticulationPreset(true);
                    return true;
                case NotationHotkeyAction.ArticulationDown:
                    cycleNotationArticulationPreset(false);
                    return true;
                case NotationHotkeyAction.ShiftLaneUp:
                    shiftSelectionToAdjacentNotationLane(true);
                    return true;
                case NotationHotkeyAction.ShiftLaneDown:
                    shiftSelectionToAdjacentNotationLane(false);
                    return true;
            }

            if (e.Key == osuTK.Input.Key.Comma)
            {
                jumpToAdjacentNote(false);
                return true;
            }

            if (e.Key == osuTK.Input.Key.Period)
            {
                jumpToAdjacentNote(true);
                return true;
            }

            if (e.Key == osuTK.Input.Key.Delete || e.Key == osuTK.Input.Key.BackSpace)
            {
                deleteSelectedNote();
                return true;
            }

            if (e.Key == osuTK.Input.Key.Left)
            {
                seekRelative(-5000);
                return true;
            }

            if (e.Key == osuTK.Input.Key.Right)
            {
                seekRelative(5000);
                return true;
            }

            if (isControlOrSuper(e))
            {
                bool alt = e.AltPressed;

                if (!alt && e.ShiftPressed && e.Key == osuTK.Input.Key.H)
                {
                    toggleHistoryPanelVisibility();
                    return true;
                }

                if (!alt && e.Key == osuTK.Input.Key.T)
                {
                    openTimingSetupOverlay();
                    return true;
                }

                if (isZoomIncreaseKey(e.Key))
                {
                    if (alt)
                        adjustWaveformScale(true);
                    else
                        adjustTimelineZoom(true);
                    return true;
                }

                if (isZoomDecreaseKey(e.Key))
                {
                    if (alt)
                        adjustWaveformScale(false);
                    else
                        adjustTimelineZoom(false);
                    return true;
                }

                if (!alt && e.Key == osuTK.Input.Key.BracketLeft)
                {
                    adjustPlaybackRate(false);
                    return true;
                }

                if (!alt && e.Key == osuTK.Input.Key.BracketRight)
                {
                    adjustPlaybackRate(true);
                    return true;
                }

                if (!alt && e.Key == osuTK.Input.Key.Number0)
                {
                    resetPlaybackRate();
                    return true;
                }
            }

            if (!e.ControlPressed && !e.SuperPressed)
            {
                if (!e.AltPressed)
                {
                    if (tryHandleLaneQuickReassign(e.Key))
                        return true;

                    if (e.Key == osuTK.Input.Key.BracketLeft)
                    {
                        adjustSnapDivisor(false);
                        return true;
                    }

                    if (e.Key == osuTK.Input.Key.BracketRight)
                    {
                        adjustSnapDivisor(true);
                        return true;
                    }

                    if (e.Key == osuTK.Input.Key.G)
                    {
                        toggleBeatGrid();
                        return true;
                    }
                }
            }

            if (isControlOrSuper(e) && e.ShiftPressed && e.Key == osuTK.Input.Key.Z)
            {
                redoLastEdit();
                return true;
            }

            if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.Y)
            {
                redoLastEdit();
                return true;
            }

            if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.S)
            {
                saveBeatmap();
                return true;
            }

            if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.A && !isTextInputFocused())
            {
                selectAllNotes();
                return true;
            }

            if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.D)
            {
                duplicateSelectedNote();
                return true;
            }

            if (!e.ControlPressed && !e.SuperPressed && !e.AltPressed && e.Key == osuTK.Input.Key.Q && !isTextInputFocused())
            {
                quantizeSelectedToGrid();
                return true;
            }

            if (isControlOrSuper(e) && e.Key == osuTK.Input.Key.Z)
            {
                undoLastEdit();
                return true;
            }

            return base.OnKeyDown(e);
        }

        private bool tryHandleLaneQuickReassign(osuTK.Input.Key key)
        {
            int laneIndex = key switch
            {
                osuTK.Input.Key.Number1 => 0,
                osuTK.Input.Key.Number2 => 1,
                osuTK.Input.Key.Number3 => 2,
                osuTK.Input.Key.Number4 => 3,
                osuTK.Input.Key.Number5 => 4,
                osuTK.Input.Key.Number6 => 5,
                osuTK.Input.Key.Number7 => 6,
                osuTK.Input.Key.Number8 => 7,
                osuTK.Input.Key.Number9 => 8,
                _ => -1
            };

            if (laneIndex < 0)
                return false;

            if (beatmap == null)
                return true;

            string? component = resolveQuickReassignComponentForVisibleLane(laneIndex);
            if (string.IsNullOrWhiteSpace(component))
            {
                appendStatusDetail($"No lane bound to {laneIndex + 1}");
                return true;
            }

            var targets = getSelectedHitObjectsForEditing(out _, out _, out _);
            if (targets.Count == 0)
            {
                appendStatusDetail("Select a note or range to reassign");
                quickActionToast?.Warning("Quick Reassign", "Select a note or range first");
                return true;
            }

            int changedCount = targets.Count(hit =>
                !string.Equals(hit.Component, component, StringComparison.OrdinalIgnoreCase)
                || hit.Lane.HasValue);
            if (changedCount <= 0)
            {
                appendStatusDetail($"Selection already uses {component}");
                quickActionToast?.Info("Quick Reassign", $"Already {formatComponentDisplayName(component)}");
                return true;
            }

            componentReassignSelection.Value = component;
            reassignSelectedComponent();
            showQuickReassignToast(component, laneIndex + 1, changedCount);
            return true;
        }

        private void showQuickReassignToast(string component, int laneNumber, int affectedNotes)
        {
            if (quickActionToast == null)
                return;

            string name = formatComponentDisplayName(component);
            string notesLabel = affectedNotes == 1 ? "1 note" : $"{affectedNotes} notes";
            quickActionToast.Success("Quick Reassign", $"Reassigned -> {name} (lane {laneNumber}) | {notesLabel}");
        }

        private static string formatComponentDisplayName(string component)
        {
            if (string.IsNullOrWhiteSpace(component))
                return "Unknown";

            string raw = component.Replace('_', ' ').Trim();
            if (raw.Length == 0)
                return "Unknown";

            return CultureInfo.InvariantCulture.TextInfo.ToTitleCase(raw.ToLowerInvariant());
        }

        private string? resolveQuickReassignComponentForVisibleLane(int visibleLaneIndex)
        {
            if (visibleLaneIndex < 0)
                return null;

            string? timelineMappedComponent = timeline?.GetLaneComponentForVisibleLane(visibleLaneIndex);
            if (!string.IsNullOrWhiteSpace(timelineMappedComponent))
                return timelineMappedComponent;

            LaneLayout layout = resolveCurrentLaneLayout();
            bool useGlobalKick = kickLaneModeSetting.Value == KickLaneMode.GlobalLine;
            int activeLaneCount = useGlobalKick
                ? Math.Max(1, layout.LaneCount - 1)
                : layout.LaneCount;

            if (visibleLaneIndex >= activeLaneCount)
                return null;

            var source = useGlobalKick
                ? globalKickLaneQuickComponents
                : dedicatedLaneQuickComponents;

            return visibleLaneIndex < source.Length
                ? source[visibleLaneIndex]
                : null;
        }

        private LaneLayout resolveCurrentLaneLayout()
        {
            if (lanePresetSetting.Value == LanePreset.AutoDynamic && beatmap?.DrumKit?.Components?.Count > 0)
                return LaneLayoutFactory.CreateFromComponents(beatmap.DrumKit.Components);

            return lanePresetSetting.Value == LanePreset.AutoDynamic
                ? LaneLayoutFactory.Create(LanePreset.DrumSevenLane)
                : LaneLayoutFactory.Create(lanePresetSetting.Value);
        }

        private static bool isZoomIncreaseKey(osuTK.Input.Key key)
            => key == osuTK.Input.Key.Plus
                || key == osuTK.Input.Key.KeypadPlus;

        private static bool isZoomDecreaseKey(osuTK.Input.Key key)
            => key == osuTK.Input.Key.Minus
                || key == osuTK.Input.Key.KeypadMinus;

        private static NotationHotkeyAction getNotationHotkeyAction(osuTK.Input.Key key, bool controlPressed, bool altPressed, bool superPressed)
        {
            if (altPressed || superPressed)
                return NotationHotkeyAction.None;

            if (key == osuTK.Input.Key.PageUp)
                return controlPressed ? NotationHotkeyAction.ArticulationUp : NotationHotkeyAction.ShiftLaneUp;

            if (key == osuTK.Input.Key.PageDown)
                return controlPressed ? NotationHotkeyAction.ArticulationDown : NotationHotkeyAction.ShiftLaneDown;

            return NotationHotkeyAction.None;
        }

        private bool isTextInputFocused()
        {
            if (titleInput?.HasFocus == true
                || artistInput?.HasFocus == true
                || creatorInput?.HasFocus == true
                || sourceInput?.HasFocus == true
                || tagsInput?.HasFocus == true
                || releaseInput?.HasFocus == true
                || providerInput?.HasFocus == true
                || descriptionInput?.HasFocus == true
                || bpmInput?.HasFocus == true
                || offsetInput?.HasFocus == true
                || tempoHintsInput?.HasFocus == true)
            {
                return true;
            }

            return componentReassignDropdown?.HasFocus == true;
        }

        private void seekRelative(double milliseconds)
        {
            seekToTime(currentTime + milliseconds);
        }

        private static string formatTime(double milliseconds)
        {
            var time = TimeSpan.FromMilliseconds(milliseconds);

            if (time.TotalHours >= 1)
                return $"{(int)time.TotalHours:00}:{time.Minutes:00}:{time.Seconds:00}.{time.Milliseconds:000}";

            return $"{(int)time.TotalMinutes:00}:{time.Seconds:00}.{time.Milliseconds:000}";
        }

        private static bool isControlOrSuper(KeyDownEvent e) => e.ControlPressed || e.SuperPressed;
    }
}
