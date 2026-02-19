# Development Guide

## Technology Stack

### Core
- **Python 3.12-3.14**
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
├── goldflipper/              # Main package
│   ├── run.py                # Entry point (orchestrated or legacy mode)
│   ├── run_multi.py          # Multi-strategy entry point
│   ├── core.py               # Trading core (Phase 2: thin wrappers)
│   ├── goldflipper_tui.py    # Main TUI interface
│   ├── strategy/             # Multi-strategy system
│   │   ├── base.py           # BaseStrategy ABC
│   │   ├── orchestrator.py   # StrategyOrchestrator
│   │   ├── registry.py       # Strategy discovery
│   │   ├── shared/           # Shared utilities
│   │   └── runners/          # Strategy implementations
│   ├── data/                 # Market data abstraction
│   │   └── market/manager.py # MarketDataManager
│   ├── config/               # Configuration
│   │   └── settings.yaml     # Main config file
│   ├── tools/                # Play creation tools
│   │   ├── play_creator_gui.py       # Tkinter GUI
│   │   ├── auto_play_creator.py      # Terminal-based
│   │   └── play_csv_ingestion_multitool.py # CSV import
│   ├── trade_logging/        # Trade logger and UI
│   ├── plays/                # Play files (new, open, closed, etc.)
│   ├── docs/                 # Package-level documentation
│   └── tests/                # Test suite
├── src/                      # Service wrapper
│   └── service/              # Windows service
├── scripts/                  # Build and utility scripts
│   ├── build_nuitka.py       # Nuitka build script
│   └── dev.bat               # Developer commands
├── docs/                     # Project-level documentation
├── pyproject.toml            # Modern Python config
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

# Markdown lint (uses .markdownlint-cli2.yaml)
npx -y markdownlint-cli2

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

### Known Third-Party Warning Filter

- `pyproject.toml` filters `DeprecationWarning` for `websockets.legacy is deprecated` from module `websockets.legacy`.
- Reason: current `alpaca-py` imports `websockets.legacy` during module import in tests.
- Remove this filter after `alpaca-py` migrates off `websockets.legacy`.

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

### Multi-Strategy System (2025-12-01)

Goldflipper supports multiple trading strategies running concurrently via the `StrategyOrchestrator`.

#### Core Components

```
goldflipper/
├── strategy/
│   ├── base.py              # BaseStrategy ABC, OrderAction, PositionSide enums
│   ├── orchestrator.py      # StrategyOrchestrator - coordinates all strategies
│   ├── registry.py          # @register_strategy decorator, auto-discovery
│   ├── shared/              # Shared utilities (Phase 2 extraction)
│   │   ├── play_manager.py  # Play file operations (560 lines)
│   │   ├── evaluation.py    # TP/SL evaluation (538 lines)
│   │   └── order_executor.py # Order placement (483 lines)
│   ├── runners/             # Strategy implementations
│   │   ├── option_swings.py      # Manual swings (BTO/STC)
│   │   ├── option_swings_auto.py # Automated swings (stub)
│   │   ├── momentum.py           # Gap/momentum trades
│   │   ├── sell_puts.py          # Cash-secured puts (STO/BTC)
│   │   └── spreads.py            # Multi-leg spreads
│   └── playbooks/           # Strategy configuration files
│       ├── schema.py        # Playbook dataclasses
│       ├── loader.py        # PlaybookLoader
│       ├── sell_puts/       # Sell puts playbooks
│       └── momentum/        # Momentum playbooks
```

#### Execution Flow

```
run.py / run_multi.py
    │
    ▼
StrategyOrchestrator.run_cycle()
    │
    ├── Sequential Mode: Strategies run one-by-one
    │
    └── Parallel Mode: ThreadPoolExecutor (configurable workers)
            │
            ▼
        For each enabled strategy:
            1. strategy.on_cycle_start()
            2. strategy.evaluate_new_plays(plays)  → Entry signals
            3. strategy.evaluate_open_plays(plays) → Exit signals
            4. Execute trades via strategy.open_position() / close_position()
            5. strategy.on_cycle_end()
```

#### Configuration

```yaml
# settings.yaml
strategy_orchestration:
  enabled: true              # Master switch
  mode: "sequential"         # or "parallel"
  max_parallel_workers: 3    # For parallel mode
  fallback_to_legacy: true   # Use core.py if orchestrator fails
  dry_run: false             # Evaluate but don't execute orders

options_swings:
  enabled: true
  # ... strategy settings

momentum:
  enabled: false
  # ... strategy settings

sell_puts:
  enabled: false
  # ... strategy settings
```

#### Adding New Strategies

See `goldflipper/docs/STRATEGY_DEVELOPMENT_GUIDE.md` for complete instructions.

Quick summary:
1. Create `strategy/runners/my_strategy.py`
2. Implement `BaseStrategy` interface
3. Add `@register_strategy('my_strategy')` decorator
4. Add module to `registry.py` `runner_modules` list
5. Add config section to `settings.yaml`

#### Trade Direction Model

Strategies support both long and short positions:

| Strategy | Entry Action | Exit Action | Position |
|----------|--------------|-------------|----------|
| option_swings | BUY_TO_OPEN | SELL_TO_CLOSE | Long |
| momentum | BUY_TO_OPEN | SELL_TO_CLOSE | Long |
| sell_puts | SELL_TO_OPEN | BUY_TO_CLOSE | Short |
| spreads | Multi-leg | Multi-leg | Varies |

#### Testing Strategies

```powershell
# Unit tests
uv run python goldflipper/tests/test_orchestrator_unit.py
uv run python goldflipper/tests/test_strategy_evaluation.py
uv run python goldflipper/tests/test_dry_run_mode.py

# Dry-run mode (no actual orders)
# Set strategy_orchestration.dry_run: true in settings.yaml
uv run goldflipper
```

#### Documentation

- `goldflipper/docs/MULTI_STRATEGY_IMPLEMENTATION.md` - Full implementation plan
- `goldflipper/docs/STRATEGY_DEVELOPMENT_GUIDE.md` - How to add strategies
- `goldflipper/docs/DEPRECATED_CODE_CANDIDATES.md` - Migration notes

### Windows Service
- Located in `src/goldflipper/service/`
- Uses pywin32 for Windows service integration
- Install/uninstall via `install_service.bat`

### TUI Interface
- Built with Textual framework
- Rich library for terminal formatting
- Main TUI: `goldflipper_tui.py`
- Trade Logger: `trade_logging/trade_logger_ui.py`
- Play Creator GUI: `tools/play_creator_gui.py` (Tkinter)

### Trading Integration
- **Alpaca API** for trading (alpaca-py)
- **Market Data**: Abstracted via `data/market/manager.py`
  - Uses yfinance for stock data
  - Uses Alpaca for options data
- **Technical Analysis**: ta library
- **Greeks**: via Alpaca options API

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
