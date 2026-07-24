@echo off
cd /d "C:\warehouse-pipeline"
call venv\Scripts\activate

:: Task Scheduler로 실행되면 setx로 저장한 사용자 환경변수가 프로세스에 자동으로
:: 반영되지 않는 경우가 있어 레지스트리에서 직접 읽어와 명시적으로 설정
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v MYSQL_PASSWORD 2^>nul ^| findstr MYSQL_PASSWORD') do set MYSQL_PASSWORD=%%B

python run_service.py
