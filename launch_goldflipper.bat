@echo off
setlocal enabledelayedexpansion

set SCRIPT_PATH=%~dp0
set ENV_FILE=%SCRIPT_PATH%..\.env.bat

:: Load shared env (DB dir, etc.)
if exist "%ENV_FILE%" (
  call "%ENV_FILE%"
)

:: Default GOLDFLIPPER_DATA_DIR if not provided (OS-standard path)
if not defined GOLDFLIPPER_DATA_DIR (
  if defined LOCALAPPDATA (
    set "GOLDFLIPPER_DATA_DIR=%LOCALAPPDATA%\Goldflipper"
  ) else (
    set "GOLDFLIPPER_DATA_DIR=%USERPROFILE%\AppData\Local\Goldflipper"
  )
)

:: Ensure DB directories exist
set "DB_DIR=%GOLDFLIPPER_DATA_DIR%\db"
set "DB_FILE=%DB_DIR%\goldflipper.db"
if not exist "%DB_DIR%" mkdir "%DB_DIR%"
if not exist "%DB_DIR%\backups" mkdir "%DB_DIR%\backups"
if not exist "%DB_DIR%\temp" mkdir "%DB_DIR%\temp"

:: Launch the application
cd /d %~dp0
echo Starting Goldflipper in interactive mode...
python -m goldflipper.goldflipper_tui
if errorlevel 1 (
    echo Error occurred while running Goldflipper
    pause
    exit /b 1
)
pause 

:ERR
echo Setup failed. Please check logs.
pause