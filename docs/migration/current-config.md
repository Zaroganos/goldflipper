# Current Configuration Analysis

## Package Metadata (from `setup.py`)
- **Package name:** `goldflipper`
- **Version:** `0.2.2`
- **Python requirement:** `>=3.10`
- **Entry point:** `goldflipper = goldflipper.run:main`
- **License:** Proprietary (see `LICENSE`)
- **Long description source:** `README.md`

## Package Data

### `setup.py` `package_data`
- `goldflipper/tools/play-template.json`
- `goldflipper/config/*.py`
- `goldflipper/config/settings_template.yaml`

### `MANIFEST.in`
- `README.md`, `LICENSE`, `requirements.txt`
- Recursive CSV data under `goldflipper/reference`
- Config templates and modules under `goldflipper/config`
- `goldflipper/tools/play-template.json`
- Windows assets: `*.bat`, `*.ps1`, `*.ico`
- Global excludes for `__pycache__`, `*.py[co]`, `.DS_Store`, etc.
- Pruned directories: `tests`, `dev-notes`, `build`, `dist`, `*.egg-info`

## Dependencies

### Runtime (from `install_requires` / `requirements.txt`)
- alpaca-py>=0.42.0
- yfinance>=0.2.54
- pandas>=2.0.0
- numpy>=1.24.0
- matplotlib>=3.7.0
- seaborn>=0.12.0
- scipy>=1.10.0
- ta>=0.10.0
- textual>=1.0.0
- psutil>=5.9.0
- nest-asyncio>=1.5.0
- pywin32
- tkinterdnd2>=0.3.0
- requests>=2.25.0
- charset-normalizer>=3.2.0
- urllib3>=1.26.0
- PyYAML>=6.0.1
- colorama>=0.4.6
- rich>=13.0.0
- mplfinance>=0.12.10b0 (requirements pins >=0.12.0)
- XlsxWriter>=3.1.0

### Development/Test
- pytest>=7.0.0

## Entry Points and Scripts
- **Console script:** `goldflipper` (calls `goldflipper.run:main`)
- **Batch/PowerShell tooling:** `launch_goldflipper.bat`, `run_console.bat`, `install_service.bat`, `bootstrap.ps1`
- **Service integration:** `src/service/service_wrapper.py`

## Platform-Specific Notes
- Primary target platform: Windows desktop (per plan and Windows-specific assets)
- `pywin32` required for Windows service wrapper and system integrations
- `tkinterdnd2` provides Windows drag/drop support in setup dialogs
- Batch scripts assume `cmd.exe`; PowerShell bootstrap automates virtualenv + pip install

## Package Structure Snapshot
- Documented in `docs/migration/package-structure.txt` (generated via `tree /F src`)
