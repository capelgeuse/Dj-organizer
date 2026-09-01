# Build and smoke-test the Python JSON-lines sidecar from Windows PowerShell.
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo
$Python = if ($env:CAPELHOUSE_PYTHON) { $env:CAPELHOUSE_PYTHON } else { Join-Path $Repo ".venv\Scripts\python.exe" }
$Spec = Join-Path $Repo "packaging\backend_bridge.spec"

if (-not (Test-Path $Spec)) {
    throw "Missing PyInstaller spec: $Spec"
}

if (-not (Test-Path $Python)) {
    py -3 -m venv (Join-Path $Repo ".venv")
    $Python = Join-Path $Repo ".venv\Scripts\python.exe"
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $Repo "packaging\requirements-sidecar.txt")
& $Python -m pip install -r (Join-Path $Repo "packaging\requirements-build.txt")
& $Python -m PyInstaller --clean --noconfirm $Spec

$BuiltSidecar = Join-Path $Repo "dist\backend_bridge.exe"
if (-not (Test-Path $BuiltSidecar)) {
    throw "PyInstaller did not produce $BuiltSidecar"
}

$Probe = '{"id":"packaging-smoke","command":"ping","payload":{}}' | & $BuiltSidecar
if ($LASTEXITCODE -ne 0) {
    throw "Packaged sidecar exited with code $LASTEXITCODE during ping smoke test."
}
$ProbeResponse = $Probe | ConvertFrom-Json
if (-not $ProbeResponse.ok -or -not $ProbeResponse.data.ready) {
    throw "Packaged sidecar did not return a valid ping response: $Probe"
}

$TargetDir = Join-Path $Repo "frontend\src-tauri\binaries"
New-Item -ItemType Directory -Force $TargetDir | Out-Null
$TargetName = if ($env:TAURI_TARGET_TRIPLE) { "backend_bridge-$env:TAURI_TARGET_TRIPLE.exe" } else { "backend_bridge-x86_64-pc-windows-msvc.exe" }
$TargetPath = Join-Path $TargetDir $TargetName
Copy-Item $BuiltSidecar $TargetPath -Force
Write-Host "Sidecar ready and ping-verified: $TargetPath"
