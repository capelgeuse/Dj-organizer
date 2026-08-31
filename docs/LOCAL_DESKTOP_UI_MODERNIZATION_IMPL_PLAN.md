# Progress

- [x] P0 — Auditar la arquitectura actual y congelar ownership del dominio
- [x] P1 — Establecer el workspace React + Vite
- [ ] P2 — Establecer el shell de escritorio Tauri
- [ ] P3 — Establecer el bridge Python ↔ desktop
- [ ] P4 — Probar una consulta backend real end-to-end
- [ ] P5 — Probar una mutación backend real end-to-end
- [ ] P6 — Construir shell y navegación de la aplicación
- [ ] P7 — Migrar la experiencia principal de biblioteca musical
- [ ] P8 — Añadir loading/error/progress de producción
- [ ] P9 — Empaquetar backend Python y dependencias
- [ ] P10 — Producir el distribuible de Windows
- [ ] P11 — Validar el build de producción contra una biblioteca real
- [ ] P12 — Retirar o deprecar la UI reemplazada sólo después de probar paridad

**Goal:** modernizar la interfaz de CapelHouse con React + Vite dentro de Tauri, conservando Python, el filesystem local y la operación totalmente offline como autoridades.

**Execution route:** Sol Medium verificado con `gpt-5.6-sol`, provider `openai-codex`, reasoning `medium`. Esta es una planificación; no autoriza implementación, commit, push ni deploy.

**Repository:** `C:\Users\user\Documents\GitHub\Dj-organizer`

---

# Recommended Architecture

```text
Windows desktop executable: CapelHouse.exe
│
├── Tauri shell
│   ├── window lifecycle
│   ├── native folder/file dialogs
│   ├── secure local asset access
│   ├── keyboard/window integration
│   └── packaged sidecar lifecycle
│
├── React + Vite frontend
│   ├── AppShell / sidebar / toolbar
│   ├── queue and TrackList
│   ├── metadata and artwork presentation
│   ├── audio element / playback controls
│   ├── keyboard command map
│   ├── nine configurable destination actions
│   └── loading/error/progress/undo feedback
│
├── Layer A — Architecture / Contracts
│   ├── immutable DTOs
│   ├── command/result contracts
│   ├── error taxonomy
│   ├── lifecycle rules
│   └── documented design decisions
│
├── Local desktop bridge
│   └── JSON-lines over stdin/stdout in DEV and production
│
└── Python application/domain layer
    ├── library scope and scanning
    ├── Mutagen metadata extraction
    ├── Librosa BPM fallback analysis
    ├── route/preset validation
    ├── atomic filesystem move
    ├── local config/persistence
    └── structured operation results
```

The bridge is intentionally not an HTTP service for the first migration. Tauri
starts one Python child process and communicates with it using JSON-lines. This
keeps the product a desktop application, avoids a manually managed localhost
port, and is compatible with the repository's existing bridge direction.

A local HTTP adapter may be added later only if a concrete Tauri limitation is
proven. It must remain loopback-only and must not become a hosted product.

## Layer A definition

Layer A is the architecture/contract boundary, not a second business authority.
It owns:

- command names and request/response DTOs;
- stable error codes;
- state/lifecycle vocabulary;
- route preset contract;
- source-scope and destination-exclusion rules;
- documented product decisions and ADRs.

Layer A must not scan folders, read metadata, play audio, move files, write
configuration, or mutate the library. Python domain services own those actions.
React consumes Layer A DTOs and never recreates its rules locally.

# Current Repository Findings

## Confirmed entrypoints

| Path | Role | Classification |
|---|---|---|
| `Capelhouse/CapelHouse_Qt.py` | Current Qt desktop UI; scanning, metadata, playback, BPM fallback, category management and file move | Current desktop UI, tightly coupled |
| `Respaldo/Texto_punto_cero.py` | Older Tkinter desktop UI with similar scanning, metadata, playback and copy classification | Legacy compatibility/reference |
| `backend_ui_bridge.py` | JSON-lines prototype with summary, category and playback commands | Intended bridge, currently broken |
| `backend_bridge.py` | Older JSON-lines bridge importing `Texto` | Dead/incomplete path; `Texto.py` is absent |
| `Capelhouse/CapelHouse.spec` | PyInstaller spec for the Qt app; collects `librosa` and `soundfile` assets | Existing packaging donor |
| `Capelhouse/Abrir_CapelHouse.bat` | Windows launcher with a machine-specific Python path | Non-portable launcher |

## Confirmed data and persistence

- The runtime has no SQLite, PostgreSQL, cloud API, ORM, watcher or remote
  persistence in the repository.
- Configuration is JSON. There are three competing locations:
  `configuracion_dj.json`, `Capelhouse/configuracion_dj.json`, and
  `configuracion_dj_punto_cero.json`.
- `Capelhouse/configuracion_dj.json` contains personal paths from another
  machine (`C:\Users\LENOVO` and `E:\Progressive House`). It is not a portable
  default and must not be treated as a valid current library.
- Production configuration should move to a per-user Windows location such as
  `%APPDATA%\\CapelHouse\\config.json`; source-tree JSON remains an import
  fixture/compatibility input.
- No new remote database is justified. JSON remains sufficient for MVP settings,
  route presets and the last selected root. An operation ledger may be added
  only for undo/recovery and remains local.

## Confirmed metadata/audio behavior

- `Mutagen` reads duration, embedded artwork, BPM keys (`bpm`, `tbpm`, `tempo`)
  and genre.
- `Librosa` is used as a BPM fallback for up to the first 90 seconds.
- `pygame` is used by the desktop UIs for playback.
- The React UI should use an HTML audio element backed by a Tauri-safe local asset
  URI. Audio bytes must never travel through JSON IPC.
