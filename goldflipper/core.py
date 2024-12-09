import os
import logging
import time
import pandas as pd
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
    # Get the path to the directory containing the 'goldflipper' folder
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(base_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, 'app_run.log')
    
    # Configure handlers with proper encoding
    console_handler = logging.StreamHandler()
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

# Call the setup_logging function at the beginning of the script
setup_logging()

# ==================================================
# 2. MARKET DATA RETRIEVAL
# ==================================================
# Function to fetch the latest market data using yfinance.

def get_market_data(symbol):
    logging.info(f"Fetching market data for {symbol}...")
    data = yf.download(symbol, period="1d", interval="1m") #DOUBLE CHECK THIS! CAN INTERVAL BE DECREASED??
    logging.info(f"Market data for {symbol} fetched successfully.")
    return data

"""Function to fetch the latest option premium data using yfinance."""

def get_option_premium_data(ticker, expiration_date=None, strike_price=None, option_type='call'):
    """
    Fetch the last price of the option premium for a specific contract.
    
    Parameters:
    - ticker (str): Stock symbol
    - expiration_date (str, optional): Option expiration date in 'YYYY-MM-DD' format
    - strike_price (float, optional): Strike price of the option
    - option_type (str): 'call' or 'put', defaults to 'call'
    
    Returns:
    - float: Last price of the option premium
             Returns None if data unavailable
    """
    logging.info(f"Fetching option premium data for {ticker}...")
    
    try:
        stock = yf.Ticker(ticker)
        
        # Get available expiration dates
        available_dates = stock.options
        if not available_dates:
            logging.error(f"No option data available for {ticker}")
            return None
            
        # Use provided expiration date or default to nearest
        target_date = expiration_date if expiration_date in available_dates else available_dates[0]
        
        # Get option chain
        chain = stock.option_chain(target_date)
        
        # Select calls or puts
        options_data = chain.calls if option_type.lower() == 'call' else chain.puts
        
        # Filter by strike price if provided
        if strike_price:
            options_data = options_data[options_data['strike'] == float(strike_price)]
            
        if options_data.empty:
            logging.warning(f"No matching options found for {ticker} with given parameters")
            return None
            
        # Get the last price
        last_price = options_data.iloc[0]['lastPrice']
        
        logging.info(f"Option premium data fetched successfully for {ticker}")
        return last_price
        
    except Exception as e:
        logging.error(f"Error fetching option premium data for {ticker}: {str(e)}")
        return None

def get_current_option_premium(play):
    """Get the current option premium for a play."""
    try:
        last_price = get_option_premium_data(
            ticker=play['symbol'],
            expiration_date=datetime.strptime(play['expiration_date'], '%m/%d/%Y').strftime('%Y-%m-%d'),
            strike_price=float(play['strike_price']),
            option_type=play['trade_type']
        )
        return last_price
    except Exception as e:
        logging.error(f"Error getting option premium: {e}")
        return None

# ==================================================
# 3. STRATEGY EVALUATION
# ==================================================
# Functions to evaluate whether the market conditions meet the strategy criteria based on trade type.

def evaluate_opening_strategy(symbol, market_data, play):
    logging.info(f"Evaluating opening strategy for {symbol} using play data...")

    entry_point = play.get("entry_point", 0)
    last_price = market_data["Close"].iloc[-1]
    trade_type = play.get("trade_type", "").upper()

    # Define a buffer of ±5 cents
    buffer = 0.05
    lower_bound = entry_point - buffer
    upper_bound = entry_point + buffer

    if trade_type == "CALL" or trade_type == "PUT":
        # Check if the last price is within ±5 cents of the entry point
        condition_met = lower_bound <= last_price <= upper_bound
        comparison = f"between {lower_bound:.2f} and {upper_bound:.2f}" if condition_met else f"not within ±{buffer:.2f} of entry point {entry_point:.2f}"
    else:
        logging.error(f"Invalid trade type: {trade_type}. Must be CALL or PUT.")
        return False

    logging.info(f"Opening condition {'met' if condition_met else 'not met'}: "
                 f"Current price {last_price:.2f} is {comparison} for {trade_type}")

    return condition_met

