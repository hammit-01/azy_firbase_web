# Warehouse Pipeline - Service Management
# Usage: .\manage_service.ps1 [start|stop|restart|status|logs]

param([string]$Action = "status")

$ServiceName = "WarehousePipeline"
$LogFile     = "C:\warehouse-pipeline\pipeline\logs\pipeline.log"

switch ($Action) {
    "start"   {
        Start-Service $ServiceName
        Write-Host "Service started" -ForegroundColor Green
    }
    "stop"    {
        Stop-Service $ServiceName
        Write-Host "Service stopped" -ForegroundColor Yellow
    }
    "restart" {
        Restart-Service $ServiceName
        Write-Host "Service restarted" -ForegroundColor Cyan
    }
    "status"  {
        $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($svc) {
            $color = if ($svc.Status -eq 'Running') { 'Green' } else { 'Red' }
            Write-Host "Service status: $($svc.Status)" -ForegroundColor $color
        } else {
            Write-Host "Service not registered" -ForegroundColor Red
        }
    }
    "logs"    {
        if (Test-Path $LogFile) {
            Get-Content $LogFile -Tail 50 -Wait
        } else {
            Write-Host "Log file not found: $LogFile" -ForegroundColor Yellow
        }
    }
    default   {
        Write-Host "Usage: .\manage_service.ps1 [start|stop|restart|status|logs]"
    }
}
