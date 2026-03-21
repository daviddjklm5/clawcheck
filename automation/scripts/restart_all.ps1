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

$CommonArgs = @(
    "-VenvDir", $VenvDir,
    "-ApiPort", [string]$ApiPort,
    "-WebuiPort", [string]$WebuiPort
)
if ($PgRoot) {
    $CommonArgs += @("-PgRoot", $PgRoot)
}
if ($PgDataDir) {
    $CommonArgs += @("-PgDataDir", $PgDataDir)
}
if ($SkipPostgres) {
    $CommonArgs += "-SkipPostgres"
}
if ($SkipApi) {
    $CommonArgs += "-SkipApi"
}
if ($SkipTaskDaemon) {
    $CommonArgs += "-SkipTaskDaemon"
}
if ($SkipWebui) {
    $CommonArgs += "-SkipWebui"
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "stop_all.ps1") @CommonArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$StartArgs = @(
    "-VenvDir", $VenvDir,
    "-TaskDaemonConfig", $TaskDaemonConfig,
    "-TaskDaemonStateFile", $TaskDaemonStateFile,
    "-ApiPort", [string]$ApiPort,
    "-ApiListenHost", $ApiListenHost,
    "-ApiLogLevel", $ApiLogLevel,
    "-ApiBaseUrl", $ApiBaseUrl,
    "-WebuiPort", [string]$WebuiPort
)
if ($WebuiDistDir) {
    $StartArgs += @("-WebuiDistDir", $WebuiDistDir)
}
if ($NodeDir) {
    $StartArgs += @("-NodeDir", $NodeDir)
}
if ($PgRoot) {
    $StartArgs += @("-PgRoot", $PgRoot)
}
if ($PgDataDir) {
    $StartArgs += @("-PgDataDir", $PgDataDir)
}
if ($SkipPostgres) {
    $StartArgs += "-SkipPostgres"
}
if ($SkipApi) {
    $StartArgs += "-SkipApi"
}
if ($SkipTaskDaemon) {
    $StartArgs += "-SkipTaskDaemon"
}
if ($SkipWebui) {
    $StartArgs += "-SkipWebui"
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "start_all.ps1") @StartArgs
exit $LASTEXITCODE
