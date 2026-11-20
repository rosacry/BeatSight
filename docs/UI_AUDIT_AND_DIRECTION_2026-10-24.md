# UI audit and visual direction — 2026-10-24

The user asked for the UI work to start while training data is processed, said the app "still looks
really bad", and delegated judgement: identify everything that is wrong and fix it. This report is the
audit (ranked), the visual direction now used in code, and the record of what this session changed.

Evidence root (outside Git): `C:\Users\10ros\BeatSight-Recovery\2026-10-24-ui-visual-overhaul-01`.

- `harness/` — capture harness built against the live checkout (`AuditHarness.csproj`, `AuditCapture.cs`,
  `run_captures*.ps1`, `run_one.ps1`, `contact_sheet.py`). It drives the real `BeatSightGame` with an isolated
  copy of the model-comparison library (`app-root/`, 8 real charts) and a portable settings file seeded from
  a snapshot of the user's `beatsight.ini` (`evidence/user-beatsight.ini.snapshot`, audio muted). The user's
  own library and settings were never touched.
- `screenshots/before/` — the audit set: 1280x720 (default settings), 1920x1080 (user settings),
  2560x1440 (user settings, real animated background), every settings section, intro, menu, song select
  (+ entry-transition frames), playback and editor in 3D / 2D / manuscript on The Sin and the Sentence
  (dense, 14 instrument classes) and WHITE WAVES, toolbar shown/hidden and mid-playback frames, and the
  onboarding / recording / import / AI-choice screens.
- `screenshots/stepN/` and `compare/` — after-captures and before/after sheets for each fix step.

## Ranked problems

P0 = makes practice harder or shows wrong information. P1 = looks broken or confusing. P2 = polish.

| # | Pri | Where | Problem (evidence) | Status |
|---|---|---|---|---|
| 1 | P0 | All views | Instrument colours disagree and collide. Four separate palettes in code (`LaneManagement`, `DrawableNote`, `DesignSystem`, 3D background) plus pastel receptors. In 2D, crash, hi-hat and ride were all orange/amber; 3D header pills used unrelated colours (crash pill green while crash notes orange). | Fixed (step 1–2) |
| 2 | P0 | 3D | China lane labelled "CR" (secondary crashes map into the china lane and crash was checked first). | Fixed (step 1) |
| 3 | P0 | 2D | Lane labels were assigned by position, not content: WHITE WAVES has no china, yet lanes 6–7 read "China/Splash" (really splash/perc); the nine-lane preset puts kick in lane 4 but labels/colours assumed lane 3. | Fixed (step 1) |
| 4 | P0 | 3D | Receptor pads, header pills and lane surfaces washed out to pastel/white: `new Color4(r, g, b, 116)` mixed 0–1 channels with a 0–255 alpha (alpha ≈ 116×). Seven instances. | Fixed (step 2) |
| 5 | P0 | Playback | Default zoom 1.0 gave ~0.5 s look-ahead (curve turned 1.0 into 2.97x). User-approved restore. | Fixed (step 1), user setting migrated |
| 6 | P0 | Manuscript | Notation is malformed: lumpy note heads, no proper five-line staff (lines at the wrong heights, extra "CR/RD/T3" rows), rests drawn as stray squiggles on separate lines, ruler "Now" ~130 px from the green playhead, 9 px legend, wide green glow band. Not readable as drum notation. Root cause: instruments were given evenly spaced rows like lanes (kick bottom, hi-hat second, crash top), and the sheet window was clamped near song start/end so "now" left the playhead. | Rebuilt (manuscript step) |
| 7 | P0 | Playback header | Back button covered the start of the title at 1080p; the header was a debug string ("Loaded: … • Kick lane: dedicated lane") with a stray off-baseline dot. | Fixed (step 1–2) |
| 8 | P1 | Playback | No progress/time visible while playing: the toolbar starts at alpha 0 and only appears on hover; when shown it covers the lower 40% of the highway. Inside it, Play is the least prominent button (dark) while Restart/Mixer are bright cyan; "Loop Low Confidence: Off" is full-bright although off; times show milliseconds. | Fixed (steps 5–7): primary Play, one-row transport, opaque panel, tucked peek strip |
| 9 | P1 | 3D | Hit bursts scaled 1.8x wide and spilled over neighbouring lanes; "3D Stage: Arcade" overlay in an unshipped font rendered as an unreadable smudge in the play area. | Fixed (step 3) |
| 10 | P1 | 2D | Lane labels 11 px dim grey; bright grid separators competing with notes; no visible hit feedback. | Labels/separators fixed; 2D hit feedback still open |
| 11 | P1 | Main menu | Five equal-weight neon buttons (cyan, magenta, green, orange, red); Exit as loud as Playback; buttons enter with random rotation and elastic bounce; logo "breathes" forever. | Fixed (step 2–3) |
| 12 | P1 | Song select | Every chart shows "[10.0]" (difficulty saturates); hot-pink metadata line; "vadtof-frame-rnn-1" ("v" glued to a non-numeric model id); 10 px "AI Generated" pill; Back and Random buttons at different heights; unlabeled "All"/"Title" dropdowns; no song selected on entry, so the left half says only "Select a song to play"; elastic card expand. | Fixed (steps 3–5) except the details panel layout (still centred text stack) |
| 13 | P1 | Settings | Lane Profile editor overflows its row and overlaps Kick Lane Mode; the Lane Profile setting is never applied to playback (a no-op); "Dedicated Line" typo; labels 26 px vs control text 10 px; unexplained bullet dots. Settings › AI says processing runs "on our servers" — false, it runs locally. | Overlap, typo and AI copy fixed; Lane Profile still not applied to playback; type scale open |
| 14 | P1 | Editor | Timeline rows have no lane labels; saturated mid-blue timeline background; dense crash notes merge into bars; toolbox takes ~30% of the height with tiny repeated −/+/Reset controls; 3D preview squashed into a ~150 px strip; Undo/Redo nearly invisible; the view button changes colour per mode. The editor also overwrites the shared playback zoom when its timeline zoom is linked. | Fixed (editor layout pass) |
| 15 | P1 | Import flow | Audio-imported / metadata / AI-generation screens have no layout: full-width pastel buttons pinned to the top-left, pale text on pastel. Onboarding repeats its paragraph. | Audio-imported, song-not-identified and onboarding fixed; AI-generation screen open |
| 16 | P2 | Global | Two parallel design systems (`UITheme`, `DesignSystem`) plus ~670 inline `new Color4(...)`; font sizes 8–48 px with no scale; Exo 2 / Nunito with a 1.2x multiplier. | Tokens unified (step 1); call sites migrate gradually |
| 17 | P2 | Motion | Elastic hover bounce (1.05x) on all shared buttons; fake boot text ("INITIALIZING KERNEL…") and an off-centre circle in the intro. | Buttons fixed (step 2); intro open |
| 18 | P2 | Recording | Large orange "START" disc, dotted pink line, sparse layout. | Open |

