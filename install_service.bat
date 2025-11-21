@echo off
cd /d %~dp0

NET SESSION >nul 2>&1
if %errorLevel% == 0 (
    echo Administrative permissions confirmed.
) else (
    echo Error: This script requires administrative privileges.
    echo Please right-click it and select "Run as administrator"
    pause
    exit /b 1
)

echo Checking Python installation...
python --version 2>nul
if errorlevel 1 (
    echo Error: Python is not installed or is not in PATH
    pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install pywin32
if errorlevel 1 (
    echo Error installing dependencies
    pause
    exit /b 1
)

echo Installing Goldflipper in development mode...
python -m pip install -e .
if errorlevel 1 (
    echo Error installing Goldflipper
    pause
    exit /b 1
)

echo Creating service directories...
mkdir "%ProgramData%\Goldflipper\logs" 2>nul
icacls "%ProgramData%\Goldflipper" /grant "Users":(OI)(CI)F /T

echo Installing Goldflipper Trading Service...
python -m goldflipper.run --startup auto install
if errorlevel 1 (
    echo Error installing service
    pause
    exit /b 1
)

echo Configuring service permissions...
sc privs GoldflipperService SeChangeNotifyPrivilege/SeCreateGlobalPrivilege/SeSecurityPrivilege

echo Configuring service recovery options...
sc failure GoldflipperService reset= 0 actions= restart/5000

echo Starting Goldflipper Trading Service...
net start GoldflipperService
if errorlevel 1 (
    echo Error starting service. Please check Windows Event Viewer for details.
    echo You can also try starting the service manually from Services (services.msc)
    pause
    exit /b 1
)

echo.
echo Goldflipper Trading Service has been installed and started successfully!
echo To manage the service, use Windows Services (services.msc)
echo.
pause 