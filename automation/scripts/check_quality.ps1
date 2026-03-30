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
        $PytestStdoutPath = Join-Path ([System.IO.Path]::GetTempPath()) "clawcheck_pytest_stdout.log"
        $PytestStderrPath = Join-Path ([System.IO.Path]::GetTempPath()) "clawcheck_pytest_stderr.log"
        Remove-Item $PytestReportPath -ErrorAction SilentlyContinue
        Remove-Item $PytestStdoutPath -ErrorAction SilentlyContinue
        Remove-Item $PytestStderrPath -ErrorAction SilentlyContinue

        $PytestArgs = @(
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:unraisableexception",
            "-p",
            "no:threadexception",
            "--junitxml",
            $PytestReportPath
        )
        $PytestProcess = Start-Process `
            -FilePath $PythonExe `
            -ArgumentList $PytestArgs `
            -WorkingDirectory $RepoRoot `
            -RedirectStandardOutput $PytestStdoutPath `
            -RedirectStandardError $PytestStderrPath `
            -PassThru `
            -Wait
        $PytestExitCode = $PytestProcess.ExitCode

        if (Test-Path $PytestStdoutPath) {
            Get-Content $PytestStdoutPath
        }
        if (Test-Path $PytestStderrPath) {
            Get-Content $PytestStderrPath
        }
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
        $TestCount = 0
        foreach ($Suite in $SuiteNodes) {
            $TestCount += [int]$Suite.tests
            $FailedCount += [int]$Suite.failures
            $ErrorCount += [int]$Suite.errors
        }
        if ($FailedCount -ne 0 -or $ErrorCount -ne 0) {
            exit $PytestExitCode
        }
        if ($PytestExitCode -ne 0) {
            if ($TestCount -gt 0) {
                Write-Warning "pytest exited with code $PytestExitCode after reporting zero failures/errors; continuing with JUnit result."
            }
            else {
                exit $PytestExitCode
            }
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
