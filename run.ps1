# TaleWeaver Run Script (PowerShell)
# Pulls the latest Git changes, syncs dependencies when lock files changed, checks the setup
# and ports configured in .env, then starts backend (Poetry) and frontend (Vite).

param (
    [switch]$NoPull
)

$ErrorActionPreference = "Stop"

# Change directory to the repository root directory
$scriptPath = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if ($scriptPath) { Set-Location $scriptPath } else { $scriptPath = (Get-Location).Path }

$onWindows = $env:OS -like "*Windows*"

function Get-PoetryCommand {
    # System Poetry first, then the venv fallback created by setup.ps1
    $system = Get-Command poetry -ErrorAction SilentlyContinue
    if ($system) { return $system.Source }
    $venvPoetry = if ($onWindows) { "venv\Scripts\poetry.exe" } else { "venv/bin/poetry" }
    if (Test-Path $venvPoetry) { return (Resolve-Path $venvPoetry).Path }
    return $null
}

function Test-PoetryEnv {
    param([string]$Poetry)
    if (-not $Poetry) { return $false }
    # 'poetry env info' reports the system Python when no env exists, so probe the deps instead
    try {
        & $Poetry run python -c "import fastapi, uvicorn, alembic" *> $null
    } catch {
        # Windows PowerShell turns redirected native stderr into terminating errors
        return $false
    }
    return $LASTEXITCODE -eq 0
}

function Test-FrontendInstalled {
    return (Test-Path "frontend/node_modules/.bin/vite.cmd") -or (Test-Path "frontend/node_modules/.bin/vite")
}

function Get-EnvValue {
    param([string]$Key, [string]$Default)
    if (-not (Test-Path ".env")) { return $Default }
    $line = Get-Content ".env" | Where-Object { $_ -match "^\s*$Key\s*=" } | Select-Object -Last 1
    if (-not $line) { return $Default }
    $value = ($line -split "=", 2)[1].Split("#")[0].Trim().Trim('"').Trim("'")
    if ($value) { return $value }
    return $Default
}

function Test-PortInUse {
    param([int]$Port)
    foreach ($address in @("127.0.0.1", "::1")) {
        $client = New-Object System.Net.Sockets.TcpClient
        try {
            $connect = $client.BeginConnect($address, $Port, $null, $null)
            if ($connect.AsyncWaitHandle.WaitOne(300) -and $client.Connected) { return $true }
        } catch {
            # Address family not available or connection refused: port is free on this address
        } finally {
            $client.Close()
        }
    }
    return $false
}

Write-Host "==============================" -ForegroundColor Green
Write-Host "      TaleWeaver Runner       " -ForegroundColor Green
Write-Host "==============================" -ForegroundColor Green

# 1. Fetch current state from Git and remember what changed
$changedFiles = @()
if ($NoPull) {
    Write-Host "[*] Skipping Git pull." -ForegroundColor Cyan
} elseif (Test-Path ".git") {
    Write-Host "[*] Fetching latest changes from Git..." -ForegroundColor Cyan
    $before = git rev-parse HEAD
    git pull
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Warning: Git pull failed. Continuing anyway..." -ForegroundColor Yellow
    } else {
        $changedFiles = @(git diff --name-only $before HEAD)
    }
} else {
    Write-Host "[!] Not a Git repository, skipping Git pull." -ForegroundColor Yellow
}

# 2. Check setup status
$poetry = Get-PoetryCommand
$missing = @()
if (-not (Test-Path ".env")) { $missing += ".env" }
if (-not $poetry) { $missing += "Poetry" }
elseif (-not (Test-PoetryEnv $poetry)) { $missing += "Poetry environment" }
if (-not (Test-FrontendInstalled)) { $missing += "frontend/node_modules" }

