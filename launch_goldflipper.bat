@echo off
setlocal enabledelayedexpansion

:: Check if this is the first run by looking for the settings file
set SCRIPT_PATH=%~dp0
cd /d %SCRIPT_PATH%

:: Launch the desktop TUI (goldflipper.launcher) via uv-managed environment
echo Goldflipper Multistrat is starting up ...
uv run python -m goldflipper.launcher %*
if errorlevel 1 (
    echo Error occurred while running Goldflipper
    pause
    exit /b 1
)
pause