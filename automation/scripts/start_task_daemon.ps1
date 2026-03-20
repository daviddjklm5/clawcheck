param(
    [string]$VenvDir = ".venv-win",
    [string]$Config = "automation/config/windows_task_daemon.local.json",
    [string]$StateFile = "automation/state/windows_task_daemon_state.json",
    [switch]$Once
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$PythonExe = Join-Path $RepoRoot "$VenvDir\Scripts\python.exe"
$DaemonScript = Join-Path $RepoRoot "automation\scripts\windows_task_daemon.py"

if (-not (Test-Path $PythonExe)) {
    throw "Python venv not found: $PythonExe"
}

Push-Location $RepoRoot
try {
    $Args = @(
        $DaemonScript,
        "--config",
        $Config,
        "--state-file",
        $StateFile
    )
    if ($Once) {
        $Args += "--once"
    }

    & $PythonExe @Args
}
finally {
    Pop-Location
}
