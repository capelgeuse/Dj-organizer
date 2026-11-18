# P0 decisions and stop conditions

## Frozen ownership

- Tauri: native window, permissions, sidecar start/stop and crash visibility.
- React/Vite: layouts, navigation, selection, keyboard intent, visual state and
  rendering only.
- Layer A: immutable contracts, error vocabulary and documented decisions only.
- Python: scanning, metadata, BPM, route validation, JSON settings, filesystem
  moves and operation receipts.

## Explicit stop conditions

Stop before implementation if any of these are required:

- a second filesystem mutation authority in React or Rust;
- a remote database or hosted API without a separate product decision;
- sending full audio binaries over IPC;
- overwriting a destination by default;
- scanning configured destinations as intake;
- treating a missing BPM or genre as a guessed value;
- removing Qt/Tkinter before real workflow parity;
- a Python sidecar lifecycle that cannot prove shutdown and no orphan process.
