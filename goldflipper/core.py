import os
import logging
import time
from datetime import datetime
import yfinance as yf
from goldflipper.json_parser import load_play
from goldflipper.alpaca_client import get_alpaca_client
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
# 5. MOVE PLAY TO CLOSED FOLDER
# ==================================================
# Function to move a play file to the closed plays folder after execution.

def move_play_to_closed(play_file):
    closed_dir = os.path.join(os.path.dirname(play_file), 'closed')
    if not os.path.exists(closed_dir):
        os.makedirs(closed_dir)
    
    closed_play_file = os.path.join(closed_dir, os.path.basename(play_file))
    os.rename(play_file, closed_play_file)
    logging.info(f"Moved executed play to {closed_play_file}")

# ==================================================
# 6. MAIN TRADE EXECUTION FLOW
# ==================================================
# Main function to orchestrate the strategy execution using the loaded plays.

def execute_trade(play_file):
    logging.info(f"Executing play: {play_file}")

    play = load_play(play_file)
    if play is None:
        logging.error(f"Failed to load play {play_file}. Aborting trade execution.")
        return

    symbol = play.get("symbol")
    if not symbol:
        logging.error(f"Play {play_file} is missing 'symbol'. Skipping execution.")
        return

    entry_point = play.get("entry_point")
    if entry_point is None:
        logging.error(f"Play {play_file} is missing 'entry_point'. Skipping execution.")
        return

    market_data = get_market_data(symbol)

    if evaluate_strategy(symbol, market_data, play):
        place_order(symbol, play)
        move_play_to_closed(play_file)
    else:
        logging.info(f"No trade signal generated for play {play_file}.")

    logging.info("Trade execution finished.")

# ==================================================
# 7. CONTINUOUS MONITORING AND EXECUTION
# ==================================================
# Monitor the plays directory continuously and execute plays as conditions are met.

def monitor_plays_continuously():
    # Ensure the path is relative to the script's directory
    plays_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'plays'))
    
    logging.info(f"Monitoring plays directory: {plays_dir}")

    while True:
        try:
            logging.info("Checking for new plays...")
            play_files = [os.path.join(plays_dir, f) for f in os.listdir(plays_dir) if f.endswith('.json')]

            if not play_files:
                logging.info("No new plays found.")
                
            for play_file in play_files:
                execute_trade(play_file)

            logging.info("Cycle complete. Waiting for the next cycle...")

        except Exception as e:
            logging.error(f"An error occurred during play monitoring: {e}")

        time.sleep(60)  # Wait for 60 seconds before re-evaluating


if __name__ == "__main__":
    monitor_plays_continuously()