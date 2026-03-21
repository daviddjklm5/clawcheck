param(
    [string]$VenvDir = ".venv-win",
    [string]$TaskDaemonConfig = "automation/config/windows_task_daemon.local.json",
    [string]$TaskDaemonStateFile = "automation/state/windows_task_daemon_state.json",
    [int]$ApiPort = 8000,
    [string]$ApiListenHost = "127.0.0.1",
    [string]$ApiLogLevel = "info",
    [string]$WebuiDistDir = "",
    [string]$NodeDir = "",
    [string]$ApiBaseUrl = "/api",
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

function Start-PowerShellService {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceName,
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,
        [string[]]$ScriptArguments = @(),
        [int]$Port = 0,
        [string]$HealthUrl = ""
    )

    $Files = Get-ServiceFiles -RepoRoot $RepoRoot -ServiceName $ServiceName
    $Existing = Read-ServiceMetadata -MetadataPath $Files.MetadataPath
    if ($null -ne $Existing -and (Test-ProcessAlive -ProcessId ([int]$Existing.pid))) {
        Write-Host "$ServiceName is already running."
        return
    }

    if ($null -ne $Existing) {
        Remove-ServiceArtifacts -RepoRoot $RepoRoot -ServiceName $ServiceName
    }

    $Arguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $ScriptPath
    ) + $ScriptArguments

    $Process = Start-ManagedProcess `
        -FilePath (Get-Command powershell.exe -ErrorAction Stop).Source `
        -ArgumentList $Arguments `
        -WorkingDirectory $RepoRoot `
        -StdoutLog $Files.StdoutLog `
        -StderrLog $Files.StderrLog

    Start-Sleep -Seconds 2

    Write-Utf8File -Path $Files.PidPath -Content ([string]$Process.Id)
    Write-ServiceMetadata -MetadataPath $Files.MetadataPath -Payload @{
        service    = $ServiceName
        pid        = $Process.Id
        port       = $Port
        healthUrl  = $HealthUrl
        logStdout  = $Files.StdoutLog
        logStderr  = $Files.StderrLog
        startedAt  = (Get-Date).ToString("s")
        command    = $ScriptPath
    }

    Write-Host "Started $ServiceName"
    Write-Host "PID=$($Process.Id)"
    if ($Port -gt 0) {
        Write-Host "Port=$Port"
    }
    if ($HealthUrl) {
        Write-Host "HealthUrl=$HealthUrl"
    }
    Write-Host "Stdout=$($Files.StdoutLog)"
    Write-Host "Stderr=$($Files.StderrLog)"
}

if (-not $SkipPostgres) {
    $PostgresArgs = @()
    if ($PgRoot) {
        $PostgresArgs += @("-PgRoot", $PgRoot)
    }
    if ($PgDataDir) {
        $PostgresArgs += @("-DataDir", $PgDataDir)
    }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "automation\scripts\start_postgres_user_mode.ps1") @PostgresArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start PostgreSQL."
    }
}

if (-not $SkipApi) {
    $ApiArgs = @(
        "-VenvDir", $VenvDir,
        "-ListenHost", $ApiListenHost,
        "-Port", [string]$ApiPort,
        "-LogLevel", $ApiLogLevel
    )
    if ($WebuiDistDir) {
        $ApiArgs += @("-WebuiDistDir", $WebuiDistDir)
    }

    Start-PowerShellService `
        -ServiceName "api" `
        -ScriptPath (Join-Path $RepoRoot "automation\scripts\start_api.ps1") `
        -ScriptArguments $ApiArgs `
        -Port $ApiPort `
        -HealthUrl "http://127.0.0.1:$ApiPort/api/health"
}

if (-not $SkipTaskDaemon) {
    $ResolvedTaskConfig = Join-Path $RepoRoot $TaskDaemonConfig
    $ExampleConfig = Join-Path $RepoRoot "automation\config\windows_task_daemon.example.json"
    if (-not (Test-Path $ResolvedTaskConfig) -and (Test-Path $ExampleConfig)) {
        Copy-Item -Path $ExampleConfig -Destination $ResolvedTaskConfig
    }

    Start-PowerShellService `
        -ServiceName "task_daemon" `
        -ScriptPath (Join-Path $RepoRoot "automation\scripts\start_task_daemon.ps1") `
        -ScriptArguments @(
            "-VenvDir", $VenvDir,
            "-Config", $TaskDaemonConfig,
            "-StateFile", $TaskDaemonStateFile
        )
}

if (-not $SkipWebui) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "automation\scripts\start_webui_dev.ps1") -NodeDir $NodeDir -ApiBaseUrl $ApiBaseUrl -Port $WebuiPort
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start webui_dev."
    }
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "automation\scripts\status_all.ps1") -VenvDir $VenvDir -TaskDaemonConfig $TaskDaemonConfig -TaskDaemonStateFile $TaskDaemonStateFile -ApiPort $ApiPort -WebuiPort $WebuiPort
