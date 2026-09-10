<#
.SYNOPSIS
    Start Learnify locally with one command.

.DESCRIPTION
    Brings up Postgres, the backend and the frontend, waits until each is actually answering,
    and opens the app. Safe to re-run: every step is idempotent, and anything already running
    is left alone rather than restarted.

    If Docker is unavailable the launch continues without it. The backend falls back to
    in-memory storage, which is fine for a look around but loses everything on exit — the
    script says so rather than letting you find out later.

.PARAMETER Stop
    Stop the backend, the frontend and Postgres.

.PARAMETER Demo
    Load sample assessments first, so the UI has something to show.

.PARAMETER Fresh
    Wipe all knowledge state and reload the sample assessments.

.PARAMETER NoDocker
    Skip Postgres entirely and run in memory.

.PARAMETER NoBrowser
    Do not open a browser.

.PARAMETER Dev
    Run the backend with --reload so code changes take effect without a restart. Off by
    default: the reload supervisor is what makes shutdown unreliable, and you do not need it
    just to use the app.

.EXAMPLE
    .\run.ps1
.EXAMPLE
    .\run.ps1 -Fresh
.EXAMPLE
    .\run.ps1 -Stop
#>
[CmdletBinding()]
param(
    [switch]$Stop,
    [switch]$Demo,
    [switch]$Fresh,
    [switch]$NoDocker,
    [switch]$NoBrowser,
    [switch]$Dev
)

$ErrorActionPreference = 'Stop'
$Root     = $PSScriptRoot
$Backend  = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$VenvPy   = Join-Path $Backend '.venv\Scripts\python.exe'

$API_PORT = 8000
$WEB_PORT = 5173
$WEB_URL  = "http://localhost:$WEB_PORT"
$API_URL  = "http://localhost:$API_PORT"

# ---------------------------------------------------------------- output

