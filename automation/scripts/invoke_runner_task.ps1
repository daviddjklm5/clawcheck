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
    [switch]$Headed,
    [switch]$Headless,
    [switch]$DryRun,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($Headed -and $Headless) {
    throw "Headed and Headless cannot both be set."
}

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$PythonExe = Join-Path $RepoRoot "$VenvDir\Scripts\python.exe"
$SettingsProdPath = Join-Path $RepoRoot "automation\config\settings.prod.yaml"
$SettingsDefaultPath = Join-Path $RepoRoot "automation\config\settings.yaml"
$CredentialsProdPath = Join-Path $RepoRoot "automation\config\credentials.prod.local.yaml"
$CredentialsDefaultPath = Join-Path $RepoRoot "automation\config\credentials.local.yaml"
$SelectorsDefaultPath = Join-Path $RepoRoot "automation\config\selectors.yaml"
$ResolvedLogDir = Join-Path $RepoRoot $LogDir

if (-not (Test-Path $PythonExe)) {
    throw "Python venv not found: $PythonExe"
}

if (-not (Test-Path $ResolvedLogDir)) {
    New-Item -ItemType Directory -Path $ResolvedLogDir -Force | Out-Null
}

function Resolve-RepoPath([string]$RawPath) {
    if ([string]::IsNullOrWhiteSpace($RawPath)) {
        return ""
    }

    if ([System.IO.Path]::IsPathRooted($RawPath)) {
        return $RawPath
    }

    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $RawPath))
}

function Resolve-OptionalDefaultPath([string]$ExplicitPath, [string]$PreferredPath, [string]$FallbackPath) {
    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        return (Resolve-RepoPath $ExplicitPath)
    }

    if (-not [string]::IsNullOrWhiteSpace($PreferredPath) -and (Test-Path $PreferredPath)) {
        return $PreferredPath
    }

    if (-not [string]::IsNullOrWhiteSpace($FallbackPath) -and (Test-Path $FallbackPath)) {
        return $FallbackPath
    }

    return ""
}

function Format-CommandArgument([string]$Argument) {
    if ($null -eq $Argument -or $Argument.Length -eq 0) {
        return '""'
    }

    if ($Argument -notmatch '[\s"]') {
        return $Argument
    }

    $Escaped = $Argument -replace '(\\*)"', '$1$1\"'
    $Escaped = $Escaped -replace '(\\+)$', '$1$1'
    return '"' + $Escaped + '"'
}

function Read-ProcessOutputText([string]$Path) {
    if (-not (Test-Path $Path)) {
        return ""
    }

    $Bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($Bytes.Length -eq 0) {
        return ""
    }

    if ($Bytes.Length -ge 2 -and $Bytes[0] -eq 0xFF -and $Bytes[1] -eq 0xFE) {
        return [System.Text.Encoding]::Unicode.GetString($Bytes, 2, $Bytes.Length - 2)
    }

    if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF) {
        return [System.Text.Encoding]::UTF8.GetString($Bytes, 3, $Bytes.Length - 3)
    }

    $LooksLikeUtf16Le = $false
    $ProbeLength = [Math]::Min($Bytes.Length, 64)
    for ($Index = 1; $Index -lt $ProbeLength; $Index += 2) {
        if ($Bytes[$Index] -eq 0) {
            $LooksLikeUtf16Le = $true
            break
        }
    }

    if ($LooksLikeUtf16Le) {
        return [System.Text.Encoding]::Unicode.GetString($Bytes)
    }

    return [System.Text.Encoding]::UTF8.GetString($Bytes)
}

$ResolvedConfig = Resolve-OptionalDefaultPath -ExplicitPath $Config -PreferredPath $SettingsProdPath -FallbackPath $SettingsDefaultPath
$ResolvedCredentials = Resolve-OptionalDefaultPath -ExplicitPath $Credentials -PreferredPath $CredentialsProdPath -FallbackPath $CredentialsDefaultPath
$ResolvedSelectors = Resolve-OptionalDefaultPath -ExplicitPath $Selectors -PreferredPath $SelectorsDefaultPath -FallbackPath ""
$ResolvedDumpJson = Resolve-RepoPath $DumpJson

$RunArguments = @("automation/scripts/run.py", $Action)
if ($ResolvedConfig) {
    $RunArguments += @("--config", $ResolvedConfig)
}
if ($ResolvedCredentials) {
    $RunArguments += @("--credentials", $ResolvedCredentials)
}
if ($ResolvedSelectors) {
    $RunArguments += @("--selectors", $ResolvedSelectors)
}
if ($Headed) {
    $RunArguments += "--headed"
}
if ($Headless) {
    $RunArguments += "--headless"
}
if ($DryRun) {
    $RunArguments += "--dry-run"
}
if ($ResolvedDumpJson) {
    $RunArguments += @("--dump-json", $ResolvedDumpJson)
}
if ($ExtraArgs) {
    $RunArguments += $ExtraArgs
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $ResolvedLogDir "$Action`_$Timestamp.log"
$QuotedRunArguments = @($RunArguments | ForEach-Object { Format-CommandArgument $_ })
$CommandPreview = '"' + $PythonExe + '" ' + ($QuotedRunArguments -join " ")

$HeaderLines = @(
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Task started",
    "RepoRoot: $RepoRoot",
    "PythonExe: $PythonExe",
    "Action: $Action",
    "Command: $CommandPreview",
    ""
)
Set-Content -Path $LogPath -Value ($HeaderLines -join [Environment]::NewLine) -Encoding UTF8

$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"

$StdOutPath = Join-Path ([System.IO.Path]::GetTempPath()) "clawcheck_$Action`_$Timestamp.stdout.log"
$StdErrPath = Join-Path ([System.IO.Path]::GetTempPath()) "clawcheck_$Action`_$Timestamp.stderr.log"

try {
    $Process = Start-Process `
        -FilePath $PythonExe `
        -ArgumentList $RunArguments `
        -WorkingDirectory $RepoRoot `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $StdOutPath `
        -RedirectStandardError $StdErrPath
    $ExitCode = $Process.ExitCode

    foreach ($StreamPath in @($StdOutPath, $StdErrPath)) {
        if (-not (Test-Path $StreamPath)) {
            continue
        }
        $OutputText = Read-ProcessOutputText $StreamPath
        if ([string]::IsNullOrEmpty($OutputText)) {
            continue
        }
        Add-Content -Path $LogPath -Value $OutputText -Encoding UTF8
        [Console]::Out.Write($OutputText)
    }
}
finally { 
    try {
        foreach ($StreamPath in @($StdOutPath, $StdErrPath)) {
            if (Test-Path $StreamPath) {
                Remove-Item -Path $StreamPath -Force -ErrorAction SilentlyContinue
            }
        }
    }
    catch {
        # Ignore cleanup failures after the child process exits.
    }
}

if ($null -eq $ExitCode) {
    $ExitCode = 1
}

Add-Content -Path $LogPath -Value ""
Add-Content -Path $LogPath -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ExitCode: $ExitCode"
Write-Host "Task log: $LogPath"
exit $ExitCode
