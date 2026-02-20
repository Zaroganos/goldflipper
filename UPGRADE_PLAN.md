
# Implementation Plan: Python Project Modernization
# **AGENTS** THOUGH THIS DOC USES BASH SYNTAX, ENSURE YOU ACTUALLY USE WINDOWS POWERSHELL COMMANDS AND SYNTAX, AND THE WINDOWS FILESYSTEM! COMPLY WITH THIS INSTRUCTION UNLESS OTHERWISE DIRECTED

## Project Context
- **Current state**: Existing Python codebase using setuptools + requirements.txt
- **Current tooling**: setup.py, pip, virtualenv, pytest (no linting/formatting configured)
- **Target stack**: Python 3.12, uv, hatchling, ruff, pyright, pytest, nuitka
- **Distribution**: Git repository + Nuitka compiled executables
- **No C extensions**: Pure Python with package data (YAML, batch files, etc.)
- **Target platform**: Windows desktop application
- **Entry point**: `goldflipper` CLI via `goldflipper.run:main`

---

## Phase 1: Project Assessment & Preparation

> **Status – 2025-12-08:** Completed. All migration artifacts documented in `docs/migration/`.

### 1.1 Document Current State
```bash
# In project root, create migration documentation directory
mkdir -p docs/migration

# Document current dependencies
copy requirements.txt docs/migration/requirements-original.txt

# Document current setup.py configuration
copy setup.py docs/migration/setup-original.py

# Document package structure
tree /F src > docs/migration/package-structure.txt  # Windows
# or
find src -type f > docs/migration/package-structure.txt  # Unix-like
```

### 1.2 Identify Key Configuration Elements

Document in `docs/migration/current-config.md`:

```markdown
# Current Configuration Analysis

## Package Metadata (from setup.py)
- Package name: goldflipper
- Python requirement: >=3.10
- Entry point: goldflipper = goldflipper.run:main

## Package Data (from setup.py and MANIFEST.in)
- Identify all package_data directories
- List all files in MANIFEST.in
- Note any data files needed at runtime

## Dependencies (from requirements.txt and setup.py)
### Runtime
- alpaca-py, yfinance, ta, mplfinance
- pandas, numpy, scipy
- matplotlib, seaborn
- textual, rich, colorama
- psutil, pywin32, tkinterdnd2
- requests, charset-normalizer, urllib3, PyYAML, XlsxWriter

### Development
- pytest

## Entry Points and Scripts
- CLI: goldflipper (points to goldflipper.run:main)
- Batch files: launch_goldflipper.bat, install_service.bat, run_console.bat
- PowerShell: bootstrap.ps1

## Platform-Specific
- Windows service integration (service_wrapper.py)
- Windows-specific dependencies (pywin32)
```

### 1.3 Backup Current Configuration
```bash
# Backup all configuration files
copy setup.py setup.py.backup
copy requirements.txt requirements.txt.backup
copy MANIFEST.in MANIFEST.in.backup  # if exists
```

---

## Phase 2: Install uv and Create Initial Configuration

> **Status – 2025-12-08:** ✅ Completed. `pyproject.toml` created with all dependencies and tool configurations.

### 2.1 Install uv

Windows PowerShell
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify installation
```powershell
uv --version
```

### 2.2 Create New pyproject.toml

Create `pyproject.toml` in project root:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "goldflipper"
version = "0.1.0"  # Extract from setup.py
description = "Trading automation and analysis tool"  # Extract from setup.py
readme = "README.md"
requires-python = ">=3.12,<3.14"  # Update from 3.10+ to modern range
authors = [
    # Extract from setup.py if present
]
license = {text = "MIT"}  # Adjust based on actual license

# Extract all dependencies from requirements.txt and setup.py install_requires
dependencies = [
    "alpaca-py",
    "yfinance",
    "ta",
    "mplfinance",
    "pandas",
    "numpy",
    "scipy",
    "matplotlib",
    "seaborn",
    "textual",
    "rich",
    "colorama",
    "psutil",
    "pywin32; sys_platform == 'win32'",
    "tkinterdnd2",
    "requests",
    "charset-normalizer",
    "urllib3",
    "PyYAML",
    "XlsxWriter",
]

[project.scripts]
goldflipper = "goldflipper.run:main"

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "ruff>=0.1.0",
    "pyright>=1.1.0",
    "nuitka>=2.0",
]

# Configure hatchling to find packages in src/
[tool.hatch.build.targets.wheel]
packages = ["src/goldflipper"]

# Include package data - migrate from setup.py package_data and MANIFEST.in
[tool.hatch.build.targets.wheel.force-include]
# Example - adjust based on actual MANIFEST.in and setup.py package_data:
# "src/goldflipper/config/*.yaml" = "goldflipper/config/"
# "src/goldflipper/templates/*" = "goldflipper/templates/"

# Ruff configuration
[tool.ruff]
line-length = 150
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

