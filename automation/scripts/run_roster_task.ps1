param(
    [string]$VenvDir = ".venv-win",
    [string]$Config = "",
    [string]$Credentials = "",
    [string]$Selectors = "",
    [string]$Scheme = "",
    [string]$EmploymentType = "",
    [string]$InputFile = "",
    [string]$DownloadsDir = "",
    [string]$DumpJson = "",
    [int]$DownloadTimeoutMinutes = 0,
    [int]$QueryTimeoutSeconds = 0,
    [switch]$Headed,
    [switch]$Headless,
    [switch]$DryRun,
    [switch]$SkipExport,
    [switch]$SkipImport
)

$InvokeScript = Join-Path $PSScriptRoot "invoke_runner_task.ps1"
$ExtraArgs = @()

if ($Scheme) {
    $ExtraArgs += @("--scheme", $Scheme)
}
if ($EmploymentType) {
    $ExtraArgs += @("--employment-type", $EmploymentType)
}
if ($InputFile) {
    $ExtraArgs += @("--input-file", $InputFile)
}
if ($DownloadsDir) {
    $ExtraArgs += @("--downloads-dir", $DownloadsDir)
}
if ($DownloadTimeoutMinutes -gt 0) {
    $ExtraArgs += @("--download-timeout-minutes", [string]$DownloadTimeoutMinutes)
}
if ($QueryTimeoutSeconds -gt 0) {
    $ExtraArgs += @("--query-timeout-seconds", [string]$QueryTimeoutSeconds)
}
if ($SkipExport) {
    $ExtraArgs += "--skip-export"
}
if ($SkipImport) {
    $ExtraArgs += "--skip-import"
}

$InvokeParams = @{
    Action = "roster"
    VenvDir = $VenvDir
    Config = $Config
    Credentials = $Credentials
    Selectors = $Selectors
    DumpJson = $DumpJson
    ExtraArgs = $ExtraArgs
}
if ($Headed) { $InvokeParams.Headed = $true }
if ($Headless) { $InvokeParams.Headless = $true }
if ($DryRun) { $InvokeParams.DryRun = $true }

& $InvokeScript @InvokeParams
exit $LASTEXITCODE
