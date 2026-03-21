param(
    [string]$VenvDir = ".venv-win",
    [string]$TaskDaemonConfig = "automation/config/windows_task_daemon.local.json",
    [string]$TaskDaemonStateFile = "automation/state/windows_task_daemon_state.json",
    [int]$ApiPort = 8000,
    [int]$WebuiPort = 5173,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "dev_runtime_helpers.ps1")

$RepoRoot = Get-RepoRoot -ScriptRoot $PSScriptRoot
$RuntimeDir = Get-DevRuntimeDir -RepoRoot $RepoRoot
$CheckedAt = (Get-Date).ToString("s")

function Get-ServiceStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceName,
        [int]$DefaultPort = 0,
        [string]$HealthUrl = "",
        [string]$CommandPattern = "",
        [string]$HealthType = "none"
    )

    $Files = Get-ServiceFiles -RepoRoot $RepoRoot -ServiceName $ServiceName
    $Metadata = Read-ServiceMetadata -MetadataPath $Files.MetadataPath
    $ServicePid = 0
    $Port = $DefaultPort
    $Detail = ""
    $StdoutLog = $Files.StdoutLog
    $StderrLog = $Files.StderrLog
    $Running = $false
    $HealthStatus = "unknown"

    if ($null -ne $Metadata) {
        if ($Metadata.pid) {
            $ServicePid = [int]$Metadata.pid
        }
        if ($Metadata.port) {
            $Port = [int]$Metadata.port
        }
        if ($Metadata.healthUrl) {
            $HealthUrl = [string]$Metadata.healthUrl
        }
        if ($Metadata.logStdout) {
            $StdoutLog = [string]$Metadata.logStdout
        }
        if ($Metadata.logStderr) {
            $StderrLog = [string]$Metadata.logStderr
        }
    }

    if ($ServicePid -gt 0 -and (Test-ProcessAlive -ProcessId $ServicePid)) {
        $Running = $true
    }

    if (-not $Running -and $Port -gt 0) {
        $PortPid = Get-PortOwningProcessId -Port $Port
        if ($PortPid -gt 0) {
            $ServicePid = $PortPid
            $Running = $true
        }
    }

    if (-not $Running -and $CommandPattern) {
        $Found = Find-ProcessByCommandPattern -Pattern $CommandPattern
        if ($null -ne $Found) {
            $ServicePid = [int]$Found.ProcessId
            $Running = $true
            if (-not $Detail) {
                $Detail = "Detected by command line pattern."
            }
        }
    }

    switch ($HealthType) {
        "http" {
            if ($HealthUrl) {
                $Health = Invoke-HealthRequest -Url $HealthUrl
                $HealthStatus = if ($Health.Ok) { "ok" } else { "error" }
                if (-not $Health.Ok) {
                    $Detail = $Health.Message
                }
            }
        }
        "tcp" {
            if ($Port -gt 0) {
                $TcpOk = Test-TcpPort -ConnectionHost "127.0.0.1" -Port $Port
                $HealthStatus = if ($TcpOk) { "ok" } else { "error" }
                if (-not $TcpOk) {
                    $Detail = "TCP port is not reachable."
                }
            }
        }
        default {
            $HealthStatus = if ($Running) { "ok" } else { "unknown" }
        }
    }

    return [ordered]@{
        service      = $ServiceName
        enabled      = $true
        running      = $Running
        pid          = $ServicePid
        port         = $Port
        healthUrl    = $HealthUrl
        healthStatus = $HealthStatus
        logStdout    = $StdoutLog
        logStderr    = $StderrLog
        detail       = $Detail
        checkedAt    = $CheckedAt
    }
}

$Statuses = [System.Collections.Generic.List[object]]::new()

$Statuses.Add((Get-ServiceStatus -ServiceName "api" -DefaultPort $ApiPort -HealthUrl "http://127.0.0.1:$ApiPort/api/health" -CommandPattern "start_api\.ps1|automation\.api\.main:app" -HealthType "http"))
$Statuses.Add((Get-ServiceStatus -ServiceName "task_daemon" -CommandPattern "windows_task_daemon\.py|start_task_daemon\.ps1"))
$Statuses.Add((Get-ServiceStatus -ServiceName "webui_dev" -DefaultPort $WebuiPort -HealthUrl "http://127.0.0.1:$WebuiPort/" -CommandPattern "vite|npm\.cmd run dev|start_webui_dev\.ps1" -HealthType "http"))

$PostgresStatus = [ordered]@{
    service      = "postgres"
    enabled      = $true
    running      = $false
    pid          = 0
    port         = 0
    healthUrl    = ""
    healthStatus = "unknown"
    logStdout    = ""
    logStderr    = ""
    detail       = ""
    checkedAt    = $CheckedAt
}