# Pyright configuration
[tool.pyright]
include = ["src"]
exclude = ["**/__pycache__", "**/.venv"]
pythonVersion = "3.12"
typeCheckingMode = "basic"
reportMissingTypeStubs = false

# Pytest configuration
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
```

### 2.3 Extract Package Data Configuration

**Action required:** Manually review `setup.py` and `MANIFEST.in` to identify all package data.

Look for:
- `package_data` in `setup.py`
- `include` statements in `MANIFEST.in`
- Any data files referenced by code

Create mapping in `docs/migration/package-data-mapping.md`:

```markdown
# Package Data Migration

## From setup.py package_data:
```python
# Example from setup.py:
package_data = {
    'goldflipper': ['config/*.yaml', 'templates/*'],
}
```

## To pyproject.toml:
```toml
[tool.hatch.build.targets.wheel.force-include]
"src/goldflipper/config/*.yaml" = "goldflipper/config/"
"src/goldflipper/templates/*" = "goldflipper/templates/"
```

## Verification needed:
- [ ] Config files accessible
- [ ] Templates load correctly
- [ ] Batch files included if needed
```

---

## Phase 3: Initialize uv Environment

> **Status – 2025-12-08:** ✅ Completed. `uv.lock` generated, `uv sync` works, dependencies verified.

### 3.1 Remove Old Virtual Environment
```powershell
# If .venv exists from bootstrap.ps1
Remove-Item -Recurse -Force .venv
```

### 3.2 Initialize uv and Install Dependencies
```powershell
# Initialize uv (will read pyproject.toml)
uv init --no-readme

# Create lock file with all dependencies
uv lock

# Create venv and install everything
uv sync --all-extras
```

### 3.3 Verify Installation
```powershell
# Verify Python version
uv run python --version

# Verify goldflipper CLI is available
uv run goldflipper --help

# Verify key dependencies
uv run python -c "import alpaca; import yfinance; import textual; import rich; print('Dependencies OK')"

# List all installed packages
uv pip list > docs/migration/uv-installed-packages.txt
```

### 3.4 Compare Dependencies
```powershell
# Compare with original requirements
# Manually review docs/migration/requirements-original.txt
# vs docs/migration/uv-installed-packages.txt
# Ensure all dependencies present
```

---

## Phase 4: Configure Development Tools

> **Status – 2025-12-08:** ⚠️ Partial. Tools configured and working; historical lint/type backlog documented (3,841 ruff issues, 431 pyright errors). Tests pass.  
> **Update – 2026-02-19:** Pyright error backlog addressed for the active code paths: `uv run pyright` now reports 0 errors. `reportMissingModuleSource` was set to `none` in `pyrightconfig.json` to remove third-party source-resolution noise.  
> **Update – 2026-02-19 (follow-up):** `reportOptionalMemberAccess` warnings reduced to 0; current Pyright baseline is 228 warnings (mostly unused imports/variables).

### 4.1 Add Development Tools
Development dependencies are already in `pyproject.toml`, but verify:

```powershell
# Should already be installed from uv sync --all-extras
uv run ruff --version
uv run pyright --version
uv run pytest --version
```

### 4.2 Run Initial Code Quality Checks

```powershell
# Format code (will make changes)
uv run ruff format src/ tests/

# Check linting (will show issues)
uv run ruff check src/ tests/

# Type check (will show issues)
uv run pyright src/

# Run tests
uv run pytest
```

**Expected outcome:** Many linting and type errors will appear since the codebase had no prior linting/type checking. This is normal.

### 4.3 Create Baseline Quality Configuration

If too many errors, adjust configuration:

```toml
# Add to pyproject.toml [tool.ruff.lint]
ignore = [
    "E501",  # Line too long (if needed temporarily)
    # Add others as needed for baseline
]

