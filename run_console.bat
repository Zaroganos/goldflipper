@echo off
cd /d %~dp0
echo Starting GoldFlipper in console mode...
python -m goldflipper.run --mode console
pause 