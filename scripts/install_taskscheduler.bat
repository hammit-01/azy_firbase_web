@echo off
:: Warehouse Pipeline - Windows Task Scheduler Registration
:: Run as Administrator (Right-click -> Run as Administrator)

set INSTALL_DIR=C:\warehouse-pipeline
set TASK_NAME=WarehousePipeline
set WRAPPER=%INSTALL_DIR%\run_pipeline.bat

echo === Task Scheduler Registration ===

:: Remove existing task
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Register task using wrapper bat (working directory handled inside bat)
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%WRAPPER%\"" ^
  /sc ONSTART ^
  /ru SYSTEM ^
  /rl HIGHEST ^
  /f

if errorlevel 1 (
    echo ERROR: Failed. Run as Administrator.
    pause
    exit /b 1
)

echo Task registered.

:: Start immediately
echo Starting...
schtasks /run /tn "%TASK_NAME%"

timeout /t 5 /nobreak >nul

echo.
echo === Done ===
echo Log: %INSTALL_DIR%\pipeline\logs\pipeline.log
echo.
echo Commands:
echo   Start : schtasks /run /tn %TASK_NAME%
echo   Stop  : schtasks /end /tn %TASK_NAME%
echo   Status: schtasks /query /tn %TASK_NAME%
echo.
pause