- Repository search found no direct `ffmpeg` or `ffprobe` integration. Packaging
  must still inspect the resolved Librosa/soundfile codec requirements before
  choosing a final PyInstaller mode.

## Confirmed sorting/classification behavior

- Qt and the legacy UI scan recursively and sort by filename using
  `casefold()`/`lower()`.
- The current UI displays filename, BPM and duration, but does not render a
  normalized artist/title metadata model.
- Qt moves a classified file with `shutil.move()`.
- The legacy UI copies it with `shutil.copy2()`.
- `backend_ui_bridge.py` copies it and builds a different destination path from
  the Qt app.
- The user decision for the new product is authoritative: classification moves
  the file. Copying is not the target behavior.

## Confirmed runtime blockers

- `backend_ui_bridge.py:9` imports `Texto_punto_cero` from the repository root,
  while the file exists at `Respaldo/Texto_punto_cero.py`.
- Even with `PYTHONPATH=Respaldo`, the bridge imports Tkinter through the legacy
  UI and fails in the inspected WSL environment because `tkinter` is absent.
- `backend_bridge.py:6` imports the missing `Texto` module.
- No frontend, Vite project, Tauri project or HTTP server exists yet.
- No automated test suite was found.
- The committed `.gitignore` already anticipates `frontend/`, Tauri targets and
  a packaged `backend_bridge.exe`; these are useful intent signals but not
  existing implementation.

# Authority Boundaries

| Concern | Canonical owner | React role | Bridge role | Forbidden shortcut |
|---|---|---|---|---|
| Source root and source scope | Python `LibraryScope` service | Show/edit through intent | Validate and route command | React scanning the filesystem |
| Track identity/path resolution | Python backend | Hold opaque `trackId` | Pass ID only | Sending full audio files |
| Metadata/BPM/artwork | Python metadata service | Render DTO | Serialize small metadata and safe artwork URI | Duplicating Mutagen/Librosa rules in TS |
| Queue ordering | Python read model plus explicit frontend view sort | Request sort mode, render order | Return ordered page/chunk | Sorting different fields independently in backend/UI |
| Route presets 1–9 | Layer A contract + Python config authority | Render labels and shortcuts | Validate target inside root | Free-form path concatenation in React |
| File move | Python classifier/filesystem service | Request move and show result | Return before/after paths and status | React or Rust directly moving files |
| Audio playback | Local file/native asset layer | Control `<audio>` | Resolve safe track URI if needed | Base64 audio through IPC |
| Settings persistence | Python config service | Bind forms | Read/write validated config | Multiple JSON authorities |
| Window lifecycle | Tauri | Presentation state only | Receive shutdown notification | Orphan Python process |
| Undo/recovery | Python operation ledger, if approved | Trigger inverse command | Validate source/destination | UI-only fake undo |

# Product Decisions Frozen for the MVP Plan

These are explicit recommended MVP defaults, not hidden assumptions. P0 must
record them in Layer A; P3/P5 stop if Product/Mono changes any of them.

1. **Root:** the selected folder is the library root. Direct audio files in that
   root are unsorted. A child folder named `UNSORTED` is an additional explicit
   intake pool and is scanned recursively.
2. **Destination exclusion:** generated/configured destination folders are not
   scanned as intake. The backend owns this exclusion, not filename heuristics.
3. **Move:** pressing a destination action moves the file; it does not copy it.
   The UI must show an immediate result and offer a last-operation undo path.
4. **Conflict:** if the destination exists, do not overwrite or delete either
   file. Leave the source in the queue and show `DESTINATION_EXISTS`.
5. **BPM:** read metadata first; use Librosa fallback locally; if still absent,
   classify into an explicit `BPM UNKNOWN` bucket with a visible warning rather
   than inventing a BPM.
6. **Genre:** display metadata genre when present. A route preset may specify a
   destination genre/folder; missing genre is shown as `Unknown`, never inferred
   from filename.
7. **Key map:** `W` previous track, `S` next track, `A` rewind five seconds,
   `D` fast-forward five seconds. Use `KeyboardEvent.code` and do not capture
   shortcuts while a text field/dialog is actively editing.
8. **Numpad:** `Numpad1`…`Numpad9` perform the configured route immediately after
   the selected track is stopped safely. No confirmation modal in the hot path;
   use visible undo/error feedback instead.
9. **Default routes:** seed slots from the existing configured genres where
   available; slot 9 defaults to `Needs Review`. Every slot is editable in the
   UI and resolves only inside the selected root.
10. **Duplicate names:** same-name destination conflicts are blocked. A later
    product decision may add rename/suffix policy; it is not silently guessed.
11. **Scope:** no duplicate finder, cloud sync, remote account, playlist system,
    waveform editor or music-content upload in this migration.

# Runtime Architecture

## Read flow

```text
React requests LOAD_LIBRARY
  → Tauri invoke/bridge client
  → Python sidecar receives one JSON request
  → Layer A validates request
  → LibraryScope scans only allowed intake paths
  → MetadataService normalizes TrackRecord values
  → Python returns one structured response
  → React stores view model and renders TrackList
```

## Mutation flow

```text
Numpad button or mouse route click
  → React sends MOVE_TRACK(trackId, routeId)
  → Python resolves trackId from backend scope
  → revalidates source exists and destination is inside root
  → stops/flushes any backend-owned handle if applicable
  → creates destination directories
  → atomically moves source when safe
  → appends operation receipt
  → returns MOVED / DESTINATION_EXISTS / INVALID_ROUTE / ERROR
  → React removes moved item and shows result/undo action
```

## Python process lifecycle

