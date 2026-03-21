param(
    [string]$ApiBaseUrl = "/api",
    [switch]$Install,
    [string]$NodeDir = ""
)

$ErrorActionPreference = "Stop"

$HelperPath = Join-Path $PSScriptRoot "dev_runtime_helpers.ps1"
. $HelperPath

$WebuiDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\webui"))

Push-Location $WebuiDir
try {
    $NodeResolution = Resolve-NpmCommand -RequestedNodeDir $NodeDir
    Write-Host "NodeSource=$($NodeResolution.Source)"
    Write-Host "NodeDir=$($NodeResolution.NodeDir)"
    $NodeEnvState = Push-NodeEnvironment -NodeResolution $NodeResolution

    if ($Install -or -not (Test-Path (Join-Path $WebuiDir "node_modules"))) {
        & $NodeResolution.NpmCommand ci
    }

    $env:VITE_API_BASE_URL = $ApiBaseUrl
    & $NodeResolution.NpmCommand run build
}
finally {
    Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue
    if ($null -ne $NodeEnvState) {
        Pop-NodeEnvironment -State $NodeEnvState
    }
    Pop-Location
}
