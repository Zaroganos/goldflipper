@echo off
setlocal enabledelayedexpansion

if "%~1"=="" (
    goto usage
)

set COMMAND=%~1
shift

if /I "%COMMAND%"=="run" goto run
if /I "%COMMAND%"=="test" goto test
if /I "%COMMAND%"=="lint" goto lint
if /I "%COMMAND%"=="format" goto format
if /I "%COMMAND%"=="check" goto check
goto usage

:run
uv run goldflipper %*
goto end

:test
uv run pytest %*
goto end

:lint
uv run ruff check src/ tests/ %*
goto end

:format
uv run ruff format src/ tests/ %*
goto end

:check
echo Running all checks...
uv run ruff format --check src/ tests/
if errorlevel 1 goto check_failed
uv run ruff check src/ tests/
if errorlevel 1 goto check_failed
uv run pyright src/
if errorlevel 1 goto check_failed
uv run pytest
if errorlevel 1 goto check_failed
echo All checks passed.
goto end

:check_failed
echo One or more checks failed.
exit /b 1

:usage
echo Usage: dev.bat [command] [args]
echo Commands:
echo   run     - Run goldflipper
echo   test    - Run tests
echo   lint    - Lint code
echo   format  - Format code
echo   check   - Run all checks \(format, lint, type, test\)
exit /b 1

:end
endlocal

