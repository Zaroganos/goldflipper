@echo off
setlocal enabledelayedexpansion

set SCRIPT_PATH=%~dp0

:: Launch in a new window (no /MAX - maximization is handled by Python code after Textual initializes)
:: chcp 65001 = UTF-8 for better Unicode rendering
:: No /WAIT = original window closes immediately
start "Goldflipper" cmd /c "cd /d %SCRIPT_PATH% && chcp 65001 >nul && uv run python -m goldflipper.launcher %*"