# Warehouse Pipeline - Windows 11 Setup Script
# Run as Administrator: PowerShell -> Right Click -> Run as Administrator

param(
    [string]$InstallDir = "C:\warehouse-pipeline",
    [string]$PythonExe  = "python"
)

Write-Host "=== Warehouse Pipeline Setup ===" -ForegroundColor Cyan

# 1. Create install directory
Write-Host "[1/5] Creating directory: $InstallDir"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\pipeline\logs" | Out-Null

# 2. Copy project files
Write-Host "[2/5] Copying project files"
$SourceDir = Split-Path -Parent $PSScriptRoot
robocopy $SourceDir $InstallDir /E /XD ".git" "__pycache__" ".vscode" /XF "*.pyc" | Out-Null
Write-Host "  Done: $SourceDir -> $InstallDir"

# 3. Create virtual environment and install packages
Write-Host "[3/5] Creating Python virtual environment"
Set-Location $InstallDir
& $PythonExe -m venv venv
& "$InstallDir\venv\Scripts\pip" install --upgrade pip -q
& "$InstallDir\venv\Scripts\pip" install -r requirements_pipeline.txt -q
Write-Host "  Packages installed"

# 4. Check Firebase key file
Write-Host "[4/5] Checking Firebase key file"
$KeyFile = Get-ChildItem -Path $InstallDir -Filter "*firebase-adminsdk*.json" | Select-Object -First 1
if ($KeyFile) {
    Write-Host "  OK: $($KeyFile.Name)" -ForegroundColor Green
} else {
    Write-Host "  WARNING: Firebase Admin SDK key not found!" -ForegroundColor Yellow
    Write-Host "  Copy the key file to: $InstallDir"
}

# 5. Import test
Write-Host "[5/5] Import test"
$TestResult = & "$InstallDir\venv\Scripts\python" -c "from pipeline.scheduler import run_pipeline; print('OK')" 2>&1
if ($TestResult -eq "OK") {
    Write-Host "  Import OK" -ForegroundColor Green
} else {
    Write-Host "  Error: $TestResult" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host "Next step: Run scripts\install_service.ps1 to register Windows service"
