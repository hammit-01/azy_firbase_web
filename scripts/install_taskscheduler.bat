@echo off
:: Warehouse Pipeline - Windows Task Scheduler Registration
:: Run as Administrator (Right-click -> Run as Administrator)
:: No additional download required

set INSTALL_DIR=C:\warehouse-pipeline
set TASK_NAME=WarehousePipeline
set PYTHON=%INSTALL_DIR%\venv\Scripts\python.exe
set SCRIPT=run_service.py

echo === Task Scheduler Service Registration ===

:: Remove existing task
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Register task (run at startup, run as SYSTEM, restart on failure)
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%PYTHON%\" %SCRIPT%" ^
  /sc ONSTART ^
  /ru SYSTEM ^
  /rl HIGHEST ^
  /sd 01/01/2024 ^
  /f

if errorlevel 1 (
    echo ERROR: Task registration failed. Run as Administrator.
    pause
    exit /b 1
)

:: Set working directory via XML patch
echo Setting working directory...
schtasks /query /tn "%TASK_NAME%" /xml > "%TEMP%\task_tmp.xml" 2>nul

powershell -Command ^
  "(Get-Content '%TEMP%\task_tmp.xml') ^
   -replace '<Command>', '<WorkingDirectory>%INSTALL_DIR%</WorkingDirectory><Command>' ^
   | Set-Content '%TEMP%\task_fixed.xml'"

schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
schtasks /create /tn "%TASK_NAME%" /xml "%TEMP%\task_fixed.xml" /f >nul 2>&1

:: Start immediately
echo Starting task...
schtasks /run /tn "%TASK_NAME%"

timeout /t 3 /nobreak >nul
schtasks /query /tn "%TASK_NAME%" | find "Running"
if not errorlevel 1 (
    echo Status: RUNNING
) else (
    echo Status: check Task Scheduler
)

echo.
echo === Done ===
echo Boots automatically on startup.
echo.
echo Manage:
echo   Start : schtasks /run /tn %TASK_NAME%
echo   Stop  : schtasks /end /tn %TASK_NAME%
echo   Status: schtasks /query /tn %TASK_NAME%
echo   Logs  : %INSTALL_DIR%\pipeline\logs\pipeline.log
echo.
pause
