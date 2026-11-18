# P11 — Local real-library validation checklist

This checklist is executed only against a disposable copy or the user's local
library. Never commit the library path, filenames, metadata dump, artwork or
logs.

## Clean-machine gate

- [ ] Install the generated Windows artifact without Node or Python installed.
- [ ] Disconnect the network.
- [ ] Launch `CapelHouse.exe` without a browser window.
- [ ] Confirm the Python sidecar starts and `Bridge ready` appears.
- [ ] Close the app and verify no Python child remains.

## Scope and queue

- [ ] Select a root containing direct unsorted audio files.
- [ ] Confirm `UNSORTED` is included only when configured.
- [ ] Confirm generated destination folders do not re-enter the intake queue.
- [ ] Confirm unsupported files do not break the scan.
- [ ] Confirm a large library remains responsive and artwork is lazy.

## Metadata and playback

- [ ] Verify title, artist, BPM, genre and duration from real metadata.
- [ ] Verify missing metadata is shown as `Unknown`/`—`.
- [ ] Verify embedded/adjacent artwork renders locally.
- [ ] Verify only the playing row shows the play overlay.
- [ ] Verify W/S selection and A/D five-second seek.

## Classification safety

- [ ] Configure one route with the native folder picker.
- [ ] Confirm the route is persisted relative to the selected root.
- [ ] Move one track with mouse and one with Numpad.
- [ ] Confirm the source is removed and the destination exists.
- [ ] Confirm no copy remains in the unsorted root.
- [ ] Confirm an existing destination returns `DESTINATION_EXISTS` without overwriting.
- [ ] Confirm Undo restores the source safely.
- [ ] Confirm missing BPM uses `BPM UNKNOWN` and does not invent a number.
- [ ] Confirm a destination outside the root is rejected.

## Persistence and recovery

- [ ] Restart the app and confirm root/routes persist in `%APPDATA%\\CapelHouse`.
- [ ] Interrupt a scan and confirm the UI recovers without changing files.
- [ ] Force sidecar exit and confirm the UI shows a recoverable bridge error.
- [ ] Confirm no cloud/network call is required for normal operation.

## Evidence

Record only aggregate results, timings and error codes. Do not record private
paths, track names, metadata, artwork or audio content.
