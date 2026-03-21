param(
    [string]$VenvDir = ".venv-win",
    [string]$SourceConfig = "",
    [string]$TargetConfig = "",
    [string]$SourceHost = "",
    [int]$SourcePort = 0,
    [string]$SourceDbName = "",
    [string]$SourceUser = "",
    [string]$SourcePassword = "",
    [string]$SourceSchema = "",
    [string]$SourceSslMode = "",
    [string]$TargetHost = "",
    [int]$TargetPort = 0,
    [string]$TargetDbName = "",
    [string]$TargetUser = "",
    [string]$TargetPassword = "",
    [string]$TargetSchema = "",
    [string]$TargetSslMode = "",
    [string]$PgBinDir = "",
    [string]$BackupFile = "",
    [string]$BackupDir = "automation\backups",
    [switch]$DropAndCreateDb,
    [switch]$SkipSourceProbe,
    [switch]$SkipTargetProbe,
    [switch]$SkipBackup,
    [switch]$SkipRestore,
    [switch]$SkipDbInit,
    [switch]$SkipAcceptance
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$ProbeScript = Join-Path $PSScriptRoot "probe_postgres.ps1"
$BackupScript = Join-Path $PSScriptRoot "backup_postgres.ps1"
$RestoreScript = Join-Path $PSScriptRoot "restore_postgres.ps1"
$AcceptScript = Join-Path $PSScriptRoot "accept_postgres.ps1"
$DbInitScript = Join-Path $PSScriptRoot "run_dbinit_task.ps1"

function Resolve-RepoPath([string]$RawPath) {
    if ([string]::IsNullOrWhiteSpace($RawPath)) {
        return ""
    }
    if ([System.IO.Path]::IsPathRooted($RawPath)) {
        return $RawPath
    }
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $RawPath))
}

function Add-DbArgs([System.Collections.Generic.List[string]]$List, [string]$Config, [string]$ConnectionHost, [int]$Port, [string]$DbName, [string]$DbUser, [string]$DbPassword, [string]$SchemaName, [string]$ConnectionSslMode) {
    if ($Config) { $List.Add("--config"); $List.Add($Config) }
    if ($ConnectionHost) { $List.Add("--host"); $List.Add($ConnectionHost) }
    if ($Port -gt 0) { $List.Add("--port"); $List.Add([string]$Port) }
    if ($DbName) { $List.Add("--dbname"); $List.Add($DbName) }
    if ($DbUser) { $List.Add("--user"); $List.Add($DbUser) }
    if ($DbPassword) { $List.Add("--password"); $List.Add($DbPassword) }
    if ($SchemaName) { $List.Add("--schema"); $List.Add($SchemaName) }
    if ($ConnectionSslMode) { $List.Add("--sslmode"); $List.Add($ConnectionSslMode) }
}

function Invoke-Step([string]$Label, [scriptblock]$Action) {
    Write-Host "==> $Label"
    & $Action
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -ne 0) {
        throw "$Label failed with exit code $ExitCode"
    }
}

$ResolvedBackupFile = Resolve-RepoPath $BackupFile
$ResolvedBackupDir = Resolve-RepoPath $BackupDir

$SourceArgs = [System.Collections.Generic.List[string]]::new()
Add-DbArgs -List $SourceArgs -Config $SourceConfig -ConnectionHost $SourceHost -Port $SourcePort -DbName $SourceDbName -DbUser $SourceUser -DbPassword $SourcePassword -SchemaName $SourceSchema -ConnectionSslMode $SourceSslMode

$TargetArgs = [System.Collections.Generic.List[string]]::new()
Add-DbArgs -List $TargetArgs -Config $TargetConfig -ConnectionHost $TargetHost -Port $TargetPort -DbName $TargetDbName -DbUser $TargetUser -DbPassword $TargetPassword -SchemaName $TargetSchema -ConnectionSslMode $TargetSslMode

if (-not $ResolvedBackupFile) {
    if (-not (Test-Path $ResolvedBackupDir)) {
        New-Item -ItemType Directory -Path $ResolvedBackupDir -Force | Out-Null
    }
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $BackupName = if ($SourceDbName) { "$SourceDbName`_$Timestamp.dump" } else { "clawcheck_cutover_$Timestamp.dump" }
    $ResolvedBackupFile = Join-Path $ResolvedBackupDir $BackupName
}

