@echo off
:: Warehouse Pipeline - Windows Setup
:: Double-click to run (no admin required for setup)

set INSTALL_DIR=C:\warehouse-pipeline
set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..

echo === Warehouse Pipeline Setup ===

:: 1. Create directories
echo [1/5] Creating directories...
if not exist "%INSTALL_DIR%\pipeline\logs" mkdir "%INSTALL_DIR%\pipeline\logs"
echo   Done

:: 2. Copy project files
echo [2/5] Copying project files...
robocopy "%PROJECT_DIR%" "%INSTALL_DIR%" /E /XD ".git" "__pycache__" ".vscode" /XF "*.pyc" >nul 2>&1
echo   Done: %PROJECT_DIR% -^> %INSTALL_DIR%

:: 3. Create virtual environment
echo [3/5] Creating Python virtual environment...
cd /d "%INSTALL_DIR%"
python -m venv venv
if errorlevel 1 (
    echo   ERROR: Python not found. Install Python first.
    pause
    exit /b 1
)
call venv\Scripts\activate
pip install --upgrade pip -q
pip install -r requirements_pipeline.txt -q
echo   Packages installed

:: 4. Check Firebase key
echo [4/5] Checking Firebase key file...
if exist "%INSTALL_DIR%\*firebase-adminsdk*.json" (
    echo   OK: Key file found
) else (
    echo   WARNING: Firebase key file not found!
    echo   Copy the key file to %INSTALL_DIR%
)

:: 5. Import test
echo [5/5] Import test...
python -c "from pipeline.scheduler import run_pipeline; print('  Import OK')"
if errorlevel 1 (
    echo   ERROR: Import failed. Check requirements.
    pause
    exit /b 1
)

echo.
echo === Setup Complete ===
echo Next: Run scripts\install_service.bat to register Windows service
echo.
pause
