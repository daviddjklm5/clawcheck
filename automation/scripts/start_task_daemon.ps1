param(
    [string]$VenvDir = ".venv-win",
    [string]$Config = "automation/config/windows_task_daemon.local.json",
    [string]$StateFile = "automation/state/windows_task_daemon_state.json",
    [switch]$Once
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "dev_runtime_helpers.ps1")

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$PythonExe = Join-Path $RepoRoot "$VenvDir\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    throw "Python venv not found: $PythonExe"
}

Push-Location $RepoRoot
try {
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    $Args = @(
        "-m",
        "automation.scripts.windows_task_daemon",
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
