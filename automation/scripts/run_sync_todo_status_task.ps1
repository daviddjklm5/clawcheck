param(
    [string]$VenvDir = ".venv-win",
    [string]$Config = "",
    [string]$Credentials = "",
    [string]$Selectors = "",
    [string]$DumpJson = "",
    [switch]$Headed,
    [switch]$Headless,
    [switch]$DryRun
)

$InvokeScript = Join-Path $PSScriptRoot "invoke_runner_task.ps1"
$InvokeParams = @{
    Action = "sync-todo-status"
    VenvDir = $VenvDir
    Config = $Config
    Credentials = $Credentials
    Selectors = $Selectors
    DumpJson = $DumpJson
}
if ($Headed) { $InvokeParams.Headed = $true }
if ($Headless) { $InvokeParams.Headless = $true }
if ($DryRun) { $InvokeParams.DryRun = $true }

& $InvokeScript @InvokeParams
exit $LASTEXITCODE