## Visual direction (implemented as tokens)

Calm practice room at night: low-chroma slate UI that recedes, one cyan accent for actions and focus,
and instrument colours as the only saturated colours on screen.

- **Neutrals** (`UITheme`): background #0B0E14, layer #10141C, surface #181D28, surface-alt #1F2634,
  raised #293142, border #30394C; text #ECF0F7 / #A8B2C5 / #707A91.
- **Accent**: cyan #38C4EC for primary actions, selection, progress. Lavender #968CFF only for rare
  secondary emphasis. Warning #F5B841, success #3DD68C, danger #F2555A (destructive actions only).
- **Instrument palette** (`DrumPalette`, Rock Band / Clone Hero conventions where they exist): snare red
  #FF5468, hi-hat yellow #FFD24A (open lighter, pedal darker), crash green #3DDC97, ride blue #4AA8FF
  (bell lighter), kick orange #FF9440, toms violet family, china magenta #F065C8, splash teal #36D3C9,
  percussion grey #A3AEC4. Every lane in a layout gets a distinct hue. Old untouched defaults stored in
  charts/settings are treated as "not customised" and shown in the new palette; real customisations stay.
- **Lane identity** (`LaneIdentityResolver`): each lane's name, short label and colour come from the
  instruments mapped to it (not its position) and are shared by 2D, 3D, notes and receptors.
- **Type scale** (`UITheme.Type*`): display 44, title 26, heading 19, body 15, label 13, caption 11.5
  (logical px at 1080p). Exo 2 for titles/numbers, Nunito for body.
- **Spacing/radii**: 4/8/12/16/24/32/48 grid; radius 6 controls, 10–12 cards and buttons, 14 panels.
- **Motion** (`UITheme.Motion*`): 120 ms feedback, 220 ms state changes, 360 ms entrances, OutQuint;
  hover scale 1.02, press 0.97; no elastic, no rotation, no idle loops in menus. Gameplay feedback stays
  inside its lane and never covers neighbours.

