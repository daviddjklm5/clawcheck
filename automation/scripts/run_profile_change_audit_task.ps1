param(
    [string]$VenvDir = ".venv-win",
    [string]$Config = "",
    [string]$Credentials = "",
    [string]$Selectors = "",
    [string]$DumpJson = "",
    [string]$DownloadsDir = "",
    [int]$Limit = 20,
    [int]$PageSize = 100,
    [switch]$Headed,
    [switch]$Headless,
    [switch]$DryRun,
    [switch]$DownloadAttachments,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$InvokeParams = @{
    Action = "profile-change-audit"
    VenvDir = $VenvDir
    Config = $Config
    Credentials = $Credentials
    Selectors = $Selectors
    DumpJson = $DumpJson
    Limit = $Limit
    PageSize = $PageSize
    DownloadsDir = $DownloadsDir
    ExtraArgs = $ExtraArgs
}
if ($Headed) { $InvokeParams.Headed = $true }
if ($Headless) { $InvokeParams.Headless = $true }
if ($DryRun) { $InvokeParams.DryRun = $true }
if ($DownloadAttachments) { $InvokeParams.DownloadAttachments = $true }

& (Join-Path $PSScriptRoot "run_windows_task.ps1") @InvokeParams
exit $LASTEXITCODE
