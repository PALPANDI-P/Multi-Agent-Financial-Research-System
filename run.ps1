<#
.SYNOPSIS
    Top-level lifecycle helper for the Multi-Agent Financial Research System.

.DESCRIPTION
    Orchestrates the database (scripts\db.ps1), Alembic migrations and the
    development stack (scripts\dev.ps1).

.PARAMETER Action
    start | stop | status. Default: start.

.PARAMETER StopDb
    When stopping, also stop the PostgreSQL cluster (default: keep it running).
#>
[CmdletBinding()]
param(
    [ValidateSet('start', 'stop', 'status')]
    [string] $Action = 'start',

    [switch] $StopDb
)

$ErrorActionPreference = 'Stop'

$RepoRoot   = $PSScriptRoot
$DbScript   = Join-Path $RepoRoot 'scripts\db.ps1'
$DevScript  = Join-Path $RepoRoot 'scripts\dev.ps1'
$BackendDir = Join-Path $RepoRoot 'backend'
$Python     = Join-Path $BackendDir '.venv\Scripts\python.exe'

try {
    switch ($Action) {
        'start' {
            Write-Host "[run] starting database..."
            & $DbScript -Action start
            if ($LASTEXITCODE -ne 0) { throw "db.ps1 start failed (exit $LASTEXITCODE)." }

            Write-Host "[run] applying Alembic migrations..."
            Push-Location $BackendDir
            try {
                if (Test-Path $Python) {
                    & $Python -m alembic upgrade head
                } else {
                    & python -m alembic upgrade head
                }
                if ($LASTEXITCODE -ne 0) { throw "alembic upgrade head failed (exit $LASTEXITCODE)." }
            } finally {
                Pop-Location
            }

            Write-Host "[run] starting development stack..."
            & $DevScript -Action start -RepoRoot $RepoRoot
            if ($LASTEXITCODE -ne 0) { throw "dev.ps1 start failed (exit $LASTEXITCODE)." }

            Write-Host ""
            Write-Host "[run] stack is up:"
            Write-Host "  frontend : http://127.0.0.1:5173/"
            Write-Host "  backend  : http://127.0.0.1:8000/"
            Write-Host "  API docs : http://127.0.0.1:8000/docs"
            Write-Host "  health   : http://127.0.0.1:8000/api/v1/health"
        }
        'stop' {
            Write-Host "[run] stopping development stack..."
            & $DevScript -Action stop -RepoRoot $RepoRoot
            if ($LASTEXITCODE -ne 0) { throw "dev.ps1 stop failed (exit $LASTEXITCODE)." }

            if ($StopDb) {
                Write-Host "[run] stopping database..."
                & $DbScript -Action stop
                if ($LASTEXITCODE -ne 0) { throw "db.ps1 stop failed (exit $LASTEXITCODE)." }
            } else {
                Write-Host "[run] database left running (use -StopDb to stop it)."
            }
        }
        'status' {
            & $DbScript -Action status
            Write-Host ""
            & $DevScript -Action status -RepoRoot $RepoRoot
        }
    }
} catch {
    Write-Host ""
    Write-Host "[run] ERROR: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.InvocationInfo -and $_.InvocationInfo.PositionMessage) {
        Write-Host $_.InvocationInfo.PositionMessage
    }
    exit 1
}
