import os
import logging
from goldflipper.core import monitor_plays_continuously

# ==================================================
# SETUP AND CONFIGURATION
# ==================================================
# Configure logging and set up necessary paths.

def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
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