- Tauri is the only process owner.
- On app start, Tauri resolves the DEV command or packaged sidecar path,
  starts Python with piped stdin/stdout/stderr, and waits for a `READY`/`ping`
  response before enabling library actions.
- Each request has an ID. Responses must echo the ID, allowing out-of-order
  background metadata jobs without mixing results.
- EOF, non-zero exit or malformed response marks the bridge unavailable and
  disables mutations while leaving the UI open with a recoverable error.
- On Tauri close, send `shutdown`, wait a bounded interval, then terminate the
  child if needed. The plan must include a Windows process-tree cleanup test.
- No Python child may bind a port in the MVP. No orphan process is acceptable.

# Development Runtime

```text
npm run tauri dev
  ├── Vite dev server, internal only
  ├── Tauri development window
  └── Python source bridge process
```

The developer may see a Vite URL in logs, but the user opens only the Tauri
window. The product is not developed as a browser-hosted application.

Proposed development commands after P1–P3:

```powershell
cd C:\Users\user\Documents\GitHub\Dj-organizer
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm install
npm run tauri dev
```

The exact Tauri script and Python sidecar command are frozen in P2/P3 rather
than guessed before the workspace exists.

# Production Runtime

```text
Installed CapelHouse.exe
  → Tauri loads bundled frontend/dist
  → Tauri starts bundled Python sidecar
  → Python reads local config and local music paths
  → React renders local DTOs
```

Normal operation requires no Node.js, Vite, Python installation, browser, web
navigation, internet connection, cloud account or remote database.

# Python Integration Strategy

Use JSON-lines over stdin/stdout for the first bridge because the repository
already has this intended shape in `backend_ui_bridge.py`, and because it avoids
port management and localhost security questions.

The refactor must remove GUI imports from the bridge. In particular,
`Respaldo/Texto_punto_cero.py` must not be imported merely to obtain the audio
extension set; move shared constants into a domain module and keep the legacy
Tkinter UI independent.

Proposed new modules:

```text
architecture/contracts.py       # DTOs/enums only
architecture/errors.py          # stable error codes
core/config.py                  # one validated config authority
core/library_scope.py           # intake/destination scope rules
core/metadata.py                # Mutagen + normalized metadata
core/bpm.py                     # metadata-first, Librosa fallback
core/routes.py                  # nine preset validation/resolution
core/classifier.py              # move transaction + receipt
core/player_model.py            # backend-independent track state if needed
bridge/local_bridge.py          # JSON-lines request loop
backend_ui_bridge.py            # compatibility entrypoint to local_bridge.py
```

`backend_bridge.py` and the missing `Texto` path remain untouched until P12
unless a concrete compatibility consumer is found.

# Persistence Strategy

- Preserve JSON as local persistence for settings and route presets.
- Add a schema version and one canonical config path.
- On first run, offer/import the nearest valid existing config, but reject stale
  personal paths silently only as data; show them as unconfigured rather than
  using them.
- Persist:
  - root path;
  - destination folder name/exclusions;
  - route slots 1–9;
  - selected sort mode/direction;
  - window preferences only if Tauri persistence is needed;
  - last operation receipt only if undo is included.
- Do not persist the full metadata library in the frontend. Re-scan or build a
  bounded local index only after profiling proves repeated scans too slow.
- Do not add PostgreSQL, Firebase, Supabase, MongoDB or a hosted API.

# Audio/File Handling Strategy

- Backend returns `trackId`, relative path, display name, title, artist, BPM,
  genre, duration and artwork reference; never returns the audio binary.
- Use a local Tauri asset URI or an approved native file URI for `<audio>`.
- Artwork should be returned as a safe local URI/reference, not an unbounded
  base64 data URL for every row.
- Track rows use lazy artwork loading and do not decode all covers on initial
  render.
- Metadata extraction is cached per scan invocation and moved files are removed
  from the current queue after a successful transaction.
- A move is allowed only when source and destination are within the selected
  root and the destination is not an intake path.
- Cross-volume moves are outside MVP; if detected, return
  `CROSS_VOLUME_MOVE_UNSUPPORTED` rather than silently changing semantics.

# Frontend Structure

```text
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── src/
│   ├── main.tsx
│   ├── app/App.tsx
│   ├── app/app-state.ts
│   ├── bridge/desktop-bridge.ts
│   ├── bridge/contracts.ts       # generated/copied Layer A DTO shape only
│   ├── components/
│   │   ├── AppShell.tsx
│   │   ├── Toolbar.tsx
│   │   ├── TrackList.tsx
│   │   ├── TrackRow.tsx
│   │   ├── TrackArtwork.tsx
│   │   ├── AudioControls.tsx
│   │   ├── RoutePad.tsx
│   │   ├── SortMenu.tsx
│   │   ├── FolderPicker.tsx
│   │   ├── ProgressIndicator.tsx
│   │   ├── ErrorState.tsx
│   │   ├── EmptyState.tsx
│   │   └── Toast.tsx
│   ├── features/library/
│   ├── features/player/
│   ├── features/routes/
│   └── styles/
└── src-tauri/
    ├── src/main.rs
    ├── tauri.conf.json
    ├── capabilities/default.json
    └── binaries/
```

The React tree must remain feature-oriented. `App.tsx` composes features; it
must not own scanning, BPM logic, path validation or file movement.

# Packaging Strategy

Use a dedicated PyInstaller `onedir` sidecar first, not the current Qt spec and
not a one-file binary by default. `onedir` makes native audio DLLs, Librosa,
soundfile and runtime assets inspectable and usually reduces startup/extraction
surprises. If packaging proves materially better with Nuitka, compare it using
the same clean-machine acceptance matrix rather than switching on preference.