if (-not $SkipSourceProbe) {
    Invoke-Step "Probe source PostgreSQL" {
        & $ProbeScript -VenvDir $VenvDir @SourceArgs
    }
}

if (-not $SkipBackup) {
    Invoke-Step "Backup source PostgreSQL" {
        $BackupParams = @(
            "-VenvDir", $VenvDir
        )
        if ($PgBinDir) {
            $BackupParams += @("-PgBinDir", $PgBinDir)
        }
        if ($ResolvedBackupFile) {
            $BackupParams += @("-OutputFile", $ResolvedBackupFile)
        } else {
            $BackupParams += @("-OutputDir", $ResolvedBackupDir)
        }
        & $BackupScript @BackupParams @SourceArgs
    }
} elseif (-not $ResolvedBackupFile) {
    throw "BackupFile must be provided when SkipBackup is set."
}

if (-not $SkipTargetProbe) {
    Invoke-Step "Probe target PostgreSQL before restore" {
        & $ProbeScript -VenvDir $VenvDir @TargetArgs
    }
}

if (-not $SkipRestore) {
    Invoke-Step "Restore into target PostgreSQL" {
        $RestoreParams = @(
            "-InputFile", $ResolvedBackupFile
            "-VenvDir", $VenvDir
        )
        if ($PgBinDir) {
            $RestoreParams += @("-PgBinDir", $PgBinDir)
        }
        if ($DropAndCreateDb) {
            $RestoreParams += "-DropAndCreateDb"
        }
        & $RestoreScript @RestoreParams @TargetArgs
    }
}

if (-not $SkipDbInit) {
    Invoke-Step "Run dbinit on target PostgreSQL" {
        $DbInitParams = @{
            VenvDir = $VenvDir
        }
        if ($TargetConfig) { $DbInitParams.Config = $TargetConfig }
        $OriginalEnv = @{
            IERP_PG_HOST = $env:IERP_PG_HOST
            IERP_PG_PORT = $env:IERP_PG_PORT
            IERP_PG_DBNAME = $env:IERP_PG_DBNAME
            IERP_PG_USER = $env:IERP_PG_USER
            IERP_PG_PASSWORD = $env:IERP_PG_PASSWORD
            IERP_PG_SCHEMA = $env:IERP_PG_SCHEMA
            IERP_PG_SSLMODE = $env:IERP_PG_SSLMODE
        }
        try {
            if ($TargetHost) { $env:IERP_PG_HOST = $TargetHost }
            if ($TargetPort -gt 0) { $env:IERP_PG_PORT = [string]$TargetPort }
            if ($TargetDbName) { $env:IERP_PG_DBNAME = $TargetDbName }
            if ($TargetUser) { $env:IERP_PG_USER = $TargetUser }
            if ($TargetPassword) { $env:IERP_PG_PASSWORD = $TargetPassword }
            if ($TargetSchema) { $env:IERP_PG_SCHEMA = $TargetSchema }
            if ($TargetSslMode) { $env:IERP_PG_SSLMODE = $TargetSslMode }
            & $DbInitScript @DbInitParams
        }
        finally {
            $env:IERP_PG_HOST = $OriginalEnv.IERP_PG_HOST
            $env:IERP_PG_PORT = $OriginalEnv.IERP_PG_PORT
            $env:IERP_PG_DBNAME = $OriginalEnv.IERP_PG_DBNAME
            $env:IERP_PG_USER = $OriginalEnv.IERP_PG_USER
            $env:IERP_PG_PASSWORD = $OriginalEnv.IERP_PG_PASSWORD
            $env:IERP_PG_SCHEMA = $OriginalEnv.IERP_PG_SCHEMA
            $env:IERP_PG_SSLMODE = $OriginalEnv.IERP_PG_SSLMODE
        }
    }
}

if (-not $SkipAcceptance) {
    Invoke-Step "Acceptance check on target PostgreSQL" {
        & $AcceptScript -VenvDir $VenvDir @TargetArgs
    }
}

Write-Host "PostgreSQL cutover flow completed."
