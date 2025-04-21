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

Loading, please wait...
"""

print(ascii_art)
import os
import logging
import logging.handlers
from goldflipper.core import monitor_plays_continuously
from goldflipper.startup_test import run_startup_tests
from goldflipper.config.config import config
import sys
from goldflipper.utils.display import TerminalDisplay as display
from pathlib import Path
import win32serviceutil
import win32service
import win32event
import servicemanager
from goldflipper.watchdog.watchdog_manager import WatchdogManager
from src.state.state_manager import StateManager
from datetime import datetime
import time
import argparse
import threading

# ==================================================
# SETUP AND CONFIGURATION
# ==================================================

def setup_logging(console_mode=False):
    """Configure logging with both file and optional console output"""
    base_dir = Path(__file__).parent.parent
    log_dir = base_dir / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / 'app_run.log'
    
    # Clear existing handlers first
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    handlers = [logging.FileHandler(log_file, encoding='utf-8')]
    
    if console_mode:
        handlers.append(logging.StreamHandler(sys.stdout))
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

def initialize_system():
    """Initialize the trading system and perform startup checks."""
    display.header("Initializing Goldflipper Trading System")
    
    # Initialize state manager
    state_dir = Path(__file__).parent / 'state'
    state_dir.mkdir(exist_ok=True)
    state_manager = StateManager(state_dir)
    
    # Load previous state if exists
    previous_state = state_manager.load_state()
    if previous_state:
        logging.info("Not implemented: Recovered previous state")
        display.info("Not implemented: Recovered previous state")
        # TODO: Implement state recovery logic
    
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
            self.state_manager.save_state({
                'timestamp': datetime.now().isoformat(),
                'shutdown': 'clean'
            })

    def SvcDoRun(self):
        """Main service run method"""
        try:
            setup_logging()
            self.running = True
            
            # Initialize system
            success, self.state_manager = initialize_system()
            if not success:
                raise Exception("System initialization failed")
            
            # Start watchdog
            self.watchdog = WatchdogManager()
            self.watchdog.start_monitoring()
            
            # Start main application loop
            while self.running:
                try:
                    self.watchdog.update_heartbeat()
                    monitor_plays_continuously()
                    self.watchdog.update_heartbeat()
                    
                    polling_interval = config.get('monitoring', 'polling_interval', default=30) * 1000  # Convert to milliseconds
                    win32event.WaitForSingleObject(self.stop_event, polling_interval)
                except Exception as e:
                    logging.error(f"Error in main loop: {str(e)}")
                    # Implement exponential backoff here
                    time.sleep(10)
                    
        except Exception as e:
            logging.error(f"Service failed: {str(e)}")
            servicemanager.LogErrorMsg(f"Service failed: {str(e)}")
            raise

def run_trading_system(console_mode=False):
    """Run the trading system in either console or service mode"""
    setup_logging(console_mode)
    logging.info(f"Starting Goldflipper trading system in {'console' if console_mode else 'service'} mode")
    
    if console_mode:
        display.info("Starting Goldflipper trading system")
    
    try:
        # Run initialization and startup tests
        success, state_manager = initialize_system()
        if not success:
            display.error("System initialization failed. Check the logs for details.")
            return
        
        logging.info("Initializing WatchdogManager")
        if console_mode:
            display.info("Initializing WatchdogManager")

        watchdog = WatchdogManager()
        
        logging.info("Starting watchdog monitoring")    
        if console_mode:
            display.info("Starting watchdog monitoring")

        watchdog.start_monitoring()
        watchdog.update_heartbeat()
        if console_mode:
            display.info("Initial heartbeat set")
        logging.info("Initial heartbeat set")
        
        state_dir = Path(__file__).parent / 'state'
        state_dir.mkdir(exist_ok=True)
        state_manager = StateManager(state_dir)
        
        from goldflipper.core import monitor_plays_continuously
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                logging.info(f"Starting cycle {cycle_count}")
                if console_mode:
                    display.info(f"Cycle {cycle_count} started")
                watchdog.update_heartbeat()
                
                # Call monitor_plays_continuously to execute a full monitoring cycle
                try:
                    monitor_plays_continuously()
                except Exception as e:
                    error_msg = f"Error in monitoring: {str(e)}"
                    logging.error(error_msg)
                    if console_mode:
                        display.error(error_msg)
                
                # Keep the heartbeat update but without the inner loop
                polling_interval = config.get('monitoring', 'polling_interval', default=30)
                time.sleep(polling_interval)
                watchdog.update_heartbeat()
                
                if console_mode:
                    display.info(f"Cycle {cycle_count} completed")
                
            except KeyboardInterrupt:
                logging.info("KeyboardInterrupt received")
                if console_mode:
                    display.info("\nShutdown requested. Cleaning up...")
                break
            except Exception as e:
                error_msg = f"Error in main loop: {str(e)}"
                logging.error(error_msg)
                if console_mode:
                    display.error(error_msg)
                watchdog.update_heartbeat()
                logging.info("Heartbeat updated after error")
                time.sleep(10)
        
    except Exception as e:
        error_msg = f"System error: {str(e)}"
        logging.error(error_msg)
        if console_mode:
            display.error(error_msg)
        raise
    finally:
        if 'watchdog' in locals():
            logging.info("Stopping watchdog monitoring")
            watchdog.stop_monitoring()
        if console_mode:
            display.info("Shutdown complete")

def main():
    parser = argparse.ArgumentParser(description='Goldflipper Trading System')
    parser.add_argument('--mode', choices=['console', 'service', 'install', 'remove', 'update'],
                       default='console', help='Run mode')
    
    args = parser.parse_args()
    
    if args.mode == 'console':
        run_trading_system(console_mode=True)
    elif args.mode in ['install', 'remove', 'update']:
        # Handle service installation commands
        if args.mode == 'install':
            win32serviceutil.HandleCommandLine(GoldflipperService, argv=['', '--startup', 'auto', 'install'])
        elif args.mode == 'remove':
            win32serviceutil.HandleCommandLine(GoldflipperService, argv=['', 'remove'])
        elif args.mode == 'update':
            win32serviceutil.HandleCommandLine(GoldflipperService, argv=['', 'update'])
    elif args.mode == 'service':
        # Run as a Windows service
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(GoldflipperService)
        servicemanager.StartServiceCtrlDispatcher()

if __name__ == "__main__":
    main()
