param(
    [string]$TaskName = "clawcheck-api",
    [string]$TaskPath = "\Clawcheck\",
    [ValidateSet("AtStartup", "AtLogOn")]
    [string]$ScheduleType = "AtStartup",
    [string]$VenvDir = ".venv-win",
    [string]$ListenHost = "127.0.0.1",
    [int]$Port = 8000,
    [string]$LogLevel = "info",
    [string]$WebuiDistDir = "",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$StartApiScript = Join-Path $PSScriptRoot "start_api.ps1"
if (-not (Test-Path $StartApiScript)) {
    throw "API startup script not found: $StartApiScript"
}

$ArgumentParts = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "`"$StartApiScript`"",
    "-VenvDir",
    "`"$VenvDir`"",
    "-ListenHost",
    "`"$ListenHost`"",
    "-Port",
    [string]$Port,
    "-LogLevel",
    "`"$LogLevel`""
)
if ($WebuiDistDir) {
    $ArgumentParts += @("-WebuiDistDir", "`"$WebuiDistDir`"")
}
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ($ArgumentParts -join " ")

switch ($ScheduleType) {
    "AtStartup" {
        $Trigger = New-ScheduledTaskTrigger -AtStartup
    }
    "AtLogOn" {
        $Trigger = New-ScheduledTaskTrigger -AtLogOn
    }
    default {
        throw "Unsupported ScheduleType: $ScheduleType"
    }
}

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

if ($Force) {
    try {
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false -ErrorAction Stop
    }
    catch {
        # Ignore when task does not exist.
    }
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -TaskPath $TaskPath `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "clawcheck FastAPI startup task" `
    | Out-Null

Write-Host "Registered API startup task: $TaskPath$TaskName"
