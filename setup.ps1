$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
Write-Host "=== FX Trading Simulator setup ===" -ForegroundColor Cyan

$hasDocker = $null -ne (Get-Command docker -ErrorAction SilentlyContinue)
if ($hasDocker) {
    try { docker info *> $null; $dockerRunning = ($LASTEXITCODE -eq 0) } catch { $dockerRunning = $false }
} else { $dockerRunning = $false }

if ($dockerRunning) {
    Write-Host "Docker detected. Building and starting all three services..." -ForegroundColor Green
    docker compose up --build -d
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed. Check Docker Desktop and run 'docker compose logs'." }
    Write-Host "Frontend: http://localhost:3000"
    Write-Host "Backend Swagger: http://localhost:8000/docs"
    Write-Host "Done. Use 'docker compose logs -f' to inspect logs."
    exit 0
}

Write-Host "Docker is unavailable. Using your local PostgreSQL installation instead." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python was not found. Install Python 3.11+ and retry." }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "Node.js/npm was not found. Install Node.js 20+ and retry." }

$pgService = Get-Service *postgres* -ErrorAction SilentlyContinue | Where-Object Status -eq "Running" | Select-Object -First 1
if (-not $pgService) { throw "PostgreSQL service is not running. Start it and retry." }

$pgPassword = Read-Host "Enter your LOCAL PostgreSQL password (input is hidden)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pgPassword)
try { $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }

Write-Host "Installing backend dependencies..."
python -m pip install -r backend/requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }

$env:DATABASE_URL = "postgresql+psycopg://postgres:$([uri]::EscapeDataString($plainPassword))@localhost:5432/fxsim"
$env:TICK_INTERVAL_SECONDS = "1"
$env:STARTING_CASH_INR = "1000000"

Write-Host "Creating isolated fxsim database if needed..."
@'
import os
import psycopg
from urllib.parse import urlparse, unquote
url = urlparse(os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1))
admin = psycopg.connect(host=url.hostname, port=url.port or 5432, user=url.username,
                        password=unquote(url.password or ""), dbname="postgres", autocommit=True)
try:
    exists = admin.execute("SELECT 1 FROM pg_database WHERE datname = 'fxsim'").fetchone()
    if not exists:
        admin.execute('CREATE DATABASE fxsim')
        print("Created database fxsim")
    else:
        print("Database fxsim already exists; keeping its data")
finally:
    admin.close()
'@ | python -
if ($LASTEXITCODE -ne 0) { throw "Could not connect to local PostgreSQL or create fxsim. Check the password and port." }

Write-Host "Running backend tests..."
Push-Location backend
python -m pytest -q
$testCode = $LASTEXITCODE
Pop-Location
if ($testCode -ne 0) { throw "Tests failed. Fix the test output before launching the app." }

Write-Host "Installing frontend packages..."
Push-Location frontend
npm install
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "npm install failed." }
Pop-Location

Write-Host "Starting backend and frontend in separate PowerShell windows..."
$backendCommand = "`$env:DATABASE_URL='$env:DATABASE_URL'; `$env:TICK_INTERVAL_SECONDS='1'; Set-Location '$root\backend'; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
$frontendCommand = "Set-Location '$root\frontend'; `$env:NEXT_PUBLIC_API_URL='http://localhost:8000'; `$env:NEXT_PUBLIC_WS_URL='ws://localhost:8000/ws/prices'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCommand
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCommand
Write-Host "Started. Frontend: http://localhost:3000 | API docs: http://localhost:8000/docs" -ForegroundColor Green
