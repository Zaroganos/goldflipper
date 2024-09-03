import os
import logging
from datetime import datetime
import yfinance as yf
from goldflipper.json_parser import load_play  # Import the JSON parser for loading plays
from goldflipper.alpaca_client import get_alpaca_client  # Get the Alpaca client connection

# Debugging information
print(f"Python path in core.py: {os.sys.path}")
print(f"Current working directory in core.py: {os.getcwd()}")

# ==================================================
# 1. LOGGING CONFIGURATION
# ==================================================
# Configure logging to work relative to the script's location, ensuring it works across different machines.

script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, '../logs')

if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

log_file = os.path.join(logs_dir, 'app.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# ==================================================
# 2. MARKET DATA RETRIEVAL
# ==================================================

def get_market_data(symbol="AAPL"):
    """
    Fetch the latest market data using yfinance.

    Parameters:
    - symbol (str): The stock symbol to retrieve data for.

    Returns:
    - DataFrame: Historical stock data as a pandas DataFrame.
    """
    logging.info(f"Fetching market data for {symbol}...")
    data = yf.download(symbol, period="1d", interval="1m")
    logging.info(f"Market data for {symbol} fetched successfully.")
    return data

# ==================================================
# 3. STRATEGY EVALUATION
# ==================================================

def evaluate_strategy(symbol, market_data, play):
    """
    Evaluate the trading strategy based on market data and JSON play.

    Parameters:
    - symbol (str): The stock symbol being evaluated.
    - market_data (DataFrame): The market data to analyze.
    - play (dict): The parsed play data from the JSON file.

    Returns:
    - bool: True if the trade conditions defined in the play are met, otherwise False.
    """
    logging.info(f"Evaluating strategy for {symbol} using play: {play.get('symbol', 'Unnamed')}...")

    entry_point = play.get("entry_point", 0)
    last_price = market_data["Close"].iloc[-1]

    if last_price <= entry_point:
        logging.info(f"Condition met: {last_price} <= {entry_point}")
        return True
    else:
        logging.info(f"Condition not met: {last_price} > {entry_point}")
        return False

# ==================================================
# 4. ORDER PLACEMENT
# ==================================================

def place_order(symbol, play):
    """
    Place an order for a stock using Alpaca API.

    Parameters:
    - symbol (str): The stock symbol to buy/sell.
    - play (dict): The parsed play data from the JSON file.
    """
    logging.info(f"Placing order for {play['contracts']} contracts of {symbol} using Alpaca...")

    client = get_alpaca_client()

    try:
        order_details = {
            'symbol': symbol,
            'qty': play['contracts'],
            'side': 'buy' if play['trade_type'] == 'CALL' else 'sell',
            'type': 'market',
            'time_in_force': 'gtc'
        }
        # Place order via Alpaca client (actual implementation can vary based on your alpaca_client.py)
        client.submit_order(order_details)
        logging.info(f"Order placed successfully for {play['contracts']} contracts of {symbol}.")
    except Exception as e:
        logging.error(f"Error placing order: {e}")

# ==================================================
# 5. MAIN TRADE EXECUTION FLOW
# ==================================================

def execute_trade(play_file):
    """
    Main function to execute the trade using a JSON play.

    Parameters:
    - play_file (str): Path to the JSON file containing the trading play.
    """
    logging.info("Starting trade execution...")

    play = load_play(play_file)
    if play is None:
        logging.error("Failed to load play. Aborting trade execution.")
        return

    symbol = play.get("symbol", "AAPL")
    market_data = get_market_data(symbol)

    if evaluate_strategy(symbol, market_data, play):
        place_order(symbol, play)
    else:
        logging.info("No trade signal generated.")

    logging.info("Trade execution finished.")

# ==================================================
# MAIN SCRIPT EXECUTION
# ==================================================

if __name__ == "__main__":
    plays_dir = os.path.join(script_dir, '..', 'plays')
    play_files = [os.path.join(plays_dir, f) for f in os.listdir(plays_dir) if f.endswith('.json')]

    for play_file in play_files:
        execute_trade(play_file)
