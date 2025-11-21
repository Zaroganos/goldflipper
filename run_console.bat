@echo off
cd /d %~dp0

:: Activate virtual environment if it exists
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
)

echo Goldflipper starting in console mode...
python -m goldflipper.run --mode console
pause