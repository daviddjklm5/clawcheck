param(
    [string]$VenvDir = ".venv-win",
    [string]$Config = "",
    [string]$Credentials = "",
    [string]$Selectors = "",
    [int]$Limit = 100,
    [string]$DocumentNo = "",
    [string]$DocumentNos = "",
    [string]$DownloadsDir = "",
    [string]$DumpJson = "",
    [switch]$Headed,
    [switch]$Headless,
    [switch]$DryRun,
    [switch]$ForceRecollect
)

$InvokeScript = Join-Path $PSScriptRoot "invoke_runner_task.ps1"
$ExtraArgs = @("--limit", [string]$Limit)

if ($DocumentNo) {
    $ExtraArgs += @("--document-no", $DocumentNo)
}
if ($DocumentNos) {
    $ExtraArgs += @("--document-nos", $DocumentNos)
}
if ($DownloadsDir) {
    $ExtraArgs += @("--downloads-dir", $DownloadsDir)
}
if ($ForceRecollect) {
    $ExtraArgs += "--force-recollect"
}

$InvokeParams = @{
    Action = "collect"
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
