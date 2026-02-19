# Nuitka Build Requirements

## Entry Point
- Main module: `goldflipper/launcher.py`
- Entry function: `main()`
- CLI script: `goldflipper = goldflipper.launcher:main` (from `pyproject.toml`)

## Build Mode
- **Standalone + Onefile** - Single portable executable
- **Full Bundle** - All tools included for internal module launching (2025-12-01)

## Data Files to Include
- `goldflipper/config/` - Settings templates and YAML configs
- `goldflipper/reference/*.csv` - API templates and reference data
- `goldflipper/tools/` - **All tool scripts** (full bundle for exe mode)
- `goldflipper/chart/` - Chart viewer module
- `goldflipper/trade_logging/` - Trade logger module
- `goldflipper/strategy/playbooks/` - Strategy playbooks (YAML configs)
- `goldflipper.ico` - Application icon

## Exe-Mode Features (2025-12-01)
The executable supports special command-line arguments:
- `--trading-mode` - Run trading system directly (spawned from TUI)
- `--service-install` - Install Windows service (requires admin)
- `--service-remove` - Remove Windows service (requires admin)

### Exe Detection
- `goldflipper/utils/exe_utils.py` - Utility module for exe detection
- `is_frozen()` function returns `True` when running from exe
- All tool launchers use internal module imports when frozen

### Desktop Shortcut
- When running from exe: Shortcut points to `goldflipper.exe`
- When running from source: Shortcut points to `launch_goldflipper.bat`

## Windows-Specific Dependencies
- `pywin32` for Windows service wrapper support
- `tkinterdnd2` for drag-and-drop UI workflows
- Any service-related modules under `src/goldflipper/service/`

## Plugin Requirements
- `matplotlib` triggers toolkit detection; enable `--enable-plugin=tk-inter`
- Ensure tkinter is available in the runtime environment before building
- Modern Nuitka automatically handles `pywin32`, so no plugin flag is required

## Hidden Imports / Special Handling
- Watch for dynamic imports in Textual/Rich components
- Verify trading adapters (e.g., Alpaca client) are detected
- Consider `--follow-imports` and `--prefer-source-code` flags
- Re-run with `--show-modules` if runtime ImportError appears

## Outstanding Checks
- [x] Confirm final list of config/templates that must be embedded (2025-12-01)
- [x] Full exe bundle implementation with internal tool launching (2025-12-01)
- [x] Exe-aware shortcut creation (2025-12-01)
- [x] Exe-aware service management (2025-12-01)
- [ ] Verify `install_service.bat` / other scripts ship with the build
- [ ] Validate the executable on a clean Windows machine
- [ ] Re-run Nuitka build on a higher-power PC (current attempt cancelled)

## Data Exclusion Patterns (2025-12-11)

**Problem:** The config directory was bundled entirely, including `settings.yaml` which is gitignored and user-specific.

**Solution:** Added `--noinclude-data-files` patterns in build scripts to exclude gitignored files:
```python
DATA_EXCLUDE_PATTERNS = [
    "**/settings.yaml",      # User-specific config (created on first run)
    "**/*.log",              # Log files
    "**/*.bak",              # Backup files
    "**/*.tmp",              # Temp files
    "**/__pycache__/**",     # Python cache
]
```

**Adding more exclusions:** To exclude additional files, add patterns to `DATA_EXCLUDE_PATTERNS` in both:
- `scripts/build_nuitka.py`
- `scripts/build_nuitka_dev.py`

## Build Status (2025-12-03)
- **Nuitka Version:** 2.8.9
- **Python Version:** 3.12.10
- **C Compiler:** MSVC 14.3 (VS 2022 Build Tools)
- **Console Mode:** `force` - Required for Textual TUI (creates a console window)
  - **Note:** Using `attach` mode fails when double-clicking the exe because there's
    no existing console to attach to, causing Textual's Windows driver to crash with
    `AttributeError: 'NoneType' object has no attribute 'fileno'`

## Build Commands

### Quick Reference
```batch
scripts\dev.bat build           # Fast dev build (~50% faster)
scripts\dev.bat build-prod      # Production build (optimized)
```

### Production Build (Optimized)
- **Script:** `scripts/build_nuitka.py`
- **Output:** `dist/goldflipper.exe`
- **Command:** `uv run python scripts/build_nuitka.py`
- **Features:**
  - LTO enabled (`--lto=yes`) - smaller, faster exe
  - Compression enabled - smaller download size
  - Ready for distribution

### Dev Build (Fast Compilation)
- **Script:** `scripts/build_nuitka_dev.py`
- **Output:** `dist/goldflipper_dev.exe`
- **Command:** `uv run python scripts/build_nuitka_dev.py`
- **Speed Optimizations:**
  - No LTO (`--lto=no`) - ~30-50% faster compilation
  - No compression (`--onefile-no-compression`) - ~20-30% faster
  - Parallel compilation (`--jobs=N`) - uses all CPU cores
- **Trade-offs:**
  - Larger exe size (no compression)
  - Slightly slower runtime (no LTO)
  - **Still a fully functional single-file exe**

## CRITICAL FIX (2025-12-03) - Dynamic Imports

**Problem:** TUI buttons worked in source mode but failed in exe mode. Only the
"Configuration" button worked because it was directly imported at module level.

**Root Cause:** The build was using `--include-data-dir` for Python modules:
- `tools/`, `chart/`, `trade_logging/` were copied as **data files** (raw .py)
- Python modules copied as data **cannot be imported** - they're not compiled
- `importlib.import_module()` failed silently because modules weren't in the exe