# Add to pyproject.toml [tool.pyright]
reportGeneralTypeIssues = false  # If needed temporarily
```

**Goal:** Get to a passing baseline, then gradually improve.

### 4.4 Outstanding Ruff Follow-Ups

The initial full `ruff check` still reports legacy cleanliness issues that we deferred while focusing on the NumPy 2 migration. Capture them here so we can tackle them in a later pass:

1. `goldflipper/utils/json_fixer.py`
   - Remove the unused `was_corrupted` variable inside `_repair_file`.
   - Wrap or refactor the long logging calls (>88 chars) so they stay within our width limit without losing detail.
   - Strip trailing whitespace from multiple blank lines and add the missing newline at EOF.
2. `goldflipper/utils/logging_setup.py`
   - Reorder imports (and drop the unused `sys` import) per Ruff’s `I001`/`F401` findings.
   - Clean up the repeated whitespace-only blank lines throughout the file.
   - Shorten the compression/rotation helper lines that currently exceed 88 characters.

Keep this list updated as we chip away at the lint backlog so Phase 4 stays actionable.

### 4.5 WebSockets Deprecation Warning (tracking)

Pytest currently emits `DeprecationWarning: websockets.legacy is deprecated` because `websockets==15.x` now warns whenever the legacy namespace is imported. None of our modules reference `websockets` directly, so the warning most likely comes from a dependency (candidates: `alpaca-py` market data streaming, or `textual`, which still ships its own websockets shim). Action plan:

- ✅ Stay on the latest `websockets` release to keep security fixes.
- ✅ Keep `alpaca-py` pinned to the current series (0.43.x at the moment); they are actively migrating their streaming layer.
- ⏳ Monitor `textual` releases (current lock: 6.7.0) for notes about dropping `websockets.legacy`.
- 📌 Once upstream removes the legacy import, rerun the suite to confirm the warning disappears. No local code changes required unless we later adopt `websockets` directly.

This section is purely informational—no immediate work needed beyond periodically revisiting the dependency changelogs.

---

## Phase 5: Update Bootstrap and Launch Scripts

> **Status – 2025-12-08:** ✅ Completed. `bootstrap.ps1` updated, `scripts/dev.bat` created, batch launchers updated.

### 5.1 Update bootstrap.ps1

Replace dependency installation section:

**OLD (in bootstrap.ps1):**
```powershell
# Install dependencies
python -m pip install --upgrade pip
pip install -e .
```

**NEW:**
```powershell
# Install uv if not present
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..." -ForegroundColor Cyan
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
}

# Install dependencies with uv
Write-Host "Installing dependencies..." -ForegroundColor Cyan
uv sync

Write-Host "Setup complete! Run 'uv run goldflipper' to start." -ForegroundColor Green
```

### 5.2 Update launch_goldflipper.bat

**OLD:**
```batch
@echo off
python -m goldflipper.run
```

**NEW (TUI launcher):**
```batch
@echo off
uv run python -m goldflipper.launcher
```

### 5.3 Update run_console.bat

**OLD:**
```batch
@echo off
call .venv\Scripts\activate.bat
python -m goldflipper.run
```

**NEW:**
```batch
@echo off
uv run goldflipper
```

### 5.4 Create New Developer Scripts

Create `scripts/dev.bat`:
```batch
@echo off
REM Quick developer commands

if "%1"=="run" goto run
if "%1"=="test" goto test
if "%1"=="lint" goto lint
if "%1"=="format" goto format
if "%1"=="check" goto check
goto usage

:run
uv run goldflipper %2 %3 %4 %5
goto end

:test
uv run pytest %2 %3 %4 %5
goto end

:lint
uv run ruff check src/ tests/
goto end

:format
uv run ruff format src/ tests/
goto end

:check
echo Running all checks...
uv run ruff format --check src/ tests/
uv run ruff check src/ tests/
uv run pyright src/
uv run pytest
goto end

:usage
echo Usage: dev.bat [command]
echo Commands:
echo   run     - Run goldflipper
echo   test    - Run tests
echo   lint    - Lint code
echo   format  - Format code
echo   check   - Run all checks (format, lint, type, test)
goto end

:end
```

---

## Phase 6: Configure Nuitka for Windows

> **Status – 2025-11-29:** Completed. Launcher-based Nuitka build tested; ready to proceed with Phase 9 validation work.

### 6.1 Identify Entry Point and Data Files

Document in `docs/migration/nuitka-requirements.md`:

```markdown
# Nuitka Build Requirements

## Entry Point
- Main module: `src/goldflipper/run.py`
- Entry function: `main()`

## Data Files to Include
- [ ] Config YAML files (if any)
- [ ] Templates (if any)
- [ ] Other package data from MANIFEST.in

## Windows-Specific Dependencies
- pywin32 (for service wrapper)
- tkinterdnd2 (for GUI components)

