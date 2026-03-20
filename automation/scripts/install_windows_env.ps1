param(
    [string]$PythonVersion = "3.12",
    [string]$VenvDir = ".venv-win",
    [switch]$IncludeDev,
    [string]$Browser = "chromium"
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
            Write-Warning "Python $RequestedVersion is not installed. Falling back to the default Windows Python."
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

Push-Location $RepoRoot
try {
    if (-not (Test-Path $PythonExe)) {
        $PythonCommand = Resolve-PythonCommand -RequestedVersion $PythonVersion
        Write-Host ("Using Python launcher: " + ($PythonCommand -join " "))
        $PythonArgs = @()
        if ($PythonCommand.Count -gt 1) {
            $PythonArgs += $PythonCommand[1..($PythonCommand.Count - 1)]
        }
        $PythonArgs += @("-m", "venv", $VenvDir)
        & $PythonCommand[0] @PythonArgs
    }

    & $PythonExe -m pip install --upgrade pip
    & $PythonExe -m pip install -r automation\requirements.txt

    if ($IncludeDev) {
        & $PythonExe -m pip install -r automation\requirements-dev.txt
    }

    & $PythonExe -m playwright install $Browser
}
finally {
    Pop-Location
}
