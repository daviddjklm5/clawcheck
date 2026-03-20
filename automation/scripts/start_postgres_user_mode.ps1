param(
    [string]$PgRoot = "",
    [string]$DataDir = "",
    [string]$LogFile = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $PgRoot) {
    $PgRoot = Join-Path $env:USERPROFILE "PostgreSQL17Clawcheck"
}
if (-not $DataDir) {
    $DataDir = Join-Path $PgRoot "data"
}
if (-not $LogFile) {
    $LogDir = Join-Path $PgRoot "log"
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    $LogFile = Join-Path $LogDir "server.log"
}

$PgCtl = Join-Path $PgRoot "bin\pg_ctl.exe"
if (-not (Test-Path $PgCtl)) {
    throw "pg_ctl.exe not found: $PgCtl"
}
if (-not (Test-Path $DataDir)) {
    throw "PostgreSQL data dir not found: $DataDir"
}

& $PgCtl -D $DataDir status | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "PostgreSQL user-mode instance is already running."
    exit 0
}

& $PgCtl -D $DataDir -l $LogFile start
if ($LASTEXITCODE -ne 0) {
    throw "Failed to start PostgreSQL user-mode instance."
}
