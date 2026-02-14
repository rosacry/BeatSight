using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using BeatSight.Game.Beatmaps;
using BeatSight.Game.Configuration;

namespace BeatSight.Game.Screens.Editor
{
    public partial class EditorScreen
    {
        private void saveBeatmap()
        {
            if (isSaving)
            {
                appendStatusDetail("Save already in progress");
                return;
            }

            if (beatmap == null)
            {
                appendStatusDetail("Nothing to save yet");
                return;
            }

            if (beatmap.HitObjects.Count == 0)
            {
                setStatusDetail("Add at least one hit object before saving");
                return;
            }

            EditorInfo editorInfo;
            try
            {
                editorInfo = ensureEditorInfo();
                editorInfo.SnapDivisor = snapDivisor;
                editorInfo.TimelineZoom = timelineZoom;
                editorInfo.WaveformScale = waveformScale;
                editorInfo.BeatGridVisible = beatGridVisible;
            }
            catch (Exception ex)
            {
                appendStatusDetail(ex.Message);
                return;
            }

            isSaving = true;
            setStatusDetail("Saving...");
            updateActionButtons();

            try
            {
                string savedPath = saveBeatmapInternal(beatmap);
                beatmapPath = savedPath;
                lastSavedSnapshot = serializeBeatmap(beatmap);
                hasUnsavedChanges = false;
                editSnapshotArmed = false;
                setStatusDetail($"Saved {Path.GetFileName(savedPath)}");
                reloadTimeline();
                refreshTimelineToolboxState();
                updateStatusText();
                updateActionButtons();
            }
            catch (Exception ex)
            {
                setStatusDetail($"Save failed: {ex.Message}");
                refreshUnsavedState(forceRecompute: true);
            }
            finally
            {
                isSaving = false;
                updateActionButtons();
            }
        }

        private string saveBeatmapInternal(Beatmap map)
        {
            if (map != beatmap)
                throw new InvalidOperationException("Beatmap reference changed during save");

            if (string.IsNullOrWhiteSpace(map.Metadata.Title) || string.IsNullOrWhiteSpace(map.Metadata.Artist))
                throw new InvalidOperationException("Please provide both title and artist before saving");

            if (map.HitObjects.Count == 0)
                throw new InvalidOperationException("Add at least one hit object before saving");

            string audioSource = resolveAudioSourceForSave();

            string targetDirectory;
            bool isExistingBeatmap = !string.IsNullOrEmpty(beatmapPath);

            if (isExistingBeatmap)
            {
                targetDirectory = Path.GetDirectoryName(beatmapPath!) ?? throw new InvalidOperationException("Beatmap path invalid");
            }
            else
            {
                targetDirectory = prepareNewBeatmapFolder();
            }

            Directory.CreateDirectory(targetDirectory);

            string slug = createSlug($"{map.Metadata.Artist}-{map.Metadata.Title}");
            if (string.IsNullOrWhiteSpace(slug))
                slug = $"beatmap-{DateTime.UtcNow:yyyyMMddHHmmss}";

            string targetPath = isExistingBeatmap
                ? beatmapPath!
                : Path.Combine(targetDirectory, $"{slug}.bsm");

            if (!isExistingBeatmap)
            {
                int counter = 1;
                while (File.Exists(targetPath))
                {
                    targetPath = Path.Combine(targetDirectory, $"{slug}-{counter++}.bsm");
                }
            }

            string destAudioFile = Path.GetFileName(audioSource);
            if (string.IsNullOrEmpty(destAudioFile))
                throw new InvalidOperationException("Unable to determine audio filename");

            string destAudioPath = Path.Combine(targetDirectory, destAudioFile);

            string sourceHash = computeFileHash(audioSource);
            bool requiresCopy = !File.Exists(destAudioPath) || !string.Equals(computeFileHash(destAudioPath), sourceHash, StringComparison.OrdinalIgnoreCase);

            if (requiresCopy)
            {
                File.Copy(audioSource, destAudioPath, overwrite: true);
            }

            map.Audio.Filename = destAudioFile;
            map.Audio.Hash = sourceHash;

            if (trackLength > 0)
                map.Audio.Duration = (int)Math.Round(trackLength);

            BeatmapLoader.SaveToFile(map, targetPath);

            return targetPath;
        }

        private string resolveAudioSourceForSave()
        {
            if (beatmap == null)
                throw new InvalidOperationException("No beatmap loaded");

            if (!string.IsNullOrWhiteSpace(beatmap.Audio.Filename))
            {
                string? candidate = resolveAudioAbsolutePath(beatmap.Audio.Filename);
                if (!string.IsNullOrEmpty(candidate))
                    return candidate;
            }

            throw new InvalidOperationException("Audio reference missing; please import audio before saving");
        }

        private string? resolveAudioAbsolutePath(string audioReference)
        {
            if (string.IsNullOrWhiteSpace(audioReference))
                return null;

            if (Path.IsPathRooted(audioReference) && File.Exists(audioReference))
                return audioReference;

            if (beatmapPath != null)
            {
                string beatmapDirectory = Path.GetDirectoryName(beatmapPath) ?? string.Empty;
                string candidate = Path.Combine(beatmapDirectory, audioReference);
                if (File.Exists(candidate))
                    return candidate;
            }

            string storageCandidate = host.Storage.GetFullPath(audioReference.Replace('/', Path.DirectorySeparatorChar));
            if (File.Exists(storageCandidate))
                return storageCandidate;

            return null;
        }

        private string prepareNewBeatmapFolder()
        {
            if (beatmap == null)
                throw new InvalidOperationException("No beatmap loaded");

            // Store editor-created beatmaps in the roaming user Songs directory.
            string baseDirectory = UserAssetDirectories.GetPath(UserAssetDirectories.Songs);
            Directory.CreateDirectory(baseDirectory);

            // Format: {artist} - {title} ({creator})
            string artist = string.IsNullOrWhiteSpace(beatmap.Metadata.Artist) ? "Unknown Artist" : beatmap.Metadata.Artist;
            string title = string.IsNullOrWhiteSpace(beatmap.Metadata.Title) ? "Untitled" : beatmap.Metadata.Title;
            string creator = string.IsNullOrWhiteSpace(beatmap.Metadata.Creator) ? "Unknown" : beatmap.Metadata.Creator;

            string folderName = $"{artist} - {title} ({creator})";
            string slug = createSlug(folderName);

            if (string.IsNullOrWhiteSpace(slug))
                slug = $"beatmap-{DateTime.UtcNow:yyyyMMddHHmmss}";

            string target = Path.Combine(baseDirectory, slug);
            int counter = 1;
            while (Directory.Exists(target))
            {
                target = Path.Combine(baseDirectory, $"{slug}-{counter++}");
            }

            Directory.CreateDirectory(target);
            return target;
        }

        private static string computeFileHash(string path)
        {
            using var stream = File.OpenRead(path);
            using var sha = SHA256.Create();
            byte[] hash = sha.ComputeHash(stream);

            var builder = new StringBuilder(hash.Length * 2);
            foreach (byte b in hash)
                builder.AppendFormat("{0:x2}", b);

            return builder.ToString();
        }

        private static string createSlug(string? value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return string.Empty;

            var builder = new StringBuilder();

            foreach (char c in value)
            {
                char lower = char.ToLowerInvariant(c);

                if (char.IsLetterOrDigit(lower))
                {
                    builder.Append(lower);
                    continue;
                }

                if (builder.Length > 0 && builder[^1] != '-')
                    builder.Append('-');
            }

            while (builder.Length > 0 && builder[^1] == '-')
                builder.Length--;

            return builder.ToString();
        }
    }
}
