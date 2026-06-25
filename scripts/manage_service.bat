@echo off
:: Warehouse Pipeline - Service Management
:: Usage: manage_service.bat [start|stop|restart|status|logs]

set SERVICE_NAME=WarehousePipeline
set LOG_FILE=C:\warehouse-pipeline\pipeline\logs\pipeline.log

if "%1"=="start"   goto START
if "%1"=="stop"    goto STOP
if "%1"=="restart" goto RESTART
if "%1"=="status"  goto STATUS
if "%1"=="logs"    goto LOGS
goto USAGE

:START
net start %SERVICE_NAME%
goto END

:STOP
net stop %SERVICE_NAME%
goto END

:RESTART
net stop %SERVICE_NAME%
timeout /t 2 /nobreak >nul
net start %SERVICE_NAME%
goto END

:STATUS
sc query %SERVICE_NAME%
goto END

:LOGS
if exist "%LOG_FILE%" (
    powershell -Command "Get-Content '%LOG_FILE%' -Tail 50 -Wait"
) else (
    echo Log file not found: %LOG_FILE%
)
goto END

:USAGE
echo Usage: manage_service.bat [start^|stop^|restart^|status^|logs]

:END
