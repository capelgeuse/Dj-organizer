# Build the complete CapelHouse desktop artifact on Windows.
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Repo "frontend"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Install the current Node.js LTS release."
}
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "cargo was not found. Install the Rust toolchain required by Tauri."
}

Set-Location $Frontend
npm ci
npm run test:ui

Set-Location $Repo
& (Join-Path $Repo "packaging\build_backend.ps1")

Set-Location $Frontend
npm run tauri:build
Write-Host "CapelHouse bundles are available under frontend\src-tauri\target\release\bundle."
