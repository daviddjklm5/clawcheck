param(
    [string]$VenvDir = ".venv-win",
    [string]$Config = "",
    [string]$OutputFile = "",
    [string]$OutputDir = "automation\backups",
    [string]$PgBinDir = "",
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
    [string]$ConnectionSslMode = "",
    [switch]$SchemaOnly,
    [switch]$DataOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$PythonExe = Join-Path $RepoRoot "$VenvDir\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Python venv not found: $PythonExe"
}

function Resolve-RepoPath([string]$RawPath) {
    if ([string]::IsNullOrWhiteSpace($RawPath)) {
        return ""
    }
    if ([System.IO.Path]::IsPathRooted($RawPath)) {
        return $RawPath
    }
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $RawPath))
}

function Resolve-PgTool([string]$ToolName, [string]$BinDir) {
    if ($BinDir) {
        return (Join-Path $BinDir $ToolName)
    }
    return $ToolName
}

$ConnectionArgs = @("automation/scripts/db_admin.py", "connection-info", "--include-password")
if ($Config) { $ConnectionArgs += @("--config", $Config) }
if ($ConnectionHost) { $ConnectionArgs += @("--host", $ConnectionHost) }
if ($Port -gt 0) { $ConnectionArgs += @("--port", [string]$Port) }
if ($DbName) { $ConnectionArgs += @("--dbname", $DbName) }
if ($DbUser) { $ConnectionArgs += @("--user", $DbUser) }
if ($DbPassword) { $ConnectionArgs += @("--password", $DbPassword) }
if ($SchemaName) { $ConnectionArgs += @("--schema", $SchemaName) }
if ($ConnectionSslMode) { $ConnectionArgs += @("--sslmode", $ConnectionSslMode) }

Push-Location $RepoRoot
try {
    $Connection = (& $PythonExe @ConnectionArgs | ConvertFrom-Json)
}
finally {
    Pop-Location
}

$ResolvedOutputFile = Resolve-RepoPath $OutputFile
if (-not $ResolvedOutputFile) {
    $ResolvedOutputDir = Resolve-RepoPath $OutputDir
    if (-not (Test-Path $ResolvedOutputDir)) {
        New-Item -ItemType Directory -Path $ResolvedOutputDir -Force | Out-Null
    }
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $ResolvedOutputFile = Join-Path $ResolvedOutputDir "$($Connection.dbname)_$Timestamp.dump"
}

$env:PGHOST = $Connection.host
$env:PGPORT = [string]$Connection.port
$env:PGDATABASE = $Connection.dbname
$env:PGUSER = $Connection.user
$env:PGPASSWORD = $Connection.password
$env:PGSSLMODE = $Connection.sslmode

$PgDump = Resolve-PgTool -ToolName "pg_dump.exe" -BinDir $PgBinDir
$Args = @("--format=custom", "--file", $ResolvedOutputFile, "--no-owner", "--no-privileges")
if ($SchemaOnly) { $Args += "--schema-only" }
if ($DataOnly) { $Args += "--data-only" }

& $PgDump @Args
$ExitCode = $LASTEXITCODE
Write-Host "Backup file: $ResolvedOutputFile"
exit $ExitCode