**Solution:** Use `--include-package` for Python modules that need compilation:
```bash
--include-package=goldflipper.tools
--include-package=goldflipper.chart
--include-package=goldflipper.trade_logging
--include-package=goldflipper.strategy
--include-package=goldflipper.utils
```

**Rule of Thumb:**
- `--include-package`: Python modules (.py) that need to be **compiled and imported**
- `--include-data-dir`: Non-Python files (YAML, JSON, CSV, templates) that are **read at runtime**

**Why this matters for dynamic imports:**
Nuitka traces static imports to determine what to compile. Dynamic imports via
`importlib.import_module()` are invisible to Nuitka's analysis. You MUST explicitly
tell Nuitka to include these packages with `--include-package`.

## Optional: Persistent Extraction Directory

By default, Nuitka onefile extracts to a temp directory that changes on each run.
This can cause issues with:
- Antivirus software flagging the temp directory
- Debugging (hard to find extracted files)
- Multiple instances trying to extract simultaneously

**Solution:** Use `--onefile-tempdir-spec` to set a persistent location:
```bash
# Extract to a .goldflipper_data folder next to the exe
--onefile-tempdir-spec={PROGRAM}/../.goldflipper_data

# Or use a user-specific location
--onefile-tempdir-spec={CACHE_DIR}/goldflipper_runtime
```

**Available placeholders:**
- `{PROGRAM}` - Full path to the exe
- `{PROGRAM_BASE}` - Exe filename without extension
- `{CACHE_DIR}` - User's cache directory (AppData\Local on Windows)
- `{TEMP}` - System temp directory (default)
- `{HOME}` - User's home directory

**Benefits of persistent extraction:**
1. Faster startup (no re-extraction if already exists)
2. Easier debugging (predictable location)
3. Fewer antivirus false positives
4. Can exclude from Windows Defender scanning

## Critical Fix (2025-12-02) - Nuitka Detection
**Problem:** `is_frozen()` only checked `sys.frozen` (PyInstaller) - Nuitka doesn't set this!

**Solution:** Updated `exe_utils.py` to detect Nuitka builds via:
1. `__nuitka_binary_dir` on main module (most reliable for onefile)
2. `__compiled__` attribute on main module
3. `__compiled__` in module globals
4. Fallback: Check if `sys.executable` is named `goldflipper.exe`

**Debug Output:** The exe now prints path debug info at startup when frozen, showing:
- `is_frozen`, `sys.executable`, `__file__`
- `nuitka_binary_dir`, `executable_dir`, `bundled_data_dir`
- `config_dir`, `settings_path`, `plays_dir`, `logs_dir`, `tools_dir`

## Files Modified for Exe Compatibility
- `goldflipper/utils/exe_utils.py` - **UPDATED 2025-12-02**: Full exe-aware path utilities
  - `get_settings_path()` - Returns persistent settings.yaml path (next to exe)
  - `get_settings_template_path()` - Returns bundled template path (in extraction)
  - `get_config_dir()` - Returns persistent config directory
  - `get_bundled_data_dir()` - Returns temp extraction directory for bundled data
  - `get_executable_dir()` - Returns directory containing the exe
  - `get_plays_dir()` - **NEW**: Returns persistent plays/ directory (next to exe)
  - `get_play_subdir(subdir)` - **NEW**: Returns persistent plays/{subdir}/ directory
  - `get_logs_dir()` - **NEW**: Returns persistent logs/ directory (next to exe)
- `goldflipper/launcher.py` - Uses exe_utils for settings path detection
- `goldflipper/config/config.py` - **UPDATED 2025-12-02**: Uses exe_utils for path resolution
- `goldflipper/first_run_setup.py` - **UPDATED 2025-12-02**: Full exe-aware path handling
- `goldflipper/goldflipper_tui.py` - Imports from exe_utils, internal module imports when frozen
- `goldflipper/core.py` - **UPDATED 2025-12-02**: Uses get_plays_dir() in monitor_plays_continuously()
- `goldflipper/strategy/orchestrator.py` - **UPDATED 2025-12-02**: Uses get_plays_dir() for pending plays
- `goldflipper/strategy/shared/play_manager.py` - **UPDATED 2025-12-02**: Uses get_plays_dir() for default plays_base_dir
- `scripts/build_nuitka.py` - Full bundle data mappings
- `nuitka-project.py` - Full bundle data files

## Path Resolution in Frozen Mode (CRITICAL)
In Nuitka onefile builds:
- `sys.executable` → Path to the .exe file
- `__file__` for modules → Temp extraction directory (NOT exe directory!)
- **Settings/config must persist NEXT TO the exe**, not in temp extraction
- **Plays/logs must persist NEXT TO the exe**, not in temp extraction
- **Bundled data (templates, reference)** are in temp extraction and read-only

**Path Resolution Functions:**
```python
from goldflipper.utils.exe_utils import (
    is_frozen,           # True if running from exe
    get_settings_path,   # Persistent settings.yaml (next to exe)
    get_config_dir,      # Persistent config directory
    get_settings_template_path,  # Bundled template in extraction
    get_plays_dir,       # Persistent plays/ directory (next to exe)
    get_play_subdir,     # Persistent plays/{subdir}/ directory
    get_logs_dir,        # Persistent logs/ directory (next to exe)
)
```
