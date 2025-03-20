@echo off
cd /d %~dp0

NET SESSION >nul 2>&1
if %errorLevel% == 0 (
    echo Administrative permissions confirmed.
) else (
    echo Error: This script requires administrative privileges.
    echo Please right-click and select "Run as administrator"
    pause
    exit /b 1
)

echo Checking Python installation...
python --version 2>nul
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

echo Checking Poetry installation...
poetry --version 2>nul
if errorlevel 1 (
    echo Installing Poetry...
    python -m pip install poetry
    if errorlevel 1 (
        echo Error installing Poetry
        pause
        exit /b 1
    )
)

echo Installing project dependencies...
poetry install
if errorlevel 1 (
    echo Error installing dependencies
    pause
    exit /b 1
)

echo Creating service directories...
mkdir "%ProgramData%\GoldFlipper\logs" 2>nul
icacls "%ProgramData%\GoldFlipper" /grant "Users":(OI)(CI)F /T

echo Installing GoldFlipper Trading Service...
poetry run python -m goldflipper.run --startup auto install
if errorlevel 1 (
    echo Error installing service
    pause
    exit /b 1
)

echo Configuring service permissions...
sc privs GoldFlipperService SeChangeNotifyPrivilege/SeCreateGlobalPrivilege/SeSecurityPrivilege

echo Configuring service recovery options...
sc failure GoldFlipperService reset= 0 actions= restart/5000

echo Starting GoldFlipper Trading Service...
net start GoldFlipperService
if errorlevel 1 (
    echo Error starting service. Please check Windows Event Viewer for details.
    echo You can also try starting the service manually from Services (services.msc)
    pause
    exit /b 1
)

echo.
echo GoldFlipper Trading Service has been installed and started successfully!
echo To manage the service, use Windows Services (services.msc)
echo.
pause 