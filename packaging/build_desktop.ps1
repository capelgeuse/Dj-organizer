# Build the complete CapelHouse desktop artifact on Windows.
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Repo "frontend")

npm install
npm run build
Set-Location $Repo
& (Join-Path $Repo "packaging\build_backend.ps1")
Set-Location (Join-Path $Repo "frontend")
npm run tauri build
