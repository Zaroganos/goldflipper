import os
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import yfinance as yf
from goldflipper.json_parser import load_play
from goldflipper.alpaca_client import get_alpaca_client
from alpaca.trading.requests import GetOptionContractsRequest, LimitOrderRequest, StopOrderRequest, MarketOrderRequest, ClosePositionRequest
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce, AssetStatus
from alpaca.common.exceptions import APIError

# ==================================================
# 1. LOGGING CONFIGURATION
# ==================================================
# Configure logging to ensure information is recorded both in the console and log files.

def setup_logging():
    # Get the absolute path to the goldflipper directory
    goldflipper_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    logs_dir = os.path.join(goldflipper_dir, 'logs')

    # Create logs directory if it doesn't exist
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    # Configure root logger
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler()])

    # Create file handlers
    info_handler = logging.FileHandler(os.path.join(logs_dir, 'app.log'))
    info_handler.setLevel(logging.INFO)
    error_handler = logging.FileHandler(os.path.join(logs_dir, 'error.log'))
    error_handler.setLevel(logging.ERROR)

    # Create formatters and add it to handlers
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    info_handler.setFormatter(formatter)
    error_handler.setFormatter(formatter)

    # Add handlers to the root logger
    logging.getLogger('').addHandler(info_handler)
    logging.getLogger('').addHandler(error_handler)

    logging.info("Logging initialized successfully")

# Call the setup_logging function at the beginning of the script
setup_logging()

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

def evaluate_opening_strategy(symbol, market_data, play):
    logging.info(f"Evaluating opening strategy for {symbol} using play data...")
    
    entry_point = play.get("entry_point", 0)
    last_price = market_data["Close"].iloc[-1]
    trade_type = play.get("trade_type", "").upper()

    if trade_type == "CALL":
        condition_met = last_price >= entry_point
        comparison = ">=" if condition_met else "<"
    elif trade_type == "PUT":
        condition_met = last_price <= entry_point
        comparison = "<=" if condition_met else ">"
    else:
        logging.error(f"Invalid trade type: {trade_type}. Must be CALL or PUT.")
        return False

    logging.info(f"Opening condition {'met' if condition_met else 'not met'}: "
                 f"Current price {last_price} {comparison} entry point {entry_point} for {trade_type}")
    
    return condition_met

def evaluate_closing_strategy(symbol, market_data, play):
    logging.info(f"Evaluating closing strategy for {symbol} using play data...")
    
    take_profit = play['take_profit']['stock_price']  # Changed from play.get("take_profit", {}).get("value", 0)
    stop_loss = play['stop_loss']['stock_price']  # Changed from play.get("stop_loss", {}).get("values", [])[-1]
    last_price = market_data["Close"].iloc[-1]

    if last_price >= take_profit or last_price <= stop_loss:
        logging.info(f"Closing condition met: Current stock price {last_price}, Take profit {take_profit}, Stop loss {stop_loss}")
        return True
    else:
        logging.info(f"Closing condition not met: Current stock price {last_price}")
        return False

# ==================================================
# 4. ORDER PLACEMENT
# ==================================================
# Function to place an order through the Alpaca API.

def get_option_contract(play):
    client = get_alpaca_client()
    symbol = play['symbol']
    expiration_date = datetime.strptime(play['expiration_date'], "%m/%d/%Y").date()
    strike_price = play['strike_price']  # Strike price must be a string

    req = GetOptionContractsRequest(
        underlying_symbols=[symbol],
        expiration_date=expiration_date,
        strike_price_gte=strike_price,
        strike_price_lte=strike_price,
        type=play['trade_type'].lower(),
        status=AssetStatus.ACTIVE
    )
    
    res = client.get_option_contracts(req)
    contracts = res.option_contracts
    if contracts:
        logging.info(f"Option contract found: {contracts[0]}")
        return contracts[0]
    else:
        logging.error(f"No option contract found for {symbol} with given parameters")
        return None

