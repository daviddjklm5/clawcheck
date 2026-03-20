param(
    [string]$PgRoot = "",
    [string]$DataDir = "",
    [ValidateSet("smart", "fast", "immediate")]
    [string]$Mode = "fast"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $PgRoot) {
    $PgRoot = Join-Path $env:USERPROFILE "PostgreSQL17Clawcheck"
}
if (-not $DataDir) {
    $DataDir = Join-Path $PgRoot "data"
}

$PgCtl = Join-Path $PgRoot "bin\pg_ctl.exe"
if (-not (Test-Path $PgCtl)) {
    throw "pg_ctl.exe not found: $PgCtl"
}
if (-not (Test-Path $DataDir)) {
    throw "PostgreSQL data dir not found: $DataDir"
}

& $PgCtl -D $DataDir status | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PostgreSQL user-mode instance is already stopped."
    exit 0
}

& $PgCtl -D $DataDir stop -m $Mode
if ($LASTEXITCODE -ne 0) {
    throw "Failed to stop PostgreSQL user-mode instance."
}