def evaluate_closing_strategy(symbol, market_data, play):
    """Evaluate if closing conditions are met for either stock price or option premium."""
    logging.info(f"Evaluating closing strategy for {symbol} using play data...")
    
    last_price = market_data["Close"].iloc[-1]
    trade_type = play.get("trade_type", "").upper()
    
    # Check if using stock price or premium percentage
    using_stock_price = play['take_profit'].get('stock_price') is not None
    
    if using_stock_price:
        # Original stock price based logic
        take_profit = play['take_profit']['stock_price']
        stop_loss = play['stop_loss']['stock_price']
        
        if trade_type == "CALL":
            profit_condition = last_price >= take_profit
            loss_condition = last_price <= stop_loss
        elif trade_type == "PUT":
            profit_condition = last_price <= take_profit
            loss_condition = last_price >= stop_loss
        else:
            logging.error(f"Invalid trade type: {trade_type}")
            return False
    else:
        # Premium percentage based logic
        current_premium = get_current_option_premium(play)
        if current_premium is None:
            logging.error("Could not get current option premium")
            return False
            
        entry_premium = play.get('entry_premium', current_premium)  # Store initial premium when opening position
        tp_pct = play['take_profit']['premium_pct'] / 100
        sl_pct = play['stop_loss']['premium_pct'] / 100
        
        # Calculate target prices
        tp_target = entry_premium * (1 + tp_pct)
        sl_target = entry_premium * (1 - sl_pct)
        
        profit_condition = current_premium >= tp_target
        loss_condition = current_premium <= sl_target
        
        logging.info(f"Premium conditions - Current: ${current_premium:.2f}, TP: ${tp_target:.2f} ({tp_pct*100}%), SL: ${sl_target:.2f} ({sl_pct*100}%)")

    if profit_condition:
        logging.info("Take profit condition met")
    if loss_condition:
        logging.info("Stop loss condition met")
        
    return profit_condition or loss_condition

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

# LIMIT BUY orders... CURRENTLY INACTIVE!
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
            logging.info(f"Calculated limit buy price for {contract.symbol}: {limit_buy_price:.2f}")
            return limit_buy_price
        else:
            logging.error(f"No option data found for {contract.symbol}")
            return None
    except Exception as e:
        logging.error(f"Error calculating limit buy price for {contract.symbol}: {str(e)}")
        return None

def open_position(play, play_file):
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
            time_in_force=TimeInForce.DAY,
        )
        response = client.submit_order(order_req)
        logging.info(f"Order submitted: {response}")

        return True

    except APIError as api_err:
        logging.error(f"API Error placing order: {api_err}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error placing order: {e}")
        return False

def close_position(play):
    client = get_alpaca_client()
    contract_symbol = play.get('option_contract_symbol')  # This should be the full option symbol

    if not contract_symbol:
        logging.error("Option contract symbol not found in play. Cannot close position.")
        return False

    qty = play.get('contracts', 1)  # Default to 1 if not specified
    
    try:
        # Get current stock price using yfinance
        current_stock_price = yf.Ticker(play['symbol']).info.get('regularMarketPrice')
        current_premium = get_current_option_premium(play)
        
        # Check if this is a TP or SL closure by checking conditions
        is_tp = False
        if play['take_profit'].get('stock_price') is not None and current_stock_price is not None:
            is_tp = current_stock_price >= play['take_profit']['stock_price']
        if play['take_profit'].get('premium_pct') is not None and current_premium is not None:
            is_tp = is_tp or (current_premium >= play['take_profit']['TP_option_prem'])
        
        # Handle limit orders
        if (is_tp and play['take_profit'].get('order_type') == 'limit') or \
           (not is_tp and play['stop_loss'].get('order_type') == 'limit'):
            
            if is_tp:
                limit_price = play['take_profit'].get('TP_option_prem')
                logging.info(f"Take Profit triggered - Using TP premium target: ${limit_price:.4f}")
            else:
                limit_price = play['stop_loss'].get('SL_option_prem')
                logging.info(f"Stop Loss triggered - Using SL premium target: ${limit_price:.4f}")
            
            if limit_price is None:
                limit_price = current_premium
                logging.info(f"Using current premium as limit price: ${limit_price:.4f}")
            
            # Round limit price to 2 decimal places
            limit_price = round(float(limit_price), 2)
            logging.info(f"Rounded limit price to: ${limit_price:.2f}")
            
            order_req = LimitOrderRequest(
                symbol=contract_symbol,
                qty=qty,
                limit_price=limit_price,
                side=OrderSide.SELL,
                type=OrderType.LIMIT,
                time_in_force=TimeInForce.DAY
            )
            logging.info(f"Creating limit sell order with limit price: ${limit_price:.2f}")
            response = client.submit_order(order_req)
        
        # Handle market orders using ClosePositionRequest
        else:
            response = client.close_position(
                symbol_or_asset_id=contract_symbol,
                close_options=ClosePositionRequest(qty=str(qty))
            )
            logging.info(f"Creating market sell order via ClosePositionRequest for {'TP' if is_tp else 'SL'}")
            
        logging.info(f"Successfully submitted close order: {response}")
        return True
    except APIError as api_err:
        logging.error(f"API Error closing position for {contract_symbol}: {api_err}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error closing position for {contract_symbol}: {e}")
        return False

