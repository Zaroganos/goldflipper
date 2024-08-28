import os
import logging
from datetime import datetime
import yfinance as yf
from goldflipper.json_parser import load_play
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from goldflipper.alpaca_client import get_alpaca_client  # Correctly import the function

# Debugging information
print(f"Python path in core.py: {os.sys.path}")
print(f"Current working directory in core.py: {os.getcwd()}")

# ==================================================
# 1. LOGGING CONFIGURATION
# ==================================================
# We configure logging to work relative to the script's location, 
# ensuring it works across different machines.

# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Define the logs directory relative to the script's location
logs_dir = os.path.join(script_dir, '../logs')

# Ensure the logs directory exists
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# Define the log file path
log_file = os.path.join(logs_dir, 'app.log')

# Setup basic logging: output to both file and console
logging.basicConfig(
    level=logging.INFO,  # Set log level to INFO
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),  # Log to file
        logging.StreamHandler()  # Also log to console
    ]
)

# ==================================================
# 2. MARKET DATA RETRIEVAL
# ==================================================
# The function below fetches historical market data using yfinance.

def get_market_data(symbol="AAPL"):
    """
    Fetch the latest market data using yfinance.

    Parameters:
    - symbol (str): The stock symbol to retrieve data for. Defaults to "AAPL".

    Returns:
    - DataFrame: Historical stock data as a pandas DataFrame.
    """
    logging.info(f"Fetching market data for {symbol}...")
    data = yf.download(symbol, start="2023-01-01", end=datetime.now().strftime("%Y-%m-%d"))
    logging.info(f"Market data for {symbol} fetched successfully.")
    return data

# ==================================================
# 3. STRATEGY EVALUATION
# ==================================================
# This function evaluates the market data to determine whether conditions
# are favorable for making a trade.

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
    logging.info(f"Evaluating strategy for {symbol} using play: {play.get('name', 'Unnamed')}...")

    # Example condition: Check if the last price is above the specified value
    condition = play.get("conditions", {})
    if condition.get("type") == "price_above":
        last_price = market_data["Close"].iloc[-1]
        if last_price > condition.get("value", 0):
            logging.info(f"Condition met: {last_price} > {condition['value']}")
            return True
        else:
            logging.info(f"Condition not met: {last_price} <= {condition['value']}")
            return False
    logging.info("No valid condition found in the play.")
    return False

# ==================================================
# 4. ORDER PLACEMENT
# ==================================================
# This function places an order for a stock using the Alpaca API.

def place_order(symbol, quantity):
    """
    Place an order for a stock using Alpaca API, following the best practices
    outlined in the Alpaca-py notebook.

    Parameters:
    - symbol (str): The stock symbol to buy/sell.
    - quantity (int): The number of shares to buy/sell.

    Returns:
    - None
    """
    logging.info(f"Placing order for {quantity} shares of {symbol} using Alpaca...")

    # Get the Alpaca client
    client = get_alpaca_client()

    try:
        # Create a MarketOrderRequest object
        market_order_data = MarketOrderRequest(
            symbol=symbol,
            qty=quantity,
            side=OrderSide.BUY,  # or OrderSide.SELL based on your strategy
            time_in_force=TimeInForce.GTC  # Good till canceled
        )

        # Submit the order via the Alpaca client
        client.submit_order(market_order_data)
        logging.info(f"Order placed successfully for {quantity} shares of {symbol}.")
    except Exception as e:
        logging.error(f"Error placing order: {e}")

# ==================================================
# 5. MAIN TRADE EXECUTION FLOW
# ==================================================
# This is the main function that orchestrates the entire trading process.

def execute_trade(play_file):
    """
    Main function to execute the trade using a JSON play.

    Parameters:
    - play_file (str): Path to the JSON file containing the trading play.
    """
    logging.info("Starting trade execution...")

    # Load the play from the JSON file
    play = load_play(play_file)
    if play is None:
        logging.error("Failed to load play. Aborting trade execution.")
        return

    # Step 1: Fetch market data
    symbol = play.get("symbol", "AAPL")  # Default to AAPL if symbol is missing
    market_data = get_market_data(symbol)

    # Step 2: Evaluate trading strategy
    trade_signal = evaluate_strategy(symbol, market_data, play)

    # Step 3: Place order if trade signal is True
    if trade_signal:
        place_order(symbol, play.get("quantity", 10))  # Use play's quantity or default to 10
    else:
        logging.info("No trade signal generated.")

    logging.info("Trade execution finished.")
