# ADR-001 — Local desktop boundary

## Status

Accepted for the MVP migration plan.

## Decision

CapelHouse remains a Windows desktop application. React + Vite is embedded in a
Tauri window and is not a hosted web application. Normal operation has no
browser navigation, public HTTP server, cloud account, remote database or
internet dependency.

Tauri owns the native window and the Python child-process lifecycle. React owns
presentation and user intent. Python remains the authority for filesystem,
metadata, BPM analysis, route validation, persistence and file movement.

## Consequences

- Vite is a development/build tool, not a production runtime requirement.
- A Python sidecar is packaged with the desktop application.
- JSON-lines IPC is preferred over an internal HTTP server for the first bridge.
- Large audio files never cross the JSON IPC boundary.
- The old Qt UI remains available until workflow parity is proven.
