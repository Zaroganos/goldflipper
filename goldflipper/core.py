import logging

logging.basicConfig(filename='logs/app.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def execute_trade():
    logging.info("Starting trade execution...")
    # Your trading logic here
    logging.info("Trade execution finished.")
