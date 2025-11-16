# Live Input Regression Checklist

> **Status (Nov 2025):** Live microphone gameplay has been de-scoped for now. This checklist is kept solely for historical reference until the experiment returns.

Use this pass before shipping any changes impacting microphone gameplay. Run through every item on each supported platform configuration when possible.

## Quick Pass (5 min)
- [ ] Launch desktop build and open **🎤 Live Input**.
- [ ] Confirm calibration overlay appears for first-time users; run ambient + kick steps.
- [ ] Toggle listening (`M`) and ensure HUD updates instantly.
- [ ] Strike kick/snare/hihat/tom/cymbal and watch for correct lane classification.
- [ ] Pause (`Esc`) and resume; meters should freeze and recover cleanly.
- [ ] Close + relaunch; ensure calibration persists and no warnings show.
- [ ] Rename calibration profile; verify next launch asks to recalibrate.
- [ ] Disconnect mic mid-run and confirm capture stops without crash.

## Environment
- Confirm default input device is the intended microphone and note the device name.
- Verify `beatsight.ini` contains no residual `MicCalibration*` entries from prior runs (delete to simulate first-time flow).
- Launch via `dotnet run` and confirm the main menu renders without audio/GL errors.

## Calibration Flow
- Enter **🎤 Live Input** from the main menu; ensure the calibration intro appears if no profile exists.
- Complete ambient noise, kick, snare, hi-hat, tom, and cymbal steps; watch for guidance text updates between stages.
- Confirm the workflow rejects silent or clipped takes (overlay should remain on the current step when the sample is invalid).
- After finishing, exit to menu and re-enter; the overlay should stay hidden and `Recalibrate Mic` button should be available.

## Runtime Behaviour
- Toggle listening with `M` and confirm status text reflects Listening/Paused states immediately.
- Trigger each drum type and observe lane-specific meter flash + estimated drum label in the HUD.
- Hit detection should respect `MinTimeBetweenOnsets` (simulate rapid rolls to ensure no double-triggering).
- Pause/resume gameplay; verify meters freeze while paused and resume smoothly afterwards.

## Persistence & Recovery
- Close the application, reopen, and verify calibration persists (check timestamp in overlay tooltip if present).
- Delete or rename the stored profile file; start the mode and confirm the overlay forces recalibration.
- Change default recording device in the OS mid-session, then re-open Live Input; ensure status text warns and listening stops until recalibration.

## Failure Handling
- Induce microphone disconnect while listening; app should stop capture gracefully without crashing.
- Force ambient noise above 80 dB during calibration to ensure the step auto-retries with warning messaging.
- With calibration complete, feed white noise and ensure detector prefers `Unknown` rather than misclassifying every frame.
