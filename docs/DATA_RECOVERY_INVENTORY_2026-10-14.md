# Data recovery inventory — 2026-10-14

## Main finding

The user reconnected the external drive, now **D: `Cold_Raw_Data`**. The original
`D:\data\raw` collection survived. **All 118,353 source-qualified file references
in ten surviving provenance inventories exist and are nonempty.** This supersedes
the earlier conclusion that raw source audio was missing from the connected PC.
It does not prove that every historical download or processed training file survived.

The drive was inventoried read-only: 267,775 files, 1,278,612,715,669 logical bytes.
No data was moved, deleted, restored in place, or written to D: or F:.

## Source evidence

The reference counts below concern the selected historical ingestion manifests,
not every file in each raw folder. All referenced paths are present and nonempty.
Full means every unique hash-bearing path in that source's selected provenance;
it does not mean every additional file in the directory was hashed.

| Source under D:\data\raw | Referenced files | Integrity evidence |
|---|---:|---|
| E-GMD (`egmd`) | 91,074 | 20/20 sampled hashes match |
| Groove MIDI (`groove_midi`) | 2,240 | Full: 2,240/2,240 hashes match |
| Slakh2100 | 5,124 | 20/20 sampled hashes match |
| ENST-Drums | 318 | Full: 318/318 hashes match |
| Cambridge multitracks | 18,031 | 20/20 sampled hashes match |
| IDMT SMT Drums v2 | 379 | Full: 379/379 hashes match |
| MedleyDB | 48 | Presence only; original provenance has no hashes |
| MUSDB18 HQ | 750 | 20/20 sampled hashes match |
| Signature Sounds | 246 | Full: 246/246 hashes match |
| Telefunken sessions | 143 | Full: 143/143 hashes match |

The initial deterministic sample passed 180/180 checks across nine sources.
The subsequent full checks passed 3,326/3,326; these overlap the initial sample.
MedleyDB contents and the remaining large sources have not received full integrity
or audio-decoding checks. Presence is not a claim of annotation quality or rights.
Machine-readable detail: [data-recovery-ledger-2026-10-14.json](data-recovery-ledger-2026-10-14.json).

## Additional survivors and unresolved checks

- `D:\cold_storage\datasets\star_drums\STAR_publication`: 42,922 files,
  181,354,709,984 bytes, including 30,517 FLAC and 6,185 MIDI files. All 350 empty
  annotation TXT files have companion MIDI with zero positive note-on events and
  a decoded, silent 1.5-second resynthesized drum stem. They are internally consistent
  empty examples, not evidence that the original music contained no drums. Handle
  their short silent stem duration explicitly. Some validation/test accompaniment is deliberately
  absent under the bundled distribution instructions. STAR uses resynthesized drums
  with real accompaniment; its labels do not establish manually verified original-song
  transcription. Per-track license restrictions apply. Historical ingestion is unproven.
