using System;
using System.Linq;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using osuTK;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void setStatusBase(string text)
        {
            statusBaseText = text;
            updateStatusText();
            updateActionButtons();
        }

        private void setStatusDetail(string? detail)
        {
            statusDetailText = string.IsNullOrWhiteSpace(detail) ? null : detail;
            updateStatusText();
        }

        private void appendStatusDetail(string detail)
        {
            if (string.IsNullOrWhiteSpace(detail))
                return;

            string normalized = detail.Trim();
            if (string.Equals(statusDetailText, normalized, StringComparison.OrdinalIgnoreCase))
            {
                updateStatusText();
                return;
            }

            // Keep the detail line focused on the latest action instead of accumulating
            // multiple edits/undo events that crowd the header.
            statusDetailText = normalized;
            updateStatusText();
        }

        private static bool isTransientPlaybackStatus(string detail)
            => transientPlaybackStatusTokens.Any(token => detail.StartsWith(token, StringComparison.OrdinalIgnoreCase));

        private static bool isInspectorLayoutStatus(string detail)
            => detail.StartsWith("Inspector hidden", StringComparison.OrdinalIgnoreCase)
               || detail.StartsWith("Inspector shown", StringComparison.OrdinalIgnoreCase);

        private void pruneStatusDetailSegments(Func<string, bool> shouldRemove)
        {
            if (string.IsNullOrWhiteSpace(statusDetailText))
                return;

            var segments = statusDetailText
                .Split(", ", StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Where(segment => !shouldRemove(segment))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray();

            statusDetailText = segments.Length > 0 ? string.Join(", ", segments) : null;
        }

        private void updateStatusText()
        {
            if (statusText != null)
            {
                statusText.Text = statusBaseText;
                statusText.Alpha = string.IsNullOrWhiteSpace(statusBaseText) ? 0 : 1;
            }

            string? detail = statusDetailText;

            if (!string.IsNullOrWhiteSpace(detail))
                detail = detail.Replace(", ", " | ");

            if (statusDetailLine != null)
            {
                bool showDetail = !string.IsNullOrWhiteSpace(detail);
                statusDetailLine.Text = showDetail ? detail! : string.Empty;
                statusDetailLine.Alpha = showDetail ? 1 : 0;
            }
        }

        private void setHoverHint(string? hint)
        {
            _ = hint;
            refreshHintText();
        }

        private void refreshHintText()
        {
            if (actionHintText == null)
                return;

            // Header hover-tooltips cause layout shifts and provide low-value noise in the
            // editor's primary transport area; keep this channel disabled.
            actionHintText.Text = string.Empty;
            actionHintText.Alpha = 0;
            updateHeaderInformationVisibility();
        }

        private void updatePlaybackAvailabilityUI()
        {
            if (playPauseButton != null)
                updatePlayPauseButtonLabel();

            if (previewToggle != null)
            {
                previewToggle.SetAvailability(true, null);

                float targetAlpha = playbackAvailable ? 1f : 0.75f;
                previewToggle.FadeTo(targetAlpha, 150);
            }

            if (playbackStatusText != null)
            {
                playbackStatusText.Text = string.Empty;
                playbackStatusText.Alpha = 0;
            }

            updateHeaderInformationVisibility();

            if (!playbackAvailable)
                appendStatusDetail(offlinePlaybackMessage);
        }

        private void updateHeaderInformationVisibility()
        {
            if (headerInformationFlow == null)
                return;

            headerInformationFlow.AutoSizeAxes = Axes.None;
            headerInformationFlow.Height = 0f;
            headerInformationFlow.Alpha = 0f;
            headerInformationFlow.AlwaysPresent = false;

            if (headerContentContainer?.Child is FillFlowContainer contentFlow)
                contentFlow.Spacing = new Vector2(0, 0f);
        }

        private void updateActionButtons()
        {
            if (saveButton == null || undoButton == null || redoButton == null)
                return;

            var currentBeatmap = beatmap;
            bool hasBeatmap = currentBeatmap != null;
            bool hasHitObjects = currentBeatmap != null && currentBeatmap.HitObjects.Count > 0;

            bool canSave = hasBeatmap && hasUnsavedChanges && !isSaving && hasHitObjects;
            bool canUndo = hasBeatmap && undoStack.Count > 0;
            bool canRedo = hasBeatmap && redoStack.Count > 0;

            string saveTooltip = !hasBeatmap
                ? "Load or create a beatmap to enable saving."
                : isSaving
                    ? "Save is already running."
                    : !hasHitObjects
                        ? "Add at least one hit object before saving."
                        : hasUnsavedChanges
                            ? $"Save beatmap ({currentBeatmap!.HitObjects.Count} notes)."
                            : "All changes are saved.";

            string undoTooltip = !hasBeatmap
                ? "Load a beatmap to undo changes."
                : canUndo
                    ? $"{undoStack.Count} undo step{(undoStack.Count == 1 ? string.Empty : "s")} available (max {maxUndoSteps})."
                    : "No edits to undo yet.";

            string redoTooltip = !hasBeatmap
                ? "Load a beatmap to redo changes."
                : canRedo
                    ? $"{redoStack.Count} redo step{(redoStack.Count == 1 ? string.Empty : "s")} available."
                    : undoStack.Count > 0
                        ? "Undo an action to enable redo."
                        : "No actions to redo yet.";

            saveButton.UpdateState(canSave, saveTooltip);
            undoButton.UpdateState(canUndo, undoTooltip);
            redoButton.UpdateState(canRedo, redoTooltip);

            if (!hasBeatmap)
            {
                defaultHintText = "Load or create a beatmap to begin mapping.";
            }
            else if (isSaving || !hasHitObjects)
            {
                defaultHintText = saveTooltip;
            }
            else if (hasUnsavedChanges)
            {
                defaultHintText = null;
            }
            else if (!canUndo && !canRedo)
            {
                defaultHintText = null;
            }
            else if (!canUndo)
            {
                defaultHintText = undoTooltip;
            }
            else if (!canRedo)
            {
                defaultHintText = redoTooltip;
            }
            else
            {
                defaultHintText = null;
            }

            refreshHintText();
            updateHistoryPanel();
        }

        private void markUnsaved()
        {
            editSnapshotArmed = false;
            hasUnsavedChanges = true;
            redoStack.Clear();
            if (beatmap?.Editor?.AiGenerationMetadata != null)
                beatmap.Editor.AiGenerationMetadata.ManualEdits = true;
            updateStatusText();
            updateActionButtons();
        }
    }
}
