param(
    [string]$TaskName = "clawcheck-postgres",
    [string]$TaskPath = "\Clawcheck\",
    [ValidateSet("AtLogOn", "AtStartup")]
    [string]$ScheduleType = "AtLogOn",
    [string]$PgRoot = "",
    [string]$DataDir = "",
    [string]$LogFile = "",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$StartScript = Join-Path $PSScriptRoot "start_postgres_user_mode.ps1"
if (-not (Test-Path $StartScript)) {
    throw "PostgreSQL startup script not found: $StartScript"
}

$ArgumentParts = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "`"$StartScript`""
)
if ($PgRoot) {
    $ArgumentParts += @("-PgRoot", "`"$PgRoot`"")
}
if ($DataDir) {
    $ArgumentParts += @("-DataDir", "`"$DataDir`"")
}
if ($LogFile) {
    $ArgumentParts += @("-LogFile", "`"$LogFile`"")
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
    -Description "clawcheck PostgreSQL user-mode startup task" `
    | Out-Null

Write-Host "Registered PostgreSQL startup task: $TaskPath$TaskName"
