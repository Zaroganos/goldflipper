import os
import logging
from datetime import datetime
import yfinance as yf
from goldflipper.json_parser import load_play  # Import the JSON parser
from goldflipper.alpaca_client import get_alpaca_client  # Import Alpaca client connection
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce


# ==================================================
# 1. LOGGING CONFIGURATION
# ==================================================
# Configure logging to ensure information is recorded both in the console and a log file.

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
# Function to fetch the latest market data using yfinance.

def get_market_data(symbol):
    logging.info(f"Fetching market data for {symbol}...")
    data = yf.download(symbol, period="1d", interval="1m")
    logging.info(f"Market data for {symbol} fetched successfully.")
    return data

# ==================================================
# 3. STRATEGY EVALUATION
# ==================================================
# Function to evaluate whether the market conditions meet the strategy criteria.

def evaluate_strategy(symbol, market_data, play):
    logging.info(f"Evaluating strategy for {symbol} using play data...")
    
    entry_point = play.get("entry_point", 0)
    last_price = market_data["Close"].iloc[-1]

    if last_price <= entry_point:
        logging.info(f"Condition met: Current price {last_price} <= entry point {entry_point}")
        return True
    else:
        logging.info(f"Condition not met: Current price {last_price} > entry point {entry_point}")
        return False

# ==================================================
# 4. ORDER PLACEMENT
# ==================================================
# Function to place an order through the Alpaca API.

def place_order(symbol, play):
    logging.info(f"Placing order for {play['contracts']} contracts of {symbol}...")
    client = get_alpaca_client()

    try:
        # Create the MarketOrderRequest with the required parameters
        order_details = MarketOrderRequest(
            symbol=symbol,
            qty=play['contracts'],
            side=OrderSide.BUY if play['trade_type'].upper() == 'CALL' else OrderSide.SELL,
            time_in_force=TimeInForce.GTC  # Good Till Canceled
        )

        # Submit the order via the Alpaca client
        client.submit_order(order_details)
        logging.info(f"Order placed successfully for {play['contracts']} contracts of {symbol}.")
    except Exception as e:
        logging.error(f"Error placing order: {e}")

# ==================================================
# 5. MAIN TRADE EXECUTION FLOW
# ==================================================
# Main function to orchestrate the strategy execution using the loaded plays.

def execute_trade(play_file):
    logging.info("Starting trade execution...")
    
    play = load_play(play_file)
    if play is None:
        logging.error("Failed to load play. Aborting trade execution.")
        return

    symbol = play.get("symbol")
    market_data = get_market_data(symbol)

    if evaluate_strategy(symbol, market_data, play):
        place_order(symbol, play)
    else:
        logging.info("No trade signal generated.")
    
    logging.info("Trade execution finished.")

# ==================================================
# MAIN SCRIPT EXECUTION
# ==================================================
# Execute the strategy for each play in the plays directory.

if __name__ == "__main__":
    plays_dir = os.path.abspath(os.path.join(script_dir, '..', 'plays'))
    play_files = [os.path.join(plays_dir, f) for f in os.listdir(plays_dir) if f.endswith('.json')]

    for play_file in play_files:
        execute_trade(play_file)