function Step($m) { Write-Host "`n> $m" -ForegroundColor Cyan }
function Ok  ($m) { Write-Host "  $m" -ForegroundColor Green }
function Note($m) { Write-Host "  $m" -ForegroundColor DarkGray }
function Warn($m) { Write-Host "  ! $m" -ForegroundColor Yellow }
function Die ($m) { Write-Host "`n  x $m`n" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- helpers

# Windows PowerShell wraps a native command's stderr in NativeCommandError records, which
# $ErrorActionPreference = 'Stop' turns into a terminating error. That makes ordinary,
# expected output - "the daemon is not running" - fatal. Native calls go through here so a
# non-zero exit is reported as a number rather than thrown.
function Invoke-Native {
    param([Parameter(Mandatory)][string]$Exe, [string[]]$Arguments = @(), [string]$WorkingDirectory)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $entry = $null
    if ($WorkingDirectory) { $entry = Get-Location; Set-Location $WorkingDirectory }
    try {
        & $Exe @Arguments 2>&1 | Out-Null
        return $LASTEXITCODE
    } finally {
        if ($entry) { Set-Location $entry }
        $ErrorActionPreference = $previous
    }
}

# Same, but hands back stdout instead of discarding it.
function Invoke-NativeText {
    param([Parameter(Mandatory)][string]$Exe, [string[]]$Arguments = @())
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { return (& $Exe @Arguments 2>$null | Out-String).Trim() }
    finally { $ErrorActionPreference = $previous }
}

function Get-PortOwner([int]$Port) {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
}

function Test-Port([int]$Port) { [bool](Get-PortOwner $Port) }

function Stop-Port([int]$Port, [string]$Label) {
    $owners = Get-PortOwner $Port
    if (-not $owners) { Note "$Label was not running"; return }

    foreach ($processId in $owners) {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" `
            -ErrorAction SilentlyContinue

        # A dead supervisor leaves its listening socket inherited by a worker, and Windows
        # keeps attributing the port to the PID that no longer exists. Killing that PID is
        # impossible; the process actually holding the socket open is its child.
        foreach ($child in (Get-CimInstance Win32_Process `
                -Filter "ParentProcessId = $processId" -ErrorAction SilentlyContinue)) {
            Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
        }

        if ($owner) {
            # `uvicorn --reload` supervises a worker and `npm run dev` sits under a shell;
            # either will put the port straight back unless the parent goes first.
            $parent = Get-Process -Id $owner.ParentProcessId -ErrorAction SilentlyContinue
            if ($parent -and $parent.ProcessName -match 'python|node|npm|cmd') {
                Stop-Process -Id $parent.Id -Force -ErrorAction SilentlyContinue
            }
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }

    # Verify. Claiming to have stopped something that is still listening is worse than
    # saying nothing, because the next launch silently reuses the old process.
    for ($i = 0; $i -lt 10 -and (Get-PortOwner $Port); $i++) { Start-Sleep -Milliseconds 300 }
    if (Get-PortOwner $Port) { Warn "$Label is STILL listening on $Port" }
    else { Ok "stopped $Label (port $Port)" }
}

# Docker Desktop installs per-user on some machines rather than under Program Files, and that
# location is often missing from PATH. Resolve the exe rather than assuming `docker` works.
function Resolve-Docker {
    $onPath = Get-Command docker -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    foreach ($candidate in @(
        "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe",
        "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe"
    )) { if (Test-Path $candidate) { return $candidate } }
    return $null
}

function Resolve-DockerDesktop {
    foreach ($candidate in @(
        "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe",
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    )) { if (Test-Path $candidate) { return $candidate } }
    return $null
}

# `docker info` can exit 0 while printing an error, so an exit-code check reports a dead
# daemon as ready. `docker ps` is the honest probe.
function Test-DockerUp($Docker) {
    if (-not $Docker) { return $false }
    return (Invoke-Native $Docker @('ps')) -eq 0
}

function Wait-Url([string]$Url, [int]$TimeoutSec = 90) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 | Out-Null
            return $true
        } catch { Start-Sleep -Milliseconds 700 }
    }
    return $false
}

# ---------------------------------------------------------------- stop

if ($Stop) {
    Step 'Stopping Learnify'
    Stop-Port $WEB_PORT 'frontend'
    Stop-Port $API_PORT 'backend'
    $docker = Resolve-Docker
    if ((Test-DockerUp $docker)) {
        Invoke-Native $docker @('compose', 'stop') -WorkingDirectory $Root | Out-Null
        Ok 'stopped Postgres (data kept)'
    }
    Write-Host "`nStopped.`n" -ForegroundColor Green
    exit 0
}

# ---------------------------------------------------------------- preflight

Write-Host "`nLearnify" -ForegroundColor White
Note $Root

Step 'Checking prerequisites'

if (-not (Test-Path $VenvPy)) {
    Warn 'no Python virtualenv yet - creating it (one-time, ~2 min)'
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { & py -3.12 -m venv (Join-Path $Backend '.venv') }
    else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) { Die 'Python 3.12+ not found. Install it, then re-run.' }
        & python -m venv (Join-Path $Backend '.venv')
    }
    if (-not (Test-Path $VenvPy)) { Die 'could not create the virtualenv' }
    Invoke-Native $VenvPy @('-m', 'pip', 'install', '--quiet', '--upgrade', 'pip') -WorkingDirectory $Backend | Out-Null
    Invoke-Native $VenvPy @('-m', 'pip', 'install', '--quiet', '-e', '.[dev]') -WorkingDirectory $Backend | Out-Null
    Ok 'virtualenv created and dependencies installed'
}

$pyVersion = (Invoke-NativeText $VenvPy @('--version')) -replace 'Python ', ''
if ([version]($pyVersion -replace '(\d+\.\d+\.\d+).*', '$1') -lt [version]'3.12.0') {
    Die "the virtualenv is Python $pyVersion; 3.12+ is required. Delete backend\.venv and re-run."
}
Ok "python $pyVersion"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Die 'Node not found. Install Node 20+, then re-run.' }
Ok "node $(Invoke-NativeText 'node' @('--version'))"

if (-not (Test-Path (Join-Path $Frontend 'node_modules'))) {
    Warn 'frontend dependencies missing - installing (one-time, ~1 min)'
    Invoke-Native 'npm' @('install', '--silent') -WorkingDirectory $Frontend | Out-Null
    Ok 'frontend dependencies installed'
}

# ---------------------------------------------------------------- database

$usingPostgres = $false

if ($NoDocker) {
    Warn 'skipping Postgres (-NoDocker). State will NOT survive a restart.'
} else {
    Step 'Database'
    $docker = Resolve-Docker

    if (-not $docker) {
        Warn 'Docker not found - continuing without it. State will NOT survive a restart.'
    } else {
        if (-not (Test-DockerUp $docker)) {
            $desktop = Resolve-DockerDesktop
            if ($desktop) {
                Note 'starting Docker Desktop (can take a minute or two)'
                Start-Process $desktop | Out-Null
                $deadline = (Get-Date).AddMinutes(3)
                while ((Get-Date) -lt $deadline -and -not (Test-DockerUp $docker)) { Start-Sleep -Seconds 3 }
            }
        }

        if (Test-DockerUp $docker) {
            Invoke-Native $docker @('compose', 'up', '-d') -WorkingDirectory $Root | Out-Null

            $deadline = (Get-Date).AddSeconds(60)
            do {
                $health = Invoke-NativeText $docker @(
                    'inspect', '--format', '{{.State.Health.Status}}', 'knowledgeos-postgres')
                if ($health -eq 'healthy') { break }
                Start-Sleep -Seconds 2
            } while ((Get-Date) -lt $deadline)

            if ($health -eq 'healthy') {
                Ok 'postgres healthy'
                $usingPostgres = $true
                Invoke-Native (Join-Path $Backend '.venv\Scripts\alembic.exe') `
                    @('upgrade', 'head') -WorkingDirectory $Backend | Out-Null
                Ok 'schema up to date'
            } else {
                Warn "postgres did not become healthy (status: $health) - continuing in memory"
            }
        } else {
            Warn 'Docker daemon did not start - continuing without it. State will NOT survive a restart.'
        }
    }
}

if ($usingPostgres -and ($Demo -or $Fresh)) {
    Step 'Sample data'
    Push-Location $Backend
    if ($Fresh) { & $VenvPy seed.py --reset --demo } else { & $VenvPy seed.py --demo }
    Pop-Location
} elseif (($Demo -or $Fresh) -and -not $usingPostgres) {
    Warn 'skipping sample data: it needs Postgres'
}

# ---------------------------------------------------------------- servers

Step 'Starting servers'

if (Test-Port $API_PORT) {
    Note "backend already running on $API_PORT - leaving it"
} else {
    # Its own window, so the log is visible and Ctrl+C there stops just the backend.
    #
    # --reload only under -Dev. It runs a supervisor that respawns the worker, and when the
    # supervisor dies the worker inherits the listening socket while Windows keeps attributing
    # the port to the dead PID - which makes the port impossible to free cleanly. You only
    # need reload if you are editing backend code.
    $uvicornArgs = @('-m', 'uvicorn', 'knowledgeos.api.main:app',
                     '--host', '127.0.0.1', '--port', "$API_PORT")
    if ($Dev) { $uvicornArgs += '--reload' }
    Start-Process -FilePath $VenvPy -ArgumentList $uvicornArgs -WorkingDirectory $Backend | Out-Null
    Ok "backend starting on $API_URL$(if ($Dev) { ' (auto-reload on)' })"
}

if (Test-Port $WEB_PORT) {
    Note "frontend already running on $WEB_PORT - leaving it"
} else {
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'npm run dev' `
        -WorkingDirectory $Frontend | Out-Null
    Ok "frontend starting on $WEB_URL"
}

Step 'Waiting for both to answer'

if (-not (Wait-Url "$API_URL/health" 90)) {
    Die "the backend never answered on $API_URL. Check its window for the error."
}
Ok 'backend ready'

# Vite compiles on demand, so the very first request is slow - this is not a hang.
if (-not (Wait-Url $WEB_URL 90)) {
    Die "the frontend never answered on $WEB_URL. Check its window for the error."
}
Ok 'frontend ready'

# ---------------------------------------------------------------- summary

try {
    $health = Invoke-RestMethod -Uri "$API_URL/health" -TimeoutSec 10
    $concepts = $health.curriculum_nodes
} catch { $concepts = '?' }

Write-Host ""
Write-Host "  Learnify is running" -ForegroundColor Green
Write-Host "    app       $WEB_URL"
Write-Host "    api docs  $API_URL/docs"
Write-Host "    curriculum $concepts concepts" -ForegroundColor DarkGray
if (-not $usingPostgres) {
    Write-Host "    storage   IN MEMORY - nothing is saved when you stop" -ForegroundColor Yellow
} else {
    Write-Host "    storage   postgres" -ForegroundColor DarkGray
}
Write-Host ""
Write-Host "  Stop with:  .\run.ps1 -Stop" -ForegroundColor DarkGray
if (-not $Dev) {
    Write-Host "  Editing backend code? .\run.ps1 -Dev turns on auto-reload" -ForegroundColor DarkGray
}
Write-Host ""

if (-not $NoBrowser) { Start-Process $WEB_URL | Out-Null }
