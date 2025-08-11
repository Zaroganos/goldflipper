@echo off
cd /d %~dp0
echo Starting Goldflipper in console mode...
python -m goldflipper.run --mode console
pause 