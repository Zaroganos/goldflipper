@echo off
cd /d %~dp0
echo Goldflipper starting in console mode...
python -m goldflipper.run --mode console
pause