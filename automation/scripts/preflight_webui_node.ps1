param(
    [string]$NodeDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "dev_runtime_helpers.ps1")

$NodeResolution = Resolve-NpmCommand -RequestedNodeDir $NodeDir
Write-Host "NodeSource=$($NodeResolution.Source)"
Write-Host "NodeDir=$($NodeResolution.NodeDir)"

$NodeEnvState = Push-NodeEnvironment -NodeResolution $NodeResolution
try {
    Invoke-WebuiNodePreflight -NodeResolution $NodeResolution
}
finally {
    Pop-NodeEnvironment -State $NodeEnvState
}
