<#
.SYNOPSIS
    Lifecycle helper for the local development stack of the Multi-Agent
    Financial Research System.

.DESCRIPTION
    Starts, stops and inspects the two long running development servers:

      * the backend  - uvicorn on 127.0.0.1:<BackendPort>   (default 8000)
      * the frontend - vite (npm run dev) on 127.0.0.1:<FrontendPort>
                       (default 5173)

    IMPORTANT (Windows): both servers have to survive the shell that started
    them, therefore they are launched as DETACHED processes
    (Start-Process with -WindowStyle Hidden and redirected output) and this
    script then polls the ports until they answer.

    The PostgreSQL cluster is NOT managed here - use scripts\db.ps1 for it.

    State lives under <RepoRoot>\var:

      var\backend.pid  var\frontend.pid   - the PIDs this script recorded
      var\logs\*.log                      - the output of the two servers

    `start` is idempotent: a server whose port already answers is never
    started a second time, and `stop` only ever kills the PIDs recorded in
    the PID files.

    All default paths below are for THIS developer machine. Every one of
    them is overridable from the command line, e.g.

        powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -Action status `
            -BackendPort 8010 -FrontendPort 5180

.PARAMETER Action
    start | stop | status | restart

.PARAMETER RepoRoot
    Root of the repository. Default: the parent directory of this script.

.PARAMETER BackendPort
    TCP port the backend listens on. Default: 8000

.PARAMETER FrontendPort
    TCP port the frontend listens on. Default: 5173

.PARAMETER Python
    Interpreter of the backend. Default: <RepoRoot>\backend\.venv\Scripts\python.exe

.PARAMETER Npm
    npm executable used for the frontend. Default: npm.cmd (resolved from PATH)
#>
[CmdletBinding()]
param(
    [ValidateSet('start', 'stop', 'status', 'restart')]
    [string] $Action = 'status',

    [string] $RepoRoot = '',

    [int] $BackendPort  = 8000,
    [int] $FrontendPort = 5173,

    [string] $Python = '',
    [string] $Npm    = 'npm.cmd'
)

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}

$ErrorActionPreference = 'Stop'

$BackendDir  = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$VarDir      = Join-Path $RepoRoot 'var'
$LogDir      = Join-Path $VarDir 'logs'

$BackendPidFile  = Join-Path $VarDir 'backend.pid'
$FrontendPidFile = Join-Path $VarDir 'frontend.pid'

$BackendLog     = Join-Path $LogDir 'backend.log'
$BackendErrLog  = Join-Path $LogDir 'backend.err.log'
$FrontendLog    = Join-Path $LogDir 'frontend.log'
$FrontendErrLog = Join-Path $LogDir 'frontend.err.log'

if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = Join-Path $BackendDir '.venv\Scripts\python.exe'
}

#: The number of seconds a port may take to answer before the start fails.
$StartTimeoutSeconds = 60


function Ensure-Directories {
    foreach ($directory in @($VarDir, $LogDir)) {
        if (-not (Test-Path $directory)) {
            New-Item -ItemType Directory -Force -Path $directory | Out-Null
        }
    }
}

function Test-PortOpen {
    param([int] $Port, [int] $TimeoutMilliseconds = 1000)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $pending = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if ($pending.AsyncWaitHandle.WaitOne($TimeoutMilliseconds, $false)) {
            $client.EndConnect($pending)
            return $true
        }
        return $false
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Wait-PortOpen {
    param([int] $Port, [int] $TimeoutSeconds = 60)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen -Port $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Wait-PortClosed {
    param([int] $Port, [int] $TimeoutSeconds = 20)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Test-PortOpen -Port $Port)) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

function Get-PortOwnerPid {
    param([int] $Port)
    try {
        $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
                        Select-Object -First 1
        if ($connection) { return [int] $connection.OwningProcess }
    } catch {
        # Get-NetTCPConnection needs the NetTCPIP module; without it the
        # script reports "no owner" instead of failing.
    }
    return $null
}

function Test-HttpOk {
    param([string] $Url, [int] $TimeoutSeconds = 5)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSeconds
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400)
    } catch {
        return $false
    }
}

function Get-RecordedPid {
    param([string] $PidFile)
    if (-not (Test-Path $PidFile)) { return $null }
    $text = Get-Content -LiteralPath $PidFile -Raw -ErrorAction SilentlyContinue
    if ($null -eq $text) { return $null }
    $text = $text.Trim()
    if ($text -eq '') { return $null }
    $value = 0
    if (-not [int]::TryParse($text, [ref] $value)) { return $null }
    return $value
}

function Set-RecordedPid {
    param([string] $PidFile, [int] $ProcessId)
    Set-Content -LiteralPath $PidFile -Value $ProcessId -Encoding ASCII
}

function Test-ProcessAlive {
    param([int] $ProcessId)
    if ($ProcessId -le 0) { return $false }
    return [bool] (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Start-Backend {
    if (-not (Test-Path $Python)) {
        throw "backend interpreter not found at $Python"
    }

    if (Test-PortOpen -Port $BackendPort) {
        $owner = Get-PortOwnerPid -Port $BackendPort
        if ($null -ne $owner) {
            Set-RecordedPid -PidFile $BackendPidFile -ProcessId $owner
        }
        Write-Host "[dev] backend  : already listening on 127.0.0.1:$BackendPort (PID $owner) - no duplicate started"
        return
    }

    Write-Host "[dev] backend  : starting uvicorn on 127.0.0.1:$BackendPort"
    $process = Start-Process -FilePath $Python `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort" `
        -WorkingDirectory $BackendDir -WindowStyle Hidden `
        -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendErrLog -PassThru

    if (-not (Wait-PortOpen -Port $BackendPort -TimeoutSeconds $StartTimeoutSeconds)) {
        Write-Warning "[dev] backend did not open port $BackendPort within $StartTimeoutSeconds s. Check $BackendErrLog"
        if (Test-Path $BackendErrLog) { Get-Content $BackendErrLog -Tail 40 | Write-Host }
        exit 1
    }

    $owner = Get-PortOwnerPid -Port $BackendPort
    if ($null -eq $owner) { $owner = $process.Id }
    Set-RecordedPid -PidFile $BackendPidFile -ProcessId $owner
    Write-Host "[dev] backend  : ready on 127.0.0.1:$BackendPort (PID $owner)"

    $health = "http://127.0.0.1:$BackendPort/api/v1/health"
    if (Test-HttpOk -Url $health) {
        Write-Host "[dev] backend  : health $health -> 200"
    } else {
        Write-Warning "[dev] backend did not answer $health yet - check $BackendLog"
    }
}

function Start-Frontend {
    $npmCommand = Get-Command $Npm -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $npmCommand) {
        throw "npm executable '$Npm' was not found on PATH"
    }
    $npmPath = $npmCommand.Source

    if (Test-PortOpen -Port $FrontendPort) {
        $owner = Get-PortOwnerPid -Port $FrontendPort
        if ($null -ne $owner) {
            Set-RecordedPid -PidFile $FrontendPidFile -ProcessId $owner
        }
        Write-Host "[dev] frontend : already listening on 127.0.0.1:$FrontendPort (PID $owner) - no duplicate started"
        return
    }

    Write-Host "[dev] frontend : starting vite on 127.0.0.1:$FrontendPort"
    $process = Start-Process -FilePath $npmPath `
        -ArgumentList 'run', 'dev', '--', '--host', '127.0.0.1', '--port', "$FrontendPort" `
        -WorkingDirectory $FrontendDir -WindowStyle Hidden `
        -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendErrLog -PassThru

    if (-not (Wait-PortOpen -Port $FrontendPort -TimeoutSeconds $StartTimeoutSeconds)) {
        Write-Warning "[dev] frontend did not open port $FrontendPort within $StartTimeoutSeconds s. Check $FrontendErrLog"
        if (Test-Path $FrontendErrLog) { Get-Content $FrontendErrLog -Tail 40 | Write-Host }
        exit 1
    }

    $owner = Get-PortOwnerPid -Port $FrontendPort
    if ($null -eq $owner) { $owner = $process.Id }
    Set-RecordedPid -PidFile $FrontendPidFile -ProcessId $owner
    Write-Host "[dev] frontend : ready on 127.0.0.1:$FrontendPort (PID $owner)"

    $root = "http://127.0.0.1:$FrontendPort/"
    if (Test-HttpOk -Url $root) {
        Write-Host "[dev] frontend : $root -> 200"
    } else {
        Write-Warning "[dev] frontend did not answer $root yet - check $FrontendLog"
    }
}