The build order is:

```text
Python core + bridge
  → PyInstaller backend_bridge.exe
  → frontend/dist
  → Tauri externalBin sidecar bundle
  → Windows installer/executable
```

The production installer contains the React assets, Tauri shell, packaged
Python sidecar, required Python/native audio dependencies, icons and fonts. It
does not contain the user's music library or private config. Configuration is
created under `%APPDATA%\\CapelHouse`; the executable directory is read-only for
application state. P9 must inspect the actual PyInstaller dependency graph,
including any soundfile codec DLLs and optional Librosa imports, on Windows.

# Migration Plan

## P0 — Audit current architecture and freeze domain ownership

**Goal**

Produce the Layer A contract and decision record before adding frontend code.

**Existing systems reused**

`Capelhouse/CapelHouse_Qt.py`, `Respaldo/Texto_punto_cero.py`,
`backend_ui_bridge.py`, `requirements.txt`, the current JSON config shape and
`Capelhouse/CapelHouse.spec` are evidence/donors only. They do not become a
new combined authority.

**New infrastructure**

- `docs/architecture/ADR-001-local-desktop-boundary.md`
- `docs/architecture/ADR-002-library-scope-and-move-policy.md`
- `docs/architecture/BRIDGE_CONTRACT.md`
- `architecture/contracts.py`
- `architecture/errors.py`

**Files/components affected**

Documentation and contract files only. No current production UI, backend,
config or packaging file is changed in P0.

**Runtime flow**

None; P0 is a documentation/contract freeze.

**Failure handling**

If ownership, move semantics, route shape or source scope is disputed, label
`DOMAIN AUTHORITY REQUIRED` or `PRODUCT INTERFACE REQUIRED` and stop. Do not
solve disagreement with a default in code.

**Validation**

- Confirm every existing writer/reader from the audit.
- Confirm exact DTO fields and error codes.
- Confirm no contract depends on a browser, HTTP port or remote DB.
- Review the four product defaults that were not answered: source scope,
  conflicts, BPM-missing behavior and immediate numpad moves.

**Entry condition**

Repository audit complete and current desktop behavior preserved.

**Migration strategy**

No runtime migration; create a written boundary around the existing app.

**Safe stopping point**

A reviewable architecture package exists with no production behavior change.

**Forbidden dependency**

No React component, Tauri command, SQLite schema, cloud service or new UI
implementation may be required to close P0.

**Regression surface**

None in runtime; only plan/contract scope drift.

**Definition of Done**

Layer A owns contracts and decisions; Python owns domain effects; React owns
presentation; Tauri owns process/window lifecycle; the no-go list is explicit.

## P1 — Establish React + Vite frontend workspace

**Goal**

Create a buildable React/TypeScript/Vite workspace with no domain behavior.

**Existing systems reused**

Existing `.gitignore` frontend exclusions and visual/product language from the
Qt UI as design reference only.

**New infrastructure**

`frontend/package.json`, Vite config, TypeScript config, `src/main.tsx`, and a
minimal health screen.

**Files/components affected**

Create only under `frontend/`; update root `.gitignore` only if the existing
patterns do not cover Vite artifacts.

**Runtime flow**

Vite serves a static React shell in development. No Python invocation yet.

**Failure handling**

Build errors fail the phase. The screen must clearly state `Bridge not connected`
without pretending backend readiness.

**Validation**

`npm run typecheck`, `npm run build`, and a Vite dev render.

**Entry condition**

P0 contracts reviewed.

**Migration strategy**

The Qt UI remains the only usable product UI.

**Safe stopping point**

A standalone frontend workspace builds and shows a non-authoritative shell.

**Forbidden dependency**

No copied Python logic, fake track data in production code, or filesystem
access from React.

**Regression surface**

No existing runtime path.

**Definition of Done**

The frontend builds from a clean checkout and contains no hardcoded music
library or classification authority.

## P2 — Establish Tauri desktop shell

**Goal**

Open the React frontend inside a native Windows window with no browser chrome.

**Existing systems reused**

Vite frontend from P1 and existing Tauri-oriented `.gitignore` intent.

**New infrastructure**

`frontend/src-tauri/`, Tauri config, capabilities, window defaults and DEV
Vite URL configuration.

**Files/components affected**

Create only under `frontend/src-tauri/` plus `frontend/package.json` scripts.

**Runtime flow**

`npm run tauri dev` starts Vite and opens the Tauri window. No Python child yet.

**Failure handling**

If Vite is unreachable, Tauri shows a visible startup error and exits cleanly.
Window close must not leave any child process because no child exists in P2.

**Validation**

Open/close on Windows; confirm no browser navigation bar; test resize and
minimum window size; run the Tauri dev command from the repository.

**Entry condition**

P1 build is green.

**Migration strategy**

Qt remains available as fallback; Tauri is opt-in development surface.

**Safe stopping point**

A native desktop window renders React.

**Forbidden dependency**

No backend HTTP server, remote URL, Python installation requirement for users,
or filesystem mutation.

**Regression surface**

Tauri permissions, Windows WebView2 availability and dev/prod asset paths.

**Definition of Done**

Tauri opens the React shell as a desktop window in DEV and has a declared
production frontend asset path.

## P3 — Establish Python ↔ desktop bridge

**Goal**

Replace the broken bridge prototype with a clean, GUI-independent Python
sidecar protocol and explicit lifecycle.

**Existing systems reused**

Metadata/BPM/classification behavior from `Capelhouse/CapelHouse_Qt.py` and
`Respaldo/Texto_punto_cero.py`; JSON-lines intent from `backend_ui_bridge.py`.

**New infrastructure**

