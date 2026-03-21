param(
    [string]$VenvDir = ".venv-win",
    [string]$Config = "",
    [string]$DumpJson = "",
    [Alias("Host")]
    [string]$ConnectionHost = "",
    [int]$Port = 0,
    [string]$DbName = "",
    [Alias("User")]
    [string]$DbUser = "",
    [Alias("Password")]
    [string]$DbPassword = "",
    [Alias("Schema")]
    [string]$SchemaName = "",
    [Alias("SslMode")]
    [string]$ConnectionSslMode = ""
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
if ($ConnectionHost) { $Args += @("--host", $ConnectionHost) }
if ($Port -gt 0) { $Args += @("--port", [string]$Port) }
if ($DbName) { $Args += @("--dbname", $DbName) }
if ($DbUser) { $Args += @("--user", $DbUser) }
if ($DbPassword) { $Args += @("--password", $DbPassword) }
if ($SchemaName) { $Args += @("--schema", $SchemaName) }
if ($ConnectionSslMode) { $Args += @("--sslmode", $ConnectionSslMode) }

Push-Location $RepoRoot
try {
    & $PythonExe @Args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