## Hidden Imports
- Identify any dynamically imported modules
- Check for plugins or extensions
```

### 6.2 Create Nuitka Build Script

Create `scripts/build_nuitka.py`:

```python
"""
Nuitka build script for goldflipper Windows executable.
Run with: uv run python scripts/build_nuitka.py
"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ENTRY_POINT = PROJECT_ROOT / "src" / "goldflipper" / "run.py"
OUTPUT_DIR = PROJECT_ROOT / "dist"
APP_NAME = "goldflipper"

def build():
    """Build standalone Windows executable with Nuitka."""
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    cmd = [
        sys.executable, "-m", "nuitka",
        
        # Basic options
        "--standalone",
        "--onefile",
        f"--output-dir={OUTPUT_DIR}",
        f"--output-filename={APP_NAME}",
        
        # Windows-specific
        "--windows-console-mode=attach",  # Or "disable" for no console
        "--enable-console",  # Keep console for TUI app
        
        # Performance
        "--lto=yes",
        "--enable-plugin=anti-bloat",
        
        # Include package data
        # Adjust these based on actual package_data from setup.py
        # "--include-data-dir=src/goldflipper/config=goldflipper/config",
        # "--include-data-dir=src/goldflipper/templates=goldflipper/templates",
        
        # Windows dependencies
        "--enable-plugin=pywin32",  # Handle pywin32 properly
        
        # Follow imports
        "--follow-imports",
        "--prefer-source-code",
        
        # Entry point
        str(ENTRY_POINT),
    ]
    
    print(f"Building {APP_NAME} with Nuitka...")
    print(f"Entry point: {ENTRY_POINT}")
    print(f"Output: {OUTPUT_DIR / APP_NAME}.exe")
    print()
    print("This may take several minutes...")
    print()
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print(f"\n{'='*60}")
        print(f"✓ Build successful!")
        print(f"{'='*60}")
        print(f"Executable: {OUTPUT_DIR / APP_NAME}.exe")
        print(f"\nTest with: .\\dist\\{APP_NAME}.exe --help")
    else:
        print(f"\n{'='*60}")
        print(f"✗ Build failed with code {result.returncode}")
        print(f"{'='*60}")
        sys.exit(1)

if __name__ == "__main__":
    build()
```

### 6.3 Create Nuitka Configuration File

Create `nuitka-project.py` in project root:

```python
"""
Nuitka project configuration for goldflipper.
See: https://nuitka.net/doc/nuitka-project-options.html
"""

# Main entry point
NUITKA_MAIN = "src/goldflipper/run.py"

# Output configuration
NUITKA_OUTPUT_DIR = "dist"
NUITKA_OUTPUT_FILENAME = "goldflipper"

# Build mode
NUITKA_STANDALONE = True
NUITKA_ONEFILE = True

# Windows console
NUITKA_WINDOWS_CONSOLE_MODE = "attach"  # Keep console for TUI

# Performance
NUITKA_LTO = "yes"
NUITKA_PLUGIN_ENABLE = ["anti-bloat", "pywin32"]

# Follow imports
NUITKA_FOLLOW_IMPORTS = True

# Data files - adjust based on package_data
# NUITKA_DATA_FILES = [
#     ("src/goldflipper/config", "goldflipper/config"),
#     ("src/goldflipper/templates", "goldflipper/templates"),
# ]
```

### 6.4 Test Nuitka Build

```powershell
# First build attempt
uv run python scripts/build_nuitka.py

# If successful, test the executable
.\dist\goldflipper.exe --help

# Test full functionality
.\dist\goldflipper.exe
```

**Troubleshooting:** If build fails, check:
1. MSVC installed (Visual Studio Build Tools)
2. All data files correctly specified
3. Hidden imports identified (use `--show-modules` flag for debugging)

---

## Phase 7: Update Documentation

> **Status – 2025-12-08:** Completed. `docs/DEVELOPMENT.md` created with full uv workflow documentation.

### 7.1 Update README.md

Add new section after installation instructions:

```markdown
## Development Setup (Modern)

### Prerequisites
- Python 3.12-3.13
- [uv](https://docs.astral.sh/uv/) package manager

### Quick Start

1. **Install uv** (first time only):
   ```powershell
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Clone and setup**:
   ```powershell
   git clone <repo-url>
   cd goldflipper
   uv sync
   ```

3. **Run goldflipper**:
   ```powershell
   uv run goldflipper
   ```

### Development Commands

```powershell
# Run application
uv run goldflipper

# Run tests
uv run pytest

# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type check
uv run pyright

# Run all quality checks
scripts\dev.bat check

# Build Windows executable
uv run python scripts/build_nuitka.py
```

### Legacy Setup (setup.py)

The legacy `setup.py` installation still works:
```powershell
pip install -e .
python -m goldflipper.run
```

However, we recommend using uv for development as it's significantly faster.

### Adding Dependencies

```powershell
# Add production dependency
uv add package-name

# Add development dependency  
uv add --dev package-name

# Update all dependencies
uv lock --upgrade
uv sync
```

### Building Executable for Distribution

```powershell
# Build standalone .exe
uv run python scripts/build_nuitka.py

# Output will be in dist/goldflipper.exe
# Can be distributed without Python installation
```
```

### 7.2 Create DEVELOPMENT.md

Create `docs/DEVELOPMENT.md`:

```markdown
# Development Guide

## Technology Stack

### Core
- **Python 3.12-3.13**
- **Package Manager**: uv
- **Build Backend**: hatchling (for Python packaging)
- **Distribution**: Nuitka (for standalone executables)

### Development Tools
- **Linting/Formatting**: ruff
- **Type Checking**: pyright
- **Testing**: pytest

### Runtime Dependencies
- Trading: alpaca-py, yfinance, ta, mplfinance
- Data: pandas, numpy, scipy
- Visualization: matplotlib, seaborn
- TUI: textual, rich, colorama
- System: psutil, pywin32, tkinterdnd2

## Project Structure

```
goldflipper/
├── src/goldflipper/          # Main package
│   ├── run.py                # Entry point
│   ├── service/              # Windows service
│   └── ...
├── tests/                    # Test suite
├── scripts/                  # Build and utility scripts
│   ├── build_nuitka.py      # Nuitka build script
│   └── dev.bat              # Developer commands
├── docs/                     # Documentation
├── pyproject.toml           # Modern Python config
├── setup.py                 # Legacy setup (maintained for compatibility)
├── requirements.txt         # Legacy requirements (maintained for compatibility)
└── README.md

```

## Development Workflow

### Initial Setup

```powershell
# 1. Install uv
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Clone repository
git clone <repo>
cd goldflipper

# 3. Install dependencies
uv sync

# 4. Verify installation
uv run goldflipper --help
```

### Daily Development

```powershell
# Run application
uv run goldflipper

# Run with arguments
uv run goldflipper --config myconfig.yaml

# Run tests
uv run pytest

# Run specific test
uv run pytest tests/test_market_data.py

# Watch mode (if pytest-watch installed)
uv run pytest-watch
```

### Code Quality

Before committing, ensure code quality:

```powershell
# Format code (makes changes)
uv run ruff format .

# Check formatting (no changes)
uv run ruff format --check .

# Lint (find issues)
uv run ruff check .

# Lint and auto-fix
uv run ruff check --fix .

# Type check
uv run pyright

# Run all checks
scripts\dev.bat check
```

### Adding Dependencies

```powershell
# Production dependency
uv add requests

# Development dependency
uv add --dev pytest-cov

# Platform-specific (Windows only)
uv add "pywin32; sys_platform == 'win32'"

# Update all dependencies
uv lock --upgrade
uv sync
```

## Building Executables

### Development Build (Quick)

```powershell
# Build with Nuitka
uv run python scripts/build_nuitka.py

# Test executable
.\dist\goldflipper.exe --help
```

### Production Build (Optimized)

For final release, consider additional Nuitka optimizations:

```powershell
# Edit scripts/build_nuitka.py and add:
# --windows-icon-from-ico=assets/icon.ico
# --company-name="Your Company"
# --product-name="GoldFlipper"
# --file-version=1.0.0
# --product-version=1.0.0

uv run python scripts/build_nuitka.py
```

## Testing

### Running Tests

```powershell
# All tests
uv run pytest

# Specific file
uv run pytest tests/test_market_data.py

# Specific test
uv run pytest tests/test_market_data.py::test_function_name

# With coverage
uv run pytest --cov=goldflipper --cov-report=html

# Verbose
uv run pytest -v

# Stop on first failure
uv run pytest -x
```

### Writing Tests

Place tests in `tests/` directory:

```python
# tests/test_feature.py
import pytest
from goldflipper.module import function

def test_function():
    result = function()
    assert result == expected
```

## Troubleshooting

### uv sync fails

```powershell
# Clear cache
uv cache clean
uv sync

# Remove lock and regenerate
del uv.lock
uv lock
uv sync
```

### Import errors

```powershell
# Reinstall in development mode
uv sync --reinstall
```

### Nuitka build fails

1. Ensure Visual Studio Build Tools installed
2. Check data files are correctly specified
3. Use `--show-modules` for debugging:
   ```powershell
   uv run nuitka --show-modules src/goldflipper/run.py
   ```

### pywin32 issues

```powershell
# Reinstall pywin32
uv pip install --force-reinstall pywin32
```

## Architecture Notes

### Windows Service
- Located in `src/goldflipper/service/`
- Uses pywin32 for Windows service integration
- Install/uninstall via `install_service.bat`

### TUI Interface
- Built with Textual framework
- Rich library for terminal formatting
- See `goldflipper_tui.py` and `trade_logger_ui.py`

### Trading Integration
- Alpaca API for trading
- yfinance for market data
- Technical analysis via ta library

## Contributing

1. Create feature branch
2. Make changes
3. Run quality checks: `scripts\dev.bat check`
4. Ensure tests pass
5. Submit PR

## Resources

- [uv Documentation](https://docs.astral.sh/uv/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Pyright Documentation](https://microsoft.github.io/pyright/)
- [Nuitka Documentation](https://nuitka.net/doc/user-manual.html)
- [Textual Documentation](https://textual.textualize.io/)

---

## Phase 8: Maintain Backward Compatibility

> **Status – 2025-12-08:** Completed. `setup.py` and `requirements.txt` retained for backward compatibility.

### 8.1 Keep setup.py (Optional but Recommended)

**Decision point:** Keep or remove setup.py?

**Recommendation: KEEP** setup.py for now because:
- Allows gradual migration
- Supports users who aren't ready for uv
- CI/CD might depend on it
- No harm in having both

Update setup.py to reference pyproject.toml:

```python
# setup.py (simplified version)
from setuptools import setup

# Setuptools will read from pyproject.toml automatically
# This file exists only for backward compatibility
setup()
```

### 8.2 Keep requirements.txt (Optional but Recommended)

**Recommendation: KEEP** for compatibility:

```powershell
# Generate requirements.txt from pyproject.toml
uv pip compile pyproject.toml -o requirements.txt

# Or export current environment
uv pip freeze > requirements.txt
```

Add comment to top of requirements.txt:

```
# This file is auto-generated for backward compatibility.
# For development, use: uv sync
# Generated from: pyproject.toml
```

### 8.3 Document Dual Installation Methods

In README.md, support both:

```markdown
## Installation

### Method 1: Modern (uv) - Recommended
```powershell
uv sync
uv run goldflipper
```

### Method 2: Legacy (pip)
```powershell
pip install -e .
python -m goldflipper.run
```

Both methods work, but uv is faster and recommended for development.

---

## Phase 9: Testing & Verification

> **Status – 2025-12-08:** ⚠️ Partial. `docs/migration/testing-checklist.md` created; core items verified (uv sync, CLI, pytest). Runtime/TUI items pending manual validation.

### 9.1 Functional Testing Checklist

Create `docs/migration/testing-checklist.md`:

```markdown
# Migration Testing Checklist

## Installation Testing

### Fresh Installation (uv)
- [ ] `uv sync` completes without errors
- [ ] All dependencies installed
- [ ] `uv run goldflipper --help` shows help
- [ ] `uv run goldflipper` launches successfully

### Legacy Installation (pip)
- [ ] `pip install -e .` still works
- [ ] `python -m goldflipper.run` launches successfully

## Core Functionality
- [ ] TUI launches and displays correctly
- [ ] Market data retrieval works
- [ ] Trading operations functional
- [ ] Service wrapper installs (Windows)
- [ ] Batch scripts work (`launch_goldflipper.bat`)
- [ ] Configuration files load correctly
- [ ] All package data accessible

## Development Tools
- [ ] `uv run pytest` - all tests pass
- [ ] `uv run ruff check .` - linting works
- [ ] `uv run ruff format .` - formatting works
- [ ] `uv run pyright` - type checking works

## Build & Distribution
- [ ] `uv run python scripts/build_nuitka.py` succeeds
- [ ] `dist/goldflipper.exe` created
- [ ] Executable runs standalone (tested on clean Windows machine)
- [ ] All features work in compiled version
- [ ] Executable size reasonable: ____ MB
- [ ] Startup time acceptable: ____ seconds

## Platform-Specific (Windows)
- [ ] pywin32 functionality works
- [ ] Windows service installs
- [ ] tkinterdnd2 functionality works
- [ ] Console output displays correctly

## Data Integrity
- [ ] YAML configs load
- [ ] Templates accessible
- [ ] Package data in correct locations
- [ ] No missing files errors

## Performance
- [ ] Dependency installation: uv ___ sec vs pip ___ sec
- [ ] Application startup time unchanged
- [ ] Memory usage unchanged
- [ ] No performance regressions

## Edge Cases
- [ ] Fresh clone on new machine works
- [ ] Works without admin privileges
- [ ] Works with firewall/antivirus enabled
- [ ] Multiple instances can run
```

### 9.2 Automated Testing Script

Create `scripts/test_migration.ps1`:

```powershell
# Migration verification script

Write-Host "=== GoldFlipper Migration Testing ===" -ForegroundColor Cyan
Write-Host ""

$ErrorCount = 0

# Test 1: uv installed
Write-Host "Test 1: Checking uv installation..." -ForegroundColor Yellow
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "✓ uv installed" -ForegroundColor Green
} else {
    Write-Host "✗ uv not found" -ForegroundColor Red
    $ErrorCount++
}

# Test 2: Dependencies sync
Write-Host "Test 2: Syncing dependencies..." -ForegroundColor Yellow
uv sync
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Dependencies synced" -ForegroundColor Green
} else {
    Write-Host "✗ Sync failed" -ForegroundColor Red
    $ErrorCount++
}

# Test 3: CLI available
Write-Host "Test 3: Testing CLI..." -ForegroundColor Yellow
uv run goldflipper --help | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ CLI works" -ForegroundColor Green
} else {
    Write-Host "✗ CLI failed" -ForegroundColor Red
    $ErrorCount++
}

# Test 4: Tests pass
Write-Host "Test 4: Running tests..." -ForegroundColor Yellow
uv run pytest --tb=short
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Tests pass" -ForegroundColor Green
} else {
    Write-Host "✗ Tests failed" -ForegroundColor Red
    $ErrorCount++
}

# Test 5: Linting
Write-Host "Test 5: Checking code quality..." -ForegroundColor Yellow
uv run ruff check src/ --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Linting passed" -ForegroundColor Green
} else {
    Write-Host "⚠ Linting issues found (non-blocking)" -ForegroundColor Yellow
}

# Test 6: Formatting
Write-Host "Test 6: Checking code formatting..." -ForegroundColor Yellow
uv run ruff format --check src/ --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Formatting correct" -ForegroundColor Green
} else {
    Write-Host "⚠ Formatting needed (non-blocking)" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "=== Test Summary ===" -ForegroundColor Cyan
if ($ErrorCount -eq 0) {
    Write-Host "✓ All critical tests passed!" -ForegroundColor Green
    Write-Host "Migration successful." -ForegroundColor Green
} else {
    Write-Host "✗ $ErrorCount critical test(s) failed" -ForegroundColor Red
    Write-Host "Please review errors above." -ForegroundColor Red
    exit 1
}
```

Run with:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\test_migration.ps1
```

### 9.3 Manual Test Scenarios

Document and execute these manual tests:

1. **Fresh Environment Test**
   - Clone repo on different machine
   - Run `uv sync`
   - Launch application
   - Verify all features

2. **Build Test**
   - Build executable
   - Copy to machine without Python
   - Run and verify all features

3. **Service Test**
   - Install Windows service
   - Start/stop service
   - Verify logging and operation

4. **Data File Test**
   - Verify all config YAMLs load
   - Check templates accessible
   - Confirm package data present

---

## Phase 10: Update CI/CD (If Applicable)

> **Status:** ⏸️ N/A. No CI/CD currently configured for this project.

### 10.1 GitHub Actions Example

If you have CI/CD, create `.github/workflows/test.yml`:

```yaml
name: Test

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: windows-latest
    strategy:
      matrix:
        python-version: ['3.12', '3.13']
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Install uv
      run: |
        powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
        echo "$HOME/.cargo/bin" >> $GITHUB_PATH
    
    - name: Set up Python ${{ matrix.python-version }}
      run: uv python install ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: uv sync
    
    - name: Lint with ruff
      run: uv run ruff check src/ tests/
    
    - name: Check formatting
      run: uv run ruff format --check src/ tests/
    
    - name: Type check with pyright
      run: uv run pyright src/
    
    - name: Test with pytest
      run: uv run pytest --cov=goldflipper --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

---

## Phase 11: Clean Up and Finalize

> **Status – 2025-12-08:** 📋 TODO. Backup files still exist; final cleanup pending full verification.

### 11.1 Update .gitignore

Add uv-specific entries:

```bash
# Add to .gitignore

# uv
.venv/
uv.lock  # Or commit it for reproducibility

# Nuitka build artifacts
*.build/
*.dist/
*.onefile-build/

# Ruff cache
.ruff_cache/

# Pyright cache
.pyright/

# pytest cache
.pytest_cache/
```

**Decision:** Commit `uv.lock`?
- **Yes** for reproducible builds (recommended)
- **No** if you want always-latest versions

### 11.2 Remove Backup Files (After Verification)

```powershell
# Only after confirming everything works!
Remove-Item setup.py.backup
Remove-Item requirements.txt.backup
Remove-Item MANIFEST.in.backup  # if exists
```

### 11.3 Create Migration Summary

Create `docs/migration/COMPLETED.md`:

```markdown
# Migration Completion Summary

**Date:** YYYY-MM-DD
**Status:** Complete ✓

## What Changed

### Package Management
- **From:** pip + virtualenv + requirements.txt
- **To:** uv + pyproject.toml
- **Result:** 10-50x faster dependency operations

### Build System
- **From:** setuptools + setup.py
- **To:** hatchling + pyproject.toml (setup.py kept for compatibility)
- **Result:** Modern PEP 621 compliance

### Code Quality
- **From:** None configured
- **To:** ruff (linting + formatting) + pyright (type checking)
- **Result:** Consistent code quality, faster checks

### Distribution
- **From:** Source distribution only
- **To:** Nuitka compiled executables
- **Result:** Standalone Windows .exe

## Metrics

### Speed Improvements
- Dependency installation: uv ___ sec vs pip ___ sec
- Cold start: ___ sec vs ___ sec
- Linting: ___ sec (new)

### Build Artifacts
- Nuitka executable: ___ MB
- Startup time: ___ sec

## Files Added
- `pyproject.toml` - Modern Python configuration
- `nuitka-project.py` - Nuitka build configuration
- `scripts/build_nuitka.py` - Build script
- `scripts/dev.bat` - Developer commands
- `docs/DEVELOPMENT.md` - Developer guide

## Files Modified
- `bootstrap.ps1` - Updated to use uv
- `launch_goldflipper.bat` - Updated to use uv
- `run_console.bat` - Updated to use uv
- `README.md` - Added uv instructions
- `.gitignore` - Added uv artifacts

## Files Kept for Compatibility
- `setup.py` - Still works for legacy workflows
- `requirements.txt` - Auto-generated from pyproject.toml

## Testing Results
- All existing tests pass: ✓
- New quality checks added: ✓
- Nuitka executable tested: ✓
- Fresh installation tested: ✓

## Issues Encountered
(Document any issues and their resolutions)

## Recommendations
1. Gradually fix linting warnings
2. Add type hints incrementally
3. Expand test coverage
4. Consider adding pre-commit hooks

## Rollback Plan
If critical issues found:
1. Restore `.backup` files
2. Use legacy pip installation
3. Document issue for resolution
```

---

## Appendix A: Command Reference

### Complete Command Mapping

| Task | Old (pip/setup.py) | New (uv) |
|------|-------------------|----------|
| Install deps | `pip install -e .` | `uv sync` |
| Add dependency | Edit setup.py + `pip install -e .` | `uv add package` |
| Remove dependency | Edit setup.py + `pip install -e .` | `uv remove package` |
| Update deps | `pip install --upgrade -e .` | `uv lock --upgrade && uv sync` |
| Run app | `python -m goldflipper.run` | `uv run goldflipper` |
| Run tests | `python -m pytest` | `uv run pytest` |
| List packages | `pip list` | `uv pip list` |
| Show package | `pip show package` | `uv pip show package` |
| Freeze deps | `pip freeze > requirements.txt` | `uv pip freeze > requirements.txt` |

### New Commands (Not Available Before)

| Task | Command |
|------|---------|
| Format code | `uv run ruff format .` |
| Lint code | `uv run ruff check .` |
| Type check | `uv run pyright` |
| Build executable | `uv run python scripts/build_nuitka.py` |
| Run all checks | `scripts\dev.bat check` |

---

## Appendix B: Troubleshooting Guide

### Common Issues and Solutions

#### Issue: uv not found after installation
```powershell
# Add to PATH manually
$env:Path += ";$env:USERPROFILE\.cargo\bin"

# Or restart terminal
```

#### Issue: pywin32 import fails
```powershell
# Reinstall pywin32 with post-install
uv pip install --force-reinstall pywin32
uv run python -m pywin32_postinstall -install
```

#### Issue: Package data not found in built executable
```python
# Update scripts/build_nuitka.py
# Add explicit data file includes:
"--include-data-dir=src/goldflipper/config=goldflipper/config",
```

#### Issue: Nuitka build fails with "MSVC not found"
**Solution:**
1. Download Visual Studio Build Tools
2. Install "Desktop development with C++"
3. Restart terminal

#### Issue: Tests fail after migration
```powershell
# Reinstall test dependencies
uv sync --reinstall

# Check for missing test files
git status

# Verify PYTHONPATH
uv run python -c "import sys; print('\n'.join(sys.path))"
```

#### Issue: Executable crashes on startup
```powershell
# Build in debug mode
# Add to build script:
"--debug",
"--show-modules",

# Run and check output
.\dist\goldflipper.exe
```

---

## Appendix C: Rollback Procedure

If critical issues arise:

```powershell
# 1. Restore backup files
Copy-Item setup.py.backup setup.py -Force
Copy-Item requirements.txt.backup requirements.txt -Force

# 2. Remove uv artifacts
Remove-Item -Recurse -Force .venv
Remove-Item uv.lock

# 3. Reinstall with pip
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .

# 4. Test legacy installation
python -m goldflipper.run --help

# 5. Document rollback reason
Add-Content -Path docs/migration/rollback-log.md -Value "$(Get-Date): Rollback due to <reason>"
```

---

## Success Criteria

Migration is complete when ALL of the following are true:

1. ✅ `uv sync` installs all dependencies without errors
2. ✅ `uv run goldflipper` launches the application
3. ✅ All existing tests pass with `uv run pytest`
4. ✅ Linting and formatting tools configured and running
5. ✅ `scripts/build_nuitka.py` creates working executable
6. ✅ Executable runs on Windows machine without Python
7. ✅ All features work in compiled version
8. ✅ Documentation updated (README, DEVELOPMENT.md)
9. ✅ Legacy installation (`pip install -e .`) still works
10. ✅ No regression in functionality or performance

---

## Timeline Estimate

| Phase | Estimated Time |
|-------|---------------|
| 1. Assessment | 1-2 hours |
| 2. Install uv & create pyproject.toml | 2-3 hours |
| 3. Initialize environment | 1 hour |
| 4. Configure dev tools | 1-2 hours |
| 5. Update scripts | 1 hour |
| 6. Configure Nuitka | 3-4 hours |
| 7. Update documentation | 2-3 hours |
| 8. Maintain compatibility | 1 hour |
| 9. Testing | 3-4 hours |
| 10. CI/CD (if applicable) | 2-3 hours |
| 11. Cleanup | 1 hour |

**Total: 18-26 hours** for complete migration with thorough testing

**Minimum viable migration: 8-12 hours** (skip comprehensive documentation and CI/CD)
