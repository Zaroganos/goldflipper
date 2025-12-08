"""
Goldflipper Multi-Strategy Entry Point

This module provides the multi-strategy entry point using the StrategyOrchestrator.

Usage:
    python -m goldflipper.run_multi --mode console

Configuration (settings.yaml):
    strategy_orchestration:
      enabled: true          # Enable orchestrator
      mode: "sequential"     # or "parallel"
      dry_run: false         # Set true to evaluate without executing orders

Multi-Strategy Implementation - Migration Complete.
"""

ascii_art = r"""
                   ___       ___    .-.      ___                                                 
                  (   )     (   )  /    \   (   )  .-.                                           
  .--.     .--.    | |    .-.| |   | .`. ;   | |  ( __)    .-..      .-..     .--.    ___ .-.    
 /    \   /    \   | |   /   \ |   | |(___)  | |  (''")   /    \    /    \   /    \  (   )   \   
;  ,-. ' |  .-. ;  | |  |  .-. |   | |_      | |   | |   ' .-,  ;  ' .-,  ; |  .-. ;  | ' .-. ;  
| |  | | | |  | |  | |  | |  | |  (   __)    | |   | |   | |  . |  | |  . | |  | | |  |  / (___) 
| |  | | | |  | |  | |  | |  | |   | |       | |   | |   | |  | |  | |  | | |  |/  |  | |        
| |  | | | |  | |  | |  | |  | |   | |       | |   | |   | |  | |  | |  | | |  ' _.'  | |        
| '  | | | '  | |  | |  | '  | |   | |       | |   | |   | |  ' |  | |  ' | |  .'.-.  | |        
'  `-' | '  `-' /  | |  ' `-'  /   | |       | |   | |   | `-'  '  | `-'  ' '  `-' /  | |        
 `.__. |  `.__.'  (___)  `.__,'   (___)     (___) (___)  | \__.'   | \__.'   `.__.'  (___)       
 ( `-' ;                                                 | |       | |                           
  `.__.                                                 (___)     (___)                          

Welcome to Project Goldflipper - Multi-Strategy Mode.

Starting up ...
"""

print(ascii_art)

import os
import sys
import logging
import time
import argparse
from datetime import datetime
from pathlib import Path

# Core imports
from goldflipper.config.config import config
from goldflipper.utils.display import TerminalDisplay as display
from goldflipper.utils.logging_setup import configure_logging
from goldflipper.startup_test import run_startup_tests
from goldflipper.watchdog.watchdog_manager import WatchdogManager
from src.state.state_manager import StateManager


# ==================================================
# SETUP AND CONFIGURATION
# ==================================================

def setup_logging(console_mode=False):
    """Configure logging using centralized rotating setup."""
    configure_logging(console_mode=console_mode)


def initialize_system():
    """Initialize the trading system and perform startup checks."""
    display.header("Initializing Goldflipper Trading System (Multi-Strategy)")
    
    # Initialize state manager
    state_dir = Path(__file__).parent / 'state'
    state_dir.mkdir(exist_ok=True)
    state_manager = StateManager(state_dir)
    
    # Run startup self-tests
    test_results = run_startup_tests()
    
    # Display test results
    display.header("Startup Self-Test Results")
    
    for test_name, test_data in test_results["tests"].items():
        if test_data["success"]:
            display.success(f"{test_name.upper()} Test: PASSED")
            display.info(f"Details: {test_data['result']}")
        else:
            display.error(f"{test_name.upper()} Test: FAILED")
            display.error(f"Details: {test_data['result']}")
    
    if test_results["all_passed"]:
        display.success("\nAll Tests Passed Successfully!")
        return True, state_manager
    else:
        display.error("\nSome Tests Failed - Check Details Above")
        return False, state_manager


def _get_config_int(section: str, key: str, default: int = 30) -> int:
    """Safely get an integer config value."""
    try:
        val = config.get(section, key, default=default)
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str) and val.isdigit():
            return int(val)
        return default
    except Exception:
        return default


