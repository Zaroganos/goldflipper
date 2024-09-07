ascii_art = """\
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
Revision: 0.1
Welcome to Project Goldflipper.
"""
print(ascii_art)
import os
import logging
from goldflipper.core import monitor_plays_continuously

# ==================================================
# SETUP AND CONFIGURATION
# ==================================================
# Configure logging and set up necessary paths.

def setup_logging():
    # Get the path to the directory containing the 'goldflipper' folder
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(base_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, 'app_run.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),  # Log to console
            logging.FileHandler(log_file)  # Log to file
        ]
    )

# ==================================================
# RUN SCRIPT
# ==================================================
# Main entry point for starting the continuous monitoring and execution of plays.

def main():
    # Set up logging
    setup_logging()
    
    logging.info("Starting the Goldflipper continuous monitoring and execution process...")
    
    # Start monitoring plays continuously
    monitor_plays_continuously()

if __name__ == "__main__":
    main()