`architecture/contracts.py`, `architecture/errors.py`, `core/` modules,
`bridge/local_bridge.py`, and the compatibility entrypoint
`backend_ui_bridge.py`.

**Files/components affected**

New `architecture/`, `core/`, `bridge/`; modify `backend_ui_bridge.py`; do not
import Tkinter, PySide6 or Qt from the bridge.

**Runtime flow**

Tauri starts Python, sends `ping`, waits for `READY`, then accepts commands.
Each request has an ID and one JSON response. stderr is diagnostic only and is
never mixed into stdout protocol data.

**Failure handling**

Handle malformed JSON, unknown command, missing root, missing track, invalid
route, Python exception, EOF, non-zero exit and shutdown timeout with stable
error codes. The frontend must never interpret a missing response as success.

**Validation**

- Bridge `ping` works from a clean Windows venv.
- Bridge starts without Tkinter/PySide6.
- Unit tests cover request parsing and error serialization.
- Tauri starts/stops the child without an orphan.

**Entry condition**

P2 native shell works; P0 bridge contract accepted.

**Migration strategy**

Keep Qt/Tkinter UIs untouched. The new bridge calls extracted core services.

**Safe stopping point**

A native shell can start and stop a real Python process reliably, even before
library commands are exposed.

**Forbidden dependency**

No HTTP port, global process, import from legacy UI, or direct React filesystem
access.

**Regression surface**

Python path resolution, Windows quoting, stdout buffering, process tree cleanup
and import cycles.

**Definition of Done**

`backend_ui_bridge.py` is a valid sidecar entrypoint, starts without GUI
modules, emits `READY`, responds by request ID and shuts down deterministically.

## P4 — Prove one real backend query end-to-end

**Goal**

Make the React/Tauri/Python path load a real library summary from a user-selected
root.

**Existing systems reused**

`rglob`/audio extension behavior from the current apps, Mutagen metadata reads
and current JSON settings concept.

**New infrastructure**

`LOAD_LIBRARY`, `GET_TRACK_PAGE`, `SET_ROOT` contracts; `LibraryScope`;
`MetadataService`; bridge client; one React result view.

**Files/components affected**

`core/library_scope.py`, `core/metadata.py`, `bridge/local_bridge.py`,
`frontend/src/bridge/desktop-bridge.ts`, `frontend/src/features/library/`.

**Runtime flow**

Folder picker chooses root → React sends path intent → Tauri forwards request
→ Python validates scope and scans → metadata DTOs return → React renders count
and rows.

**Failure handling**

Invalid path, permission denied, unreadable audio, malformed tags and unknown
artwork become per-track diagnostics; total scan failure remains a visible
error. No failed metadata read removes a track.

**Validation**

Use a fixture folder with real small audio files and one malformed/unsupported
file. Prove returned artist/title/BPM/genre/duration, count and empty state.

**Entry condition**

P3 bridge lifecycle is green.

**Migration strategy**

Qt remains the reference behavior; new UI only reads.

**Safe stopping point**

The new native window displays real local songs and metadata without mutation.

**Forbidden dependency**

No full audio transfer, no frontend metadata parsing, no sorting authority in
React, no library-wide eager artwork base64.

**Regression surface**

Large scan latency, path escaping and metadata field normalization.

**Definition of Done**

A real local root loads through all three layers and displays a truthful queue;
no fake production data is used.

## P5 — Prove one real backend mutation end-to-end

**Goal**

Move one real selected track through a validated configured route and refresh
state.

**Existing systems reused**

Qt move semantics as behavioral evidence, existing BPM bucket rule and category
folder creation logic.

**New infrastructure**

`MOVE_TRACK`, `UNDO_LAST_MOVE` if retained, route preset validation, atomic move
transaction, operation receipt and refresh response.

**Files/components affected**

`core/routes.py`, `core/classifier.py`, `core/config.py`, Layer A contracts,
`RoutePad` test harness and bridge client.

**Runtime flow**

Mouse/numpad test action → command → resolve opaque track ID → metadata/BPM
resolution → safe destination under root → create folders → move → receipt →
return before/after → React removes row and shows result.

**Failure handling**

Block invalid route, root escape, missing source, existing destination,
unsupported cross-volume move and permission failure. On failure, source remains
in the queue and no success toast is emitted.

**Validation**

Use a temporary Windows fixture root; assert source disappears, destination
exists, metadata is unchanged, config is local, conflict leaves both files and
queue refresh is correct.

**Entry condition**

P4 real query works; move policy is accepted in P0.

**Migration strategy**

The new classifier is exercised on a fixture only; current UIs are not changed.

**Safe stopping point**

One read and one write path are proven through the real desktop architecture.

**Forbidden dependency**

No direct file operation in Rust/React, no overwrite default, no copy fallback,
no hidden BPM/genre inference.

**Regression surface**

Destructive filesystem behavior, duplicate names, file locks and partial moves.

**Definition of Done**

A real file can be safely moved through the new UI/backend boundary and every
failure mode is observable and non-destructive.

## P6 — Build application shell/navigation

**Goal**

Create the durable desktop UX frame around the proven bridge.

**Existing systems reused**

Qt layout concepts: source/destination context, list, inspector and playback
controls; existing logo/fonts/assets where licensing and packaging permit.

**New infrastructure**

`AppShell`, toolbar, root picker, status area, settings dialog, resizable panes,
route toasts and command palette/shortcut registry.

**Files/components affected**

`frontend/src/components/AppShell.tsx`, `Toolbar.tsx`, `FolderPicker.tsx`,
`Toast.tsx`, CSS/theme files and app state.

**Runtime flow**

App ready state → select root → load summary → shell shows library/inspector
regions. The shell owns visual state only.

