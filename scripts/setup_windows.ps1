# =============================================================
# 창고 파이프라인 Windows 11 초기 설정 스크립트
# 관리자 권한으로 실행: PowerShell → 우클릭 → 관리자로 실행
# =============================================================

param(
    [string]$InstallDir = "C:\warehouse-pipeline",
    [string]$PythonExe  = "python"
)

Write-Host "=== 창고 파이프라인 설치 시작 ===" -ForegroundColor Cyan

# 1. 설치 디렉터리 생성
Write-Host "`n[1/5] 설치 디렉터리 생성: $InstallDir"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\pipeline\logs" | Out-Null

# 2. 현재 프로젝트 복사 (이미 이 PC에 있다면 로보카피, 없으면 git clone)
Write-Host "`n[2/5] 프로젝트 파일 복사"
$SourceDir = Split-Path -Parent $PSScriptRoot
robocopy $SourceDir $InstallDir /E /XD ".git" "__pycache__" ".vscode" /XF "*.pyc" | Out-Null
Write-Host "  완료: $SourceDir → $InstallDir"

# 3. 가상환경 생성 및 패키지 설치
Write-Host "`n[3/5] Python 가상환경 생성"
Set-Location $InstallDir
& $PythonExe -m venv venv
& "$InstallDir\venv\Scripts\pip" install --upgrade pip -q
& "$InstallDir\venv\Scripts\pip" install -r requirements_pipeline.txt -q
Write-Host "  패키지 설치 완료"

# 4. Firebase 키 파일 확인
Write-Host "`n[4/5] Firebase 키 파일 확인"
$KeyFile = Get-ChildItem -Path $InstallDir -Filter "*firebase-adminsdk*.json" | Select-Object -First 1
if ($KeyFile) {
    Write-Host "  ✓ 키 파일 발견: $($KeyFile.Name)"
} else {
    Write-Host "  ⚠ Firebase Admin SDK 키 파일이 없습니다!" -ForegroundColor Yellow
    Write-Host "    $InstallDir 에 키 파일을 복사해주세요."
}

# 5. 테스트 실행
Write-Host "`n[5/5] 파이프라인 임포트 테스트"
$TestResult = & "$InstallDir\venv\Scripts\python" -c "from pipeline.scheduler import run_pipeline; print('OK')" 2>&1
if ($TestResult -eq "OK") {
    Write-Host "  ✓ 임포트 성공" -ForegroundColor Green
} else {
    Write-Host "  ✗ 오류: $TestResult" -ForegroundColor Red
}

Write-Host "`n=== 설치 완료 ===" -ForegroundColor Green
Write-Host "다음 단계: scripts\install_service.ps1 실행 (NSSM 서비스 등록)"
