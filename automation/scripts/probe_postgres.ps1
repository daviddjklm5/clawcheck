param(
    [string]$VenvDir = ".venv-win",
    [string]$Config = "",
    [string]$DumpJson = "",
    [string]$Host = "",
    [int]$Port = 0,
    [string]$DbName = "",
    [string]$User = "",
    [string]$Password = "",
    [string]$Schema = "",
    [string]$SslMode = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$PythonExe = Join-Path $RepoRoot "$VenvDir\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Python venv not found: $PythonExe"
}

$Args = @("automation/scripts/db_admin.py", "probe")
if ($Config) { $Args += @("--config", $Config) }
if ($DumpJson) { $Args += @("--dump-json", $DumpJson) }
if ($Host) { $Args += @("--host", $Host) }
if ($Port -gt 0) { $Args += @("--port", [string]$Port) }
if ($DbName) { $Args += @("--dbname", $DbName) }
if ($User) { $Args += @("--user", $User) }
if ($Password) { $Args += @("--password", $Password) }
if ($Schema) { $Args += @("--schema", $Schema) }
if ($SslMode) { $Args += @("--sslmode", $SslMode) }

Push-Location $RepoRoot
try {
    & $PythonExe @Args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
