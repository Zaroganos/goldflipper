# goldflipper
Goldflipper Trading System

![goldlfipper](https://github.com/user-attachments/assets/60a7b1c3-40ef-4dd2-9c64-98be7e93f185)


## Disclaimer
This repository contains proprietary, source-available code. Please note that technical support is neither promised nor available, and bug fix and feature requests of any kind will be addressed solely at the author's discretion. 
Additionally, please note that this program does not capture or transmit any of your data. The only connections made are to brokerage(s) and market data provider(s). Newer branches also make calls using python libraries solely for the purpose of enhancing function by validating inputs (to address user entry errors) and checking the market calendar. However, please note that in this version, access keys are stored in the settings file in plaintext (or, plain-yaml).

## Introduction

Goldflipper v1 (aka Classic) is a rules-based semi-autonomous trading system developed in Python. It utilizes a modular, event-driven architecture to automate trading strategy execution, with a current focus on level 2 options trading. The system is designed for customizability, modularity, and offers a feature-rich parameter selection that enables functionality not seen in any other program of its kind. Goldflipper v1 integrates with the Alpaca Markets API for live trading, and has API integrations with market data providers as well in order to provide a modular and robust trading experience with fallbacks for reliability.

## Project Structure

The project is roughly organized into the following directories:
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
├── logging/                   # Comprehensive logging system
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
│   ├── auto_play_creator.py  # Automated play generation (for testing purposes)
│   ├── play_creation_tool.py # Interactive play creation
│   ├── play-edit-tool.py     # Advanced play editing with safety features
│   ├── view_plays.py         # Play viewing and management
│   ├── option_data_fetcher.py # Options data retrieval
│   ├── get_alpaca_info.py    # Alpaca account information
│   ├── system_status.py      # System health monitoring
│   ├── configuration.py      # Configuration management
│   └── [multiple other tools] # JSON processing, CSV ingestion, etc.
├── utils/                     # General utility functions
├── watchdog/                  # System monitoring and health checks
├── state/                     # System state management and persistence
├── strategy/                  # Trading strategy definitions
├── reference/                 # Reference materials and templates
├── src/                       # Windows Service code
│   ├── service/              # Windows service integration
│   └── state/                # State management components
└── tests/                     # Test suites and validations
```

## Getting Started

### Prerequisites

Before you start, ensure you have the following:

- **Alpaca Markets account** for brokerage access; multi-broker support is planned with v2
- **Windows OS** (required for service functionality and batch files); multi-OS support is planned with v2
- **Git** (required for cloning the repository and keeping it up to date)
- **Python 3.8 or higher** (Python 3.10+ recommended)
- **Python libraries** (see Installation section); strongly recommended to use a virtual environment to avoid dependency conflicts. Consider using Poetry as well (directions to be added in time)
- **Market Data Provider account(s)** (required if not using market data from brokerage):
  - Yahoo Finance (free, built-in support via yfinance)

### Installation

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
pip install -e .
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

### Running the System

Goldflipper offers multiple interfaces and execution modes:

#### 1. **TUI Interface (Recommended)**
The modern Text User Interface provides an intuitive way to interact with all system features:
- Double-click the Goldflipper desktop shortcut, or:
```cmd
python goldflipper\goldflipper_tui.py
```

#### 2. **Console Mode**

#### 3. **Windows Service Mode**

## Key Features

### 🎯 **Core Trading System**
- **Semi-autonomous options trading** with rules-based execution
- **Advanced play management** with state-based workflow (new → pending → open → closed)
- **Multiple order types**: Market, limit at bid/ask/mid/last, contingency orders
- **Risk management**: Take profit, stop loss, and contingency stop loss orders
- **Real-time monitoring** with continuous play evaluation

### 📊 **Market Data & Analysis**
- **Multiple data providers** with automatic failover:
- **Complete Options Greeks calculations**: Delta, Gamma, Theta, Vega, Rho, and 15+ advanced Greeks
- **Technical indicators**: EMA, MACD, TTM Squeeze, and custom indicators
- **Interactive charting** with candlestick charts and overlay indicators

### 🖥️ **User Interfaces**
- **Modern TUI (Text User Interface)** built with Textual framework
- **Console mode** for direct system interaction
- **Web-based trade logger** with Dash framework for analytics
- **Windows service integration** for background operation

### 🔧 **Management Tools**
- **Play creation tool** with guided setup and validation
- **Play editing system** with safety protections for active trades
- **Auto play creator** for bulk play generation
- **System status monitoring** with health checks
- **Configuration management** with YAML-based settings
- **Data export capabilities** (CSV, Excel) for analysis

### 🛡️ **System Reliability**
- **Watchdog system** for automated health monitoring
- **Comprehensive logging** with structured trade tracking
- **State persistence** with automatic backup and recovery
- **Error handling** with graceful degradation and retry logic
- **Market hours validation** and holiday awareness

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

# System Configuration
monitoring:
  polling_interval: 30  # seconds
  
watchdog:
  enabled: true
  check_interval: 30
```

### **Advanced Settings**
- **Trading parameters**: Risk management, position sizing
- **Market hours**: Custom trading session definitions
- **Logging levels**: Debug, info, warning, error
- **Display options**: Chart settings, option chain columns
- **File paths**: Custom directory structures

## License

Copyright (c) 2024-2025 Iliya Yaroshevskiy. All Rights Reserved.
