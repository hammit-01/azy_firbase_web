# =============================================================
# NSSM으로 Windows 서비스 등록
# 관리자 권한 PowerShell에서 실행
# NSSM 다운로드: https://nssm.cc/download
# =============================================================

param(
    [string]$InstallDir   = "C:\warehouse-pipeline",
    [string]$NssmPath     = "C:\tools\nssm\nssm.exe",
    [string]$ServiceName  = "WarehousePipeline"
)

$PythonExe  = "$InstallDir\venv\Scripts\python.exe"
$ScriptPath = "$InstallDir\run_service.py"
$LogDir     = "$InstallDir\pipeline\logs"

Write-Host "=== NSSM 서비스 등록 ===" -ForegroundColor Cyan

# NSSM 존재 확인
if (-not (Test-Path $NssmPath)) {
    Write-Host "NSSM을 찾을 수 없습니다: $NssmPath" -ForegroundColor Red
    Write-Host "다운로드: https://nssm.cc/download" -ForegroundColor Yellow
    Write-Host "압축 해제 후 nssm.exe 경로를 -NssmPath 파라미터로 지정하세요."
    exit 1
}

# 기존 서비스 제거
$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "기존 서비스 제거 중..."
    & $NssmPath stop $ServiceName 2>$null
    & $NssmPath remove $ServiceName confirm
    Start-Sleep -Seconds 2
}

# 서비스 등록
Write-Host "`n서비스 등록 중..."
& $NssmPath install $ServiceName $PythonExe $ScriptPath

# 서비스 설정
& $NssmPath set $ServiceName AppDirectory $InstallDir
& $NssmPath set $ServiceName DisplayName  "창고 재고 파이프라인"
& $NssmPath set $ServiceName Description  "1분 주기 창고 재고 크롤링 및 Firebase 업데이트"
& $NssmPath set $ServiceName Start        SERVICE_AUTO_START

# 로그 설정
& $NssmPath set $ServiceName AppStdout "$LogDir\service_out.log"
& $NssmPath set $ServiceName AppStderr "$LogDir\service_err.log"
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateBytes 10485760  # 10MB 로그 로테이션

# 재시작 설정 (크래시 시 15초 후 재시작)
& $NssmPath set $ServiceName AppRestartDelay 15000

# 서비스 시작
Write-Host "`n서비스 시작..."
& $NssmPath start $ServiceName

Start-Sleep -Seconds 3
$svc = Get-Service -Name $ServiceName
Write-Host "`n서비스 상태: $($svc.Status)" -ForegroundColor $(if ($svc.Status -eq 'Running') {'Green'} else {'Red'})

Write-Host "`n=== 완료 ===" -ForegroundColor Green
Write-Host "로그 확인: $LogDir"
Write-Host "서비스 관리: services.msc 또는 아래 명령어"
Write-Host "  시작: Start-Service $ServiceName"
Write-Host "  중지: Stop-Service $ServiceName"
Write-Host "  상태: Get-Service $ServiceName"
