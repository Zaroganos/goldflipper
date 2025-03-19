# goldflipper
Goldflipper Trading System

## Goldflipper v1 set to Public on Github temporarily
This repository is set to public temporarily. Though the code is accesible, use is permitted on a case-by-case basis only. For more information please get in touch by dm. Otherwise, please note that no support is promised or available, and requests of any kind will be addressed at my discretion. 
Though the code is public at this time, you are not permitted to make any use of it without express written permission from myself.

## Introduction

Goldflipper is an algorithmic trading system developed using Python. It utilizes a modular, event-driven architecture to automate trading strategies, with a particular focus on options swing trading. The system is designed for scalability, maintainability, and reliability, integrating with Alpaca Markets for live trading.

## Project Structure

The project is organized into the following directories:

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
- An Alpaca trading account with API access
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
   - Modify the config/config.py file with your Alpaca API keys
   - Set up your trading parameters in the configuration files

### Running the System

The system can be launched in several ways:

1. Using the desktop shortcut (recommended):
   - Double-click the Goldflipper desktop shortcut

2. Using the batch files:
   - `launch_goldflipper.bat` - Launches the main application
   - `run_console.bat` - Launches in console mode
   - `install_service.bat` - Installs the system as a Windows service

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

This project is copyright Iliya Yaroshevskiy. All rights reserved.
