$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

Require-Command "python"
Require-Command "npm"
Require-Command "iscc"

Push-Location "$Root\frontend"
try {
    if (Test-Path "package-lock.json") {
        npm ci
    } else {
        npm install
    }
    npm run typecheck
    npm run build
} finally {
    Pop-Location
}

Push-Location $Root
try {
    python -m pip install -r requirements-gui.txt
    python -m PyInstaller --noconfirm --clean packaging\pycapcut-studio.spec
    iscc packaging\installer.iss
} finally {
    Pop-Location
}

Write-Host "Installer created at packaging\output\pyCapCut-Studio-Setup.exe" -ForegroundColor Green