**Failure handling**

Bridge unavailable, root unset, empty root and settings migration appear as
explicit states with retry/reconfigure actions.

**Validation**

Keyboard focus, resize, dark/light choice if retained, native folder picker,
window close and empty-state screenshots/manual checks on Windows.

**Entry condition**

P4/P5 vertical proofs pass.

**Migration strategy**

Do not remove Qt; users can launch the old app while the shell grows.

**Safe stopping point**

A coherent native React shell can configure a root and show honest status.

**Forbidden dependency**

No feature-wide state in one monolithic `App.tsx`; no business logic in CSS or
components.

**Regression surface**

Focus ownership and accidental shortcut activation inside inputs/dialogs.

**Definition of Done**

Navigation, root setup, status and recovery are reusable and independently
renderable components.

## P7 — Migrate primary music-library experience

**Goal**

Deliver the MVP workflow: cycle tracks with WASD, inspect metadata/artwork and
classify with Numpad 1–9 or mouse-configured destination routes.

**Existing systems reused**

Mutagen fields, current BPM bucket logic and the user's move-in-place-root
workflow. Qt remains visual reference, not a code dependency.

**New infrastructure**

`TrackList`, `TrackRow`, `TrackArtwork`, `AudioControls`, `RoutePad`,
`SortMenu`, keyboard command map, HTML audio playback and lazy artwork loading.

**Files/components affected**

`frontend/src/features/library/`, `frontend/src/features/player/`,
`frontend/src/features/routes/`, components listed in the frontend structure,
plus core DTOs only where the current normalized metadata is insufficient.

**Runtime flow**

Selected row → artwork with play overlay only for the active track → title/artist
→ BPM/genre → `<audio>` playback. `W/S` changes selection; `A/D` seeks five
seconds; `Numpad1..9` invokes the selected route and advances to the next remaining
track only after a successful move.

**Failure handling**

Playback error does not alter classification. Missing artwork shows a neutral
placeholder. Missing metadata remains labeled `Unknown`/`—`. Move errors keep
selection and queue entry. The active play overlay is not shown on inactive rows.

**Validation**

- Keyboard matrix for W/S/A/D and Numpad 1–9.
- Shortcut suppression in text fields and dialogs.
- Mouse route click equals keyboard route behavior.
- Selected/playing visual state is mutually consistent.
- Metadata and artwork are lazy and bounded.
- Successful move removes exactly one source row.

**Entry condition**

P5 mutation and P6 shell are green.

**Migration strategy**

Migrate one queue/list workflow first; keep category management in Qt until
routes and config parity are proven.

**Safe stopping point**

The new app is genuinely useful for a complete manual sorting session.

**Forbidden dependency**

No playlist/cloud sync, duplicate finder, waveform editor or eager render of
all tens of thousands of tracks.

**Regression surface**

Destructive hotkeys, playback/selection race, accidental double move and large
library rendering.

**Definition of Done**

Mono can select a root, listen, read metadata, press WASD and classify through
keyboard or mouse without leaving the native app or opening a browser.

## P8 — Add production loading/error/progress behavior

**Goal**

Make long scans, BPM analysis and moves understandable and recoverable.

**Existing systems reused**

Current metadata/BPM operations and status messages as copy reference.

**New infrastructure**

Progress events, cancel tokens, job IDs, scan phases, retry states, operation
receipts, structured logs and bounded frontend store updates.

**Files/components affected**

`architecture/contracts.py`, `core/metadata.py`, `core/bpm.py`, bridge loop,
frontend progress/toast/error components and state management.

**Runtime flow**

Start job → progress events → partial rows where safe → complete/cancel/error.
A move remains one atomic command; cancellation is allowed before the move
boundary, not halfway through a filesystem rename.

**Failure handling**

Cancellation before mutation stops cleanly; cancellation after mutation reports
committed result and never retries automatically. Python crash marks all active
jobs interrupted and offers reload. A malformed track is isolated.

**Validation**

Fixture with slow metadata/analyzer stubs; test cancel before/after boundary,
bridge restart, duplicate request ID, stale response and progress monotonicity.

**Entry condition**

P7 manual workflow works.

**Migration strategy**

Add observability without changing move authority or accepted destination rules.

**Safe stopping point**

The MVP is usable on a large library with honest progress and recovery.

**Forbidden dependency**

No hidden background worker that outlives Tauri, no retry of a possibly committed
move without reconciliation.

**Regression surface**

Race conditions, stale UI responses, cancellation timing and process cleanup.

**Definition of Done**

Every long-running operation has visible state, bounded cancellation semantics
and a diagnostic path.

## P9 — Package Python backend and dependencies

**Goal**

Produce a standalone Windows Python sidecar without requiring Python for the
end user.

**Existing systems reused**

`Capelhouse/CapelHouse.spec` collection patterns for `librosa` and `soundfile`,
plus runtime dependencies from `requirements.txt`.

**New infrastructure**

A dedicated sidecar spec, build script, dependency verification fixture and
Tauri `externalBin`/sidecar configuration.

**Files/components affected**

Create `packaging/backend_bridge.spec`, `packaging/build_backend.ps1` and
modify Tauri packaging configuration. Do not repurpose the Qt spec as the
React/Tauri sidecar spec.

**Runtime flow**

PyInstaller builds `backend_bridge.exe` → Tauri resolves architecture-specific
sidecar name → starts it with packaged assets/config path → bridge reports READY.

**Failure handling**

Missing DLL/codec/import fails at startup with a user-readable diagnostic and
log path. Config writes go to `%APPDATA%`, not the installation directory.

**Validation**

