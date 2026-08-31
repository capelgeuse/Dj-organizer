# Build the Python sidecar from a Windows PowerShell terminal.
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Python = if ($env:CAPELHOUSE_PYTHON) { $env:CAPELHOUSE_PYTHON } else { Join-Path $Repo ".venv\Scripts\python.exe" }

if (-not (Test-Path $Python)) {
    py -3 -m venv (Join-Path $Repo ".venv")
    $Python = Join-Path $Repo ".venv\Scripts\python.exe"
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $Repo "packaging\requirements-sidecar.txt")
& $Python -m pip install -r (Join-Path $Repo "packaging\requirements-build.txt")
& $Python -m PyInstaller --clean --noconfirm (Join-Path $Repo "packaging\backend_bridge.spec")

$TargetDir = Join-Path $Repo "frontend\src-tauri\binaries"
New-Item -ItemType Directory -Force $TargetDir | Out-Null
$BuiltSidecar = Join-Path $Repo "dist\backend_bridge\backend_bridge.exe"
if (-not (Test-Path $BuiltSidecar)) {
    throw "PyInstaller did not produce $BuiltSidecar"
}
$TargetName = if ($env:TAURI_TARGET_TRIPLE) { "backend_bridge-$env:TAURI_TARGET_TRIPLE.exe" } else { "backend_bridge-x86_64-pc-windows-msvc.exe" }
Copy-Item $BuiltSidecar (Join-Path $TargetDir $TargetName) -Force
Write-Host "Sidecar ready: $(Join-Path $TargetDir $TargetName)"