def monitor_and_manage_position(play, play_file):
    """Monitor position using appropriate price type."""
    client = get_alpaca_client()
    contract_symbol = play.get('option_contract_symbol')
    underlying_symbol = play.get('symbol')
    
    if not contract_symbol or not underlying_symbol:
        logging.error("Missing required symbols")
        return False

    # Get current market data
    market_data = None
    current_premium = None
    
    # Check if we need stock price monitoring
    if play['take_profit'].get('stock_price') is not None or play['stop_loss'].get('stock_price') is not None:
        market_data = get_market_data(underlying_symbol)  # Use existing get_market_data function
        if market_data is None:
            logging.error(f"Failed to get market data for {underlying_symbol}")
            return False
        current_price = market_data['Close'].iloc[-1]
        logging.info(f"Current stock price for {underlying_symbol}: ${current_price:.2f}")

    # Check if we need premium monitoring
    if play['take_profit'].get('premium_pct') is not None or play['stop_loss'].get('premium_pct') is not None:
        current_premium = get_current_option_premium(play)
        if current_premium is None:
            logging.error("Failed to get current option premium.")
            return False
        if market_data is None:
            market_data = pd.DataFrame({'Close': [current_premium]})
        logging.info(f"Current option premium for {contract_symbol}: ${current_premium:.4f}")

        # Log premium targets if using limit orders
        if play['take_profit'].get('order_type') == 'limit' and play['take_profit'].get('TP_option_prem'):
            logging.info(f"TP limit order target: ${play['take_profit']['TP_option_prem']:.4f}")
        if play['stop_loss'].get('order_type') == 'limit' and play['stop_loss'].get('SL_option_prem'):
            logging.info(f"SL limit order target: ${play['stop_loss']['SL_option_prem']:.4f}")

    # Verify position is still open
    position = client.get_open_position(contract_symbol)
    if position is None:
        logging.info(f"Position {contract_symbol} closed.")
        return True

    # Evaluate closing conditions
    if evaluate_closing_strategy(underlying_symbol, market_data, play):
        close_attempts = 0
        max_attempts = 3
        
        while close_attempts < max_attempts:
            logging.info(f"Attempting to close position: Attempt {close_attempts + 1}")
            if close_position(play):
                move_play_to_closed(play_file)
                logging.info("Position closed successfully")
                return True
            close_attempts += 1
            logging.warning(f"Close attempt {close_attempts} failed. Retrying...")
            time.sleep(2)
        
        logging.error("Failed to close position after maximum attempts")
        return False

    return True

# ==================================================
# 5. MOVE PLAY TO APPROPRIATE FOLDER
# ==================================================
# Functions to move a play file to the appropriate plays folder after execution or upon conditional trigger.

# Move to NEW (for OTO triggered plays)
def move_play_to_new(play_file):
    new_dir = os.path.join(os.path.dirname(play_file), '..', 'new')
    os.makedirs(new_dir, exist_ok=True)
    new_path = os.path.join(new_dir, os.path.basename(play_file))
    os.rename(play_file, new_path)
    logging.info(f"Moved play to NEW folder: {new_path}")

