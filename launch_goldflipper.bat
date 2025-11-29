@echo off
setlocal enabledelayedexpansion

:: Check if this is the first run by looking for the settings file
set SCRIPT_PATH=%~dp0
cd /d %SCRIPT_PATH%

:: Launch the application via uv-managed environment
echo Goldflipper starting in interactive mode with uv...
uv run goldflipper %*
if errorlevel 1 (
    echo Error occurred while running Goldflipper
    pause
    exit /b 1
)
pause