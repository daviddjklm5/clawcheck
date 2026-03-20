param(
    [string]$VenvDir = ".venv-win",
    [string]$Config = "",
    [string]$Credentials = "",
    [string]$Selectors = "",
    [string]$DumpJson = ""
)

$InvokeScript = Join-Path $PSScriptRoot "invoke_runner_task.ps1"
$InvokeParams = @{
    Action = "rolecatalog"
    VenvDir = $VenvDir
    Config = $Config
    Credentials = $Credentials
    Selectors = $Selectors
    DumpJson = $DumpJson
}

& $InvokeScript @InvokeParams
exit $LASTEXITCODE
