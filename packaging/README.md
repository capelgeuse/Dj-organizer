# Windows production packaging checklist

Run from a Windows PowerShell terminal:

```powershell
.\packaging\build_desktop.ps1
```

The script builds a one-file Python sidecar, verifies its JSON-lines `ping`, copies the target-triple executable into `frontend/src-tauri/binaries/`, runs the frontend UI tests, and invokes the Tauri production bundle.

Final acceptance:

1. Confirm `dist/backend_bridge.exe` answers `ping` outside the repository.
2. Confirm the Tauri app opens without a terminal window.
3. Confirm the packaged app finds its sidecar and reports `Bridge Connected`.
4. Test W/S navigation, A/D seek, click routing, numpad routing, undo, shutdown, and restart.
5. Run from a clean Windows account with no Python installed.
6. Run the offline real-library smoke checklist before release.

Never package the user's music, personal config, or `Capelhouse/configuracion_dj.json`.
