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

Welcome to Project Goldflipper.

Starting up ...
"""

print(ascii_art)
import argparse
import logging
import logging.handlers
import time
from datetime import datetime
from typing import Any

import servicemanager
import win32event
import win32service
import win32serviceutil
from src.state.state_manager import StateManager

from goldflipper.config.config import config

# from goldflipper.core import monitor_plays_continuously  // Deprecated
from goldflipper.startup_test import run_startup_tests
from goldflipper.utils.display import TerminalDisplay as display
from goldflipper.utils.exe_utils import get_application_dir
from goldflipper.utils.logging_setup import configure_logging
from goldflipper.watchdog.watchdog_manager import WatchdogManager

# ==================================================
# SETUP AND CONFIGURATION
# ==================================================


def setup_logging(console_mode=False):
    """Configure logging using centralized rotating setup."""
    configure_logging(console_mode=console_mode)


def initialize_system():
    """
    Initialize the trading system and perform startup checks.

    Returns:
        Tuple of (success: bool, state_manager: StateManager, test_results: dict)
        - success: True if system can start (no critical failures)
        - state_manager: Initialized StateManager instance
        - test_results: Full test results dictionary for further processing
    """
    display.header("Initializing Goldflipper Trading System")

    # Initialize state manager - use exe_utils for Nuitka-compatible path
    state_dir = get_application_dir() / "state"
    state_dir.mkdir(exist_ok=True)
    state_manager = StateManager(state_dir)

    """
    # TO DO: Implement state recovery logic
    # Load previous state if exists
    previous_state = state_manager.load_state()
    if previous_state:
        logging.info("Not implemented: Recovered previous state")
        display.info("Not implemented: Recovered previous state")
    """

    # Run startup self-tests
    test_results = run_startup_tests()

    # Display test results using formatted output
    display.header("Startup Self-Test Results")

    for test_name, test_data in test_results["tests"].items():
        severity = test_data.get("severity", "error")
        is_primary = test_data.get("is_primary_provider", False)
        provider_tag = " [PRIMARY]" if is_primary else ""

        if test_data["success"]:
            display.success(f"{test_name.upper()}{provider_tag} Test: PASSED")
            display.info(f"  Details: {test_data['result']}")
        elif severity == "error":
            display.error(f"{test_name.upper()}{provider_tag} Test: FAILED (CRITICAL)")
            display.error(f"  Details: {test_data['result']}")
        else:
            display.warning(f"{test_name.upper()}{provider_tag} Test: FAILED (WARNING)")
            display.warning(f"  Details: {test_data['result']}")

    # Summary
    if test_results["all_passed"]:
        display.success("\nAll Tests Passed Successfully!")
        return True, state_manager, test_results
    elif test_results.get("should_block_trading", False):
        display.error("\n" + "=" * 60)
        display.error("CRITICAL TEST FAILURES - TRADING BLOCKED")
        display.error(f"Critical failures: {', '.join(test_results.get('critical_failures', []))}")
        if test_results.get("warnings"):
            display.warning(f"Warnings: {', '.join(test_results.get('warnings', []))}")
        return False, state_manager, test_results
    else:
        # Only warnings, not critical failures
        display.warning("\n" + "=" * 60)
        display.warning("Some tests failed with warnings - trading can continue")
        display.warning(f"Warnings: {', '.join(test_results.get('warnings', []))}")
        return True, state_manager, test_results


class GoldflipperService(win32serviceutil.ServiceFramework):
    _svc_name_ = "GoldflipperService"
    _svc_display_name_ = "Goldflipper Trading Service"
    _svc_description_ = "Automated trading service for the Goldflipper platform"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = False
        self.watchdog = None
        self.state_manager = None

    def SvcStop(self):
        """Handle service stop request"""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.running = False

        if self.watchdog:
            self.watchdog.stop_monitoring()

        if self.state_manager:
            # Save final state before stopping
            self.state_manager.save_state({"timestamp": datetime.now().isoformat(), "shutdown": "clean"})

    def SvcDoRun(self):
        """Main service run method - uses strategy orchestration"""
        try:
            setup_logging()
            self.running = True

            # Initialize system
            success, self.state_manager, test_results = initialize_system()
            if not success:
                raise Exception("System initialization failed - critical test failures")

            # Start watchdog only if enabled in config
            watchdog_enabled = bool(config.get("watchdog", "enabled", default=False))
            watchdog_check_interval_val = config.get("watchdog", "check_interval", default=30)
            watchdog_check_interval: int = int(watchdog_check_interval_val) if isinstance(watchdog_check_interval_val, (int, float)) else 30

            if watchdog_enabled:
                self.watchdog = WatchdogManager(check_interval=watchdog_check_interval)
                self.watchdog.start_monitoring()
                logging.info("Watchdog monitoring started in service mode")
            else:
                logging.info("Watchdog system is disabled in configuration")
                self.watchdog = None

            # Initialize orchestrator
            from goldflipper.alpaca_client import get_alpaca_client
            from goldflipper.core import get_market_data_manager, get_sleep_interval, validate_market_hours
            from goldflipper.strategy.orchestrator import StrategyOrchestrator

            market_data = get_market_data_manager()
            client = get_alpaca_client()

            orchestrator = StrategyOrchestrator(config=config._config, market_data=market_data, brokerage_client=client)

            if not orchestrator.initialize():
                raise Exception("Orchestrator initialization failed")

            logging.info(f"Orchestrator initialized: {orchestrator.get_status()['strategy_count']} strategies")

            # Start main application loop
            while self.running:
                try:
                    if self.watchdog:
                        self.watchdog.update_heartbeat()

                    # Check market hours
                    is_open, minutes_to_open = validate_market_hours()
                    if not is_open:
                        sleep_time = get_sleep_interval(minutes_to_open)
                        logging.info(f"Market closed. Sleeping {sleep_time}s")
                        win32event.WaitForSingleObject(self.stop_event, sleep_time * 1000)
                        continue

                    # Run orchestrator cycle
                    orchestrator.run_cycle()

                    if self.watchdog:
                        self.watchdog.update_heartbeat()

                    polling_interval_val = config.get("monitoring", "polling_interval", default=30)
                    polling_interval: int = int(polling_interval_val) if isinstance(polling_interval_val, (int, float)) else 30
                    win32event.WaitForSingleObject(self.stop_event, polling_interval * 1000)
                except Exception as e:
                    logging.error(f"Error in main loop: {str(e)}")
                    time.sleep(10)

            orchestrator.stop()

        except Exception as e:
            logging.error(f"Service failed: {str(e)}")
            servicemanager.LogErrorMsg(f"Service failed: {str(e)}")
            raise


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


def _is_orchestration_enabled() -> bool:
    """Check if strategy orchestration is enabled in config."""
    try:
        orch_config = config.get("strategy_orchestration", default={})
        if isinstance(orch_config, dict):
            return bool(orch_config.get("enabled", False))
        return False
    except Exception:
        return False


def _init_orchestrator(console_mode: bool = False) -> Any | None:
    """
    Initialize the StrategyOrchestrator if orchestration is enabled.

    Returns:
        Initialized orchestrator or None if disabled/failed
    """
    if not _is_orchestration_enabled():
        return None

    try:
        from goldflipper.alpaca_client import get_alpaca_client
        from goldflipper.core import get_market_data_manager
        from goldflipper.strategy.orchestrator import StrategyOrchestrator

        market_data = get_market_data_manager()
        client = get_alpaca_client()

        orchestrator = StrategyOrchestrator(config=config._config, market_data=market_data, brokerage_client=client)

        if orchestrator.initialize():
            status = orchestrator.get_status()
            logging.info(f"Orchestrator initialized: {status['strategy_count']} strategies")
            if console_mode:
                display.success(f"Strategy orchestration ENABLED: {status['strategy_count']} strategies loaded")
                for strat in status["strategies"]:
                    display.info(f"  - {strat['name']} (priority={strat['priority']})")
            return orchestrator
        else:
            logging.warning("Orchestrator initialization returned False")
            return None

    except Exception as e:
        logging.error(f"Failed to initialize orchestrator: {e}")
        if console_mode:
            display.warning(f"Orchestrator init failed: {e}")
        return None


def run_trading_system(console_mode=False):
    """Run the trading system in either console or service mode"""
    setup_logging(console_mode)
    logging.info(f"Starting Goldflipper trading system in {'console' if console_mode else 'service'} mode")

    if console_mode:
        display.info("Starting Goldflipper trading system")

    orchestrator = None  # Will be set if orchestration is enabled

    try:
        # Run initialization and startup tests
        success, state_manager, test_results = initialize_system()
        if not success:
            display.error("System initialization failed. Check the logs for details.")
            # Keep window open if configured
            if test_results.get("pause_on_error", True):
                display.error("\n" + "=" * 60)
                display.error("STARTUP FAILED - Press Enter to exit...")
                try:
                    input()
                except (EOFError, KeyboardInterrupt):
                    pass
            return

        logging.info("Initializing WatchdogManager")
        if console_mode:
            display.info("Initializing WatchdogManager")

        # Check if watchdog is enabled in config
        watchdog_enabled = bool(config.get("watchdog", "enabled", default=False))
        watchdog_check_interval: int = _get_config_int("watchdog", "check_interval", 30)
        watchdog_warning = config.get("watchdog", "warning", default="EXPERIMENTAL: The watchdog system is experimental.")

        # Initialize watchdog only if enabled
        watchdog = None
        if watchdog_enabled:
            logging.info("Watchdog system is enabled")
            if console_mode:
                display.warning(f"Watchdog Warning: {watchdog_warning}")
                display.info("Watchdog system is enabled")

            watchdog = WatchdogManager(check_interval=watchdog_check_interval)

            logging.info("Starting watchdog monitoring")
            if console_mode:
                display.info("Watchdog monitoring starting...")

            watchdog.start_monitoring()
            watchdog.update_heartbeat()
            if console_mode:
                display.info("Initial heartbeat set")
            logging.info("Initial heartbeat set")
        else:
            logging.info("Watchdog system is disabled in configuration")
            if console_mode:
                display.info("Watchdog system is disabled. Check settings to enable.")

        # Use exe_utils for Nuitka-compatible path
        state_dir = get_application_dir() / "state"
        state_dir.mkdir(exist_ok=True)
        state_manager = StateManager(state_dir)

        # Initialize orchestrator for multi-strategy mode
        orchestrator = _init_orchestrator(console_mode)

        if orchestrator is None:
            error_msg = "Orchestrator initialization failed. Check strategy_orchestration config."
            logging.error(error_msg)
            if console_mode:
                display.error(error_msg)
            raise RuntimeError(error_msg)

        logging.info("Using orchestrated multi-strategy mode")
        if console_mode:
            display.success("Running in multi-strategy orchestration mode")

        from goldflipper.core import get_sleep_interval, validate_market_hours
        from goldflipper.utils.json_fixer import PlayFileFixer

        json_fixer = PlayFileFixer()

        cycle_count = 0

        while True:
            try:
                cycle_count += 1
                logging.info(f"Starting orchestrated cycle {cycle_count}")

                if watchdog:
                    watchdog.update_heartbeat()

                # Check market hours
                is_open, minutes_to_open = validate_market_hours()
                if not is_open:
                    sleep_time = get_sleep_interval(minutes_to_open)
                    display.status(f"Market is CLOSED. Next check in {sleep_time} seconds.")
                    time.sleep(sleep_time)
                    continue

                display.success("Market is OPEN. Orchestrated monitoring starting.")

                # Run orchestrator cycle
                try:
                    orchestrator.run_cycle()
                except Exception as e:
                    error_msg = f"Error in orchestrated monitoring: {str(e)}"
                    logging.error(error_msg)
                    if console_mode:
                        display.error(error_msg)

                if watchdog:
                    watchdog.update_heartbeat()

                # Run JSON fixer
                polling_interval = _get_config_int("monitoring", "polling_interval", 30)
                json_fix_delay = 3

                if json_fix_delay < polling_interval:
                    time.sleep(json_fix_delay)
                    try:
                        fixed_count = json_fixer.check_and_fix_all_plays()
                        if fixed_count > 0:
                            logging.info(f"JSON fixer repaired {fixed_count} corrupted play files")
                    except Exception as e:
                        logging.error(f"Error in JSON fixer: {e}")

                    time.sleep(max(0, polling_interval - json_fix_delay))
                else:
                    time.sleep(float(polling_interval))

            except KeyboardInterrupt:
                logging.info("KeyboardInterrupt received")
                if console_mode:
                    display.info("\nShutdown requested. Cleaning up...")
                orchestrator.stop()
                break
            except Exception as e:
                error_msg = f"Error in orchestrated main loop: {str(e)}"
                logging.error(error_msg)
                if console_mode:
                    display.error(error_msg)

                if watchdog:
                    watchdog.update_heartbeat()
                time.sleep(10)

    except Exception as e:
        error_msg = f"System error: {str(e)}"
        logging.error(error_msg)
        if console_mode:
            display.error(error_msg)
        raise
    finally:
        if orchestrator is not None:
            logging.info("Stopping orchestrator")
            orchestrator.stop()
        if "watchdog" in locals() and watchdog:
            logging.info("Stopping watchdog monitoring")
            watchdog.stop_monitoring()
        if console_mode:
            display.info("Shutdown complete")


def main():
    parser = argparse.ArgumentParser(description="Goldflipper Trading System")
    parser.add_argument("--mode", choices=["console", "service", "install", "remove", "update"], default="console", help="Run mode")

    args = parser.parse_args()

    if args.mode == "console":
        run_trading_system(console_mode=True)
    elif args.mode in ["install", "remove", "update"]:
        # Handle service installation commands
        if args.mode == "install":
            win32serviceutil.HandleCommandLine(GoldflipperService, argv=["", "--startup", "auto", "install"])
        elif args.mode == "remove":
            win32serviceutil.HandleCommandLine(GoldflipperService, argv=["", "remove"])
        elif args.mode == "update":
            win32serviceutil.HandleCommandLine(GoldflipperService, argv=["", "update"])
    elif args.mode == "service":
        # Run as a Windows service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(GoldflipperService)
        servicemanager.StartServiceCtrlDispatcher()


if __name__ == "__main__":
    main()