$ProbeScript = Join-Path $RepoRoot "automation\scripts\probe_postgres.ps1"
$ProbeJson = Join-Path $RuntimeDir "postgres_probe.json"
$ConnectionInfoJson = Join-Path $RuntimeDir "postgres_connection_info.json"
if (Test-Path $ProbeJson) {
    Remove-Item -Force $ProbeJson
}
if (Test-Path $ConnectionInfoJson) {
    Remove-Item -Force $ConnectionInfoJson
}

try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ProbeScript -VenvDir $VenvDir -DumpJson $ProbeJson *> $null
    $ProbeExitCode = $LASTEXITCODE
}
catch {
    $ProbeExitCode = 1
    $PostgresStatus.detail = $_.Exception.Message
}

if (Test-Path $ProbeJson) {
    try {
        $ProbePayload = Get-Content -Path $ProbeJson -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($ProbePayload.connection.port) {
            $PostgresStatus.port = [int]$ProbePayload.connection.port
        }
        if ($ProbePayload.status -eq "ok") {
            $PostgresStatus.running = $true
            $PostgresStatus.healthStatus = if ($ProbePayload.acceptance.passed) { "ok" } else { "failed" }
            $PostgresStatus.detail = [string]$ProbePayload.acceptance.message
        }
        else {
            $PostgresStatus.healthStatus = "error"
            $PostgresStatus.detail = [string]$ProbePayload.message
        }
    }
    catch {
        $PostgresStatus.healthStatus = "error"
        $PostgresStatus.detail = "Failed to parse PostgreSQL probe output."
    }
}
elseif ($ProbeExitCode -ne 0) {
    $PostgresStatus.healthStatus = "error"
    if (-not $PostgresStatus.detail) {
        $PostgresStatus.detail = "PostgreSQL probe script failed before producing output."
    }
}

if ($PostgresStatus.port -le 0) {
    $PythonExe = Resolve-PythonExe -RepoRoot $RepoRoot -VenvDir $VenvDir
    if (Test-Path $PythonExe) {
        & $PythonExe (Join-Path $RepoRoot "automation\scripts\db_admin.py") connection-info --dump-json $ConnectionInfoJson *> $null
        if ((Test-Path $ConnectionInfoJson) -and ($LASTEXITCODE -eq 0)) {
            try {
                $ConnectionInfo = Get-Content -Path $ConnectionInfoJson -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($ConnectionInfo.port) {
                    $PostgresStatus.port = [int]$ConnectionInfo.port
                }
            }
            catch {
            }
        }
    }
}

if ($PostgresStatus.port -gt 0) {
    $PostgresStatus.pid = Get-PortOwningProcessId -Port ([int]$PostgresStatus.port)
}
if (-not $PostgresStatus.running -and $PostgresStatus.port -gt 0) {
    $PostgresStatus.running = Test-TcpPort -ConnectionHost "127.0.0.1" -Port ([int]$PostgresStatus.port)
    if ($PostgresStatus.running -and $PostgresStatus.healthStatus -ne "ok") {
        $PostgresStatus.healthStatus = "tcp_only"
        if (-not $PostgresStatus.detail) {
            $PostgresStatus.detail = "Port is reachable but structured probe did not succeed."
        }
    }
}

$Statuses.Add($PostgresStatus)

$Payload = [ordered]@{
    checkedAt = $CheckedAt
    runtimeDir = $RuntimeDir
    taskDaemonConfig = $TaskDaemonConfig
    taskDaemonStateFile = $TaskDaemonStateFile
    services = $Statuses
}

$StatusJsonPath = Join-Path $RuntimeDir "status.json"
Write-Utf8File -Path $StatusJsonPath -Content ($Payload | ConvertTo-Json -Depth 8)

if ($AsJson) {
    Get-Content -Path $StatusJsonPath -Raw -Encoding UTF8
    exit 0
}

foreach ($Service in $Statuses) {
    Write-Host "[$($Service.service)] running=$($Service.running) pid=$($Service.pid) port=$($Service.port) health=$($Service.healthStatus)"
    if ($Service.healthUrl) {
        Write-Host "  url=$($Service.healthUrl)"
    }
    if ($Service.logStdout) {
        Write-Host "  stdout=$($Service.logStdout)"
    }
    if ($Service.logStderr) {
        Write-Host "  stderr=$($Service.logStderr)"
    }
    if ($Service.detail) {
        Write-Host "  detail=$($Service.detail)"
    }
}

Write-Host "statusJson=$StatusJsonPath"
