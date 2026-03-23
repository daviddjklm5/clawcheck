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
        $PytestReportPath = Join-Path ([System.IO.Path]::GetTempPath()) "clawcheck_pytest_junit.xml"
        Remove-Item $PytestReportPath -ErrorAction SilentlyContinue
        & $PythonExe -m pytest -q -p no:unraisableexception -p no:threadexception --junitxml $PytestReportPath
        $PytestExitCode = $LASTEXITCODE
        if (-not (Test-Path $PytestReportPath)) {
            exit $PytestExitCode
        }

        [xml]$PytestReport = Get-Content $PytestReportPath -Raw
        $SuiteNodes = @($PytestReport.testsuites.testsuite)
        if ($SuiteNodes.Count -eq 0 -and $null -ne $PytestReport.testsuite) {
            $SuiteNodes = @($PytestReport.testsuite)
        }

        $FailedCount = 0
        $ErrorCount = 0
        foreach ($Suite in $SuiteNodes) {
            $FailedCount += [int]$Suite.failures
            $ErrorCount += [int]$Suite.errors
        }
        if ($FailedCount -ne 0 -or $ErrorCount -ne 0) {
            exit $PytestExitCode
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
