@echo off
cd /d %~dp0

:: Activate virtual environment if it exists (uv now manages environments automatically)

echo Goldflipper starting in console mode ...
uv run goldflipper --mode console %*
pause