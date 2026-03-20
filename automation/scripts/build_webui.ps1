param(
    [string]$ApiBaseUrl = "/api",
    [switch]$Install,
    [string]$NodeDir = ""
)

$ErrorActionPreference = "Stop"

$WebuiDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\webui"))

function Resolve-NpmCommand {
    param(
        [string]$RequestedNodeDir
    )

    $Candidates = @()
    if ($RequestedNodeDir) {
        $Candidates += $RequestedNodeDir
    }
    if ($env:CLAWCHECK_NODE_DIR) {
        $Candidates += $env:CLAWCHECK_NODE_DIR
    }

    foreach ($Candidate in $Candidates) {
        $ResolvedNpm = Join-Path $Candidate "npm.cmd"
        if (Test-Path $ResolvedNpm) {
            return $ResolvedNpm
        }
    }

    $Command = Get-Command npm -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }

    throw "npm was not found. Install Node.js, pass -NodeDir, or set CLAWCHECK_NODE_DIR."
}

Push-Location $WebuiDir
try {
    $NpmCommand = Resolve-NpmCommand -RequestedNodeDir $NodeDir
    $NodeBinDir = Split-Path -Parent $NpmCommand
    $OriginalPath = $env:PATH
    $env:PATH = "$NodeBinDir;$OriginalPath"
    $env:npm_config_script_shell = (Get-Command cmd.exe -ErrorAction Stop).Source

    if ($Install -or -not (Test-Path (Join-Path $WebuiDir "node_modules"))) {
        & $NpmCommand ci
    }

    $env:VITE_API_BASE_URL = $ApiBaseUrl
    & $NpmCommand run build
}
finally {
    Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:npm_config_script_shell -ErrorAction SilentlyContinue
    if ($null -ne $OriginalPath) {
        $env:PATH = $OriginalPath
    }
    Pop-Location
}