- `D:\cold_storage\datasets\lakh_midi\lmd_full.tar.gz`: 1,768,163,879 bytes.
  **Damaged/incomplete:** gzip fails before its end marker. A first tar listing
  found 16,257 members, but the last failed the original filename MD5 check.
  Salvage preserved **16,256 checksum-matching files**, 547,301,634 source bytes,
  in a new ZIP on C:, with every entry read back and SHA-256 verified. An aligned
  header scan and subsequent name search found no additional members beyond the
  damage. The entire damaged archive was also copied and hash-verified on C:.
  Of 50,722 files selected by the historical synthesis list, 4,592 are in the
  salvage and 46,130 are absent from it. The [published full release](https://colinraffel.com/projects/lmd/)
  has 176,581 files and includes invalid MIDI; 94 salvaged originals lack an MThd
  header (16 of those have RIFF/RMID wrappers, so a missing MThd at byte zero alone
  does not prove corruption). Byte identity is not a claim of valid musical annotation.
  A separate 46-file extracted subset was preserved and ZIP-verified; 44 pass their
  filename MD5 checks and add to the salvage. Combined, **16,300 checksum-matching
  MIDI files** cover **4,602/50,722** historical synthesis selections. Two extracted
  files fail their filename checks and are preserved as evidence, not trusted inputs.
  A separate rare-drum event JSONL also survives on D:.
  Its 816,823,199 bytes and 819,858 newline records are now archived and read-back
  hash-verified on C: together with STAR's license/mapping/readme metadata:
  `external-annotation-metadata.zip` (34 files, 818,422,081 original bytes).
- `D:\cold_storage\runs`: 49 model checkpoint files totaling 3,752,706,388 bytes.
  These contain **43 unique contents**, all newly copied to C: and hash-verified,
  totaling 3,351,576,336 bytes. The six remaining filenames refer to identical
  already-copied contents. All 49 manifest copy references were rechecked successfully.
  No old model pickle was loaded; preservation does not establish model quality.
- **D: Recycle Bin contains 50,209 WAV files**, plus two metadata files, totaling
  1,240,792,723 bytes. Names under `$RV1HGY3\train\audio` resemble old generated
  training clips (`UUID__hihat_closed.wav`, `UUID__ride_bow.wav`, etc.). These are
  confirmed project survivors: **all 50,209 event IDs match E-GMD provenance**,
  covering 163 source recordings. Of these, 46,192 filenames occur in the surviving
  indices (42,058 training, 4,134 validation); all their 13-class integer labels
  agree with the filename labels. The other 4,017 are absent from those current
  indices. Generic `tom` filenames correspond to fine `tom_high`/`tom_low` event
  labels in 238 cases. **Preservation passed for all 50,209 files**: 1,240,792,530
  source bytes in an 875,642,449-byte ZIP, with every entry read back and SHA-256
  verified. All 50,209 then decoded successfully as finite, non-silent 44.1 kHz mono
  PCM16 audio; durations range from 0.11494 to 0.28002 seconds. Evidence is under
  `external-survivors-preserved`, including manifest, verification, and audio health.
  One separate `$I` entry names `E:\data\TO_DELETE` and `$RMM5JGX`; do not assume
  that metadata describes the `$RV1HGY3` audio. Do not empty or restore this bin in place.
- No `.npy` or `.npz` files were found in the D: metadata inventory. The old
  `F:\datasets` processed layout remains absent. The exact lost processed-file count
  cannot be established from surviving records; the Recycle Bin clips may recover
  a portion. Raw source recovery makes regeneration possible if measurements justify it.

**Split-quality finding:** the 163 source recordings correspond to 18 distinct MIDI
SHA-256 values. Five identical MIDI performances appear in both train and validation,
despite different rendered-audio filenames. All 163 current MIDI hashes were freshly
checked against the original provenance and matched. This is verified performance
overlap in the surviving indices, not an estimate of overlap across the whole corpus
or proof that every saved checkpoint trained on these exact indices. Future splits
must group the underlying performance across kit renders, and across E-GMD/GMD
where applicable; separating audio filenames alone is insufficient.

On C:, surviving manifests, indices, personal notes, models, and application audio
were preserved. Ten canonical event manifests total 17,400,306 rows; these include
session/stem records as well as note events and must not be summed as labeled hits.
13-class train/validation indices contain 16,223,363 rows; velocity/21-class indices
contain 16,282,047. Their integer label mappings differ. Neither count establishes
that its referenced generated audio remains available.

A surviving Lakh event JSONL on C: is 29,698,515,148 bytes with 158,432,479 newline
records. Its bytes are preserved and hashed, but all records have not been validated.
The old synthesis list names 50,722 unique selected MIDI files; compare those names
with actual recovered archive members before rebuilding.

## Search coverage and preservation

Private evidence is under
`C:\Users\10ros\BeatSight-Recovery\2026-10-13\data-discovery`.

- C:/E:/F: metadata inventory: 5,739,406 files and 661,300 directories, including
  ignored files. It recorded 194 permission failures and 258 reparse exclusions.
  D: was added after connection; its two exclusions were protected system locations.
- Ubuntu WSL: 365,895 native files inventoried; symlinks, virtual/mounted filesystems,
  and inaccessible paths were excluded and logged. No project raw collection found.
- 635 ZIP directories and 162 other large archive containers were inspected, with
  failures recorded. Not every virtual disk, custom container, encrypted archive,
  cloud-only file, or inaccessible system location was opened. This is a broad
  accessible-PC inventory, not proof that every byte on every device was searched.
- Gmail is connected again. Fifteen saved query pages produced 210 distinct candidate
  messages, and 14 relevant threads were read and privately preserved. Queries used
  `in:anywhere` across all dates, including archived mail, Spam, and Trash. This is
  a topical mailbox search, not a claim to have read every unrelated email.
  The three post-restart pages added direct vendor-domain and custom-permission
  searches; they found no new developer permission threads.
- Original ENST access and MedleyDB v1/v2 approvals survive in Gmail. The Signature
  Sounds order lists 15 ZIP packs. Expired download URLs need not be used to recover
  the 246 ingested samples now verified on D:. Emails, credentials, and private URLs
  remain outside Git. No messages were sent or mailbox contents changed.
- All 15 Signature Sounds order-pack names have corresponding directories on D:.
  Some packs retain nested ZIPs rather than fully extracted audio. This is pack-name
  coverage, not a claim that every archive member is complete or usable. The 246
  historically ingested samples are independently hash-verified as above.
- `additional-survivors.zip`: 328 entries, 32,031,415,606 original bytes, compressed
  to 3,402,387,931 bytes; all archive entries were read back and hash-verified.
  This adds application audio/charts, dataset research, and Lakh records to the
  previous model/provenance and annotation archives. Originals already on C: are
  not protected by an independent-device backup. D: is a separate USB disk from
  C:'s NVMe disk, so verified D-to-C copies protect those particular artifacts on
  another device. The bulk raw collection still needs its own second copy before
  any reorganization.

## Rights and which data to use

Access approval or a download receipt does not establish custom training,
redistribution, or commercial rights. Historical `legal`/license summaries are
unverified claims unless supported by an original agreement or applicable terms.
The recovered ENST access email is not a separate commercial-use agreement; the
[primary ENST license](https://perso.telecom-paristech.fr/grichard/ENST-drums/ENST_Drums_License.pdf)
requires additional consent for commercial uses. STAR combines sources with
noncommercial/share-alike and per-track terms; keep those restrictions attached.
The inherited license summaries and download guide now carry a prominent recovery
notice so their unsupported blanket commercial-clearance claims are not mistaken
for current findings. Historical text is preserved underneath.

Use the recovered data selectively after finding a measured failure:

1. **Evaluation first:** expand the manually checked full-song test set, with known
   exclusion from training and explicit tom/brush/ghost-note/cymbal coverage.
   [MDB Drums++](https://github.com/xavriley/MDBDrumsPlusPlus) offers corrected
   annotations, but previous evaluation songs may overlap historical training.
   The existing ADTOF comparison is diagnostic, not independent generalization proof.
2. **Timing and dynamics:** use recovered [Groove MIDI](https://magenta.tensorflow.org/datasets/groove),
   [E-GMD](https://magenta.tensorflow.org/datasets/e-gmd), ENST, and IDMT for targeted
   checks. Avoid random clip splits that leak the same song, kit, or performance.
3. **Full mixtures and articulations:** recovered STAR and Slakh are candidates.
   Validate label mappings and synthesis-domain limitations first. The
   [STAR paper](https://reference-global.com/article/10.5334/tismir.244?tab=article)
   describes the resynthesis design; the recovered bundle includes its licenses.
4. **Separation context:** Cambridge, Telefunken, [MedleyDB](https://medleydb.weebly.com/),
   and [MUSDB](https://sigsep.github.io/datasets/musdb.html) provide real music and
   stems, not automatic note-onset ground truth. Respect shared-song overlap.
5. **Additional candidate only if needed:** [StemGMD](https://zenodo.org/records/7860223)
   supplies isolated instruments but expands to terabyte scale. Do not download it
   broadly before a separation bottleneck is established. General sound-event and
   piano datasets mentioned in old plans are not a substitute for drum-note labels.

For evaluation preflight, 25 files totaling 68,763 bytes were acquired from the
MDB Drums++ repository at revision `13aa81750e74810aec7ca17a75fe438961613d82`:
23 MIDI annotations, README, and metadata, all checked against Git blob hashes.
Seven complete benchmark recordings (454.93 seconds, 2,461 annotated hits) are
prepared locally for a diagnostic including 81 tom hits and 32 other-percussion
hits. Five mixes reuse local survivors/earlier evaluation copies; two small mixes
were fetched from the pinned original MDB Drums source. This is a bounded
evaluation addition, not a training-corpus download. Both models have now run on
all seven recordings; see [the measured comparison](TRANSCRIPTION_DIAGNOSTIC_2026-10-14.md).

No broad redownload or retraining has been started. The executable recovery baseline
and its measured transcription limitations remain in `RECOVERY_AUDIT_2026-10-13.md`.

## Continuation after the restart

The user returned after reboot. D: was verified as `Cold_Raw_Data`, same size and
free space. Lakh damage/salvage, STAR empty-label consistency, Recycle Bin source
matching, and performance overlap are now resolved to the extent described above.
Recycle Bin archival preservation, all clip decoder checks, and all 49 checkpoint
copy references have now passed. A separate extracted Lakh subset is preserved too.
The expanded diagnostic and the evaluation plan identify the next measured quality
work. A full copy of the terabyte-scale raw collection has not been made; the
processed F: dataset and much of Lakh remain incomplete. No claim is made that
every historically downloaded byte has been recovered.
Keep D: and F: read-only. Do not run legacy cleanup/migration/restore scripts.
