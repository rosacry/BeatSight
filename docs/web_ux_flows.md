# BeatSight Web & Mobile UX Flows

_Last updated: 2025-11-12_

## 1. Information Architecture
```
Home / Intake
├─ Verified Map Detail
│  ├─ Preview Player
│  ├─ Download / Export (.bsm)
│  └─ Launch Editor
├─ Unverified Map Detail
│  ├─ AI Status (Queued / Processing / Complete)
│  ├─ Request Verification
│  └─ Submit Fix
├─ Editor (Timeline-Lite)
│  ├─ Note Adjust
│  ├─ Comment Marker
│  └─ Submit Fix
├─ Karma Dashboard
│  ├─ Stats & Perks
│  └─ Leaderboards
├─ Verification Queue
│  ├─ Pending Fixes
│  ├─ Diff Playback
│  └─ Decision Panel
└─ Profile / Library
   ├─ Saved Maps
   ├─ Notifications
   └─ Subscription
```

## 2. Primary Flow — Drag & Drop Intake
1. **Landing**: Hero drag area with CTA, list of recently verified maps, community activity highlights.
2. **On Drop**:
   - Show inline progress bar (audio upload → fingerprint → lookup).
   - Display spinner with text "Identifying your song…".
3. **Lookup Result**:
   - **Found Verified Map**: Show card with song art/info, quality score, karma stats.
     - Actions: `Play Preview`, `Download Map`, `Open in Editor`, `Sync to Desktop`, `Request Alternate Difficulty`.
   - **Not Found**: Show metadata form (title, artist, tags) with auto-filled suggestions; let user edit or accept.
4. **AI Queue Confirmation**: Explain estimated wait (<5 min), show user quota usage, upsell pro if needed.
5. **Completion Notification**: Inline toast if user stays, plus email/WebPush; map card becomes accessible with status `Unverified` and quick call-to-action `Review & Request Verification`.

### Mobile Variations
- Swap drag/drop for large `Select Audio` button + OS file picker.
- Progress UI becomes full-width sheet with compact status text.
- Use bottom sheets for metadata form and AI confirmation; keep interactions thumb-friendly.

## 3. Secondary Flow — Unverified Map Review
1. User opens map detail (web/mobile).
2. Header badges: `Unverified`, `AI Generated <timestamp>`, karma summary.
3. Inline player with toggle `3D Lane View` ↔ `2D Scroll View` and beatmap timeline preview.
4. Buttons: `Request Verification` (if qualifies), `Submit Fix`, `Leave Feedback`.
5. Comments thread surfaces previous feedback; encourage collaborative edits before verification request.

## 4. Editor (Timeline-Lite)
- **Layout (Desktop)**:
  - Left panel: track inspector (metadata, difficulty, instruments).
  - Center: vertical timeline with lanes; supports pinch zoom (trackpad) and scroll.
  - Right: comment thread, diff preview vs canonical.
  - Footer: transport controls (play/pause, speed slider, metronome toggle).
- **Layout (Mobile)**:
  - Full-width timeline with horizontal lane view, pinch zoom, long-press to move notes.
  - Collapsible overlays for metadata and comments.
  - Floating action button `Submit Fix` -> modal for summary + optional attachments.
- **Key Interactions**:
  - Tap note → detail popover (time, lane, velocity) with quick-edit controls.
  - Drag to reposition; snap toggle for rhythmic grid.
  - Add comment marker to highlight problematic regions.

## 5. Verification Dashboard
1. Entry: `Verification` tab visible to users with Verifier karma.
2. List view with filters (instrument, genre, age, fixer karma, status).
3. Card content:
   - Song info, fixer notes, diff highlights (note count changes, timing adjustments).
   - Quick actions: `Preview A/B`, `View Comments`, `Approve`, `Request Changes`, `Reject`.
4. Decision modal requires feedback notes; display karma rewards/penalties before confirmation.
5. Post-action snackbar confirms karma adjustments; map state updates immediately.

## 6. Karma & Perks Experience
- Profile page shows karma breakdown, recent actions, upcoming perk thresholds.
- Leaderboard accessible via `Community` tab; filters by genre, timeframe, region.
- Tooltip overlays on actions (e.g., "Approve fix to earn +50 karma") to reinforce incentives.

## 7. Error & Edge Cases
- **Fingerprint Fail**: Offer manual metadata entry and optional re-upload; show tips on supported formats.
- **AI Queue Full**: Display estimated start time, invite user to subscribe for priority access, allow leaving email for notification.
- **Verification Backlog**: Badge pending count on `Community` nav; send targeted prompts to verifiers with idle karma.
- **Permission Denied**: When user lacks karma for action, show modal describing requirements and how to earn.

## 8. Accessibility
- All interactive elements reachable via keyboard (desktop) and large hit targets (mobile).
- Provide captions for audio previews; show timeline markers with high-contrast color palette.
- Implement ARIA live regions for async status updates (uploads, queue states, verification outcomes).

## 9. Future Enhancements
- Collaborative editing sessions (multi-user presence indicators).
- Tutorial overlays guiding new fixers/verifiers through first action.
- Integration with desktop app: "Send to Desktop" button triggers deep link.
- Optional dark/light themes synchronized with OS preference.
