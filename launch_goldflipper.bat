@echo off
setlocal enabledelayedexpansion

:: Check if this is the first run by looking for the settings file
set SCRIPT_PATH=%~dp0
set SETTINGS_FILE=%SCRIPT_PATH%goldflipper\config\settings.yaml

if not exist "%SETTINGS_FILE%" (
    echo Setting up Goldflipper...
    python -m goldflipper.first_run_setup
    if errorlevel 1 (
        echo Error occurred during setup
        pause
        exit /b 1
    )
)

:: Launch the application
cd /d %~dp0
echo Goldflipper starting in interactive mode...
python -m goldflipper.goldflipper_tui
if errorlevel 1 (
    echo Error occurred while running Goldflipper
    pause
    exit /b 1
)
pause 