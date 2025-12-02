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

## Build Status (2025-12-01)
- **Nuitka Version:** 2.8.9
- **Python Version:** 3.12.10
- **C Compiler:** MSVC 14.3 (VS 2022 Build Tools)
- **Build Script:** `scripts/build_nuitka.py` - Updated with full bundle resources
- **Config File:** `nuitka-project.py` - Updated with tools/chart/trade_logging
- **Command:** `uv run python scripts/build_nuitka.py`

## Files Modified for Exe Compatibility
- `goldflipper/utils/exe_utils.py` - NEW: Exe detection utilities
- `goldflipper/launcher.py` - Added --trading-mode, --service-* args
- `goldflipper/first_run_setup.py` - Exe-aware shortcut creation
- `goldflipper/goldflipper_tui.py` - Internal module imports when frozen
- `scripts/build_nuitka.py` - Full bundle data mappings
- `nuitka-project.py` - Full bundle data files