Build on Windows x64; run the packaged exe outside the source tree; test
Mutagen formats, Librosa fallback, artwork, playback URI and filesystem move.
Inspect included DLLs/native modules instead of assuming PyInstaller collected
all optional audio paths.

**Entry condition**

P8 is green and the Python module graph is stable.

**Migration strategy**

Qt PyInstaller packaging remains intact as fallback until P12.

**Safe stopping point**

A standalone sidecar can run and answer `ping` and `LOAD_LIBRARY`.

**Forbidden dependency**

No user-installed Python, Node, Vite, dev server or internet download at runtime.

**Regression surface**

PyInstaller hidden imports, soundfile/native DLLs, path resolution and antivirus
false positives.

**Definition of Done**

The sidecar runs from its packaged location and passes the same bridge contract
as the development Python process.

## P10 — Produce Windows distributable

**Goal**

Build the normal desktop product artifact `CapelHouse.exe`/installer.

**Existing systems reused**

Tauri shell, frontend build and packaged Python sidecar from P2/P9.

**New infrastructure**

`npm run tauri build`, Windows installer configuration, icons/assets, sidecar
bundle and release smoke script.

**Files/components affected**

`frontend/src-tauri/tauri.conf.json`, capabilities, icons and packaging scripts.
Do not alter user library files during build.

**Runtime flow**

Build frontend → build sidecar → bundle assets → produce installer/executable →
install to a clean Windows test account → first-run config → operate offline.

**Failure handling**

Installer/build failure stops release. First-run migration failure offers a new
empty config without deleting source JSON. Sidecar failure offers repair/log
information rather than opening a browser fallback.

**Validation**

Install/uninstall on clean Windows; launch without Node/Python; disconnect
internet; choose a test root; execute query, playback and one move; verify clean
shutdown and no orphan process.

**Entry condition**

P9 packaged sidecar passes.

**Migration strategy**

Do not replace the old launcher or Qt executable yet.

**Safe stopping point**

A distributable desktop application is installable and locally functional.

**Forbidden dependency**

No hosted frontend, remote API, mandatory localhost tab or runtime package
installation.

**Regression surface**

Installer permissions, WebView2, sidecar signing/paths and Windows Defender.

**Definition of Done**

A clean Windows machine can install and use CapelHouse offline without developer
tools.

## P11 — Validate production build against a real music library

**Goal**

Prove behavior and performance with a representative local library before
retiring the old UI.

**Existing systems reused**

The user's real root only as a test input; no library content is committed or
uploaded.

**New infrastructure**

A redacted validation checklist, timing log and disposable test config. Never
commit paths, filenames, metadata dumps or artwork from the private library.

**Files/components affected**

`docs/validation/LOCAL_REAL_LIBRARY_CHECKLIST.md` and optional ignored local
reports only.

**Runtime flow**

Install production artifact → select real root → scan → sort/view → play →
classify with keyboard → restart → confirm sorted destinations are excluded.

**Failure handling**

Stop immediately for unexpected move, overwrite, duplicate processing, path
escape, lost metadata, orphan process or inability to undo/reconcile an
operation. Do not “fix” by editing the real library manually during the test.

**Validation**

Check:

- root/direct files and `UNSORTED` scope;
- no reappearance of moved tracks;
- artist/title/BPM/genre/duration/artwork;
- WASD and Numpad behavior;
- missing BPM and conflict behavior;
- large-list responsiveness/windowing;
- offline operation;
- restart and config persistence;
- no cloud/network calls;
- no Python/Node dependency on clean user machine.

**Entry condition**

P10 installer works.

**Migration strategy**

Old Qt app remains available as emergency fallback and comparison tool.

**Safe stopping point**

The new app is validated against real usage without claiming broad parity beyond
the tested workflow.

**Forbidden dependency**

No private music files in Git, screenshots, logs or remote services.

**Regression surface**

Real metadata variation, long scan time, file locks, route collisions and user
expectation around direct-root versus nested folders.

**Definition of Done**

A real sorting session completes safely, the queue contains only unsorted input,
and all observed deviations are recorded and resolved or explicitly accepted.

## P12 — Remove/deprecate replaced UI path only after parity is proven

**Goal**

Reduce architectural duplication without deleting the safety net prematurely.

**Existing systems reused**

The new Python core and bridge are authoritative; Qt/Tkinter become fallback or
archived references only after P11.

**New infrastructure**

Migration note, compatibility launcher decision, deprecation warning or archive
layout, and final README/runbook.

**Files/components affected**

Potentially `Capelhouse/CapelHouse_Qt.py`, `Respaldo/Texto_punto_cero.py`,
`backend_bridge.py`, `Capelhouse/Abrir_CapelHouse.bat` and old Qt spec. Exact
removals require evidence from P11 and an explicit owner decision.

**Runtime flow**

Normal launcher starts Tauri app. Legacy UI is either retained as a documented
fallback or removed in a separate cleanup commit after all required workflows
are covered.

**Failure handling**

If parity is incomplete, do not remove the old path. If a compatibility launcher
is broken, repair or document it before deprecation. No silent deletion of user
config or music is allowed.

**Validation**

Run the final desktop smoke suite, bridge contract tests, move safety tests,
installer test and real-library checklist. Verify Git diff contains no accidental
music/config artifacts.

**Entry condition**

P11 has passed for the agreed MVP workflow.

**Migration strategy**

Deprecate in stages: documentation → default launcher switch → fallback period
→ optional removal.

**Safe stopping point**

The new app is the default while legacy code remains recoverable.

**Forbidden dependency**

No cleanup by mass deletion, no removal justified only by aesthetic preference,
and no deletion before real-library parity.

**Regression surface**

Config migration, old launcher expectations, packaging references and user
recovery path.