## Changes in this session (all uncommitted, `desktop/` only)

Before/after sheets are in the evidence root's `compare/` folder; raw frames in `screenshots/stepN/`.

1. **One instrument palette and lane identity** (`compare/step1-playback.png`). New `UI/Theming/DrumPalette.cs`
   and `Mapping/LaneIdentity.cs`; `LaneManagement` defaults, `DrawableNote`, `DesignSystem` component colours,
   the editor timeline and the 3D background all use them. 2D labels and colours follow lane content; the
   China lane reads "CH". Stored old default colours count as "not customised" (`DrumPalette.IsLegacyDefault`).
2. **3D alpha bug** (`compare/step2-3d.png`): seven `Color4(r, g, b, byteAlpha)` calls fixed; receptors, header
   pills and lane surfaces now show their instrument colour instead of pastel/white.
3. **Playback header**: song title, then artist, BPM and charter with drawn separators (the "•"/"·" glyphs are
   missing from the UI fonts); starts after the Back button at every width (`keepHeaderClearOfBackButton`).
4. **Zoom** (user-approved): manual zoom is a direct multiplier (1.0x = 1.4 measures of look-ahead). One-time
   migration in `BeatSightConfigManager` (`PlaybackZoomScaleVersion`) converts saved values with the old curve so
   the user's look-ahead is unchanged (their 0.45 becomes 2.25x). The editor no longer overwrites the shared
   playback zoom when it opens (its linked timeline follows playback instead); verified the saved value stays
   2.25 after opening the editor. Zoom tests updated to the new exact values, not loosened.
5. **Motion**: shared buttons and the back button use 120/220 ms OutQuint, hover 1.02, press 0.97 (no elastic);
   menu entry is a short fade/rise (no random rotation, no breathing logo); song cards expand without bounce;
   3D hit bursts expand vertically (1.08x wide, was 1.8x) and note bursts 1.12x (was 1.4x).
6. **Main menu** (`compare/step3-main.png`): one filled primary action (Playback), neutral secondary buttons,
   quiet Exit; label colour applied after the base constructor (it was dark on first try).
7. **Buttons keep their intended colours**: `BeatSightButton` forced cyan in its load step, overriding colours
   given at construction (12 call sites). This was why inactive toolbar toggles looked primary and Play looked
   disabled. Added `TextColour` for accent-filled buttons.
8. **Playback toolbar** (`compare/step5-toolbar-import.png`): Play/Pause is the primary control; Restart, Mixer
   and toggles are neutral; transport, progress bar and time share one row; time shows tenths, not
   milliseconds; the panel is opaque. The toolbar now rests as a visible peek strip (was alpha 0 until hovered)
   and its tucked offset tracks the real layout height. `SetExpanded`/`ExpandOnHover` make captures independent
   of the mouse; the regression renderer (`LiveVisualCaptureRenderer.cs`) now uses them.
9. **Song select** (`compare/step3-main.png`): first song selected on entry; header controls centred on the Back
   button; labelled Tag/Sort fields; cards show length, BPM, notes/s and charter (the star rating saturates at
   10.0 on these songs) and an outlined "AI transcription" tag; model ids shown without a stray "v"; Random is a
   secondary button; details panel shows note count/density, Play button has dark text on accent.
10. **Settings**: rows grow to fit multi-line controls (Lane Profile no longer overlaps the next row);
    "Dedicated Lane" typo; the AI section no longer claims processing happens on servers.
11. **Import flow** (`compare/step5-toolbar-import.png`): Audio-imported and Song-not-identified screens use a
    shared centred card layout (`UI/Components/FlowCardLayout.cs`); their summary card was zero-height before
    (relative-size child in an auto-size parent) and is now visible. AI transcription is the primary action.
12. **Onboarding**: description was added twice; fixed and moved to the app fonts.
13. **Editor**: neutral slate palette; low-contrast neutral beat grid (fine-snap blue lines used to tint the whole
    timeline); timeline notes use the instrument palette; Play uses the accent, Save the success colour.
14. **2D view**: lane labels larger and in their instrument colour; quieter lane separators. 3D: the
    "3D Stage" overlay (unshipped font, unreadable) removed from the play area; the setting stays in the toolbar.

15. **Late fixes**: the toolbar peek height is computed from the real transport-row height (no sliver of the next
    row); "Reset All Settings" no longer re-triggers the zoom migration; per-frame toolbar check avoids LINQ.