def _get_config_bool(section: str, key: str, default: bool = False) -> bool:
    """Safely get a boolean config value."""
    try:
        val = config.get(section, key, default=default)
        if isinstance(val, bool):
            return val
        return default
    except Exception:
        return default


def is_orchestration_enabled() -> bool:
    """Check if strategy orchestration is enabled in config."""
    orch_config = config.get('strategy_orchestration', default={})
    if not isinstance(orch_config, dict):
        return False
    return bool(orch_config.get('enabled', False))


def validate_market_hours():
    """
    Validate if market is currently open.
    
    Returns:
        Tuple[bool, int]: (is_open, minutes_to_open)
    """
    from goldflipper.core import validate_market_hours as core_validate
    return core_validate()


def get_sleep_interval(minutes_to_open: int) -> int:
    """Calculate appropriate sleep interval based on time to market open."""
    from goldflipper.core import get_sleep_interval as core_get_interval
    return core_get_interval(minutes_to_open)


# ==================================================
# ORCHESTRATOR-BASED MONITORING
# ==================================================

def run_orchestrated_monitoring(console_mode: bool = True, watchdog=None):
    """
    Run the multi-strategy monitoring using StrategyOrchestrator.
    
    This is the new monitoring approach that coordinates multiple strategies
    through the orchestrator infrastructure.
    """
    from goldflipper.strategy.orchestrator import StrategyOrchestrator
    from goldflipper.core import get_market_data_manager
    from goldflipper.alpaca_client import get_alpaca_client
    from goldflipper.utils.json_fixer import PlayFileFixer
    
    # Initialize shared resources
    market_data = get_market_data_manager()
    client = get_alpaca_client()
    
    # Create and initialize orchestrator
    orchestrator = StrategyOrchestrator(
        config=config._config,
        market_data=market_data,
        brokerage_client=client
    )
    
    try:
        success = orchestrator.initialize()
        if not success:
            if console_mode:
                display.warning("Orchestrator initialization returned False (likely disabled)")
            logging.warning("Orchestrator initialization returned False")
            return False
            
    except Exception as e:
        logging.error(f"Failed to initialize orchestrator: {e}")
        if console_mode:
            display.error(f"Failed to initialize orchestrator: {e}")
        return False
    
    # Display loaded strategies
    status = orchestrator.get_status()
    if console_mode:
        display.success(f"Orchestrator initialized: {status['strategy_count']} strategies loaded")
        for strat in status['strategies']:
            display.info(f"  - {strat['name']} (priority={strat['priority']}, enabled={strat['enabled']})")
    
    logging.info(f"Orchestrator initialized with {status['strategy_count']} strategies")
    
    # JSON fixer for file integrity
    json_fixer = PlayFileFixer()
    
    cycle_count = 0
    
    while True:
        try:
            cycle_count += 1
            logging.info(f"Starting orchestrated cycle {cycle_count}")
            
            # Update watchdog if enabled
            if watchdog:
                watchdog.update_heartbeat()
            
            # Check market hours
            is_open, minutes_to_open = validate_market_hours()
            if not is_open:
                sleep_time = get_sleep_interval(minutes_to_open)
                display.status(f"Market is CLOSED. Next check in {sleep_time} seconds.")
                time.sleep(sleep_time)
                continue
            
            display.success("Market is OPEN. Multi-strategy monitoring starting.")
            
            # Run orchestrator cycle
            cycle_success = orchestrator.run_cycle()
            
            if cycle_success:
                display.header(f"Orchestrated cycle {cycle_count} complete.")
            else:
                display.warning(f"Orchestrated cycle {cycle_count} completed with warnings.")
                # Log any errors from the cycle
                for error in orchestrator._cycle_errors:
                    logging.error(f"Cycle error: {error}")
            
            # Update watchdog after cycle
            if watchdog:
                watchdog.update_heartbeat()
            
            # Run JSON fixer
            polling_interval: int = _get_config_int('monitoring', 'polling_interval', 30)
            json_fix_delay = 3
            
            if json_fix_delay < polling_interval:
                time.sleep(json_fix_delay)
                try:
                    fixed_count = json_fixer.check_and_fix_all_plays()
                    if fixed_count > 0:
                        logging.info(f"JSON fixer repaired {fixed_count} corrupted play files")
                except Exception as e:
                    logging.error(f"Error in JSON fixer: {e}")
                
                remaining_sleep: int = max(0, polling_interval - json_fix_delay)
                time.sleep(remaining_sleep)
            else:
                time.sleep(float(polling_interval))
                
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt received in orchestrated monitoring")
            if console_mode:
                display.info("\nShutdown requested. Cleaning up orchestrator...")
            orchestrator.stop()
            break
            
        except Exception as e:
            logging.error(f"Error in orchestrated monitoring cycle: {e}")
            if console_mode:
                display.error(f"Error in orchestrated cycle: {e}")
            
            # Update watchdog even after error
            if watchdog:
                watchdog.update_heartbeat()
            
            time.sleep(10)
    
    return True


