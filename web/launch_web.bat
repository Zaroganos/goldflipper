@echo off
rem Load shared environment
if exist "%~dp0..\..\.env.bat" call "%~dp0..\..\.env.bat"

:: Default GOLDFLIPPER_DATA_DIR if not provided (Windows standard path)
if not defined GOLDFLIPPER_DATA_DIR (
  if defined LOCALAPPDATA (
    set "GOLDFLIPPER_DATA_DIR=%LOCALAPPDATA%\Goldflipper"
  ) else (
    set "GOLDFLIPPER_DATA_DIR=%USERPROFILE%\AppData\Local\Goldflipper"
  )
)

:: Ensure DB directories exist
set "DB_DIR=%GOLDFLIPPER_DATA_DIR%\db"
if not exist "%DB_DIR%" mkdir "%DB_DIR%"
if not exist "%DB_DIR%\backups" mkdir "%DB_DIR%\backups"
if not exist "%DB_DIR%\temp" mkdir "%DB_DIR%\temp"
python "%~dp0launch_web.py"