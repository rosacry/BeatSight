# E-drum Openness Calibration

This directory stores vendor-specific CC4→openness normalization curves used by
`normalize_openness.py`.

## Adding a New Device

1. Capture a calibration session that sweeps the hi-hat controller from fully
   closed to fully open while recording raw CC4 values and measuring acoustic
   openness via the labeling UI.
2. Compute averaged breakpoints (raw CC4 → normalized openness) and note any
   systematic offsets required to match acoustic perception.
3. Append an entry to `openness_curves.json`:
   ```json
   {
     "YourVendor": {
       "ModelName": {
         "curve_id": "yourvendor_model_cc4_v1",
         "offset": 0.0,
         "breakpoints": [
           {"raw": 0, "normalized": 0.0},
           {"raw": 30, "normalized": 0.2},
           {"raw": 127, "normalized": 1.0}
         ],
         "notes": "Document the calibration procedure, pads, and environmental factors."
       }
     }
   }
   ```
4. Run `python normalize_openness.py --events annotations/events.jsonl --output annotations/events_calibrated.jsonl --dry-run`
   to confirm the new curve is detected and applied.
5. Commit the updated JSON and reference the new `curve_id` in provenance
   (`openness_curve_id`) when ingesting events from that device.

## Versioning

- Increment the suffix (`_v1`, `_v2`, …) when a curve is re-measured.
- Preserve old entries so historical events remain reproducible; downstream
  tooling uses `curve_id` to locate the correct mapping.