def calculate_limit_buy_price(contract):
    try:
        option_ticker = yf.Ticker(contract.root_symbol)
        option_data = option_ticker.option_chain(contract.expiration_date.strftime('%Y-%m-%d'))

        options = option_data.calls if contract.type == 'call' else option_data.puts
        option = options[(options['strike'] == contract.strike_price) & (options['contractSymbol'] == contract.symbol)]
        if not option.empty:
            bid = option.iloc[0]['bid']
            ask = option.iloc[0]['ask']
            limit_buy_price = bid + (ask - bid) * 0.25  # Set limit buy price to 25% above the bid price
            logging.info(f"Calculated limit buy price for {contract.symbol}: {limit_buy_price}")
            return limit_buy_price
        else:
            logging.error(f"No option data found for {contract.symbol}")
            return None
    except Exception as e:
        logging.error(f"Error calculating limit buy price for {contract.symbol}: {str(e)}")
        return None

def open_position(play):
    client = get_alpaca_client()
    contract = get_option_contract(play)
    
    if not contract:
        logging.error("Failed to retrieve option contract. Aborting order placement.")
        return False
    
    logging.info(f"Opening position for {play['contracts']} contracts of {contract.symbol}")
    
    try:
        # Default to market order unless explicitly set to limit
        order_type = play.get('order_type', 'market').lower()
        
        if order_type == 'limit':
            logging.info("Limit order requested, but not implemented yet. Defaulting to market order.")
            # TODO: Implement limit order logic here in the future
        
        # Use market order for all cases for now
        order_req = MarketOrderRequest(
            symbol=contract.symbol,
            qty=play['contracts'],
            side=OrderSide.BUY,
            type=OrderType.MARKET,
            time_in_force=TimeInForce.DAY
        )
        
        order = client.submit_order(order_req)
        logging.info(f"Position opened successfully for {play['contracts']} contracts of {contract.symbol} using MARKET order.")
        return True
    except Exception as e:
        logging.error(f"Error opening position: {e}")
        return False

def close_position(play):
    """
    Close an existing position by selling the specified number of option contracts.

    Parameters:
    - play (dict): A dictionary containing play details such as symbol, contracts, etc.

    Returns:
    - bool: True if the position was closed successfully, False otherwise.
    """
    client = get_alpaca_client()
    contract = get_option_contract(play)

    if not contract:
        logging.error("Failed to retrieve option contract. Aborting position closure.")
        return False

    symbol = contract.symbol
    qty = play.get('contracts', 1)  # Default to 1 if not specified

    logging.info(f"Attempting to close position: {qty} contracts of {symbol}")

    try:
        # Create a ClosePositionRequest with the desired quantity
        close_req = ClosePositionRequest(
            qty=qty  # Ensure qty is an integer
        )

        # Utilize the high-level close_position method from Alpaca-py
        response = client.close_position(
            symbol_or_asset_id=symbol,
            close_options=close_req
        )

        logging.info(f"Successfully closed position: {qty} contracts of {symbol}")
        return True

    except APIError as api_err:
        logging.error(f"API Error closing position for {symbol}: {api_err}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error closing position for {symbol}: {e}")
        return False

