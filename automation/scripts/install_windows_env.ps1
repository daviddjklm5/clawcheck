param(
    [string]$PythonVersion = "3.12",
    [string]$VenvDir = ".venv-win",
    [switch]$IncludeDev,
    [string]$Browser = "chromium",
    [switch]$ForceRecreateVenv,
    [switch]$SkipRecreateOnVersionMismatch,
    [switch]$SkipPlaywrightInstall
)

$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$PythonExe = Join-Path $RepoRoot "$VenvDir\Scripts\python.exe"

function Resolve-PythonCommand {
    param(
        [string]$RequestedVersion
    )

    if (Get-Command py -ErrorAction SilentlyContinue) {
        if (-not [string]::IsNullOrWhiteSpace($RequestedVersion)) {
            $VersionCheck = & py "-$RequestedVersion" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($VersionCheck | Out-String).Trim())) {
                return @("py", "-$RequestedVersion")
            }
            throw "Python $RequestedVersion is not installed. Install the requested version first."
        }

        $DefaultCheck = & py -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($DefaultCheck | Out-String).Trim())) {
            return @("py")
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }

    throw "No usable Windows Python was found. Install Python 3.10+ first."
}

function Get-PythonVersion {
    param(
        [string]$PythonExecutable
    )

    if (-not (Test-Path $PythonExecutable)) {
        return ""
    }

    $Version = & $PythonExecutable -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    if ($LASTEXITCODE -ne 0) {
        return ""
    }
    return ($Version | Out-String).Trim()
}

function Test-VersionMatch {
    param(
        [string]$ActualVersion,
        [string]$RequestedVersion
    )

    if ([string]::IsNullOrWhiteSpace($RequestedVersion)) {
        return $true
    }
    if ([string]::IsNullOrWhiteSpace($ActualVersion)) {
        return $false
    }
    return $ActualVersion.StartsWith($RequestedVersion)
}

Push-Location $RepoRoot
try {
    $PythonCommand = Resolve-PythonCommand -RequestedVersion $PythonVersion
    $PythonCommandText = $PythonCommand -join " "
    $PythonCommandArgs = @()
    if ($PythonCommand.Count -gt 1) {
        $PythonCommandArgs += $PythonCommand[1..($PythonCommand.Count - 1)]
    }

    $ResolvedPythonExe = & $PythonCommand[0] @PythonCommandArgs -c "import sys; print(sys.executable)"
    $ResolvedPythonExe = ($ResolvedPythonExe | Out-String).Trim()
    $ResolvedPythonVersion = & $PythonCommand[0] @PythonCommandArgs -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    $ResolvedPythonVersion = ($ResolvedPythonVersion | Out-String).Trim()

    $ExistingVenvVersion = Get-PythonVersion -PythonExecutable $PythonExe
    $ShouldRecreateVenv = $ForceRecreateVenv
    $RecreateReason = ""

    if (-not (Test-Path $PythonExe)) {
        $ShouldRecreateVenv = $true
        $RecreateReason = "venv_missing"
    }
    elseif (-not (Test-VersionMatch -ActualVersion $ExistingVenvVersion -RequestedVersion $PythonVersion)) {
        if ($SkipRecreateOnVersionMismatch) {
            Write-Warning "Existing venv version $ExistingVenvVersion does not match requested Python $PythonVersion, but recreation was skipped by parameter."
        }
        else {
            $ShouldRecreateVenv = $true
            $RecreateReason = "version_mismatch"
        }
    }

    Write-Host "RequestedPythonVersion=$PythonVersion"
    Write-Host "ResolvedPythonLauncher=$PythonCommandText"
    Write-Host "ResolvedPythonExe=$ResolvedPythonExe"
    Write-Host "ResolvedPythonVersion=$ResolvedPythonVersion"
    Write-Host "ExistingVenvVersion=$ExistingVenvVersion"
    Write-Host "WillRecreateVenv=$ShouldRecreateVenv"
    if ($RecreateReason) {
        Write-Host "RecreateReason=$RecreateReason"
    }

    if ($ShouldRecreateVenv) {
        if (Test-Path $VenvDir) {
            Remove-Item -Recurse -Force $VenvDir
        }

        $PythonArgs = @()
        if ($PythonCommand.Count -gt 1) {
            $PythonArgs += $PythonCommand[1..($PythonCommand.Count - 1)]
        }
        $PythonArgs += @("-m", "venv", $VenvDir)
        & $PythonCommand[0] @PythonArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create virtual environment in $VenvDir."
        }
    }

    & $PythonExe -m pip install --upgrade pip
    & $PythonExe -m pip install -r automation\requirements.txt

    if ($IncludeDev) {
        & $PythonExe -m pip install -r automation\requirements-dev.txt
    }

    if (-not $SkipPlaywrightInstall) {
        & $PythonExe -m playwright install $Browser
    }
}
finally {
    Pop-Location
}
