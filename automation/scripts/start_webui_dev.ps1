param(
    [string]$NodeDir = "",
    [string]$ApiBaseUrl = "/api",
    [int]$Port = 5173,
    [switch]$Install
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "dev_runtime_helpers.ps1")

$RepoRoot = Get-RepoRoot -ScriptRoot $PSScriptRoot
$WebuiDir = Join-Path $RepoRoot "webui"
$Files = Get-ServiceFiles -RepoRoot $RepoRoot -ServiceName "webui_dev"
$Existing = Read-ServiceMetadata -MetadataPath $Files.MetadataPath
if ($null -ne $Existing -and (Test-ProcessAlive -ProcessId ([int]$Existing.pid))) {
    Write-Host "webui_dev is already running."
    Write-Host "PID=$($Existing.pid)"
    Write-Host "URL=http://127.0.0.1:$($Existing.port)/"
    Write-Host "Stdout=$($Existing.logStdout)"
    Write-Host "Stderr=$($Existing.logStderr)"
    exit 0
}

if ($null -ne $Existing) {
    Remove-ServiceArtifacts -RepoRoot $RepoRoot -ServiceName "webui_dev"
}

$NodeResolution = Resolve-NpmCommand -RequestedNodeDir $NodeDir
$NodeEnvState = Push-NodeEnvironment -NodeResolution $NodeResolution

Push-Location $WebuiDir
try {
    Invoke-WebuiNodePreflight -NodeResolution $NodeResolution

    if ($Install -or -not (Test-Path (Join-Path $WebuiDir "node_modules"))) {
        & $NodeResolution.NpmCommand ci
        if ($LASTEXITCODE -ne 0) {
            throw "npm ci failed."
        }
    }

    $env:VITE_API_BASE_URL = $ApiBaseUrl
    $Command = "`"$($NodeResolution.NpmCommand)`" run dev -- --host 127.0.0.1 --port $Port"
    $Process = Start-ManagedProcess `
        -FilePath (Get-Command cmd.exe -ErrorAction Stop).Source `
        -ArgumentList @("/d", "/c", $Command) `
        -WorkingDirectory $WebuiDir `
        -StdoutLog $Files.StdoutLog `
        -StderrLog $Files.StderrLog
}
finally {
    Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue
    Pop-Location
    Pop-NodeEnvironment -State $NodeEnvState
}

Start-Sleep -Seconds 2

Write-Utf8File -Path $Files.PidPath -Content ([string]$Process.Id)
Write-ServiceMetadata -MetadataPath $Files.MetadataPath -Payload @{
    service    = "webui_dev"
    pid        = $Process.Id
    port       = $Port
    healthUrl  = "http://127.0.0.1:$Port/"
    healthType = "http"
    nodeSource = $NodeResolution.Source
    nodeDir    = $NodeResolution.NodeDir
    logStdout  = $Files.StdoutLog
    logStderr  = $Files.StderrLog
    startedAt  = (Get-Date).ToString("s")
}

Write-Host "Started webui_dev"
Write-Host "PID=$($Process.Id)"
Write-Host "URL=http://127.0.0.1:$Port/"
Write-Host "NodeSource=$($NodeResolution.Source)"
Write-Host "Stdout=$($Files.StdoutLog)"
Write-Host "Stderr=$($Files.StderrLog)"
