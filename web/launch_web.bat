@echo off
rem Load shared environment
call "%~dp0..\..\.env.bat"
python "%~dp0launch_web.py"