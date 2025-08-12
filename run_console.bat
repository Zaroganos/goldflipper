@echo off
cd /d %~dp0
echo Starting Goldflipper in console mode...
uv run python -m goldflipper.run --mode console
pause 