def monitor_and_manage_position(play, entry_price):
    client = get_alpaca_client()
    contract = get_option_contract(play)
    
    if not contract:
        return False

    tp_price = play['take_profit']['value']
    sl_price = play['stop_loss']['values'][-1]  # Use the last stop loss value
    tp_order_placed = False
    sl_order_placed = False

    while True:
        try:
            position = client.get_open_position(contract.symbol)
            if position is None:
                logging.info(f"Position {contract.symbol} closed.")
                break

            current_price = float(client.get_latest_trade(contract.symbol).price)
            logging.info(f"Current price for {contract.symbol}: {current_price}")

            if not tp_order_placed and current_price >= tp_price:
                tp_order = LimitOrderRequest(
                    symbol=contract.symbol,
                    qty=play['contracts'],
                    side=OrderSide.SELL,
                    type=OrderType.LIMIT,
                    time_in_force=TimeInForce.DAY,
                    limit_price=tp_price,
                )
                client.submit_order(tp_order)
                logging.info(f"Take profit order placed for {contract.symbol}")
                tp_order_placed = True

            if not sl_order_placed and current_price <= sl_price:
                sl_order = StopOrderRequest(
                    symbol=contract.symbol,
                    qty=play['contracts'],
                    side=OrderSide.SELL,
                    type=OrderType.STOP,
                    time_in_force=TimeInForce.GTC,
                    stop_price=sl_price,
                )
                client.submit_order(sl_order)
                logging.info(f"Stop loss order placed for {contract.symbol}")
                sl_order_placed = True

            if tp_order_placed or sl_order_placed:
                break

            time.sleep(10)  # Wait for 10s before checking again
        except Exception as e:
            logging.error(f"Error monitoring position {contract.symbol}: {str(e)}")
            break

# ==================================================
# 5. MOVE PLAY TO APPROPRIATE FOLDER
# ==================================================
# Function to move a play file to the appropriate plays folder after execution.

def move_play_to_open(play_file):
    open_dir = os.path.join(os.path.dirname(play_file), '..', 'open')
    os.makedirs(open_dir, exist_ok=True)
    new_path = os.path.join(open_dir, os.path.basename(play_file))
    os.rename(play_file, new_path)
    logging.info(f"Moved play to open folder: {new_path}")

def move_play_to_closed(play_file):
    closed_dir = os.path.join(os.path.dirname(play_file), '..', 'closed')
    os.makedirs(closed_dir, exist_ok=True)
    new_path = os.path.join(closed_dir, os.path.basename(play_file))
    os.rename(play_file, new_path)
    logging.info(f"Moved play to closed folder: {new_path}")

# ==================================================
# 6. MAIN TRADE EXECUTION FLOW
# ==================================================
# Main function to orchestrate the strategy execution using the loaded plays.

def execute_trade(play_file, play_type):
    logging.info(f"Executing {play_type} play: {play_file}")

    play = load_play(play_file)
    if play is None:
        logging.error(f"Failed to load play {play_file}. Aborting trade execution.")
        return False

    symbol = play.get("symbol")
    if not symbol:
        logging.error(f"Play {play_file} is missing 'symbol'. Skipping execution.")
        return False

    market_data = get_market_data(symbol)

    if play_type == "new":
        if evaluate_opening_strategy(symbol, market_data, play):
            if open_position(play):
                move_play_to_open(play_file)  # Move this line here immediately after opening the position
                monitor_and_manage_position(play, play['entry_point'])  # Continue monitoring after moving
                return True
    elif play_type == "open":
        if evaluate_closing_strategy(symbol, market_data, play):
            if close_position(play):
                move_play_to_closed(play_file)
                return True

    return False

# ==================================================
# 7. CONTINUOUS MONITORING AND EXECUTION
# ==================================================
# Monitor the plays directory continuously and execute plays as conditions are met.

def monitor_plays_continuously():
    plays_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'plays'))
    
    logging.info(f"Monitoring plays directory: {plays_dir}")

    while True:
        try:
            logging.info("Checking for new and open plays...")
            
            for play_type in ['new', 'open']:
                play_dir = os.path.join(plays_dir, play_type)
                play_files = [os.path.join(play_dir, f) for f in os.listdir(play_dir) if f.endswith('.json')]
                
                for play_file in play_files:
                    if execute_trade(play_file, play_type):
                        logging.info(f"Successfully executed {play_type} play: {play_file}")
                    else:
                        logging.info(f"Conditions not met for {play_type} play: {play_file}")

            logging.info("Cycle complete. Waiting for the next cycle...")

        except Exception as e:
            logging.error(f"An error occurred during play monitoring: {e}")

        time.sleep(30)  # Wait for 30 seconds before re-evaluating

if __name__ == "__main__":
    monitor_plays_continuously()

