<#
.SYNOPSIS
    Lifecycle helper for the local PostgreSQL 16 + pgvector development database.

.DESCRIPTION
    Wraps the micromamba-managed PostgreSQL cluster used by the Multi-Agent
    Financial Research System.

    IMPORTANT (Windows): `pg_ctl start` on Windows does not return after the
    server is ready - it keeps waiting on the postmaster process handle. This
    script therefore launches `pg_ctl start` as a DETACHED process and then
    polls `pg_isready` until the server accepts connections, so the script
    itself always returns to the shell.

    All default paths below are for THIS developer machine
    (micromamba root E:\mamba, cluster E:\pgdata\frs, port 55432).
    Every one of them is overridable from the command line, e.g.

        powershell -ExecutionPolicy Bypass -File scripts\db.ps1 -Action status `
            -MambaRoot "D:\mamba" -EnvName frs -DataDir "D:\pgdata\frs" -Port 55432

.PARAMETER Action
    start | stop | status | reset

.PARAMETER MambaRoot
    micromamba root prefix. Default: E:\mamba

.PARAMETER EnvName
    Conda environment name inside $MambaRoot\envs. Default: frs

.PARAMETER DataDir
    PostgreSQL data directory. Default: E:\pgdata\frs

.PARAMETER Port
    PostgreSQL port. Default: 55432

.PARAMETER SuperuserPassword
    Password for the `postgres` superuser. Default: frs_dev_password

.PARAMETER AppRole / AppPassword
    Application role created by `reset`. Default: frs / frs_dev_password
#>
[CmdletBinding()]
param(
    [ValidateSet('start', 'stop', 'status', 'reset')]
    [string] $Action = 'status',

    [string] $MambaRoot = 'E:\mamba',
    [string] $EnvName  = 'frs',
    [string] $DataDir  = 'E:\pgdata\frs',
    [int]    $Port     = 55432,

    [string] $SuperuserPassword = 'frs_dev_password',
    [string] $AppRole           = 'frs',
    [string] $AppPassword       = 'frs_dev_password'
)

$ErrorActionPreference = 'Stop'

$EnvBin  = Join-Path $MambaRoot "envs\$EnvName\Library\bin"
$EnvLib  = Join-Path $MambaRoot "envs\$EnvName\Library\lib"
$PgCtl   = Join-Path $EnvBin 'pg_ctl.exe'
$InitDb  = Join-Path $EnvBin 'initdb.exe'
$Psql    = Join-Path $EnvBin 'psql.exe'
$PgIsRdy = Join-Path $EnvBin 'pg_isready.exe'
$LogFile = Join-Path $DataDir 'server.log'

# The conda env ships libpq/libcrypto/libxml2/... next to the executables;
# put them on PATH so postgres.exe and its child processes can load them.
$env:PATH = "$EnvBin;$EnvLib;$env:PATH"


function Test-ServerRunning {
    & $PgIsRdy -h 127.0.0.1 -p $Port *> $null
    return ($LASTEXITCODE -eq 0)
}

function Wait-ServerReady {
    param([int] $TimeoutSeconds = 120)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-ServerRunning) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Start-Postgres {
    if (Test-ServerRunning) {
        Write-Host "[db] server already running on 127.0.0.1:$Port"
        return
    }
    if (-not (Test-Path $PgCtl)) {
        throw "pg_ctl.exe not found at $PgCtl"
    }
    if (-not (Test-Path $DataDir)) {
        New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    }

    Write-Host "[db] starting PostgreSQL on 127.0.0.1:$Port (data dir $DataDir)"

    # pg_ctl blocks on Windows, so run it detached and poll for readiness.
    # The -o value must stay a single quoted argument: if it is split on
    # spaces, pg_ctl reads "55432" as the operation mode and fails with
    # 'unrecognized operation mode'.
    $pgCtlArgs = '-D "{0}" -l "{1}" -o "-p {2} -c listen_addresses=127.0.0.1" -w start' -f `
                  $DataDir, $LogFile, $Port
    $ctlOut = Join-Path $DataDir 'pg_ctl.out'
    $ctlErr = Join-Path $DataDir 'pg_ctl.err'
    Start-Process -FilePath $PgCtl -ArgumentList $pgCtlArgs -WindowStyle Hidden `
                  -RedirectStandardOutput $ctlOut -RedirectStandardError $ctlErr | Out-Null

    if (Wait-ServerReady -TimeoutSeconds 120) {
        Write-Host "[db] server is ready on 127.0.0.1:$Port"
    } else {
        Write-Warning "[db] server did not become ready within 120s. Check $LogFile"
        if (Test-Path $LogFile) { Get-Content $LogFile -Tail 40 | Write-Host }
        exit 1
    }
}

function Stop-Postgres {
    if (-not (Test-Path $PgCtl)) {
        throw "pg_ctl.exe not found at $PgCtl"
    }
    Write-Host "[db] stopping PostgreSQL (data dir $DataDir)"
    & $PgCtl -D $DataDir -m fast -w stop 2>&1 | ForEach-Object { Write-Host "[db] $_" }
    if (Test-ServerRunning) {
        Write-Warning "[db] server still responding after stop request"
    } else {
        Write-Host "[db] server stopped"
    }
}

function Show-Status {
    if (Test-ServerRunning) {
        Write-Host "[db] RUNNING  - 127.0.0.1:$Port"
    } else {
        Write-Host "[db] STOPPED  - 127.0.0.1:$Port"
    }
    if (Test-Path $PgCtl) {
        & $PgCtl -D $DataDir status 2>&1 | ForEach-Object { Write-Host "[db] $_" }
    }
}

function Invoke-Sql {
    param(
        [string] $Sql,
        [string] $Database = 'postgres',
        [string] $User     = 'postgres'
    )
    $tmp = Join-Path $env:TEMP ("frs_db_{0}_{1}.sql" -f $User, [guid]::NewGuid().ToString('N'))
    try {
        Set-Content -LiteralPath $tmp -Value $Sql -Encoding UTF8
        $env:PGPASSWORD = if ($User -eq 'postgres') { $SuperuserPassword } else { $AppPassword }
        & $Psql --host=127.0.0.1 --port=$Port --username=$User --dbname=$Database `
                --no-psqlrc --quiet --file=$tmp 2>&1 | ForEach-Object { Write-Host "[db] $_" }
        if ($LASTEXITCODE -ne 0) { throw "psql failed (exit $LASTEXITCODE) for $User@$Database" }
    } finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
}

