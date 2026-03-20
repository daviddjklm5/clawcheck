param(
    [string]$VenvDir = ".venv-win",
    [string]$Config = "",
    [string]$Credentials = "",
    [string]$Selectors = "",
    [int]$Limit = 20,
    [string]$DocumentNo = "",
    [string]$DocumentNos = "",
    [string]$DumpJson = "",
    [switch]$DryRun
)

$InvokeScript = Join-Path $PSScriptRoot "invoke_runner_task.ps1"
$ExtraArgs = @("--limit", [string]$Limit)

if ($DocumentNo) {
    $ExtraArgs += @("--document-no", $DocumentNo)
}
if ($DocumentNos) {
    $ExtraArgs += @("--document-nos", $DocumentNos)
}

$InvokeParams = @{
    Action = "audit"
    VenvDir = $VenvDir
    Config = $Config
    Credentials = $Credentials
    Selectors = $Selectors
    DumpJson = $DumpJson
    ExtraArgs = $ExtraArgs
}
if ($DryRun) { $InvokeParams.DryRun = $true }

& $InvokeScript @InvokeParams
exit $LASTEXITCODE
