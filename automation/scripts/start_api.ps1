param(
    [string]$VenvDir = ".venv-win",
    [string]$ListenHost = "127.0.0.1",
    [int]$Port = 8000,
    [string]$LogLevel = "info",
    [string]$WebuiDistDir = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$PythonExe = Join-Path $RepoRoot "$VenvDir\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Python venv not found: $PythonExe"
}

Push-Location $RepoRoot
try {
    if ($WebuiDistDir) {
        $env:CLAWCHECK_WEBUI_DIST_DIR = $WebuiDistDir
    }

    & $PythonExe -m uvicorn automation.api.main:app --host $ListenHost --port $Port --log-level $LogLevel
}
finally {
    Pop-Location
}