function Reset-Database {
    Write-Host "[db] resetting cluster at $DataDir"
    Stop-Postgres

    if (Test-Path $DataDir) {
        Get-ChildItem -LiteralPath $DataDir -Force | Remove-Item -Recurse -Force
    } else {
        New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    }

    $pwFile = Join-Path $env:TEMP ("frs_pw_{0}.txt" -f [guid]::NewGuid().ToString('N'))
    try {
        Set-Content -LiteralPath $pwFile -Value $SuperuserPassword -NoNewline -Encoding ASCII
        & $InitDb -D $DataDir -U postgres -E UTF8 --locale=C -A md5 --pwfile=$pwFile 2>&1 |
            ForEach-Object { Write-Host "[db] $_" }
        if ($LASTEXITCODE -ne 0) { throw "initdb failed (exit $LASTEXITCODE)" }
    } finally {
        Remove-Item -LiteralPath $pwFile -Force -ErrorAction SilentlyContinue
    }

    Start-Postgres

    # Role + databases. CREATE DATABASE cannot run inside a transaction block,
    # so each statement is issued separately by psql.
    Invoke-Sql -User 'postgres' -Sql @"
DO `$`$
BEGIN
   IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$AppRole') THEN
      CREATE ROLE $AppRole LOGIN PASSWORD '$AppPassword';
   ELSE
      ALTER ROLE $AppRole LOGIN PASSWORD '$AppPassword';
   END IF;
END
`$`$;
"@

    foreach ($db in @('financial_research', 'financial_research_test')) {
        Invoke-Sql -User 'postgres' -Sql @"
SELECT 'CREATE DATABASE $db OWNER $AppRole'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '$db')\gexec
"@
    }

    # pgvector 0.8.6 for win-64 is NOT a trusted extension, so it has to be
    # installed by the superuser and then handed to the application role.
    foreach ($db in @('financial_research', 'financial_research_test')) {
        Invoke-Sql -User 'postgres' -Database $db -Sql @"
CREATE EXTENSION IF NOT EXISTS vector;
UPDATE pg_extension SET extowner = '$AppRole'::regrole WHERE extname = 'vector';
ALTER TYPE vector OWNER TO $AppRole;
"@
    }

    Write-Host "[db] reset complete"
    Write-Host "[db] dev  URI: postgresql+psycopg://$AppRole`:$AppPassword@127.0.0.1`:$Port/financial_research"
    Write-Host "[db] test URI: postgresql+psycopg://$AppRole`:$AppPassword@127.0.0.1`:$Port/financial_research_test"
}

switch ($Action) {
    'start'  { Start-Postgres }
    'stop'   { Stop-Postgres }
    'status' { Show-Status }
    'reset'  { Reset-Database }
}