# ==================================================
# MAIN ENTRY POINTS
# ==================================================

def run_trading_system_multi(console_mode: bool = True):
    """
    Run the trading system using the multi-strategy orchestrator.
    """
    setup_logging(console_mode)
    logging.info(f"Starting Goldflipper Multi-Strategy system in {'console' if console_mode else 'service'} mode")
    
    if console_mode:
        display.info("Starting Goldflipper Multi-Strategy trading system")
    
    try:
        # Run initialization and startup tests
        success, state_manager = initialize_system()
        if not success:
            display.error("System initialization failed. Check the logs for details.")
            return
        
        # Initialize watchdog if enabled
        watchdog_enabled = _get_config_bool('watchdog', 'enabled', False)
        watchdog_check_interval: int = _get_config_int('watchdog', 'check_interval', 30)
        watchdog = None
        
        if watchdog_enabled:
            logging.info("Watchdog system is enabled")
            if console_mode:
                display.info("Watchdog system is enabled")
            
            watchdog = WatchdogManager(check_interval=watchdog_check_interval)
            watchdog.start_monitoring()
            watchdog.update_heartbeat()
            
            if console_mode:
                display.info("Initial heartbeat set")
            logging.info("Initial heartbeat set")
        else:
            logging.info("Watchdog system is disabled in configuration")
            if console_mode:
                display.info("Watchdog system is disabled. Check settings to enable.")
        
        # Run orchestrated monitoring
        if not is_orchestration_enabled():
            error_msg = "Strategy orchestration is disabled. Enable it in settings.yaml"
            logging.error(error_msg)
            if console_mode:
                display.error(error_msg)
            raise RuntimeError(error_msg)
        
        if console_mode:
            display.success("Strategy orchestration is ENABLED")
            display.info("Using multi-strategy orchestrator")
        logging.info("Strategy orchestration enabled, using orchestrator")
        
        run_orchestrated_monitoring(console_mode, watchdog)
            
    except Exception as e:
        error_msg = f"System error: {e}"
        logging.error(error_msg)
        if console_mode:
            display.error(error_msg)
        raise
        
    finally:
        if 'watchdog' in locals() and watchdog:
            logging.info("Stopping watchdog monitoring")
            watchdog.stop_monitoring()
        if console_mode:
            display.info("Shutdown complete")


def main():
    """Main entry point with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description='Goldflipper Multi-Strategy Trading System'
    )
    parser.add_argument(
        '--mode', 
        choices=['console'],
        default='console', 
        help='Run mode (console)'
    )
    
    parser.parse_args()
    run_trading_system_multi(console_mode=True)


if __name__ == "__main__":
    main()
