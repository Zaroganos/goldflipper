# goldflipper
Goldflipper Trading System

![goldlfipper](https://github.com/user-attachments/assets/60a7b1c3-40ef-4dd2-9c64-98be7e93f185)


## Goldflipper v1 set to Public on Github temporarily
Although this repository is public and the code is accesible, the use of this code, explicitly permitted according to the author's moral rights, is granted on a case-by-case basis only. For more information please get in touch with the author directly. Otherwise, please note that technical support is neither promised nor available, and bug fix and feature requests of any kind will be addressed solely at the author's discretion. 

## Introduction

Goldflipper v1 is a rules-based semi-autonomous trading system developed in Python. It utilizes a modular, event-driven architecture to automate trading strategy execution, with a current focus on level 2 options trading. The system is designed for customizability, modularity, and offers a feature-rich parameter selection that enables functionality not seen in any other program of its kind. Goldflipper v1 integrates with the Alpaca Markets API for live trading, and has API integrations with market data providers as well in order to provide a modular and robust trading experience with fallbacks for reliability.

## Project Structure

The project is roughly organized into the following directories:
(Simplified for brevity, access the codebase to discover the full content.)

```
goldflipper/
├── config/                     # Configuration files and settings
│   └── config.py
├── data/                      # Data handling modules
│   ├── greeks/               # Options Greeks calculations
│   ├── indicators/           # Technical indicators
│   ├── market/               # Market data handling
│   │   └── providers/        # Market data providers (Alpaca, yfinance)
│   └── ta/                   # Technical analysis tools
├── logging/                   # Logging functionality
│   └── logs/                 # Application logs
├── plays/                     # Trading plays management
│   ├── closed/               # Closed trading positions
│   ├── expired/              # Expired options
│   ├── new/                  # New trading opportunities
│   ├── open/                 # Currently open positions
│   ├── pending-closing/      # Positions pending closure
│   ├── pending-opening/      # Positions pending opening
│   └── temp/                 # Temporary play storage
├── reference/                 # Reference materials and templates
├── state/                     # System state management
├── strategy/                  # Trading strategies
├── tools/                     # Utility tools
│   ├── auto_play_creator.py
│   ├── configuration.py
│   ├── play_creation_tool.py
│   └── system_status.py
├── utils/                     # Utility functions
├── watchdog/                  # System monitoring
├── src/                       # Source code
│   ├── service/              # Service management
│   └── state/                # State management
└── tests/                     # Test suite
```

## Getting Started

### Prerequisites

Before you start, ensure you have the following installed on your system:

- Python 3.8 or higher
- An Alpaca Markets account
- Required Python libraries listed in requirements.txt

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd goldflipper
```

2. Install the required libraries:
```bash
pip install -r requirements.txt
```

3. Configure your API keys:
   - Modify the settings.yaml file with your Alpaca API keys and market data provider API keys
   - Set up your trading and operating parameters as well

### Running the System

The system can be launched in several ways:

1. Using the desktop shortcut (recommended):
   - Double-click the Goldflipper desktop shortcut

2. Using the batch files:
   - `launch_goldflipper.bat` - Launches the main application (default)
   - `run_console.bat` - Launches in console mode
   - `install_service.bat` - Installs the system as a Windows service (experimental)

3. Direct Python execution:
```bash
python goldflipper/run.py
```

## Key Features

- Options Greeks calculations and analysis
- Technical indicators and market data processing
- Automated trading play creation and management
- Real-time market data integration with Alpaca
- System state management and monitoring
- Comprehensive logging and error tracking
- Windows service integration for automated operation

## Directory Overview

- `config/`: Configuration files and settings management
- `data/`: Core data handling modules including Greeks calculations and market data
- `logging/`: Logging functionality and log storage
- `plays/`: Trading plays management with different states (new, open, closed, etc.)
- `reference/`: Reference materials and templates for trading
- `state/`: System state management and persistence
- `strategy/`: Trading strategy definitions and parameters
- `tools/`: Utility tools for system management and trading
- `utils/`: General utility functions
- `watchdog/`: System monitoring and health checks
- `src/`: Core source code including service management
- `tests/`: Test suite for system components

## License

Copyright (c) 2024-2025 Iliya Yaroshevskiy. All Rights Reserved.