if ($missing.Count -gt 0) {
    Write-Host "[!] Project setup is missing or incomplete (missing: $($missing -join ', '))." -ForegroundColor Yellow
    $choice = Read-Host "Would you like to run the setup script now? (y/n)"
    if ($choice -ne "y" -and $choice -ne "Y") {
        Write-Host "[*] Exiting. Run .\setup.ps1 to set up the project."
        exit 0
    }
    Write-Host "[*] Running setup.ps1..." -ForegroundColor Cyan
    & .\setup.ps1 -SkipStart
    $poetry = Get-PoetryCommand
    if (-not (Test-Path ".env") -or -not (Test-PoetryEnv $poetry) -or -not (Test-FrontendInstalled)) {
        Write-Host "[!] Setup failed or is still incomplete. Exiting." -ForegroundColor Red
        exit 1
    }
    $changedFiles = @()
}

# 3. Sync dependencies and database when the pull brought relevant changes
if ($changedFiles | Where-Object { $_ -in @("poetry.lock", "pyproject.toml") }) {
    Write-Host "[*] Python dependencies changed, running 'poetry install'..." -ForegroundColor Cyan
    & $poetry install
    if ($LASTEXITCODE -ne 0) { Write-Host "[!] 'poetry install' failed." -ForegroundColor Red; exit 1 }
}
if ($changedFiles | Where-Object { $_ -in @("frontend/package.json", "frontend/package-lock.json") }) {
    Write-Host "[*] Frontend dependencies changed, running 'npm install'..." -ForegroundColor Cyan
    Push-Location frontend
    npm install --include=dev
    $npmExit = $LASTEXITCODE
    Pop-Location
    if ($npmExit -ne 0) { Write-Host "[!] 'npm install' failed." -ForegroundColor Red; exit 1 }
}

# 4. Check the ports configured in .env (backend and Vite both read them from there)
$backendPort = [int](Get-EnvValue "BACKEND_PORT" "8000")
$frontendPort = [int](Get-EnvValue "FRONTEND_PORT" "5173")
if ($backendPort -eq $frontendPort) {
    Write-Host "[!] BACKEND_PORT and FRONTEND_PORT in .env must differ (both are $backendPort)." -ForegroundColor Red
    exit 1
}
$busy = @(@($backendPort, $frontendPort) | Where-Object { Test-PortInUse $_ })
if ($busy.Count -gt 0) {
    Write-Host "[!] Port(s) already in use: $($busy -join ', ')." -ForegroundColor Red
    Write-Host "    Another TaleWeaver instance (e.g. a second checkout) or another program is running." -ForegroundColor Red
    Write-Host "    Stop it, or set different BACKEND_PORT / FRONTEND_PORT values in .env." -ForegroundColor Red
    exit 1
}

# 5. Start the application locally
Write-Host "[*] Starting backend (port $backendPort) and frontend (port $frontendPort)..." -ForegroundColor Green
$backendCommand = "`$host.UI.RawUI.WindowTitle = 'TaleWeaver Backend :$backendPort'; & '$poetry' run taleweaver"
$frontendCommand = "`$host.UI.RawUI.WindowTitle = 'TaleWeaver Frontend :$frontendPort'; npm run dev"

if ($onWindows) {
    Start-Process powershell -WorkingDirectory $scriptPath -ArgumentList "-NoExit", "-Command", $backendCommand
    Start-Process powershell -WorkingDirectory (Join-Path $scriptPath "frontend") -ArgumentList "-NoExit", "-Command", $frontendCommand
    Write-Host "[+] Application started in separate PowerShell windows." -ForegroundColor Green
} else {
    # Non-Windows PowerShell fallback (macOS/Linux)
    Start-Job -Name "taleweaver-backend" -ScriptBlock { Set-Location $using:scriptPath; & $using:poetry run taleweaver } | Out-Null
    Start-Job -Name "taleweaver-frontend" -ScriptBlock { Set-Location (Join-Path $using:scriptPath "frontend"); npm run dev } | Out-Null
    Write-Host "[+] Jobs started. Use 'Get-Job' / 'Receive-Job' to check them, 'Stop-Job' to stop them." -ForegroundColor Green
}
Write-Host "[+] Open http://localhost:$frontendPort" -ForegroundColor Green
