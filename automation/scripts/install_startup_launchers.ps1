param(
    [string]$RepoRoot = "",
    [string]$VenvDir = ".venv-win",
    [int]$ApiPort = 8000,
    [string]$StartupDir = "",
    [string]$TaskDaemonConfig = "automation/config/windows_task_daemon.local.json",
    [switch]$InstallTaskDaemon = $true
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    $RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
}
if (-not $StartupDir) {
    $StartupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
}

New-Item -ItemType Directory -Path $StartupDir -Force | Out-Null

$DaemonExamplePath = Join-Path $RepoRoot "automation\config\windows_task_daemon.example.json"
$DaemonLocalPath = Join-Path $RepoRoot $TaskDaemonConfig
if ($InstallTaskDaemon -and -not (Test-Path $DaemonLocalPath) -and (Test-Path $DaemonExamplePath)) {
    Copy-Item -Path $DaemonExamplePath -Destination $DaemonLocalPath
}

$PostgresLauncher = @"
@echo off
start "clawcheck-postgres" powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "$RepoRoot\automation\scripts\start_postgres_user_mode.ps1"
"@

$ApiLauncher = @"
@echo off
start "clawcheck-api" powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "$RepoRoot\automation\scripts\start_api.ps1" -VenvDir "$VenvDir" -Port $ApiPort
"@

$TaskDaemonLauncher = @"
@echo off
start "clawcheck-task-daemon" powershell.exe -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "$RepoRoot\automation\scripts\start_task_daemon.ps1" -VenvDir "$VenvDir" -Config "$TaskDaemonConfig"
"@

Set-Content -Path (Join-Path $StartupDir "clawcheck-postgres.cmd") -Value $PostgresLauncher -Encoding ASCII
Set-Content -Path (Join-Path $StartupDir "clawcheck-api.cmd") -Value $ApiLauncher -Encoding ASCII
if ($InstallTaskDaemon) {
    Set-Content -Path (Join-Path $StartupDir "clawcheck-task-daemon.cmd") -Value $TaskDaemonLauncher -Encoding ASCII
}

Write-Host "Installed startup launchers into $StartupDir"