function Stop-Recorded {
    param(
        [string] $Name,
        [string] $PidFile,
        [int]    $Port
    )

    $recorded = Get-RecordedPid -PidFile $PidFile
    if ($null -eq $recorded) {
        Write-Host "[dev] $Name : no PID recorded in $PidFile - nothing to stop"
        return
    }

    if (-not (Test-ProcessAlive -ProcessId $recorded)) {
        Write-Host "[dev] $Name : recorded PID $recorded is not running - removing the stale PID file"
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        return
    }

    Write-Host "[dev] $Name : stopping PID $recorded"
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $output = & taskkill.exe /PID $recorded /T /F 2>&1
    $ErrorActionPreference = $previous
    $output | ForEach-Object { Write-Host "[dev] $_" }

    if (Wait-PortClosed -Port $Port -TimeoutSeconds 20) {
        Write-Host "[dev] $Name : stopped, port $Port is free"
    } else {
        Write-Warning "[dev] $Name : port $Port is still in use after the stop request"
    }

    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

function Show-ServerStatus {
    param(
        [string] $Name,
        [string] $PidFile,
        [int]    $Port
    )

    $owner = Get-PortOwnerPid -Port $Port
    if ($null -ne $owner) {
        Write-Host "[dev] $Name : RUNNING  - 127.0.0.1:$Port (PID $owner)"
    } else {
        Write-Host "[dev] $Name : STOPPED  - 127.0.0.1:$Port"
    }

    $recorded = Get-RecordedPid -PidFile $PidFile
    if ($null -ne $recorded) {
        $state = if (Test-ProcessAlive -ProcessId $recorded) { 'alive' } else { 'stale' }
        Write-Host "[dev] $Name : pid file $PidFile -> $recorded ($state)"
    } else {
        Write-Host "[dev] $Name : pid file $PidFile -> none"
    }
}

function Show-Status {
    Write-Host "[dev] repo root : $RepoRoot"
    Show-ServerStatus -Name 'backend ' -PidFile $BackendPidFile -Port $BackendPort
    Show-ServerStatus -Name 'frontend' -PidFile $FrontendPidFile -Port $FrontendPort
    Write-Host "[dev] logs      : $BackendLog"
    Write-Host "[dev] logs      : $BackendErrLog"
    Write-Host "[dev] logs      : $FrontendLog"
    Write-Host "[dev] logs      : $FrontendErrLog"

    $health = "http://127.0.0.1:$BackendPort/api/v1/health"
    if (Test-HttpOk -Url $health) {
        Write-Host "[dev] health    : $health -> 200"
    } else {
        Write-Host "[dev] health    : $health -> not reachable"
    }
}

function Start-Stack {
    Ensure-Directories
    Start-Backend
    Start-Frontend
    Write-Host "[dev] stack is up - frontend http://127.0.0.1:$FrontendPort/ - API docs http://127.0.0.1:$BackendPort/docs"
}

function Stop-Stack {
    Stop-Recorded -Name 'frontend' -PidFile $FrontendPidFile -Port $FrontendPort
    Stop-Recorded -Name 'backend ' -PidFile $BackendPidFile -Port $BackendPort
    Write-Host "[dev] stack is down"
}

switch ($Action) {
    'start'   { Start-Stack }
    'stop'    { Stop-Stack }
    'status'  { Show-Status }
    'restart' { Stop-Stack; Start-Stack }
}