# Move to OPEN (for plays whose BUY condition has hit)
def move_play_to_open(play_file):
    open_dir = os.path.join(os.path.dirname(play_file), '..', 'open')
    os.makedirs(open_dir, exist_ok=True)
    new_path = os.path.join(open_dir, os.path.basename(play_file))
    os.rename(play_file, new_path)
    logging.info(f"Moved play to OPEN folder: {new_path}")

# Move to CLOSED (for plays whose TP or SL condition has hit)
def move_play_to_closed(play_file):
    closed_dir = os.path.join(os.path.dirname(play_file), '..', 'closed')
    os.makedirs(closed_dir, exist_ok=True)
    new_path = os.path.join(closed_dir, os.path.basename(play_file))
    os.rename(play_file, new_path)
    logging.info(f"Moved play to CLOSED folder: {new_path}")

# Move to EXPIRED (for plays which have expired, and OCO triggered plays)
def move_play_to_expired(play_file):
    expired_dir = os.path.join(os.path.dirname(play_file), '..', 'expired')
    os.makedirs(expired_dir, exist_ok=True)
    new_path = os.path.join(expired_dir, os.path.basename(play_file))
    os.rename(play_file, new_path)
    logging.info(f"Moved play to EXPIRED folder: {new_path}")
       
    
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
    trade_type = play.get("trade_type", "").upper()
    if not symbol or trade_type not in ["CALL", "PUT"]:
        logging.error(f"Play {play_file} is missing 'symbol' or has invalid 'trade_type'. Skipping execution.")
        return False

    market_data = get_market_data(symbol)
    # OPENING a Play
    if play_type == "new":
        if evaluate_opening_strategy(symbol, market_data, play):
            if open_position(play, play_file):
                move_play_to_open(play_file)
                monitor_and_manage_position(play, play_file)
                return True
            
    # CONDITIONAL PLAYS: Activate OCO / OTO upon play opening for PRIMARY plays
    if play.get("class") == "PRIMARY":
        if "OCO_trigger" in play:
            oco_trigger_play = play["OCO_trigger"]
            oco_trigger_path = os.path.join(os.path.dirname(play_file), '..', 'new', oco_trigger_play)
            try:
                if os.path.exists(oco_trigger_path):
                    if move_play_to_expired(oco_trigger_play):  # Add return value check
                        logging.info(f"Moved OCO_trigger play to expired folder: {oco_trigger_play}")
                    else:
                        logging.error(f"Failed to move OCO trigger play: {oco_trigger_play}")
                else:
                    logging.error(f"OCO trigger play file not found: {oco_trigger_play}")
            except Exception as e:
                logging.error(f"Error processing OCO trigger: {str(e)}")

        if "OTO_trigger" in play:
            oto_trigger_play = play["OTO_trigger"]
            try:
                if os.path.exists(oto_trigger_play):
                    if move_play_to_new(oto_trigger_play):  # Add return value check
                        logging.info(f"Moved OTO_trigger play to new folder: {oto_trigger_play}")
                    else:
                        logging.error(f"Failed to move OTO trigger play: {oto_trigger_play}")
                else:
                    logging.error(f"OTO trigger play file not found: {oto_trigger_play}")
            except Exception as e:
                logging.error(f"Error processing OTO trigger: {str(e)}")
    # CLOSING a Play
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

            # Check for expired plays in the "new" folder
            new_play_dir = os.path.join(plays_dir, 'new')
            play_files = [os.path.join(new_play_dir, f) for f in os.listdir(new_play_dir) if f.endswith('.json')]
            current_date = datetime.now().date()  # Get the current date
            
            for play_file in play_files:
                play = load_play(play_file)
                if play and 'play_expiration_date' in play:
                    expiration_date = datetime.strptime(play['play_expiration_date'], "%m/%d/%Y").date()
                    if expiration_date < current_date:
                        move_play_to_expired(play_file)  # Move expired play
                        logging.info(f"Moved expired play to expired folder: {play_file}")

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