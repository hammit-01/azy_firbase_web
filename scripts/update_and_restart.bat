@echo off
:: Warehouse Pipeline - Update and Restart
:: Run as Administrator

set INSTALL_DIR=C:\warehouse-pipeline
set TASK_NAME=WarehousePipeline

echo === Stopping scheduler...
schtasks /end /tn %TASK_NAME% >nul 2>&1
timeout /t 3 /nobreak >nul

echo === Pulling latest code (force)...
cd /d %INSTALL_DIR%
git fetch origin
git reset --hard origin/main

echo === Deleting snapshot (format may have changed)...
if exist pipeline\snapshot.pkl del pipeline\snapshot.pkl

echo === Starting scheduler...
schtasks /run /tn %TASK_NAME%

echo.
echo === Done. Check logs:
echo %INSTALL_DIR%\pipeline\logs\pipeline.log
echo.
pause
