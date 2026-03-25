param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("check", "login", "run", "collect", "roster", "orglist", "rolecatalog", "dbinit", "audit", "sync-todo-status")]
    [string]$Action,
    [string]$VenvDir = ".venv-win",
    [string]$Config = "",
    [string]$Credentials = "",
    [string]$Selectors = "",
    [string]$DumpJson = "",
    [string]$LogDir = "automation\logs\windows_tasks",
    [int]$Limit = 100,
    [string]$DocumentNo = "",
    [string]$DocumentNos = "",
    [string]$DownloadsDir = "",
    [string]$InputFile = "",
    [string]$Reason = "",
    [string]$Scheme = "",
    [string]$EmploymentType = "",
    [int]$DownloadTimeoutMinutes = 15,
    [int]$QueryTimeoutSeconds = 60,
    [switch]$Create,
    [switch]$Submit,
    [switch]$Headed,
    [switch]$Headless,
    [switch]$DryRun,
    [switch]$ForceRecollect,
    [switch]$AutoAudit,
    [switch]$AutoBatchApprove,
    [switch]$SkipExport,
    [switch]$SkipImport,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "dev_runtime_helpers.ps1")

if ($Headed -and $Headless) {
    throw "Headed and Headless cannot both be set."
}

$InvokeScript = Join-Path $PSScriptRoot "invoke_runner_task.ps1"
$RunnerExtraArgs = @()

switch ($Action) {
    "collect" {
        $RunnerExtraArgs += @("--limit", [string]$Limit)
        if ($DocumentNo) { $RunnerExtraArgs += @("--document-no", $DocumentNo) }
        if ($DocumentNos) { $RunnerExtraArgs += @("--document-nos", $DocumentNos) }
        if ($DownloadsDir) { $RunnerExtraArgs += @("--downloads-dir", $DownloadsDir) }
        if ($ForceRecollect) { $RunnerExtraArgs += "--force-recollect" }
        if ($AutoAudit) { $RunnerExtraArgs += "--auto-audit" }
        if ($AutoBatchApprove) { $RunnerExtraArgs += "--auto-batch-approve" }
    }
    "audit" {
        $RunnerExtraArgs += @("--limit", [string]$Limit)
        if ($DocumentNo) { $RunnerExtraArgs += @("--document-no", $DocumentNo) }
        if ($DocumentNos) { $RunnerExtraArgs += @("--document-nos", $DocumentNos) }
    }
    "roster" {
        if ($InputFile) { $RunnerExtraArgs += @("--input-file", $InputFile) }
        if ($DownloadsDir) { $RunnerExtraArgs += @("--downloads-dir", $DownloadsDir) }
        if ($Scheme) { $RunnerExtraArgs += @("--scheme", $Scheme) }
        if ($EmploymentType) { $RunnerExtraArgs += @("--employment-type", $EmploymentType) }
        if ($SkipExport) { $RunnerExtraArgs += "--skip-export" }
        if ($SkipImport) { $RunnerExtraArgs += "--skip-import" }
        $RunnerExtraArgs += @("--download-timeout-minutes", [string]$DownloadTimeoutMinutes)
        $RunnerExtraArgs += @("--query-timeout-seconds", [string]$QueryTimeoutSeconds)
    }
    "orglist" {
        if ($InputFile) { $RunnerExtraArgs += @("--input-file", $InputFile) }
        if ($DownloadsDir) { $RunnerExtraArgs += @("--downloads-dir", $DownloadsDir) }
        if ($SkipExport) { $RunnerExtraArgs += "--skip-export" }
        if ($SkipImport) { $RunnerExtraArgs += "--skip-import" }
        $RunnerExtraArgs += @("--download-timeout-minutes", [string]$DownloadTimeoutMinutes)
        $RunnerExtraArgs += @("--query-timeout-seconds", [string]$QueryTimeoutSeconds)
    }
    "run" {
        if ($Create) { $RunnerExtraArgs += "--create" }
        if ($Submit) { $RunnerExtraArgs += "--submit" }
        if ($Reason) { $RunnerExtraArgs += @("--reason", $Reason) }
        if ($DocumentNo) { $RunnerExtraArgs += @("--document-no", $DocumentNo) }
    }
}

if ($ExtraArgs) {
    $RunnerExtraArgs += $ExtraArgs
}

$InvokeParams = @{
    Action = $Action
    VenvDir = $VenvDir
    Config = $Config
    Credentials = $Credentials
    Selectors = $Selectors
    DumpJson = $DumpJson
    LogDir = $LogDir
    ExtraArgs = $RunnerExtraArgs
}
if ($Headed) { $InvokeParams.Headed = $true }
if ($Headless) { $InvokeParams.Headless = $true }
if ($DryRun) { $InvokeParams.DryRun = $true }

& $InvokeScript @InvokeParams
exit $LASTEXITCODE
