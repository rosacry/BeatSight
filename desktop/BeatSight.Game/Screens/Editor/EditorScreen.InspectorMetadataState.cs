using System;
using System.Globalization;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.UI.Components;
using BeatSight.Game.UI.Theming;
using osu.Framework.Graphics;
using osu.Framework.Graphics.UserInterface;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void applyMetadataChange(Action<BeatmapMetadata> mutation, bool refreshStatus = false)
        {
            if (beatmap == null || suppressInspectorFieldSync)
                return;

            prepareInspectorUndoSnapshot();
            mutation(beatmap.Metadata);
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            markUnsaved();

            if (refreshStatus)
                refreshMetadataStatus();
        }

        private void prepareInspectorUndoSnapshot()
        {
            if (beatmap == null || editSnapshotArmed)
                return;

            DateTime now = DateTime.UtcNow;
            if (now - lastInspectorSnapshotAtUtc < inspectorSnapshotDebounce)
                return;

            prepareUndoSnapshot();
            if (editSnapshotArmed)
                lastInspectorSnapshotAtUtc = now;
        }

        private void refreshMetadataStatus()
        {
            if (beatmap == null)
                return;

            string artist = string.IsNullOrWhiteSpace(beatmap.Metadata.Artist) ? "Unknown Artist" : beatmap.Metadata.Artist;
            string title = string.IsNullOrWhiteSpace(beatmap.Metadata.Title) ? "Untitled" : beatmap.Metadata.Title;
            setStatusBase($"Editing: {artist} - {title}");
        }

        private void applyBpmText(string? value)
        {
            if (beatmap == null || suppressInspectorFieldSync)
                return;

            if (double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out double bpm) && bpm > 0)
            {
                setBpm(bpm);
            }
            else if (!string.IsNullOrWhiteSpace(value))
            {
                bpmInput?.FlashColour(EditorColours.Warning, 200);
            }
        }

        private void applyOffsetText(string? value)
        {
            if (beatmap == null || suppressInspectorFieldSync)
                return;

            if (double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out double offset))
            {
                prepareInspectorUndoSnapshot();
                beatmap.Timing.Offset = (int)Math.Round(offset);
                beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
                markUnsaved();
            }
            else if (!string.IsNullOrWhiteSpace(value))
            {
                offsetInput?.FlashColour(EditorColours.Warning, 200);
            }
        }

        private void setBpm(double bpm)
        {
            if (beatmap == null)
                return;

            prepareInspectorUndoSnapshot();
            beatmap.Timing.Bpm = Math.Clamp(bpm, 20, 400);
            beatmap.Metadata.ModifiedAt = DateTime.UtcNow;
            timeline?.SetSnap(snapDivisor, beatmap.Timing.Bpm);
            bpmStatValue.Text = $"{beatmap.Timing.Bpm:0.##} BPM";
            markUnsaved();
            updateInspectorStats();
        }

        private void updateInspectorStats()
        {
            if (noteCountValue == null)
                return;

            int noteCount = beatmap?.HitObjects.Count ?? 0;
            double duration = trackLength > 0
                ? trackLength
                : beatmap?.Audio.Duration ?? 0;

            double minutes = duration > 0 ? duration / 60000.0 : 0;
            double density = minutes > 0 ? noteCount / minutes : 0;

            noteCountValue.Text = noteCount.ToString();
            mapLengthValue.Text = duration > 0 ? formatSongLength(duration) : "--";
            densityValue.Text = density > 0 ? $"{density:0.0} notes/min" : "--";
            bpmStatValue.Text = beatmap != null ? $"{beatmap.Timing.Bpm:0.##} BPM" : "--";
        }

        private static string formatSongLength(double milliseconds)
        {
            var span = TimeSpan.FromMilliseconds(Math.Max(0, milliseconds));
            if (span.TotalHours >= 1)
                return $"{(int)span.TotalHours}:{span.Minutes:00}:{span.Seconds:00}.{span.Milliseconds:000}";
            return $"{(int)span.TotalMinutes:00}:{span.Seconds:00}.{span.Milliseconds:000}";
        }

        private void updateInspectorEnabledState(bool enabled)
        {
            setTextBoxEnabled(titleInput, enabled);
            setTextBoxEnabled(artistInput, enabled);
            setTextBoxEnabled(creatorInput, enabled);
            setTextBoxEnabled(sourceInput, enabled);
            setTextBoxEnabled(tagsInput, enabled);
            setTextBoxEnabled(releaseInput, enabled);
            setTextBoxEnabled(providerInput, enabled);
            setTextBoxEnabled(descriptionInput, enabled);
            setTextBoxEnabled(bpmInput, enabled);
            setTextBoxEnabled(offsetInput, enabled);
        }

        private void setTextBoxEnabled(BasicTextBox? textBox, bool enabled)
        {
            if (textBox == null)
                return;

            textBox.ReadOnly = !enabled;
            textBox.FadeTo(enabled ? 1f : 0.4f, 120, Easing.OutQuint);
        }

        private void populateInspectorFromBeatmap()
        {
            if (titleInput == null)
                return;

            suppressInspectorFieldSync = true;

            if (beatmap == null)
            {
                titleInput.Current.Value = string.Empty;
                artistInput.Current.Value = string.Empty;
                creatorInput.Current.Value = string.Empty;
                sourceInput.Current.Value = string.Empty;
                tagsInput.Current.Value = string.Empty;
                releaseInput.Current.Value = string.Empty;
                providerInput.Current.Value = string.Empty;
                descriptionInput.Current.Value = string.Empty;
                bpmInput.Current.Value = string.Empty;
                offsetInput.Current.Value = string.Empty;
            }
            else
            {
                titleInput.Current.Value = beatmap.Metadata.Title ?? string.Empty;
                artistInput.Current.Value = beatmap.Metadata.Artist ?? string.Empty;
                creatorInput.Current.Value = beatmap.Metadata.Creator ?? string.Empty;
                sourceInput.Current.Value = beatmap.Metadata.Source ?? string.Empty;
                tagsInput.Current.Value = beatmap.Metadata.Tags != null && beatmap.Metadata.Tags.Count > 0
                    ? string.Join(", ", beatmap.Metadata.Tags)
                    : string.Empty;
                releaseInput.Current.Value = beatmap.Metadata.ReleaseDate ?? string.Empty;
                providerInput.Current.Value = beatmap.Metadata.Provider ?? string.Empty;
                descriptionInput.Current.Value = beatmap.Metadata.Description ?? string.Empty;
                bpmInput.Current.Value = beatmap.Timing.Bpm.ToString("0.##", CultureInfo.InvariantCulture);
                offsetInput.Current.Value = beatmap.Timing.Offset.ToString(CultureInfo.InvariantCulture);
            }

            suppressInspectorFieldSync = false;

            refreshMetadataStatus();
            updateInspectorEnabledState(beatmap != null);
            updateInspectorStats();
            refreshComponentReassignmentOptions();
            updateSelectionSummary();
        }
    }
}
