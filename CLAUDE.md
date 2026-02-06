# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Goldflipper is a rules-based, semi-autonomous options trading system in Python that integrates with Alpaca Markets. It uses an event-driven, multi-strategy architecture for customizable trading strategy execution.

- **Python**: 3.12+ (requires 3.12 < version < 3.14)
- **Package Manager**: uv (preferred over pip)
- **Build Backend**: hatchling
- **Platform**: Windows-focused (multi-OS planned for v2)

## Development Commands

```powershell
# Run application
uv run goldflipper

# Run all quality checks (format + lint + type + test)
scripts\dev.bat check

# Individual commands
uv run pytest                        # Run tests
uv run pytest tests/test_file.py     # Run specific test file
uv run pytest tests/test_file.py::test_name  # Run specific test
uv run ruff format .                 # Format code
uv run ruff check --fix .            # Lint and auto-fix
uv run pyright                       # Type check

# Build Windows executable
scripts\dev.bat build                # Fast dev build
scripts\dev.bat build-prod           # Production build (optimized)

# Dependency management
uv add package-name                  # Add production dependency
uv add --dev package-name            # Add dev dependency
uv lock --upgrade && uv sync         # Update all dependencies
```

## Architecture

### Multi-Strategy System

The core trading logic is in `goldflipper/strategy/`:

```
strategy/
├── base.py           # BaseStrategy ABC, OrderAction enum (BTO, STC, STO, BTC)
├── orchestrator.py   # StrategyOrchestrator - coordinates all strategies
├── registry.py       # @register_strategy decorator, auto-discovery
├── trailing.py       # Trailing stop loss implementation
├── shared/           # Shared utilities extracted from core.py
│   ├── play_manager.py   # Play file I/O operations
│   ├── evaluation.py     # TP/SL evaluation logic
│   └── order_executor.py # Order placement
├── runners/          # Strategy implementations
│   ├── option_swings.py      # Manual BTO→STC swings
│   ├── momentum.py           # Gap/momentum trades
│   ├── sell_puts.py          # Cash-secured puts (STO→BTC)
│   └── spreads.py            # Multi-leg spreads
└── playbooks/        # YAML strategy configs per strategy type
```

**Execution flow:**
1. `run.py` initializes `StrategyOrchestrator`
2. Orchestrator loads enabled strategies via registry
3. Each cycle: `on_cycle_start()` → `evaluate_new_plays()` → `evaluate_open_plays()` → execute orders → `on_cycle_end()`
4. Modes: sequential (safer) or parallel (ThreadPoolExecutor)

### Adding a New Strategy

1. Create `strategy/runners/my_strategy.py` implementing `BaseStrategy`
2. Add `@register_strategy('my_strategy')` decorator
3. Add module name to `runner_modules` list in `strategy/registry.py`
4. Add config section to `config/settings.yaml`
5. See `goldflipper/docs/STRATEGY_DEVELOPMENT_GUIDE.md` for full details

### Play Files (State-Based Workflow)

Trades are managed as JSON files that move between folders:
- `plays/new/` → Entry signals pending execution
- `plays/pending-opening/` → Entry orders submitted
- `plays/open/` → Active positions being monitored
- `plays/pending-closing/` → Exit orders submitted
- `plays/closed/` → Completed trades
- `plays/expired/` → Expired options

### Market Data

`data/market/manager.py` provides a unified `MarketDataManager` with automatic fallback:
1. MarketDataApp (primary)
2. Alpaca (backup)
3. Yahoo Finance (fallback)

### Configuration

- Main config: `goldflipper/config/settings.yaml` (created from template on first run)
- Template: `goldflipper/config/settings_template.yaml`
- Strategy-specific sections control enable/disable and parameters

## Key Files

| File | Purpose |
|------|---------|
| `goldflipper/run.py` | Main entry point (service/orchestrated modes) |
| `goldflipper/goldflipper_tui.py` | Textual TUI interface |
| `goldflipper/core.py` | Legacy trading core (being phased out) |
| `goldflipper/alpaca_client.py` | Alpaca API wrapper |
| `pyproject.toml` | Package config, dependencies, tool settings |
| `nuitka-project.py` | Nuitka EXE build configuration |

## Testing

```powershell
uv run pytest -v                     # Verbose output
uv run pytest -x                     # Stop on first failure
uv run pytest --cov=goldflipper      # With coverage
```

Test files are in `tests/` with fixtures in `conftest.py`.

**Dry-run mode**: Set `strategy_orchestration.dry_run: true` in settings.yaml to evaluate plays without executing orders.

## Code Style

- **Linter/Formatter**: Ruff (line length 150)
- **Type Checker**: Pyright (basic mode)
- Run `scripts\dev.bat check` before committing

## Build Notes

- Nuitka builds standalone Windows EXE to `dist/goldflipper.exe`
- Use `NUITKA_INCLUDE_PACKAGES` for Python modules, not `--include-data-dir`
- Console mode forced for Textual TUI compatibility
- All play file writes use `atomic_write_json()` to prevent corruption
- The Windows filesystem on beQuiet is not used for dev building for this project
