param(
    [string]$VenvDir = ".venv-win",
    [string]$NodeDir = "",
    [switch]$SkipRuff,
    [switch]$SkipCompileAll,
    [switch]$SkipPytest,
    [switch]$SkipWebuiBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "dev_runtime_helpers.ps1")

function Invoke-PythonCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe,
        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList
    )

    $Process = Start-Process -FilePath $PythonExe -ArgumentList $ArgumentList -NoNewWindow -Wait -PassThru
    if ($Process.ExitCode -ne 0) {
        exit $Process.ExitCode
    }
}

$RepoRoot = Get-RepoRoot -ScriptRoot $PSScriptRoot
$PythonExe = Resolve-PythonExe -RepoRoot $RepoRoot -VenvDir $VenvDir
if (-not (Test-Path $PythonExe)) {
    throw "Python venv not found: $PythonExe"
}

Push-Location $RepoRoot
try {
    if (-not $SkipRuff) {
        Invoke-PythonCommand -PythonExe $PythonExe -ArgumentList @("-m", "ruff", "check", "automation", "tests")
    }

    if (-not $SkipCompileAll) {
        Invoke-PythonCommand -PythonExe $PythonExe -ArgumentList @("-m", "compileall", "automation")
    }

    if (-not $SkipPytest) {
        $PytestRunnerPath = Join-Path ([System.IO.Path]::GetTempPath()) "clawcheck_pytest_runner.py"
        @'
import os
import sys
import pytest

rc = pytest.main(["-q", "-p", "no:unraisableexception"])
print(f"pytest_main_rc={rc}")
sys.stdout.flush()
sys.stderr.flush()
os._exit(rc)
'@ | Set-Content -Path $PytestRunnerPath -Encoding utf8
        try {
            Invoke-PythonCommand -PythonExe $PythonExe -ArgumentList @($PytestRunnerPath)
        }
        finally {
            Remove-Item $PytestRunnerPath -ErrorAction SilentlyContinue
        }
    }

    if (-not $SkipWebuiBuild) {
        $BuildScript = Join-Path $RepoRoot "automation\scripts\build_webui.ps1"
        Write-Host "Running webui build..."
        if ($NodeDir) {
            & $BuildScript -NodeDir $NodeDir
        }
        else {
            & $BuildScript
        }
        Write-Host "Webui build completed."
    }
}
finally {
    Pop-Location
}

exit 0
