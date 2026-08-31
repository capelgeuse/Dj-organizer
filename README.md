# CapelHouse

Local Windows desktop music organizer.

The modernization uses React + Vite inside Tauri while keeping Python as the
local authority for filesystem scanning, audio metadata, BPM analysis, route
configuration and file movement. It is not a hosted web application.

## Current development shape

```text
frontend/                 React + Vite UI
frontend/src-tauri/       Tauri desktop shell and Python process owner
bridge/local_bridge.py    JSON-lines Python bridge
core/                     local scanning, metadata, routes, sorting and moves
architecture/             Layer A contracts and error vocabulary
```

## Development prerequisites

- Windows: Node.js, Rust, WebView2 and Python for development/build only.
- Python packages: `requirements.txt` for Qt fallback, or
  `packaging/requirements-sidecar.txt` for the headless sidecar.

Run the current frontend shell:

```powershell
cd C:\Users\user\Documents\GitHub\Dj-organizer\frontend
npm install
npm run dev
```

Run the complete desktop development runtime after installing Rust/Tauri
prerequisites:

```powershell
npm run tauri:dev
```

The desktop runtime starts one Python sidecar owned by Tauri. The user does not
visit a localhost URL manually.

## Packaging

From a Windows PowerShell terminal:

```powershell
cd C:\Users\user\Documents\GitHub\Dj-organizer
.\packaging\build_desktop.ps1
```

See `docs/LOCAL_DESKTOP_UI_MODERNIZATION_IMPL_PLAN.md` and
`docs/LOCAL_REAL_LIBRARY_CHECKLIST.md` for the implementation gates.
