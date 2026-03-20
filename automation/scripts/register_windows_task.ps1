param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("collect", "roster", "orglist", "audit", "sync-todo-status", "rolecatalog", "dbinit")]
    [string]$TaskType,
    [ValidateSet("Daily", "Hourly", "Once", "AtLogOn", "AtStartup")]
    [string]$ScheduleType = "Daily",
    [string]$At = "08:00",
    [int]$IntervalMinutes = 60,
    [string]$TaskName = "",
    [string]$TaskPath = "\Clawcheck\",
    [string]$Description = "",
    [string]$VenvDir = ".venv-win",
    [string]$TaskScriptArguments = "",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$ResolvedTaskScript = Join-Path $PSScriptRoot "run_windows_task.ps1"
if (-not (Test-Path $ResolvedTaskScript)) {
    throw "Task script not found: $ResolvedTaskScript"
}

if (-not $TaskName) {
    $TaskName = "clawcheck-$TaskType"
}

if (-not $Description) {
    $Description = "clawcheck $TaskType task"
}

$ArgumentParts = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "`"$ResolvedTaskScript`"",
    "-Action",
    "`"$TaskType`"",
    "-VenvDir",
    "`"$VenvDir`""
)
if ($TaskScriptArguments) {
    $ArgumentParts += $TaskScriptArguments
}
$ActionArgument = $ArgumentParts -join " "
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $ActionArgument

switch ($ScheduleType) {
    "Daily" {
        $Trigger = New-ScheduledTaskTrigger -Daily -At $At
    }
    "Once" {
        $Trigger = New-ScheduledTaskTrigger -Once -At $At
    }
    "Hourly" {
        if ($IntervalMinutes -le 0) {
            throw "IntervalMinutes must be > 0 for Hourly schedule."
        }
        $Trigger = New-ScheduledTaskTrigger -Once -At $At
        $Trigger.Repetition = New-ScheduledTaskRepetitionSettingsSet -Interval (New-TimeSpan -Minutes $IntervalMinutes) -Duration (New-TimeSpan -Days 1)
    }
    "AtLogOn" {
        $Trigger = New-ScheduledTaskTrigger -AtLogOn
    }
    "AtStartup" {
        $Trigger = New-ScheduledTaskTrigger -AtStartup
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
        # Ignore when task does not yet exist.
    }
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -TaskPath $TaskPath `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description $Description `
    | Out-Null

Write-Host "Registered scheduled task: $TaskPath$TaskName"
