# =============================================================
# 서비스 관리 편의 스크립트
# 사용: .\manage_service.ps1 [start|stop|restart|status|logs]
# =============================================================

param([string]$Action = "status")

$ServiceName = "WarehousePipeline"
$LogDir = "C:\warehouse-pipeline\pipeline\logs"

switch ($Action) {
    "start"   {
        Start-Service $ServiceName
        Write-Host "서비스 시작됨" -ForegroundColor Green
    }
    "stop"    {
        Stop-Service $ServiceName
        Write-Host "서비스 중지됨" -ForegroundColor Yellow
    }
    "restart" {
        Restart-Service $ServiceName
        Write-Host "서비스 재시작됨" -ForegroundColor Cyan
    }
    "status"  {
        $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($svc) {
            $color = if ($svc.Status -eq 'Running') { 'Green' } else { 'Red' }
            Write-Host "서비스 상태: $($svc.Status)" -ForegroundColor $color
        } else {
            Write-Host "서비스가 등록되지 않았습니다." -ForegroundColor Red
        }
    }
    "logs"    {
        $logFile = "$LogDir\pipeline.log"
        if (Test-Path $logFile) {
            Get-Content $logFile -Tail 50 -Wait
        } else {
            Write-Host "로그 파일 없음: $logFile" -ForegroundColor Yellow
        }
    }
    default   {
        Write-Host "사용법: .\manage_service.ps1 [start|stop|restart|status|logs]"
    }
}