**Definition of Done**

The repository has one documented default desktop runtime, one Python domain
authority, an explicit legacy decision, and no broken hidden fallback.

# Validation Strategy

## Layer A/contract tests

- DTO schema accepts valid `TrackRecord`, `LibrarySummary`, `RoutePreset`,
  `MoveResult` and `ProgressEvent`.
- Unknown commands, invalid paths, invalid route IDs and unsupported states fail.
- `BLOCKED`/unknown state remains visible rather than converted into success.

## Python core tests

Use `pytest` or a standard-library test runner added explicitly as a development
requirement; do not require test dependencies in the end-user bundle.

- scan scope excludes configured destinations and includes direct root/
  `UNSORTED` according to the frozen rule;
- filename sorting is deterministic and tie-broken by relative path;
- metadata normalization maps missing values honestly;
- BPM metadata wins over Librosa fallback;
- BPM unknown uses the explicit bucket;
- route resolution cannot escape root;
- destination conflict does not modify either file;
- successful move removes source and records receipt;
- cross-volume behavior fails closed;
- shutdown and malformed protocol cases are covered.

## Bridge tests

- `ping`/`READY` handshake;
- request ID correlation;
- one request/one response;
- stderr isolation;
- malformed JSON recovery;
- Python exception serialization;
- cancellation boundary;
- EOF/non-zero exit handling;
- shutdown without orphan child.

## Frontend tests

- render loading, empty, error and populated states;
- row artwork/play overlay behavior;
- artist/title/BPM/genre/duration rendering;
- W/S/A/D shortcuts;
- Numpad 1–9 and mouse route equivalence;
- shortcut suppression in editable controls;
- successful move refresh;
- conflict/error toast and source remains visible;
- virtualized/windowed rendering for large queues.

## Production smoke gate

A release is not accepted until the Windows packaged artifact passes P11 with a
real local library, offline, without Node/Python installed separately. Do not
claim localhost deployment; the product is a packaged desktop executable.

# Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Two existing UIs disagree on copy vs move | Critical | Freeze move as authority in Layer A; test filesystem result before migrating UI |
| Bridge imports legacy GUI modules | High | Extract shared constants/services; bridge must run headless |
| Destination folders are rescanned | Critical | Explicit intake scope and backend-owned exclusion registry |
| Existing destination silently overwritten | Critical | Block with `DESTINATION_EXISTS`; add undo/receipt before broad use |
| Python sidecar orphaned on Windows close | High | Tauri-owned lifecycle, bounded shutdown and process-tree test |
| BPM analysis freezes UI | High | Backend job/progress events, metadata-first, cancellation before mutation |
| Large library overwhelms React | High | Backend paging/incremental scan, lazy artwork and virtualization |
| Config from LENOVO/E drive is reused | High | Per-user config migration and invalid-path state |
| PyInstaller misses audio native assets | High | Dedicated sidecar spec and clean-machine codec/import tests |
| React duplicates classification logic | High | Layer A DTOs plus Python-only validation/mutation |
| Keyboard shortcut triggers inside dialogs | Medium | `event.code` map with editable-target suppression tests |
| User loses a file during move failure | Critical | Same-volume atomic move, conflict block, receipts and fail-closed error handling |
| Old UI removed too early | High | Keep fallback through P11; deprecate only after parity gate |

# What We Explicitly Will Not Change

- We will not convert CapelHouse into a hosted web app or SaaS.
- We will not require a browser, browser navigation bar or manually visited
  localhost URL.
- We will not upload music, metadata, artwork or audio to a remote service.
- We will not introduce PostgreSQL, Firebase, Supabase, MongoDB or cloud storage.
- We will not rewrite working Python domain behavior into TypeScript merely to
  simplify React.
- We will not send complete audio files through Tauri/Python JSON IPC.
- We will not let React, CSS, Tauri Rust commands or route buttons become file
  movement authorities.
- We will not silently copy files when the new product contract says move.
- We will not overwrite destination files by default.
- We will not infer genre from filename or BPM from a guessed value.
- We will not build a generic plugin framework, duplicate finder, playlist system,
  waveform editor or cloud sync in the MVP.
- We will not delete Qt/Tkinter or the old bridge before P11 parity evidence.
- We will not commit private user-library paths, audio files, artwork or logs.

# Definition of Done

The modernization is complete when all of the following are true:

- `CapelHouse.exe` launches as a normal Windows desktop program.
- Normal operation is offline and does not require Node, Vite, Python or a
  browser installation.
- Tauri owns the Python sidecar lifecycle and leaves no orphan process.
- Layer A documents ownership, contracts, error taxonomy, source scope and move
  semantics.
- Python remains the authority for scanning, metadata, BPM, routes, persistence
  and filesystem mutation.
- React/Vite owns the modern presentation layer without duplicated domain rules.
- The root/`UNSORTED` intake policy prevents already moved tracks from returning
  to the unsorted queue.
- WASD works as `W=previous`, `S=next`, `A=rewind`, `D=fast-forward` outside
  editable controls.
- Numpad 1–9 and mouse-configured routes perform the same validated move.
- Rows show artwork, play overlay only on the active track, name/title, artist,
  BPM and metadata genre, with honest missing-data states.
- Sorting is deterministic and can be extended to metadata fields without
  moving authority into React.
- Moves are atomic/fail-closed, conflicts do not overwrite files, and progress/
  error/undo behavior is visible.
- Large libraries use incremental loading/windowing and lazy artwork.
- The packaged sidecar includes all required Python/native audio dependencies.
- A clean Windows install passes the real-library offline validation checklist.
- The legacy UI decision is documented and no replaced path is removed without
  parity evidence.
