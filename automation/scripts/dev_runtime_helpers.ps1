Set-StrictMode -Version Latest

function Initialize-Utf8Console {
    $Utf8NoBom = [System.Text.UTF8Encoding]::new($false)

    try {
        [Console]::InputEncoding = $Utf8NoBom
    }
    catch {
    }

    try {
        [Console]::OutputEncoding = $Utf8NoBom
    }
    catch {
    }

    try {
        $global:OutputEncoding = $Utf8NoBom
    }
    catch {
    }

    try {
        & chcp.com 65001 > $null
    }
    catch {
    }
}

function Get-RepoRoot {
    param(
        [string]$ScriptRoot = $PSScriptRoot
    )

    return [System.IO.Path]::GetFullPath((Join-Path $ScriptRoot "..\.."))
}

function Ensure-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
    return $Path
}

function Write-Utf8File {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

function Get-DevRuntimeDir {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $RuntimeDir = Join-Path $RepoRoot "automation\runtime\dev"
    Ensure-Directory -Path $RuntimeDir | Out-Null
    return $RuntimeDir
}

function Get-ServiceFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        [string]$ServiceName
    )

    $RuntimeDir = Get-DevRuntimeDir -RepoRoot $RepoRoot
    return [pscustomobject]@{
        RuntimeDir   = $RuntimeDir
        PidPath      = Join-Path $RuntimeDir "$ServiceName.pid"
        MetadataPath = Join-Path $RuntimeDir "$ServiceName.json"
        StdoutLog    = Join-Path $RuntimeDir "$ServiceName.stdout.log"
        StderrLog    = Join-Path $RuntimeDir "$ServiceName.stderr.log"
    }
}

function Write-ServiceMetadata {
    param(
        [Parameter(Mandatory = $true)]
        [string]$MetadataPath,
        [Parameter(Mandatory = $true)]
        [hashtable]$Payload
    )

    $Json = $Payload | ConvertTo-Json -Depth 8
    Write-Utf8File -Path $MetadataPath -Content $Json
}

function Read-ServiceMetadata {
    param(
        [Parameter(Mandatory = $true)]
        [string]$MetadataPath
    )

    if (-not (Test-Path $MetadataPath)) {
        return $null
    }

    try {
        return Get-Content -Path $MetadataPath -Raw | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Remove-ServiceArtifacts {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        [string]$ServiceName
    )

    $Files = Get-ServiceFiles -RepoRoot $RepoRoot -ServiceName $ServiceName
    foreach ($Path in @($Files.PidPath, $Files.MetadataPath)) {
        if (Test-Path $Path) {
            Remove-Item -Force $Path
        }
    }
}

function Resolve-PythonExe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [string]$VenvDir = ".venv-win"
    )

    return Join-Path $RepoRoot "$VenvDir\Scripts\python.exe"
}

function Resolve-NpmCommand {
    param(
        [string]$RequestedNodeDir = ""
    )

    $Candidates = @()
    if ($RequestedNodeDir) {
        $Candidates += [pscustomobject]@{ Source = "NodeDir"; Directory = $RequestedNodeDir }
    }
    if ($env:CLAWCHECK_NODE_DIR) {
        $Candidates += [pscustomobject]@{ Source = "CLAWCHECK_NODE_DIR"; Directory = $env:CLAWCHECK_NODE_DIR }
    }

    foreach ($Candidate in $Candidates) {
        $ResolvedNpm = Join-Path $Candidate.Directory "npm.cmd"
        if (Test-Path $ResolvedNpm) {
            return [pscustomobject]@{
                NpmCommand = $ResolvedNpm
                NodeDir    = $Candidate.Directory
                NodeExe    = Join-Path $Candidate.Directory "node.exe"
                Source     = $Candidate.Source
            }
        }
    }

    $Command = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $Command) {
        $Command = Get-Command npm -ErrorAction SilentlyContinue
    }
    if ($Command) {
        $NodeDir = Split-Path -Parent $Command.Source
        return [pscustomobject]@{
            NpmCommand = $Command.Source
            NodeDir    = $NodeDir
            NodeExe    = Join-Path $NodeDir "node.exe"
            Source     = "PATH"
        }
    }

    throw "npm was not found. Install Node.js, pass -NodeDir, or set CLAWCHECK_NODE_DIR."
}

function Push-NodeEnvironment {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$NodeResolution
    )

    $State = [pscustomobject]@{
        Path           = $env:PATH
        NpmScriptShell = $env:npm_config_script_shell
    }

    if ($NodeResolution.NodeDir) {
        $env:PATH = "$($NodeResolution.NodeDir);$($env:PATH)"
    }
    $env:npm_config_script_shell = (Get-Command cmd.exe -ErrorAction Stop).Source
    return $State
}

