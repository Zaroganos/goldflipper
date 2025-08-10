@echo off
setlocal enabledelayedexpansion

set SCRIPT_PATH=%~dp0
set ENV_FILE=%SCRIPT_PATH%..\.env.bat

:: Load shared env (DB dir, etc.)
if exist "%ENV_FILE%" (
  call "%ENV_FILE%"
)

if not exist "%SETTINGS_FILE%" (
    echo First time setup: Running setup dialog...
    python -m goldflipper.first_run_setup
    if errorlevel 1 (
        echo Error occurred during setup
        pause
        exit /b 1
    )
)

:: First-run DB check (deprecated YAML removed)
set "DB_DIR=%GOLDFLIPPER_DATA_DIR%\db"
set "DB_FILE=%DB_DIR%\goldflipper.db"

if not defined GOLDFLIPPER_DATA_DIR (
  echo No GOLDFLIPPER_DATA_DIR set. Running first-run DB setup...
  python -m goldflipper.first_run_db_setup
  if errorlevel 1 goto :ERR
  call "%ENV_FILE%"
)

if not exist "%DB_FILE%" (
  echo Database not found at "%DB_FILE%". Running first-run DB setup...
  python -m goldflipper.first_run_db_setup
  if errorlevel 1 goto :ERR
  call "%ENV_FILE%"
)

:: Launch the application
cd /d %~dp0
echo Starting Goldflipper in interactive mode...
python -m goldflipper.goldflipper_tui
if errorlevel 1 (
    echo Error occurred while running GoldFlipper
    pause
    exit /b 1
)
pause 

:ERR
echo Setup failed. Please check logs.
pause