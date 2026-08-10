@echo off
cd /d "C:\warehouse-pipeline"

:: Task Scheduler로 실행되면 setx로 저장한 사용자 환경변수가 프로세스에 자동으로
:: 반영되지 않는 경우가 있어 레지스트리에서 직접 읽어와 명시적으로 설정
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v MYSQL_PASSWORD 2^>nul ^| findstr MYSQL_PASSWORD') do set MYSQL_PASSWORD=%%B

:: venv\Scripts\activate 대신 시스템 파이썬 직접 사용 — venv에 dbutils/gspread가
:: 안 깔려 있어 시작하자마자 죽었다(2026-08-10 발견). WarehouseAPI 작업과 예전
:: dev 폴더 파이프라인 작업이 이미 이 시스템 파이썬으로 정상 동작 중이라 그대로 맞춤.
"C:\Users\OWNER\AppData\Local\Python\pythoncore-3.14-64\python.exe" run_service.py
