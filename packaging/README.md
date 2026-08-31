# Windows production packaging checklist

1. Build on Windows x64 with `packaging/build_backend.ps1`.
2. Confirm `backend_bridge.exe` starts outside the repository and answers `ping`.
3. Inspect `dist/backend_bridge/` for Mutagen, Librosa, soundfile and native DLLs.
4. Confirm the sidecar does not import PySide6, Tkinter or pygame.
5. Copy the target-triple binary into `frontend/src-tauri/binaries/`.
6. Run the Tauri bundle from a clean Windows account with no Python installed.
7. Run the offline real-library smoke checklist before release.

Never package the user's music, personal config or `Capelhouse/configuracion_dj.json`.
