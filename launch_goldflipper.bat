@echo off
cd /d %~dp0
echo Starting GoldFlipper in interactive mode...
python -m goldflipper.goldflipper_tui
if errorlevel 1 (
    echo Error occurred while running GoldFlipper
    pause
    exit /b 1
)
pause 