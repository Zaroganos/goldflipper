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
from goldflipper.core import monitor_plays_continuously
from goldflipper.startup_test import run_startup_tests
import sys
from goldflipper.utils.display import TerminalDisplay as display

# ==================================================
# SETUP AND CONFIGURATION
# ==================================================
# Configure logging and set up necessary paths.

def setup_logging():
    """Configure file logging only - no console output"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(base_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'app_run.log')
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    
    # File handler only - no console handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

def initialize_system():
    """Initialize the trading system and perform startup checks."""
    display.header("Initializing GoldFlipper Trading System")
    
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
    else:
        display.error("\nSome Tests Failed - Check Details Above")
        return False
    
    return True

# ==================================================
# RUN SCRIPT
# ==================================================
# Main entry point for starting the continuous monitoring and execution of plays.

def main():
    # Set up file logging first
    setup_logging()
    
    # Now we can use both systems:
    # - display.info() for terminal output
    # - logging.info() for file logging
    logging.info("Starting GoldFlipper trading system")
    display.info("Starting GoldFlipper trading system")
    
    if initialize_system():
        monitor_plays_continuously()
    else:
        display.error("System initialization failed")
        logging.error("System initialization failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