function Invoke-WebuiNodePreflight {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$NodeResolution
    )

    Write-Host "[preflight] where node"
    $NodeCandidates = @(& where.exe node)
    if ($LASTEXITCODE -ne 0) {
        throw "Node preflight failed: where node"
    }
    $NodeCandidates | ForEach-Object { Write-Host $_ }
    if ($NodeCandidates.Count -gt 1) {
        Write-Warning "Multiple node executables detected. Keep a single primary Node source in PATH to avoid shell mismatch."
    }

    Write-Host "[preflight] where npm"
    $NpmCandidates = @(& where.exe npm)
    if ($LASTEXITCODE -ne 0) {
        throw "Node preflight failed: where npm"
    }
    $NpmCandidates | ForEach-Object { Write-Host $_ }
    $NpmCandidateDirs = @($NpmCandidates | ForEach-Object { Split-Path -Parent $_ } | Sort-Object -Unique)
    if ($NpmCandidateDirs.Count -gt 1) {
        Write-Warning "Multiple npm locations detected. Keep a single primary Node source in PATH to avoid command drift."
    }

    Write-Host "[preflight] node -v"
    if (Test-Path $NodeResolution.NodeExe) {
        & $NodeResolution.NodeExe -v
    }
    else {
        & node -v
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Node preflight failed: node -v"
    }

    Write-Host "[preflight] npm -v"
    & $NodeResolution.NpmCommand -v
    if ($LASTEXITCODE -ne 0) {
        if (Test-Path "C:\Program Files\nodejs\npm.cmd") {
            Write-Host "[preflight] npm -v fallback C:\\Program Files\\nodejs\\npm.cmd"
            & "C:\Program Files\nodejs\npm.cmd" -v
        }
        else {
            Write-Host "[preflight] npm -v fallback cmd /c npm -v"
            & cmd.exe /d /c npm -v
        }
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Node preflight failed: npm -v"
    }
}

function Pop-NodeEnvironment {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$State
    )

    $env:PATH = $State.Path
    if ([string]::IsNullOrWhiteSpace($State.NpmScriptShell)) {
        Remove-Item Env:npm_config_script_shell -ErrorAction SilentlyContinue
    }
    else {
        $env:npm_config_script_shell = $State.NpmScriptShell
    }
}

function Test-ProcessAlive {
    param(
        [int]$ProcessId
    )

    if ($ProcessId -le 0) {
        return $false
    }
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Get-ProcessCommandLine {
    param(
        [int]$ProcessId
    )

    if ($ProcessId -le 0) {
        return ""
    }

    $Process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if ($null -eq $Process) {
        return ""
    }
    return [string]$Process.CommandLine
}

function Find-ProcessByCommandPattern {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Pattern
    )

    return Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $Pattern } |
        Sort-Object ProcessId |
        Select-Object -First 1
}

function Stop-ProcessTree {
    param(
        [int]$ProcessId
    )

    if ($ProcessId -le 0) {
        return $false
    }
    if (-not (Test-ProcessAlive -ProcessId $ProcessId)) {
        return $true
    }

    & taskkill.exe /PID $ProcessId /T /F | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Get-PortOwningProcessId {
    param(
        [int]$Port
    )

    if ($Port -le 0) {
        return 0
    }

    $Connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Sort-Object OwningProcess |
        Select-Object -First 1

    if ($null -eq $Connection) {
        return 0
    }
    return [int]$Connection.OwningProcess
}

function Test-TcpPort {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ConnectionHost,
        [Parameter(Mandatory = $true)]
        [int]$Port,
        [int]$TimeoutMs = 2000
    )

    $Client = New-Object System.Net.Sockets.TcpClient
    try {
        $AsyncResult = $Client.BeginConnect($ConnectionHost, $Port, $null, $null)
        if (-not $AsyncResult.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
            return $false
        }
        $Client.EndConnect($AsyncResult)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $Client.Dispose()
    }
}

function Invoke-HealthRequest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [int]$TimeoutSec = 3
    )

    try {
        $Response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return [pscustomobject]@{
            Ok         = ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 300)
            StatusCode = [int]$Response.StatusCode
            Message    = "HTTP $($Response.StatusCode)"
        }
    }
    catch {
        return [pscustomobject]@{
            Ok         = $false
            StatusCode = 0
            Message    = $_.Exception.Message
        }
    }
}

function Start-ManagedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,
        [Parameter(Mandatory = $true)]
        [string]$StdoutLog,
        [Parameter(Mandatory = $true)]
        [string]$StderrLog
    )

    return Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $StdoutLog `
        -RedirectStandardError $StderrLog `
        -PassThru
}

Initialize-Utf8Console