## Test record

- New tests: `LaneIdentityResolverTests` (lane labels/colours, palette, legacy colour migration, legacy zoom
  factors) and `PlaybackZoomMigrationTests` (existing ini 0.45 -> 2.25 once; fresh install 1.0; reset keeps 1.0).
  `PlaybackPlayfieldAutoZoomTests` updated to the approved direct-zoom values (exact ranges, not widened).
- Full non-visual desktop suite (Release): 547/547 after the main changes (`evidence/tests-full-nonvisual-run1.log`),
  551/551 on the final code (`evidence/tests-full-nonvisual-run2.log`).
- Live visual comparison, all 17 scenes at 1080p (`BEATSIGHT_RUN_VISUAL_TESTS=1`, thresholds unchanged):
  2 pass (AudioImportLoading, MappingGeneration — not restyled), 15 fail against baselines that predate this
  restyle, changed pixels 0.5% (Intro, accent colour) to 99.9% (rebuilt import screens). Per-scene numbers in
  `evidence/visual-1080p-run1-summary.json`; diffs in `desktop/BeatSight.Tests/TestResults/visual-diff/`.
  No baseline or threshold was changed. The regression renderer is now toolbar-deterministic, so the next step
  is one baseline regeneration from a single accepted code state (open item 8).
- Release app rebuilt from this source at 11:17 (`desktop/BeatSight.Desktop/bin/Release/net8.0`); the previous
  March build is backed up in the evidence root.

## Manuscript rebuild (same day, user-requested)

New code in `desktop/BeatSight.Game/Screens/Playback/Playfield/Notation/`:

- `DrumNotation.cs` — standard drum key (PAS/Weinberg): kick bottom space, floor tom second space, snare third
  space, mid tom fourth line, high tom fourth space, ride "x" top line (bell = diamond), hi-hat "x" above the staff
  (open = "o" mark), crash "x" on the first ledger line, china above it, hi-hat pedal "x" below the staff,
  cross-stick circled "x", other percussion triangle. Hands are stems up, feet (kick, hi-hat pedal) stems down.
  Noteheads keep the instrument colours of the rest of the app.
- `DrumStaffEngraver.cs` — tempo map from the beatmap's offset/timing points; per measure, hits are grouped into
  chords (25 ms), assigned to beats (half-a-sixteenth lead so slightly early downbeats stay on the downbeat),
  quantised per beat to the simplest grid that fits within min(30 ms, beat/10) (sixteenths, eighth triplets,
  thirty-seconds, sixteenth triplets), split into voices, beamed by beat with 1–3 beam levels, dotted rhythms,
  flags for lone chords, triplet "3", quarter/eighth/sixteenth rests for empty hand beats and a whole-measure rest.
- `DrumStaffView.cs`, `DrumStaffMeasureRenderer.cs`, `DrumStaffGlyphs.cs` — static five-line staff with
  percussion clef and time signature in a fixed gutter; measures engraved lazily as they scroll in; playhead fixed
  at 22% of the timeline with the ruler (measure numbers, beat numbers, "&" in Full count-in mode), bar lines and
  notes all on one time-to-x mapping (no clamping, so "now" is always on the playhead); past notes dimmed; heads
  pulse as they cross the playhead; legend of the instruments actually in the song plus "stems up: hands / stems
  down: feet". Horizontal scale keeps sixteenths at least 2.4 staff spaces apart; manual zoom changes the
  look-ahead gently (2 measures / sqrt(zoom)). The editor preview uses the same view in compact form.
- `PlaybackPlayfield` uses the staff view in manuscript mode (playback and editor preview); per-note drawables
  stay for judging and hit sounds but are hidden, as are the highway strike zone and hit bursts. The editor's
  "move selection up/down the staff" now follows the real staff order (snare -> mid tom -> high tom -> ride ->
  hi-hat -> crash -> china).
- Tests: `DrumStaffNotationTests` (30: positions, heads, voices, normalisation, staff order, tempo map, eighth
  groove beaming, jittered sixteenths, triplets, whole-measure rest, offbeat eighth with rest and flag, dotted
  eighth + sixteenth, early downbeat, simultaneous hits). `EditorScreenUtilityTests` expectation updated
  (snare moves up to mid tom on a real staff, was high tom in the old row order). Full suite 581/581.
