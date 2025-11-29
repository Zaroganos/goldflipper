# Development Guide

## Technology Stack

### Core
- **Python 3.11-3.13**
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

