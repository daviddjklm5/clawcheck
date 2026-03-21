param(
    [Parameter(Mandatory = $true)]
    [string]$InputFile,
    [string]$VenvDir = ".venv-win",
    [string]$Config = "",
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
    [switch]$DropAndCreateDb
)

$ErrorActionPreference = "Stop"
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$PythonExe = Join-Path $RepoRoot "$VenvDir\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Python venv not found: $PythonExe"
}

function Resolve-RepoPath([string]$RawPath) {
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

$ResolvedInputFile = Resolve-RepoPath $InputFile
if (-not (Test-Path $ResolvedInputFile)) {
    throw "Input dump file not found: $ResolvedInputFile"
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

$env:PGHOST = $Connection.host
$env:PGPORT = [string]$Connection.port
$env:PGDATABASE = $Connection.dbname
$env:PGUSER = $Connection.user
$env:PGPASSWORD = $Connection.password
$env:PGSSLMODE = $Connection.sslmode

$PgRestore = Resolve-PgTool -ToolName "pg_restore.exe" -BinDir $PgBinDir
$DropDb = Resolve-PgTool -ToolName "dropdb.exe" -BinDir $PgBinDir
$CreateDb = Resolve-PgTool -ToolName "createdb.exe" -BinDir $PgBinDir
$Psql = Resolve-PgTool -ToolName "psql.exe" -BinDir $PgBinDir

if ($DropAndCreateDb) {
    & $DropDb --if-exists $Connection.dbname
    & $CreateDb $Connection.dbname
}

if ($ResolvedInputFile.ToLowerInvariant().EndsWith(".sql")) {
    & $Psql --file $ResolvedInputFile
    exit $LASTEXITCODE
}

& $PgRestore --clean --if-exists --no-owner --no-privileges --dbname $Connection.dbname $ResolvedInputFile
exit $LASTEXITCODE
