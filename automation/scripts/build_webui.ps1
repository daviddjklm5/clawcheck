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
    Invoke-WebuiNodePreflight -NodeResolution $NodeResolution

    if ($Install -or -not (Test-Path (Join-Path $WebuiDir "node_modules"))) {
        & $NodeResolution.NpmCommand ci
        if ($LASTEXITCODE -ne 0) {
            throw "npm ci failed."
        }
    }

    $env:VITE_API_BASE_URL = $ApiBaseUrl
    & $NodeResolution.NpmCommand exec -- tsc --noEmit
    if ($LASTEXITCODE -ne 0) {
        throw "tsc --noEmit failed."
    }

    & $NodeResolution.NpmCommand exec -- vite build
    if ($LASTEXITCODE -ne 0) {
        throw "vite build failed."
    }
}
finally {
    Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue
    if ($null -ne $NodeEnvState) {
        Pop-NodeEnvironment -State $NodeEnvState
    }
    Pop-Location
}
