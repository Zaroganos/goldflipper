import logging
import logging.config
from config import config
from goldflipper.data import data_retrieval, data_processing, data_storage
from goldflipper.strategies import swings_option_branching_brackets
from goldflipper.execution import alpaca_client, order_management
from goldflipper.backtesting import backtester

def setup_logging():
    logging.config.fileConfig(config.LOGGING_CONFIG_FILE)

def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Goldflipper Trading System...")

    # Retrieve and preprocess data
    raw_data = data_retrieval.fetch_data(config.TRADE_SYMBOL)
    processed_data = data_processing.preprocess_data(raw_data)
    data_storage.store_data(processed_data)

    # Initialize the Alpaca trading client
    alpaca = alpaca_client.initialize_client(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)

    # Run the trading strategy
    strategy = swings_option_branching_brackets.SwingsOptionBranchingBrackets(alpaca, processed_data)
    strategy.run()

    # Perform backtesting
    backtester.run_backtesting(processed_data, strategy.parameters)

    logger.info("Goldflipper Trading System finished.")

if __name__ == "__main__":
    main()