- Live visual check (1080p, unchanged thresholds): PlaybackManuscript 67.1% and EditorManuscript 84.5% changed
  pixels against baselines that show the old renderer (`evidence/tests-visual-manuscript-1080p.log`); expected for
  a rebuild, nothing loosened. The fixture groove renders as a textbook 8th-note beat.
- Evidence: `compare/manuscript-before-after.png`; frames in `screenshots/ms*/` (ms6 final; `ww-intro` shows rests).
- The old manuscript renderer was removed afterwards (next section).

## Old manuscript renderer removed (user-requested)

- Deleted: `Views/ManuscriptViewEnhanced.cs`, `Views/ManuscriptView.cs`, `Views/ManuscriptPlaybackHighlighter.cs`,
  `Playfield/ManuscriptBackground.cs`, `Playfield/DrawableManuscriptRest.cs` and their six test files
  (`DrawableManuscriptRestTests`, `DrawableNoteManuscriptRenderingTests`, `ManuscriptNotationMappingTests`,
  `ManuscriptPlaybackHighlighterTests`, `PlaybackPlayfieldManuscriptBeamingTests`,
  `PlaybackPlayfieldManuscriptSubdivisionTests`), which only tested the removed code.
- `PlaybackPlayfield` lost its four manuscript layers, rest/beam/tie/duration structs and ~50 methods
  (3,518 -> ~2,345 lines); `DrawableNote` lost its manuscript drawing (~350 lines). In manuscript mode the note
  drawables only judge and play hit sounds; the staff view draws everything. The editor's placement mapping uses
  the staff view's own time-to-x mapping.
- The three manuscript layout tests in `LayoutResponsivenessTests` became one (`ManuscriptModeUsesTheDrumStaffView`).
  Full suite 469/469 (`evidence/tests-full-nonvisual-run5-after-removal.log`); 3D, 2D and sheet captured with no
  runtime errors (`screenshots/rm1`, `compare/after-removal-check.png`). The deleted files are also copied to the
  evidence root (`source-backup-before-manuscript-removal/`).
- Left for later (not drawing code): `PlayfieldViewManager` and the rest of `Screens/Playback/Views/` are never
  instantiated anywhere (dead framework); the `ShowManuscriptPlaybackHighlighter` setting no longer does anything.

## Editor layout (user-requested)

Before/after: `compare/editor/editor-*-before-after.png` and `editor-top-before-after.png` in the evidence root
(before = `screenshots/rm1`, after = `screenshots/ed4`, 1080p and 720p, user settings, The Sin and the Sentence).

- **Timeline rows are the playfield lanes.** The timeline built its own rows from the chart's most frequent
  components while the preview used the lane preset, so rows and preview disagreed (9 preview lanes, 7 rows) and
  row colours came from a third, positional mapping: the green "crash" row actually held the kicks. The timeline
  now takes the preview's resolved layout (`EditorTimeline.SetLaneLayout`, `PlaybackPreview.ResolveLaneLayoutFor`
  and `LaneLayoutResolved`): row N is playfield lane N, notes are placed with the same heuristics and stored-lane
  rule, and a note added to a row gets the component that lane holds most (else the lane's own instrument,
  `LaneIdentityResolver.ComponentKey`). Without a layout (unit tests) the old behaviour remains.
- **Lane labels on every row.** The labels existed but sat at time 0 inside the scrolling content, so they were
  never on screen. They are now pinned to the left edge of the viewport: instrument colour bar plus the lane's name
  as the playfield names it (user-renamed lanes keep their name).
- **Colours.** Timeline notes were tinted twice (container and fill multiplied), which over-saturated them.
  Stored lane colours equal to the editor's positional defaults (Crash, HiHat, ... by index) no longer count as
  customisations (`DrumPalette.IsPositionalDefault`), so lanes show the colour of what they hold in any preset,
  in the editor and in practice.
- **Toolbox: three rows -> two** (about 260 px -> 130 px at 1080p). Row 1: timeline zoom, playback zoom, speed,
  note width, waveform as slim sliders with the value and a small reset icon (the −/+/Reset button triplets are
  gone; arrow keys and the existing hotkeys still step), plus Hide/Show. Row 2: snap, overlays (beat grid, link
  zoom, drum waveform), tools, and "Lanes: Edit" which opens the lane name/colour/order editor as a third row only
  when needed. Collapsing keeps exactly row 1 (no clipped slice of row 2). Mini buttons have a visible surface;
  the snap value is centred between its buttons.
