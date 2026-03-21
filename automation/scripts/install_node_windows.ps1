param(
    [string]$Version = "24.14.0",
    [string]$InstallRoot = "",
    [switch]$Force,
    [switch]$PersistUserEnv = $true,
    [switch]$PersistUserPath
)

$ErrorActionPreference = "Stop"

if (-not $InstallRoot) {
    $InstallRoot = Join-Path $env:LOCALAPPDATA "clawcheck\tools"
}

$NodeDir = Join-Path $InstallRoot "node-v$Version-win-x64"
$NodeExe = Join-Path $NodeDir "node.exe"
$NpmCmd = Join-Path $NodeDir "npm.cmd"
$ZipPath = Join-Path $env:TEMP "node-v$Version-win-x64.zip"
$DownloadUrl = "https://nodejs.org/dist/v$Version/node-v$Version-win-x64.zip"

if ($Force -and (Test-Path $NodeDir)) {
    Remove-Item -Recurse -Force $NodeDir
}

if (-not (Test-Path $NodeExe)) {
    New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null

    if (Test-Path $ZipPath) {
        Remove-Item -Force $ZipPath
    }

    Write-Host "Downloading Node.js v$Version from $DownloadUrl"
    & curl.exe -L $DownloadUrl -o $ZipPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to download Node.js."
    }

    Expand-Archive -Path $ZipPath -DestinationPath $InstallRoot -Force
}

if (-not (Test-Path $NodeExe) -or -not (Test-Path $NpmCmd)) {
    throw "Node.js installation failed. node.exe or npm.cmd is missing."
}

if ($PersistUserEnv) {
    [Environment]::SetEnvironmentVariable("CLAWCHECK_NODE_DIR", $NodeDir, "User")
}

if ($PersistUserPath) {
    $CurrentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $PathEntries = @()
    if ($CurrentUserPath) {
        $PathEntries = $CurrentUserPath.Split(';', [System.StringSplitOptions]::RemoveEmptyEntries)
    }
    if ($PathEntries -notcontains $NodeDir) {
        $NewUserPath = @($NodeDir) + $PathEntries
        [Environment]::SetEnvironmentVariable("Path", ($NewUserPath -join ';'), "User")
    }
}

Write-Host "NodeDir=$NodeDir"
Write-Host "NodeExe=$NodeExe"
Write-Host "NpmCmd=$NpmCmd"
Write-Host "PersistUserPath=$PersistUserPath"
