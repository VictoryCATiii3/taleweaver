# TaleWeaver Setup Script (PowerShell)
# This script sets up the Python environment, database, and frontend dependencies.

param (
    [switch]$SkipStart
)

$ErrorActionPreference = "Stop"

# Change directory to the repository root directory
$scriptPath = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if ($scriptPath) { Set-Location $scriptPath } else { $scriptPath = (Get-Location).Path }

Write-Host "--- TaleWeaver Setup ---" -ForegroundColor Cyan

# Helper: set or append a key=value pair in .env
# If the key line already exists it is replaced, otherwise appended.
function Set-EnvKey {
    param([string]$Key, [string]$Value)
    $content = Get-Content ".env" -Raw
    if ($content -match "(?m)^${Key}=") {
        $content = $content -replace "(?m)^${Key}=.*", "${Key}=${Value}"
    } else {
        $content = $content.TrimEnd() + "`r`n${Key}=${Value}`r`n"
    }
    Set-Content ".env" $content -NoNewline
}

# 1. Environment Variables (.env)
$envCreated = $false
if (-not (Test-Path ".env")) {
    Write-Host "[*] Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    $envCreated = $true
}

$envFile = Get-Content ".env" -Raw
if ($envFile -notmatch "PROJECT_NAME=") {
    $envFile = "PROJECT_NAME=`"TaleWeaver`"`r`n" + $envFile
} else {
    $envFile = $envFile -replace "PROJECT_NAME=.*", "PROJECT_NAME=`"TaleWeaver`""
}
Set-Content ".env" $envFile

# 2. Dependency Management (Poetry)
Write-Host "[*] Setting up Python dependencies with Poetry..." -ForegroundColor Yellow
if (Get-Command poetry -ErrorAction SilentlyContinue) {
    Write-Host "[+] Using system Poetry..." -ForegroundColor Green
    poetry install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Error: 'poetry install' failed with exit code $LASTEXITCODE." -ForegroundColor Red
        exit 1
    }
    $RUN_CMD = "poetry run"
} else {
    Write-Host "[*] Poetry not found in PATH. Checking virtual environment (venv)..." -ForegroundColor Yellow
    if (-not (Test-Path "venv")) {
        Write-Host "[*] Creating virtual environment (venv)..." -ForegroundColor Yellow
        python -m venv venv
    }
    Write-Host "[*] Installing Poetry and dependencies in venv..." -ForegroundColor Yellow
    .\venv\Scripts\python.exe -m pip install --upgrade pip
    .\venv\Scripts\pip.exe install "poetry>=2.0.0"
    .\venv\Scripts\poetry.exe install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Error: 'poetry install' in venv failed with exit code $LASTEXITCODE." -ForegroundColor Red
        exit 1
    }
    $RUN_CMD = ".\venv\Scripts\poetry.exe run"
}

# 3. Ports (asked once for a new .env; run.ps1 checks them before every start)
if ($envCreated) {
    Write-Host "[*] Configure ports (press Enter for the default). Use different ports per checkout." -ForegroundColor Yellow
    $backendPort = Read-Host "Backend port [8000]"
    $frontendPort = Read-Host "Frontend port [5173]"
    if ($backendPort -match "^\d+$") { Set-EnvKey "BACKEND_PORT" $backendPort }
    if ($frontendPort -match "^\d+$") { Set-EnvKey "FRONTEND_PORT" $frontendPort }
}

# 4. Security Keys
if (-not (Test-Path "data")) {
    Write-Host "[*] Creating data directory..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "data" | Out-Null
}

$envFile = Get-Content ".env" -Raw

# ENCRYPTION_KEY
if ($envFile -notmatch "(?m)^ENCRYPTION_KEY=[a-zA-Z0-9+/=_-]{20,}") {
    Write-Host "[*] Generating ENCRYPTION_KEY..." -ForegroundColor Yellow
    $key = Invoke-Expression "$RUN_CMD python -c `"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())`""
    Set-EnvKey "ENCRYPTION_KEY" $key
    Write-Host "[+] ENCRYPTION_KEY written to .env" -ForegroundColor Green
}

# SECRET_KEY
$envFile = Get-Content ".env" -Raw
if ($envFile -notmatch "(?m)^SECRET_KEY=[a-fA-F0-9]{64}") {
    Write-Host "[*] Generating SECRET_KEY..." -ForegroundColor Yellow
    $skey = Invoke-Expression "$RUN_CMD python -c `"import secrets; print(secrets.token_hex(32))`""
    Set-EnvKey "SECRET_KEY" $skey
    Write-Host "[+] SECRET_KEY written to .env" -ForegroundColor Green
}


# 5. Database Setup (Migrations)
Write-Host "[*] Running database migrations..." -ForegroundColor Yellow
Invoke-Expression "$RUN_CMD alembic upgrade head"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Error: Database migrations ('alembic upgrade head') failed with exit code $LASTEXITCODE." -ForegroundColor Red
    exit 1
}

# 6. Frontend Setup
Write-Host "[*] Installing frontend dependencies..." -ForegroundColor Yellow
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "[!] Error: 'npm' is not installed or not in PATH. Please install Node.js and npm first." -ForegroundColor Red
    exit 1
}
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeVersion = node --version
    Write-Host "[+] Found Node.js version: $nodeVersion" -ForegroundColor Green
}
Set-Location frontend
npm install --include=dev
if ($LASTEXITCODE -ne 0) {
    Set-Location ..
    Write-Host "[!] Error: 'npm install --include=dev' failed with exit code $LASTEXITCODE." -ForegroundColor Red
    exit 1
}
if (-not ((Test-Path "node_modules/.bin/vite.cmd") -or (Test-Path "node_modules/.bin/vite"))) {
    Set-Location ..
    Write-Host "[!] Error: Vite executable not found in frontend/node_modules/.bin after npm install." -ForegroundColor Red
    exit 1
}
Set-Location ..

# 7. Git Hooks Setup
if (Test-Path ".git") {
    Write-Host "[*] Configuring Git pre-commit hooks..." -ForegroundColor Yellow
    git config core.hooksPath .githooks
    Write-Host "[+] Git hooks linked to .githooks" -ForegroundColor Green
}

Write-Host "`n--- Setup Complete! ---" -ForegroundColor Green
Write-Host "Start the application with: .\run.ps1"
Write-Host "(Backend only: $RUN_CMD taleweaver | Frontend only: cd frontend; npm run dev)`n"

# 8. Start (Optional / Interactive) - run.ps1 owns the start logic incl. port checks
if (-not $SkipStart) {
    $start = Read-Host "Would you like to start the application now? (y/n)"
    if ($start -eq "y" -or $start -eq "Y") {
        & (Join-Path $scriptPath "run.ps1") -NoPull
    }
}
