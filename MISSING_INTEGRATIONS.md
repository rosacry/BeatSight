# Missing AI & Model Integrations

This document outlines the features and integrations missing from the current frontend screens (`SongSelect`, `Playback`, `Editor`, `Settings`) based on the capabilities of the AI pipeline and the `.bsm` file format.

## 1. Song Select Screen (`SongSelectScreen.cs`)

The song select screen currently treats all maps equally and lacks features to leverage AI-generated metadata.

*   **AI Generation Indicators**:
    *   [ ] **"AI Generated" Badge**: Display a visual indicator for maps created by the pipeline vs. human-made maps.
    *   [ ] **Confidence Score**: Show the global `AiGenerationMetadata.Confidence` score on the beatmap panel.
    *   [ ] **Model Version**: Display which version of the model generated the map (useful for knowing when to re-generate).

*   **Filtering & Sorting**:
    *   [ ] **Filter by AI Confidence**: Allow users to hide maps with low confidence scores.
    *   [ ] **Filter by Detected Genre**: Use the `Tags` detected by `metadata_detection.py` for filtering.
    *   [ ] **Sort by "Date Generated"**: Distinct from "Date Added".

*   **Metadata Display**:
    *   [ ] **Extended Metadata**: Display fields detected by the AI but currently hidden:
        *   `Source` (e.g., Album/Game)
        *   `Release Date`
        *   `Tags` (Genre)
        *   `Provider` (e.g., "Metadata via Spotify")

*   **Creation Workflow**:
    *   [ ] **"New from Audio" Button**: A direct entry point to import an audio file and trigger the AI pipeline immediately.

## 2. Playback Screen (`PlaybackScreen.cs`)

The playback screen is missing audio features enabled by source separation and visual feedback for AI reliability.

*   **Audio Stem Control**:
    *   [ ] **Drum Stem Mixing**: The `.bsm` format supports a `DrumStem` file. The player needs a mixer to:
        *   Mute the original drums (if using a drumless track).
        *   Solo the AI-isolated drums (to hear what the AI heard).
        *   Adjust the balance between the backing track and the drum stem.

*   **Visual Feedback**:
    *   [ ] **Confidence Heatmap**: A progress bar or background overlay showing the local confidence of the transcription over time (e.g., red sections = low confidence/likely errors).
    *   [ ] **Ghost Note Gameplay**: While visual opacity is implemented, ensure "Ghost Notes" (low velocity) have appropriate scoring windows (e.g., maybe they are bonus points or have lenient timing).

*   **Practice Tools**:
    *   [ ] **"Loop Low Confidence"**: A practice mode that automatically loops sections where the AI was unsure, allowing the user to verify or learn complex parts.

*   **Audio Engine**:
    *   [ ] **Custom Sample Loading**: The `.bs` format supports `CustomSamples` (e.g., specific snare sounds classified by AI). The player must load these instead of the default kit if specified.

## 3. Editor Screen (`EditorScreen.cs`)

The editor is the most critical missing piece. It currently lacks any interface to control the AI pipeline.

*   **Pipeline Integration**:
    *   [ ] **Generation Panel**: A new tool/window to run `process_audio_file`.
    *   [ ] **Parameter Controls**: UI inputs for:
        *   `Confidence Threshold` (0.0 - 1.0)
        *   `Detection Sensitivity` (0-100)
        *   `Quantization Grid` (1/4, 1/8, 1/16, etc.)
        *   `Isolate Drums` (Toggle)
        *   `Max Snap Error` (ms)
        *   `Force Quantization` (Toggle)
        *   `ML Classifier` (Toggle: Heuristic vs ML)
        *   `Tempo Hints` (Input for manual BPM suggestions)

*   **Metadata Editing**:
    *   [ ] **Extended Fields**: Inputs for `Release Date`, `Provider`, and `Description` which are currently missing from the metadata panel.

*   **Interactive Re-generation**:
    *   [ ] **Region Re-generation**: Select a time range on the timeline and "Re-generate this section" with different parameters (e.g., "Make this fill more sensitive").
    *   [ ] **Snap-to-Transients**: A tool to snap notes to the nearest detected onset in the `DrumStem` waveform.

*   **Visualization**:
    *   [ ] **Stem Waveform**: Option to toggle the waveform display between "Full Track" and "Drum Stem" (Demucs output) to see drum transients more clearly.
    *   [ ] **Onset Markers**: Visualize raw detected onsets (before they became notes) as faint vertical lines to help manual placement.
    *   [ ] **Debug Visualization**: Import `debug.json` (if available) to visualize:
        *   Raw detection confidence peaks.
        *   Tempo candidates (ambiguity).
    *   [ ] **Pipeline Logs**: View `stderr` output from the Python process to diagnose failures (e.g., OOM, missing dependencies).

## 4. Settings Screen (`SettingsScreen.cs`)

There is no configuration for the AI backend.

*   **New "AI / Generation" Section**:
    *   [ ] **Python Environment Path**: Setting to specify where the python environment for the pipeline is located.
    *   [ ] **Model Checkpoints**: Selector for different model versions (if multiple exist).
    *   [ ] **ML Configuration**:
        *   `Use GPU/CUDA` (Toggle).
        *   `Custom Model Path` (File picker for .pth files).
    *   [ ] **External Services**:
        *   `AcoustID API Key` (for metadata detection).
    *   [ ] **Default Generation Settings**:
        *   Default Quantization (e.g., 1/16).
        *   Default Sensitivity.
        *   "Auto-generate on Import" (Toggle).
    *   [ ] **Cache Management**: Button to clear `feature_cache` or `separation` temp files to free up space.
