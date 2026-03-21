param(
    [string]$VenvDir = ".venv-win",
    [int]$ApiPort = 8000,
    [int]$WebuiPort = 5173,
    [string]$PgRoot = "",
    [string]$PgDataDir = "",
    [switch]$SkipPostgres,
    [switch]$SkipApi,
    [switch]$SkipTaskDaemon,
    [switch]$SkipWebui
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "dev_runtime_helpers.ps1")

$RepoRoot = Get-RepoRoot -ScriptRoot $PSScriptRoot

function Stop-Service {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceName,
        [int]$Port = 0,
        [string]$CommandPattern = ""
    )

    $Files = Get-ServiceFiles -RepoRoot $RepoRoot -ServiceName $ServiceName
    $Metadata = Read-ServiceMetadata -MetadataPath $Files.MetadataPath
    $ServicePid = 0

    if ($null -ne $Metadata -and $Metadata.pid) {
        $ServicePid = [int]$Metadata.pid
    }
    if ($ServicePid -le 0 -and $Port -gt 0) {
        $ServicePid = Get-PortOwningProcessId -Port $Port
    }
    if ($ServicePid -le 0 -and $CommandPattern) {
        $Found = Find-ProcessByCommandPattern -Pattern $CommandPattern
        if ($null -ne $Found) {
            $ServicePid = [int]$Found.ProcessId
        }
    }

    if ($ServicePid -gt 0) {
        $Stopped = Stop-ProcessTree -ProcessId $ServicePid
        if (-not $Stopped) {
            throw "Failed to stop $ServiceName process tree for PID $ServicePid."
        }
        Write-Host "Stopped $ServiceName PID=$ServicePid"
    }
    else {
        Write-Host "$ServiceName is already stopped."
    }

    Remove-ServiceArtifacts -RepoRoot $RepoRoot -ServiceName $ServiceName
}

if (-not $SkipWebui) {
    Stop-Service -ServiceName "webui_dev" -Port $WebuiPort -CommandPattern "vite|npm\.cmd run dev|start_webui_dev\.ps1"
}

if (-not $SkipTaskDaemon) {
    Stop-Service -ServiceName "task_daemon" -CommandPattern "windows_task_daemon\.py|start_task_daemon\.ps1"
}

if (-not $SkipApi) {
    Stop-Service -ServiceName "api" -Port $ApiPort -CommandPattern "start_api\.ps1|automation\.api\.main:app"
}

if (-not $SkipPostgres) {
    $PostgresArgs = @()
    if ($PgRoot) {
        $PostgresArgs += @("-PgRoot", $PgRoot)
    }
    if ($PgDataDir) {
        $PostgresArgs += @("-DataDir", $PgDataDir)
    }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "automation\scripts\stop_postgres_user_mode.ps1") @PostgresArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to stop PostgreSQL."
    }
}
