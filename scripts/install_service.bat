@echo off
:: Warehouse Pipeline - NSSM Service Registration
:: Run as Administrator (Right-click -> Run as Administrator)
:: Download NSSM: https://nssm.cc/download -> extract to C:\tools\nssm\

set INSTALL_DIR=C:\warehouse-pipeline
set SERVICE_NAME=WarehousePipeline
set NSSM=C:\tools\nssm\nssm.exe
set PYTHON=%INSTALL_DIR%\venv\Scripts\python.exe
set SCRIPT=%INSTALL_DIR%\run_service.py
set LOG_DIR=%INSTALL_DIR%\pipeline\logs

echo === NSSM Service Registration ===

:: Check NSSM
if not exist "%NSSM%" (
    echo ERROR: NSSM not found at %NSSM%
    echo Download: https://nssm.cc/download
    echo Extract and place nssm.exe at C:\tools\nssm\nssm.exe
    pause
    exit /b 1
)

:: Remove existing service
sc query %SERVICE_NAME% >nul 2>&1
if not errorlevel 1 (
    echo Removing existing service...
    "%NSSM%" stop %SERVICE_NAME% >nul 2>&1
    "%NSSM%" remove %SERVICE_NAME% confirm
    timeout /t 2 /nobreak >nul
)

:: Register service
echo Registering service...
"%NSSM%" install %SERVICE_NAME% "%PYTHON%" "%SCRIPT%"
"%NSSM%" set %SERVICE_NAME% AppDirectory "%INSTALL_DIR%"
"%NSSM%" set %SERVICE_NAME% DisplayName  "Warehouse Inventory Pipeline"
"%NSSM%" set %SERVICE_NAME% Description  "1-minute crawling and Firebase update"
"%NSSM%" set %SERVICE_NAME% Start        SERVICE_AUTO_START

:: Log settings
"%NSSM%" set %SERVICE_NAME% AppStdout      "%LOG_DIR%\service_out.log"
"%NSSM%" set %SERVICE_NAME% AppStderr      "%LOG_DIR%\service_err.log"
"%NSSM%" set %SERVICE_NAME% AppRotateFiles 1
"%NSSM%" set %SERVICE_NAME% AppRotateBytes 10485760

:: Restart on crash (15s delay)
"%NSSM%" set %SERVICE_NAME% AppRestartDelay 15000

:: Start service
echo Starting service...
"%NSSM%" start %SERVICE_NAME%
timeout /t 3 /nobreak >nul

sc query %SERVICE_NAME% | find "RUNNING" >nul
if not errorlevel 1 (
    echo Service status: RUNNING
) else (
    echo Service status: NOT RUNNING - check logs
)

echo.
echo === Done ===
echo Log directory: %LOG_DIR%
echo.
pause
