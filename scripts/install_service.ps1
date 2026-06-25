# Warehouse Pipeline - NSSM Windows Service Registration
# Run as Administrator
# Download NSSM: https://nssm.cc/download

param(
    [string]$InstallDir  = "C:\warehouse-pipeline",
    [string]$NssmPath    = "C:\tools\nssm\nssm.exe",
    [string]$ServiceName = "WarehousePipeline"
)

$PythonExe  = "$InstallDir\venv\Scripts\python.exe"
$ScriptPath = "$InstallDir\run_service.py"
$LogDir     = "$InstallDir\pipeline\logs"

Write-Host "=== NSSM Service Registration ===" -ForegroundColor Cyan

# Check NSSM
if (-not (Test-Path $NssmPath)) {
    Write-Host "NSSM not found: $NssmPath" -ForegroundColor Red
    Write-Host "Download: https://nssm.cc/download"
    Write-Host "Extract and place nssm.exe, then specify path with -NssmPath"
    exit 1
}

# Remove existing service
$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing service..."
    & $NssmPath stop $ServiceName 2>$null
    & $NssmPath remove $ServiceName confirm
    Start-Sleep -Seconds 2
}

# Register service
Write-Host "Registering service..."
& $NssmPath install $ServiceName $PythonExe $ScriptPath

# Configure service
& $NssmPath set $ServiceName AppDirectory $InstallDir
& $NssmPath set $ServiceName DisplayName  "Warehouse Inventory Pipeline"
& $NssmPath set $ServiceName Description  "1-minute interval warehouse crawling and Firebase update"
& $NssmPath set $ServiceName Start        SERVICE_AUTO_START

# Log configuration
& $NssmPath set $ServiceName AppStdout      "$LogDir\service_out.log"
& $NssmPath set $ServiceName AppStderr      "$LogDir\service_err.log"
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateBytes 10485760   # 10MB rotation

# Restart on crash (15 seconds delay)
& $NssmPath set $ServiceName AppRestartDelay 15000

# Start service
Write-Host "Starting service..."
& $NssmPath start $ServiceName

Start-Sleep -Seconds 3
$svc = Get-Service -Name $ServiceName
$color = if ($svc.Status -eq 'Running') { 'Green' } else { 'Red' }
Write-Host "Service status: $($svc.Status)" -ForegroundColor $color

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "Log directory: $LogDir"
Write-Host "Commands:"
Write-Host "  Start  : Start-Service $ServiceName"
Write-Host "  Stop   : Stop-Service $ServiceName"
Write-Host "  Status : Get-Service $ServiceName"
