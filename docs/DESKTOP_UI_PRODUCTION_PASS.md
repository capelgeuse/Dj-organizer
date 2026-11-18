# Desktop UI Production Pass

**Branch:** `feat/desktop-ui-production-pass`  
**Base:** `4736f22d26d73b715872bf71805257a366f89c87`

## Outcome

CapelHouse keeps the existing offline-first Python authority and Tauri bridge, but the working screen now reads as a desktop DJ utility rather than a miniaturized web dashboard.

- **Player Surface:** readable library and inspector on 27-inch 4K displays; W/S selection, A/D five-second seek, and physical numpad routing.
- **Designer Surface:** the visual scale is isolated in `frontend/src/production-pass.css`; Routing Matrix structure remains a reusable component rather than nine custom buttons.
- **Observability Surface:** the root `.app-shell` exposes `data-ui-revision="desktop-production-pass-r1"`, keyboard mapping has a pure unit test, and the Windows sidecar build performs a real JSON-lines `ping` before Tauri packaging.

## Runtime path

```text
W/S
→ DesktopKeyboardController clicks the same visible TrackRow used by the mouse
→ existing React selection state
→ selected TrackRecord read model

A/D
→ DesktopKeyboardController clicks the existing rewind/forward transport control
→ AudioControls seek path
→ HTML audio element + preview position state

Numpad 1–9
→ DesktopKeyboardController clicks the matching existing Routing Matrix cell
→ preview pulse only when bridge is unavailable
→ otherwise existing handleMove()
→ desktop bridge
→ Python classifier/file authority
```

Preview mode never reports or simulates a successful file move. It only confirms the key/cell relationship visually.

## Visual contract

- Routing slots use physical numpad order: `7 8 9 / 4 5 6 / 1 2 3`.
- The whole slot is interactive, but visual hierarchy is number → route label → destination name; no CTA copy is repeated inside the nine cells.
- Gold is reserved for focus, active work, recent confirmation, and selected content.
- Operational microcopy has a 10px floor at normal desktop scale and scales modestly at wide/4K viewport widths.
- The main library remains dense; the pass does not redesign the sidebar, queue model, Files tab, Notes persistence, or backend domain.

## Keyboard acceptance

| Input | Result |
|---|---|
| `W` | Previous visible track and keep it in view |
| `S` | Next visible track and keep it in view |
| `A` | Rewind five seconds through the same seek function as the transport |
| `D` | Forward five seconds through the same seek function as the transport |
| `Numpad 1–9` | Route through the existing move intent; held-key repeats are ignored |
| `Numpad 0` | Current Crate; deliberately non-mutating |

Shortcuts do not fire while typing in inputs, textareas, selects, content-editable fields, or an active modal. Ctrl/Alt/Meta combinations remain available to the OS/application shell.

## Validation

From `frontend/`:

```powershell
npm ci
npm run lint
npm run test:ui
npm run build
```

Visual checks:

1. Inspect `.app-shell.dataset.uiRevision`; it must be `desktop-production-pass-r1`. This distinguishes the current source from a stale Vite or packaged build.
2. Capture the working screen at 1920×1080, 2560×1440, and the effective Windows viewport used on the 4K monitor.
3. Confirm all route labels remain single-line and no `Assign to Route` copy exists.
4. In Local Preview, confirm W/S, A/D and numpad feedback work while file mutation remains unavailable.
5. With the native bridge ready, route one disposable track by click and a second by numpad; both must use the same success/error/refresh behavior.

## Windows package

From repository root in Windows PowerShell:

```powershell
.\packaging\build_desktop.ps1
```

The build now:

1. installs the locked frontend dependencies;
2. runs the UI tests;
3. creates a one-file `backend_bridge.exe`;
4. sends it a real `ping` over stdin/stdout;
5. copies the target-triple sidecar into Tauri's expected binaries folder;
6. runs the Tauri production bundle.

Final acceptance still requires a clean Windows account with no Python installed and a disposable local music library. Signing, auto-update, and release automation remain deferred.
