#!/usr/bin/env python
import os
import sys

# Add the project root directory to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

import psutil
import json
from datetime import datetime
import subprocess
import alpaca
from ..alpaca_client import get_alpaca_client

def update_alpaca():
    """
    Update alpaca-py package using pip
    """
    print("\nUpdating alpaca-py package...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "alpaca-py"])
        print("alpaca-py updated successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error updating alpaca-py: {e}")

def check_system_status():
    """
    Tool to check system status and perform maintenance tasks.
    """
    print("System Status and Upkeep Tool")
    print("--------------------------")

    # Check alpaca-py version
    print(f"\nCurrent alpaca-py version: {alpaca.__version__}")

    # Update alpaca-py package first
    update_alpaca()
    
    # Initialize trading client using existing setup
    try:
        trade_client = get_alpaca_client()
        
        # Check trading account status
        acct = trade_client.get_account()
        print("\nTrading Account Status:")
        print(f"Options Buying Power: ${acct.options_buying_power}")
        print(f"Options Approved Level: {acct.options_approved_level}")
        print(f"Options Trading Level: {acct.options_trading_level}")
        
        # Check account configuration
        acct_config = trade_client.get_account_configurations()
        print("\nAccount Configuration:")
        print(f"Max Options Trading Level: {acct_config.max_options_trading_level}")
        
    except Exception as e:
        print(f"\nError accessing Alpaca API: {e}")

def run_system_status():
    update_alpaca()
    check_system_status()

def main():
    run_system_status()
    # Pause at the end so that the console window remains visible.
    input("Press Enter to exit...")

if __name__ == "__main__":
    # Ensure proper package resolution in frozen mode.
    if __package__ is None:
        __package__ = "goldflipper.tools"
    main() 