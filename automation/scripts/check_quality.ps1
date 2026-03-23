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

$RepoRoot = Get-RepoRoot -ScriptRoot $PSScriptRoot
$PythonExe = Resolve-PythonExe -RepoRoot $RepoRoot -VenvDir $VenvDir
if (-not (Test-Path $PythonExe)) {
    throw "Python venv not found: $PythonExe"
}

Push-Location $RepoRoot
try {
    if (-not $SkipRuff) {
        & $PythonExe -m ruff check automation tests
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }

    if (-not $SkipCompileAll) {
        & $PythonExe -m compileall automation
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }

    if (-not $SkipPytest) {
        & $PythonExe -m pytest -q
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }

    if (-not $SkipWebuiBuild) {
        $BuildScript = Join-Path $RepoRoot "automation\scripts\build_webui.ps1"
        if ($NodeDir) {
            & $BuildScript -NodeDir $NodeDir
        }
        else {
            & $BuildScript
        }
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }
}
finally {
    Pop-Location
}

exit 0