- **Bigger preview.** The saved split ratio (1.0 in the user's settings) let the timeline take everything but
  188 px. The preview now always keeps at least 42% of the editor body (`minimumPreviewWorkspaceShare`); the
  splitter still works inside that range. 3D notes are thinned in proportion when the stage is wider than 2:1
  (the editor preview), so consecutive kicks no longer stack into one bar; practice stages (about 2:1) are
  unchanged.
- **Header buttons.** osu!framework's `BasicButton` multiplies a disabled button by grey; together with the
  editor's own dimming this made disabled Save/Undo/Redo darker than the header. Editor buttons now turn that off
  (`DisabledColour = White`) and show disabled as a neutral outlined button with muted text at full opacity;
  labels on light accents (Play, Save) use dark text. The view toggle is one neutral colour in every mode with a
  cyan icon. Metronome "on" is the accent with dark text, "off" matches the other buttons.
- **Checkboxes (app-wide).** Unchecked boxes were a dark square with a border the colour of the panel; they now
  have a visible outline, and checked boxes show a tick.
- **Ruler and playhead.** Ruler time labels were anchored to the centre of the whole song's width and landed far
  off-screen; they now sit above their ticks ("2:28", "2:28.5"). The timeline only re-aligned with the fixed
  playhead when time changed, so a resize or a zoom anchored elsewhere left the line pointing at the wrong time
  (seen as a 0.15 s offset in one capture); it now keeps the current time under the playhead every frame outside
  zoom/drag interactions.
- Tests: `EditorTimelineSelectionTests.SetLaneLayout_RowsFollowThePlayfieldLanes`,
  `LaneIdentityResolverTests.PositionalDefaultLaneColoursAreNotTreatedAsCustomisations` and
  `ComponentKeyNamesTheLanesOwnInstrument`. Full suite 472/472 (`evidence/tests-full-nonvisual-run6-editor-layout.log`).
  Live visual, 1080p, thresholds unchanged (`evidence/tests-visual-editor-layout-1080p.log`): Editor 84.5%,
  EditorTwoDimensional 69.7%, EditorManuscript 90.9%, Playback 26.3% (was 27.0%), Settings 28.1% (unchanged, so the
  checkbox change is not in that frame) changed pixels against baselines that predate the restyle; no baseline
  changed. The 720p editor layout contracts (`VisualRegressionEditorLayoutContractTests`, never part of the earlier
  snapshot-only runs) failed on the toolbox check, which encoded the old design (fixed 145-170 px zoom slider,
  25-31 px slider blocks, zoom wider than waveform). Restated for the new toolbox, same tightness: the game reports
  drawn sizes; each slider is 14-18% of the toolbox width (an 18% column less padding), zoom and waveform within
  2 px of each other (equal columns), slim-row height 17-23 px. Header, footer, inspector and mini-button checks
  unchanged. 3/3 pass (`evidence/tests-visual-editor-contracts-720p.log`); full suite again 472/472
  (`evidence/tests-full-nonvisual-run7-editor-final.log`). Release app rebuilt 16:19 from this source.
- Harness: `harness/AuditCapture.cs` has an `editor` group (three views, lane editor open, toolbox collapsed);
  `harness/editor_compare.py` builds the sheets.

## Lane setup row and slim sliders (user-requested)

Before/after: `compare/editor/lane-setup-before-after.png` and `sliders-before-after.png` in the evidence root
(before = `ed4`, `rm1`, `step8`; after = `sl1`, `sl2`, 1080p; `sl1` also has 720p editor frames).

- **Lane setup row** (`Screens/Editor/EditorScreen.LaneEditorRow.cs`, behind "Lanes: Edit"). One chip per timeline
  row (colour bar + short label, the selected one outlined) replaces "< L1 CR >"; Name and Short fields show the
  automatic name as a placeholder and stay empty unless the lane was renamed; Colour is "Auto" plus eleven
  instrument swatches and a hex field; Order uses arrow buttons; "Add lane" / "Remove lane" are labelled. Enter or
  leaving a field applies it (no Save step); clearing a field returns that lane to automatic. Arrows and Add/Remove
  dim at their limits.
- **Lane count and chart writes.** The row edits the lanes the timeline shows (the playfield's count; it edited 7
  while the timeline showed 9). Opening the editor no longer writes positional lane entries into the chart; they
  are written only when a lane is actually edited (`EnsureLaneLayout` with the visible lane count).
- New `EditorTimeline.LaneCount` / `DescribeLane(lane, includeCustomisations)` give the row the same names and
  colours as the timeline rows and the playfield. The harness renames lane 2 to "Hats", colours it teal and
  returns it to Auto; the log shows Hi-hat/yellow -> Hats/teal -> Hi-hat/yellow and the row label, chip and
  swatch follow (`screenshots/sl2`, `lane-edit` entries in its log).
- **Slim slider everywhere** (`UI/Components/BeatSightSliderBar.cs`): a 4-6 px rounded track and a 10-14 px knob
  centred in the control (the full control height stays the click target), knob grows on hover and gets an accent
  ring when focused, sliders bound to a disabled value dim. The ends are inset by the knob radius and the pointer
  mapping uses the same inset (`RangePadding`), so 0 and 1 sit under the knob. The practice heatmap is inset by
  the same amount so it stays aligned with the seek track. Applies to settings, the practice toolbar (seek,
  speed, offset, zoom, note width), mixer, editor toolbox/footer/inspector, AI generation and recording screens.
  The editor's own slim-bar workaround is gone (its sliders fill their rows again).
- Tests: `EditorTimelineSelectionTests.DescribeLane_ShowsUserLaneNameAndColourOverTheAutomaticIdentity`.
  Full non-visual suite 473/473 (`evidence/tests-full-nonvisual-run9-sliders-lanes-final.log`). All live visual
  scenes at 1080p plus the 720p editor contracts, thresholds unchanged
  (`evidence/tests-visual-all-sliders-lanes-1080p.log`): the same 15 restyled scenes fail against older baselines
  as in the first run (Settings 27.9%, Recording 45.6%, Playback 26.3%, Editor 85.2%, EditorTwoDimensional 70.4%,
  EditorManuscript 91.6%, others unchanged from earlier runs); AudioImportLoading and MappingGeneration still pass;
  the three 720p contracts pass. No baseline or threshold changed. Release app rebuilt 16:53 from this source.

## 2D note height (user-requested: "WAY too much vertical", Lorna Shore - Oblivion)

- Cause: `PlaybackPlayfield.resolveTwoDimensionalNoteHeight` made every 2D note 64% of the sixteenth-note gap,
  clamped 8-44 px, with nothing tying it to the lane or screen. With the user's 2.25x zoom and auto zoom, Oblivion
  (129 BPM, blast beats) drew ~50 px bricks 130 px apart.
- Now: a fixed bar of 2.2% of the travel distance (8-22 px; ~17 px at 1080p), never more than 60% of the sixteenth
  gap (4 px floor), so fast runs stay separate. The editor's snap-aware path starts from this bar height; the
  editor preview, already thin, barely changes.
- Before/after: `compare/editor/oblivion-2d-practice-before-after.png` and `oblivion-2d-editor-before-after.png`
  (frames `screenshots/ob0` / `ob1`; the Oblivion map was copied into this session's isolated library from
  `2026-10-24-model-comparison-03`, original untouched; harness option "oblivion").
- Test: `PlaybackPlayfieldAutoZoomTests.TwoDimensionalNotesAreThinBarsThatNeverFillTheSixteenthGap` (60/129/240
  BPM; the old rule gave ~40 px at 60 BPM). Full suite 476/476 (`evidence/tests-full-nonvisual-run10-*.log`). Live
  visual 1080p (PlaybackTwoDimensional 31.6%, EditorTwoDimensional 69.3%, Editor 85.2%, EditorManuscript 91.6%)
  still fail only against the older baselines; 720p contracts pass (`evidence/tests-visual-2d-note-height-1080p.log`).
- Release app rebuilt 17:37 after the user closed BeatSight (it had locked `BeatSight.Game.dll` at 17:30);
  `BeatSight.Game.dll` in the Release folder matches the build output (SHA-256 29798c4e...), no source newer.

## Separate tom lanes (user request via the handoff session, 2026-10-24 evening)

User: "give high, mid and low tom their own lanes in the 2D view, like Clone Hero" (seen on the human Clone Hero
chart of Oblivion, whose tom fills collapsed into one "Toms" lane).

- `LaneLayoutFactory.CreateFromComponents` (the "Auto (match drum kit)" preset, which the user's settings use): a
  kit with two or more tom voices gets one lane per tom, high to low (T1 High tom, T2 Mid tom, T3 Floor tom),
  between kick and ride. A single tom voice keeps one shared "Toms" lane: ADTOF writes every tom as `tom_mid`, so
  ADTOF maps are unchanged. The fixed 4-9 lane presets are unchanged.
- 2D, 3D and the editor timeline share the layout, so all three show the tom lanes with the shared palette
  (tom violets light to dark) and labels; sheet music already placed toms on their own staff positions.
- Lane counts: Clone Hero Oblivion 7 -> 8 lanes (Crash, Hi-hat, Snare, Kick, High/Mid/Floor tom, Ride; the empty
  padding "Lane 7" disappears); phase-2 maps 9 -> 11 lanes, all labels fit at 1080p (152 px lanes) and the 3D
  header pills fit. `LaneManagement.MaxLaneCount` 9 -> 11 so the lane setup row can rename/recolour every lane;
  positional default colours past lane 9 are recognised as automatic (`DrumPalette.IsPositionalDefault` wraps
  like the fallback colour).
- A tom voice the kit lacks still lands on a tom lane: for a high + floor kit, `tom_mid` used to fall through to
  the snare lane; `DrumLaneHeuristics` now tries high and low tom after mid tom. Layouts with a mid-tom lane (all
  presets, merged toms) resolve exactly as before.
- Before/after: `compare/editor/oblivion-toms-2d-clonehero-before-after.png` and
  `oblivion-toms-2d-phase2-before-after.png` (frames `screenshots/tm0` / `tm1`, at the 7:00 tom fill; both
  "Oblivion (chart audio)" maps copied into this session's isolated library from `2026-10-24-model-comparison-03`,
  originals untouched; harness option "toms"). Editor: `tm1/*oblivion-ch-editor-TwoDimensional.png`.
- Tests: `LaneIdentityResolverTests` phase-2 label row updated to the requested lanes (CR HH SN K T1 T2 T3 RD CH
  SP PC, was ... K TM RD ...); new `KitsWithSeveralTomVoicesGetOneLanePerTomHighToLow`,
  `ASingleTomVoiceKeepsOneSharedTomsLane`, `AMissingMidTomFallsBackToATomLaneNotTheSnare`. Full suite 479/479
  (`evidence/tests-full-nonvisual-run11-tom-lanes.log`). All live visual scenes at 1080p
  plus the 720p contracts (`evidence/tests-visual-all-tom-lanes-1080p.log`): the same 15 restyled scenes fail against
  older baselines with unchanged numbers (the fixtures have single-tom kits), AudioImportLoading and MappingGeneration
  pass, contracts pass; nothing loosened. Release app rebuilt 18:42 after the user closed BeatSight
  (`BeatSight.Game.dll` SHA-256 becaf09f..., matches the build output).
- Not changed: with fewer than seven instrument groups (ADTOF: five) the auto layout still pads with empty
  "Lane 6/7" lanes.

## Still open (next sessions, in order)

1. **Manuscript follow-ups**: editor click-to-place directly on staff positions
   (`DrumStaffView.ComponentAtY` is ready); accents/flams/rolls/chokes when the model outputs them; beam slope
   and stem-length polish; optional "1 e & a" counting.
2. **Editor follow-ups.** The 2D preview's lane names are hidden under its strike bar; the left-most ruler label is
   clipped at the viewport edge; text boxes (app-wide) are very low contrast. Add/Remove/Move lane only remap
   stored note lanes and lane names/colours, so on AI charts (no stored lanes) Remove and Move change nothing
   visible; decide whether to keep them. The Settings "Lane Profile" editor is the same old form and does nothing
   in playback (see item 5). Remove the dead `Screens/Playback/Views/` framework and the no-op
   `ShowManuscriptPlaybackHighlighter` setting. Mixer overlay: no panel behind it and four equal cyan buttons.
3. **2D hit feedback** (lane-confined flash at the strike line) and 3D lane-edge "ladder" ticks.
4. **Song select details panel**: left-aligned layout and a tighter type scale. (A "dimmed" panel in the step-7
   capture was the capture catching its cross-fade; step 8 confirms full opacity: `screenshots/step8/*songselect-late*`.)
5. **Settings**: apply the type scale (26 px labels vs 10 px control text); explain or remove the "modified"
   dots; make the Lane Profile setting actually apply to playback, or remove it.
6. **AI generation screen** and **Recording** screen: move to `FlowCardLayout` / theme tokens.
7. **Intro**: drop the fake boot text; centre the logo animation.
8. **Visual baselines**: once the user accepts the new look, regenerate all baselines from one code state with
   the now toolbar-deterministic renderer (approved plan) and confirm compare mode passes. Until then the live
   visual comparisons fail against the old baselines by design (see the test record below).
