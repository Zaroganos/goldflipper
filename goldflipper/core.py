import os
import logging
import time
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import yfinance as yf
from goldflipper.json_parser import load_play
from goldflipper.alpaca_client import get_alpaca_client
from goldflipper.config.config import config
from alpaca.trading.requests import (
    GetOptionContractsRequest, 
    LimitOrderRequest, 
    MarketOrderRequest, 
    ClosePositionRequest
)
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce, AssetStatus
from alpaca.common.exceptions import APIError
import json
from goldflipper.tools.option_data_fetcher import calculate_greeks


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
    """
    Fetch market data for a given symbol using configuration settings.
    
    Args:
        symbol (str): The stock symbol to fetch data for
        
    Returns:
        pandas.DataFrame: Market data with timestamp index and OHLCV columns
        
    Logs:
        INFO: Fetch attempt and success
        ERROR: Any failures during data retrieval
    """
    logging.info(f"Fetching market data for {symbol}...")
    try:
        data = yf.download(
            symbol,
            period=config.get('market_data', 'period', default='1d'),
            interval=config.get('market_data', 'interval', default='1m')
        )
        logging.info(f"Market data for {symbol} fetched successfully.")
        
        if data.empty:
            logging.error(f"No data returned for {symbol}")
            return None
            
        return data
        
    except Exception as e:
        logging.error(f"Error fetching market data for {symbol}: {str(e)}")
        return None

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

def calculate_and_store_premium_levels(play, current_premium):
    """Calculate and store TP/SL premium levels in the play data."""
    if play['take_profit'].get('premium_pct'):
        tp_pct = play['take_profit']['premium_pct'] / 100
        play['take_profit']['TP_option_prem'] = current_premium * (1 + tp_pct)
        
    if play['stop_loss'].get('premium_pct'):
        sl_pct = play['stop_loss']['premium_pct'] / 100
        play['stop_loss']['SL_option_prem'] = current_premium * (1 - sl_pct)
    
    # Add contingency SL premium calculation if it exists
    if play['stop_loss'].get('contingency_premium_pct'):
        contingency_sl_pct = play['stop_loss']['contingency_premium_pct'] / 100
        play['stop_loss']['contingency_SL_option_prem'] = current_premium * (1 - contingency_sl_pct)

def save_play(play, play_file):
    """Save the updated play data to the specified file."""
    try:
        with open(play_file, 'w') as f:
            json.dump(play, f, indent=4)
        logging.info(f"Play data saved to {play_file}")
    except Exception as e:
        logging.error(f"Error saving play data to {play_file}: {e}")

def evaluate_opening_strategy(symbol, market_data, play):
    logging.info(f"Evaluating opening strategy for {symbol} using play data...")

    entry_point = play.get("entry_point", {}).get("stock_price", 0)
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
    """
    Evaluate if closing conditions are met. Supports:
    - Mixed conditions (e.g., TP by stock price, SL by premium %)
    - Multiple conditions (both stock price AND premium % for either TP or SL)
    - Contingency stop loss with primary and backup conditions
    """
    logging.info(f"Evaluating closing strategy for {symbol} using play data...")
    
    last_price = market_data["Close"].iloc[-1]
    trade_type = play.get("trade_type", "").upper()
    
    # Initialize condition flags
    profit_condition = False
    loss_condition = False
    contingency_loss_condition = False

    # Check stock price-based take profit condition
    if play['take_profit'].get('stock_price') is not None:
        if trade_type == "CALL":
            profit_condition = last_price >= play['take_profit']['stock_price']
        elif trade_type == "PUT":
            profit_condition = last_price <= play['take_profit']['stock_price']

    # Get stop loss type
    sl_type = play['stop_loss'].get('SL_type', 'STOP')  # Default to STOP for backward compatibility

    # Check stock price-based stop loss conditions
    if play['stop_loss'].get('stock_price') is not None:
        if trade_type == "CALL":
            loss_condition = last_price <= play['stop_loss']['stock_price']
            # Check contingency condition if applicable
            if sl_type == 'CONTINGENCY' and play['stop_loss'].get('contingency_stock_price') is not None:
                contingency_loss_condition = last_price <= play['stop_loss']['contingency_stock_price']
        elif trade_type == "PUT":
            loss_condition = last_price >= play['stop_loss']['stock_price']
            # Check contingency condition if applicable
            if sl_type == 'CONTINGENCY' and play['stop_loss'].get('contingency_stock_price') is not None:
                contingency_loss_condition = last_price >= play['stop_loss']['contingency_stock_price']

    # Check premium-based conditions if available
    current_premium = get_current_option_premium(play)
    if current_premium is not None:
        # Check premium-based take profit - combines with stock price condition using OR
        if play['take_profit'].get('premium_pct') is not None:
            tp_target = play['take_profit']['TP_option_prem']
            profit_condition = profit_condition or (current_premium >= tp_target)

        # Check premium-based stop loss - combines with stock price condition using OR
        if play['stop_loss'].get('premium_pct') is not None:
            sl_target = play['stop_loss']['SL_option_prem']
            loss_condition = loss_condition or (current_premium <= sl_target)
            
            # Check contingency premium condition if applicable
            if sl_type == 'CONTINGENCY' and play['stop_loss'].get('contingency_premium_pct') is not None:
                contingency_sl_target = play['stop_loss']['contingency_SL_option_prem']
                contingency_loss_condition = contingency_loss_condition or (current_premium <= contingency_sl_target)

    # Log conditions
    if profit_condition:
        logging.info("Take profit condition met")
    if loss_condition:
        logging.info(f"{'Primary' if sl_type == 'CONTINGENCY' else ''} Stop loss condition met")
    if contingency_loss_condition:
        logging.info("Contingency (backup) stop loss condition met")

    # Return tuple with condition flags and stop loss type
    return {
        'should_close': profit_condition or loss_condition or contingency_loss_condition,
        'is_profit': profit_condition,
        'is_primary_loss': loss_condition,
        'is_contingency_loss': contingency_loss_condition,
        'sl_type': sl_type
    }

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

# LIMIT BUY orders... CURRENTLY INACTIVE! this was auto-generated and probably not needed
# def calculate_limit_buy_price(contract):
#     try:
#         option_ticker = yf.Ticker(contract.root_symbol)
#         option_data = option_ticker.option_chain(contract.expiration_date.strftime('%Y-%m-%d'))
#
#        options = option_data.calls if contract.type == 'call' else option_data.puts
#        option = options[(options['strike'] == contract.strike_price) & (options['contractSymbol'] == contract.symbol)]
#        if not option.empty:
#            bid = option.iloc[0]['bid']
#            ask = option.iloc[0]['ask']
#            limit_buy_price = bid + (ask - bid) * 0.25  # Set limit buy price to 25% above the bid price
#            logging.info(f"Calculated limit buy price for {contract.symbol}: {limit_buy_price:.2f}")
#            return limit_buy_price
#        else:
#            logging.error(f"No option data found for {contract.symbol}")
#            return None
#    except Exception as e:
#        logging.error(f"Error calculating limit buy price for {contract.symbol}: {str(e)}")
#        return None

def open_position(play, play_file):
    client = get_alpaca_client()
    contract = get_option_contract(play)
    
    if not contract:
        logging.error("Failed to retrieve option contract. Aborting order placement.")
        return False
    
    # Get current premium before opening position
    current_premium = get_current_option_premium(play)
    if current_premium is None:
        logging.error("Failed to get current option premium. Aborting order placement.")
        return False
        
    # Store the entry premium in the play data's entry_point object
    if 'entry_point' not in play:
        play['entry_point'] = {}
    play['entry_point']['entry_premium'] = current_premium
    logging.info(f"Entry premium: ${current_premium:.4f}")
        
    # Calculate and store TP/SL levels if using premium percentages
    calculate_and_store_premium_levels(play, current_premium)
    
    # Capture Greeks
    delta, theta = capture_greeks(play, current_premium)
    
    # Initialize logging section if it doesn't exist
    if 'logging' not in play:
        play['logging'] = {}
    
    # Store Greeks
    play['logging']['delta_atOpen'] = delta
    play['logging']['theta_atOpen'] = theta
    
    logging.info(f"Greeks at entry - Delta: {delta:.4f}, Theta: {theta:.4f}")
    
    logging.info(f"Opening position for {play['contracts']} contracts of {contract.symbol}")
    try:
        # Create appropriate order request based on order type
        if play.get('entry_point', {}).get('order_type') == 'limit':
            order_req = LimitOrderRequest(
                symbol=contract.symbol,
                qty=play['contracts'],
                limit_price=current_premium,  # Use current premium as limit price
                side=OrderSide.BUY,
                type=OrderType.LIMIT,
                time_in_force=TimeInForce.DAY,
            )
            logging.info(f"Creating limit buy order with limit price: ${current_premium:.4f}")
        else:
            order_req = MarketOrderRequest(
                symbol=contract.symbol,
                qty=play['contracts'],
                side=OrderSide.BUY,
                type=OrderType.MARKET,
                time_in_force=TimeInForce.DAY,
            )
            logging.info("Creating market buy order")

        response = client.submit_order(order_req)
        logging.info(f"Order submitted: {response}")
        
        # Save the updated play data with the entry premium and TP/SL values
        save_play(play, play_file)
        return True
        
    except Exception as e:
        logging.error(f"Error placing order: {e}")
        return False

def close_position(play, close_conditions):
    """
    Close position based on the triggered conditions.
    
    Args:
        play (dict): The play data
        close_conditions (dict): Dict containing condition flags from evaluate_closing_strategy
    """
    client = get_alpaca_client()
    contract_symbol = play.get('option_contract_symbol')

    if not contract_symbol:
        logging.error("Option contract symbol not found in play. Cannot close position.")
        return False

    qty = play.get('contracts', 1)  # Default to 1 if not specified
    
    try:
        # Take profit handling (unchanged)
        if close_conditions['is_profit']:
            if play['take_profit'].get('order_type') == 'limit':
                order_req = LimitOrderRequest(
                    symbol=contract_symbol,
                    qty=qty,
                    limit_price=play['take_profit']['TP_option_prem'],
                    side=OrderSide.SELL,
                    type=OrderType.LIMIT,
                    time_in_force=TimeInForce.DAY
                )
                logging.info(f"Creating take profit limit sell order at ${play['take_profit']['TP_option_prem']:.4f}")
                response = client.submit_order(order_req)
            else:
                response = client.close_position(
                    symbol_or_asset_id=contract_symbol,
                    close_options=ClosePositionRequest(qty=str(qty))
                )
                logging.info("Creating take profit market sell order")
        
        # Stop loss handling
        else:
            # For contingency stop loss
            if close_conditions['sl_type'] == 'CONTINGENCY':
                # Cancel any existing orders first
                try:
                    client.cancel_all_orders()
                    logging.info("Cancelled all existing orders")
                except Exception as e:
                    logging.warning(f"Error canceling existing orders: {e}")
                
                # If backup condition is met, use market order
                if close_conditions['is_contingency_loss']:
                    response = client.close_position(
                        symbol_or_asset_id=contract_symbol,
                        close_options=ClosePositionRequest(qty=str(qty))
                    )
                    logging.info("Creating contingency market sell order")
                # If only primary condition is met, use limit order
                elif close_conditions['is_primary_loss']:
                    order_req = LimitOrderRequest(
                        symbol=contract_symbol,
                        qty=qty,
                        limit_price=play['stop_loss']['SL_option_prem'],
                        side=OrderSide.SELL,
                        type=OrderType.LIMIT,
                        time_in_force=TimeInForce.DAY
                    )
                    logging.info(f"Creating primary stop loss limit sell order at ${play['stop_loss']['SL_option_prem']:.4f}")
                    response = client.submit_order(order_req)
            
            # For regular limit stop loss
            elif play['stop_loss'].get('order_type') == 'limit':
                order_req = LimitOrderRequest(
                    symbol=contract_symbol,
                    qty=qty,
                    limit_price=play['stop_loss']['SL_option_prem'],
                    side=OrderSide.SELL,
                    type=OrderType.LIMIT,
                    time_in_force=TimeInForce.DAY
                )
                logging.info(f"Creating stop loss limit sell order at ${play['stop_loss']['SL_option_prem']:.4f}")
                response = client.submit_order(order_req)
            
            # For regular market stop loss
            else:
                response = client.close_position(
                    symbol_or_asset_id=contract_symbol,
                    close_options=ClosePositionRequest(qty=str(qty))
                )
                logging.info("Creating stop loss market sell order")
        
        logging.info(f"Order submitted: {response}")
        return True
        
    except APIError as api_err:
        logging.error(f"API Error closing position for {contract_symbol}: {api_err}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error closing position for {contract_symbol}: {e}")
        return False

def monitor_and_manage_position(play, play_file):
    """Monitor position using both stock price and premium conditions if configured."""
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
        try:
            current_price = float(client.get_latest_trade(underlying_symbol).price)
            market_data = pd.DataFrame({'Close': [current_price]})
            logging.info(f"Current stock price for {underlying_symbol}: ${current_price:.2f}")
        except Exception as e:
            logging.error(f"Error getting stock price: {e}")
            return False

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
        
        # Log stop loss targets
        sl_type = play['stop_loss'].get('SL_type', 'STOP')
        if sl_type == 'CONTINGENCY':
            if play['stop_loss'].get('SL_option_prem'):
                logging.info(f"Primary SL limit order target: ${play['stop_loss']['SL_option_prem']:.4f}")
            if play['stop_loss'].get('contingency_SL_option_prem'):
                logging.info(f"Backup SL market order target: ${play['stop_loss']['contingency_SL_option_prem']:.4f}")
        elif play['stop_loss'].get('order_type') == 'limit' and play['stop_loss'].get('SL_option_prem'):
            logging.info(f"SL limit order target: ${play['stop_loss']['SL_option_prem']:.4f}")

    # Verify position is still open
    position = client.get_open_position(contract_symbol)
    if position is None:
        logging.info(f"Position {contract_symbol} closed.")
        return True

    # Evaluate closing conditions
    close_conditions = evaluate_closing_strategy(underlying_symbol, market_data, play)
    if close_conditions['should_close']:
        close_attempts = 0
        max_attempts = 3
        
        while close_attempts < max_attempts:
            logging.info(f"Attempting to close position: Attempt {close_attempts + 1}")
            if close_position(play, close_conditions):  # Pass close_conditions to close_position
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
    # Update status in JSON
    with open(play_file, 'r') as f:
        play_data = json.load(f)
    play_data['status'] = 'new'
    with open(play_file, 'w') as f:
        json.dump(play_data, f, indent=4)
    
    # Existing move logic
    new_dir = os.path.join(os.path.dirname(play_file), '..', 'new')
    os.makedirs(new_dir, exist_ok=True)
    new_path = os.path.join(new_dir, os.path.basename(play_file))
    os.rename(play_file, new_path)
    logging.info(f"Moved play to NEW folder: {new_path}")

# Move to OPEN (for plays whose BUY condition has hit)
def move_play_to_open(play_file):
    # Update status in JSON
    with open(play_file, 'r') as f:
        play_data = json.load(f)
    play_data['status'] = 'open'
    with open(play_file, 'w') as f:
        json.dump(play_data, f, indent=4)
    
    # Existing move logic
    open_dir = os.path.join(os.path.dirname(play_file), '..', 'open')
    os.makedirs(open_dir, exist_ok=True)
    new_path = os.path.join(open_dir, os.path.basename(play_file))
    os.rename(play_file, new_path)
    logging.info(f"Moved play to OPEN folder: {new_path}")

# Move to CLOSED (for plays whose TP or SL condition has hit)
def move_play_to_closed(play_file):
    # Update status in JSON
    with open(play_file, 'r') as f:
        play_data = json.load(f)
    play_data['status'] = 'closed'
    with open(play_file, 'w') as f:
        json.dump(play_data, f, indent=4)
    
    # Existing move logic
    closed_dir = os.path.join(os.path.dirname(play_file), '..', 'closed')
    os.makedirs(closed_dir, exist_ok=True)
    new_path = os.path.join(closed_dir, os.path.basename(play_file))
    os.rename(play_file, new_path)
    logging.info(f"Moved play to CLOSED folder: {new_path}")

# Move to EXPIRED (for plays which have expired, and OCO triggered plays)
def move_play_to_expired(play_file):
    # Update status in JSON
    with open(play_file, 'r') as f:
        play_data = json.load(f)
    play_data['status'] = 'expired'
    with open(play_file, 'w') as f:
        json.dump(play_data, f, indent=4)

    # Existing move logic
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

    # Validate order types first
    if not validate_play_order_types(play):
        logging.error(f"Invalid order types in play {play_file}. Aborting trade execution.")
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
                
                # Handle conditional plays if this is a PRIMARY play
                if play.get("class") == "PRIMARY":
                    plays_base_dir = os.path.dirname(os.path.dirname(play_file))
                    
                    # Handle OCO trigger
                    if "OCO_trigger" in play:
                        oco_file = play["OCO_trigger"]
                        oco_path = os.path.join(plays_base_dir, 'new', oco_file)
                        if os.path.exists(oco_path):
                            logging.info(f"Processing OCO trigger: {oco_file}")
                            move_play_to_expired(oco_path)
                        else:
                            logging.error(f"OCO trigger file not found: {oco_path}")

                    # Handle OTO trigger
                    if "OTO_trigger" in play:
                        oto_file = play["OTO_trigger"]
                        oto_path = os.path.join(plays_base_dir, 'new', oto_file)
                        if os.path.exists(oto_path):
                            logging.info(f"Processing OTO trigger: {oto_file}")
                            move_play_to_new(oto_path)
                        else:
                            logging.error(f"OTO trigger file not found: {oto_path}")
                
                return True
            
    # MONITORING an Open Play
    elif play_type == "open":
        return monitor_and_manage_position(play, play_file)
    
    # Handle Expired Play
    elif play_type == "expired":
        move_play_to_expired(play_file)
        return True
        
    return False

def validate_play_order_types(play):
    """Validate order types in play data."""
    valid_types = ['market', 'limit']
    
    # Validate entry order type
    entry_type = play.get('entry_order_type')
    if entry_type is None:
        logging.error("Missing entry_order_type in play")
        return False
    if entry_type not in valid_types:
        logging.error(f"Invalid entry_order_type: {entry_type}")
        return False
    
    # Validate take profit order type
    tp = play.get('take_profit', {})
    tp_type = tp.get('order_type')
    if tp_type is not None and tp_type not in valid_types:
        logging.error(f"Invalid take_profit order_type: {tp_type}")
        return False
    
    # Validate stop loss order type(s)
    sl = play.get('stop_loss', {})
    sl_type = sl.get('SL_type')
    sl_order_type = sl.get('order_type')
    
    if sl_type == 'CONTINGENCY':
        if not isinstance(sl_order_type, list) or len(sl_order_type) != 2:
            logging.error("Contingency stop loss must have array of two order types")
            return False
        if sl_order_type != ['limit', 'market']:
            logging.error("Contingency stop loss must have ['limit', 'market'] order types")
            return False
    elif sl_order_type is not None and sl_order_type not in valid_types:
        logging.error(f"Invalid stop_loss order_type: {sl_order_type}")
        return False
    
    return True

# ==================================================
# 7. CONTINUOUS MONITORING AND EXECUTION
# ==================================================
# Monitor the plays directory continuously and execute plays as conditions are met.

def get_sleep_interval(minutes_to_open):
    """Return appropriate sleep interval based on time to market open."""
    if minutes_to_open > 240:    # More than 4 hours
        return 600               # Check every 10 minutes
    elif minutes_to_open > 120:  # More than 2 hours
        return 300               # Check every 5 minutes
    elif minutes_to_open > 30:   # More than 30 minutes
        return 120               # Check every 2 minutes
    elif minutes_to_open > 5:    # More than 5 minutes
        return 60                # Check every minute
    else:
        return 30                # Check every 30 seconds when close to open

MAX_RETRIES = 3

def validate_market_hours():
    """
    Validate if current time is within configured market hours.
    Returns True if trading should proceed, False if should pause.
    """
    # Skip validation if disabled in settings
    if not config.get('market_hours', 'enabled', default=True):
        return True
        
    # Get configured timezone with error handling
    try:
        market_tz = ZoneInfo(config.get('market_hours', 'timezone', default='America/New_York'))
    except Exception as e:
        logging.error(f"Invalid timezone configuration: {e}. Defaulting to America/New_York")
        market_tz = ZoneInfo('America/New_York')
    
    current_time = datetime.now(market_tz)
    current_time_only = current_time.time()
    
    # Check for weekends first
    if current_time.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        next_market_day = current_time + timedelta(days=(7 - current_time.weekday()))
        try:
            start_time = config.get('market_hours', 'regular_hours', 'start', default='09:30')
            next_market_day = next_market_day.replace(
                hour=int(start_time.split(':')[0]),
                minute=int(start_time.split(':')[1]),
                second=0
            )
        except (ValueError, AttributeError) as e:
            logging.error(f"Invalid market start time format: {e}. Using default 09:30")
            next_market_day = next_market_day.replace(hour=9, minute=30, second=0)
            
        wait_hours = (next_market_day - current_time).total_seconds() / 3600
        logging.info(f"Market is closed for the weekend. Current time in {market_tz}: {current_time_only}")
        logging.info(f"Next market open in approximately {int(wait_hours)} hours")
        return False, int(wait_hours * 60)  # Return minutes to next open
    
    # Get market hours with error handling
    try:
        market_open = datetime.strptime(config.get('market_hours', 'regular_hours', 'start', default='09:30'), '%H:%M').time()
        market_close = datetime.strptime(config.get('market_hours', 'regular_hours', 'end', default='16:00'), '%H:%M').time()
    except ValueError as e:
        logging.error(f"Invalid time format in configuration: {e}. Using default market hours")
        market_open = datetime.strptime('09:30', '%H:%M').time()
        market_close = datetime.strptime('16:00', '%H:%M').time()
    
    # Check if within regular market hours
    is_market_open = market_open <= current_time_only <= market_close
    
    # Handle extended hours if enabled
    if not is_market_open and config.get('market_hours', 'extended_hours', 'enabled', default=False):
        try:
            pre_market = datetime.strptime(config.get('market_hours', 'extended_hours', 'pre_market_start', default='04:00'), '%H:%M').time()
            after_market = datetime.strptime(config.get('market_hours', 'extended_hours', 'after_market_end', default='20:00'), '%H:%M').time()
            is_market_open = pre_market <= current_time_only <= after_market
        except ValueError as e:
            logging.error(f"Invalid extended hours format: {e}. Using default extended hours")
            pre_market = datetime.strptime('04:00', '%H:%M').time()
            after_market = datetime.strptime('20:00', '%H:%M').time()
            is_market_open = pre_market <= current_time_only <= after_market
    
    if not is_market_open:
        # Create next_open datetime with timezone awareness
        next_open = datetime.combine(current_time.date(), market_open)
        next_open = next_open.replace(tzinfo=market_tz)
        
        if current_time_only > market_close:
            next_open += timedelta(days=1)
        elif current_time_only < market_open:
            # Already on the correct day, no adjustment needed
            pass
            
        wait_minutes = int((next_open - current_time).total_seconds() / 60)
        
        logging.info(f"Market is closed. Current time in {market_tz}: {current_time_only}")
        logging.info(f"Next market open in approximately {wait_minutes} minutes")
        return False, wait_minutes
        
    logging.debug(f"Validating market hours at {datetime.now()}")
    logging.info(f"Market is open. Current time in {market_tz}: {current_time_only}")
    return True, 0

def is_market_holiday(date):
    """Check if given date is a US market holiday."""
    holidays = [
        (1, 1),    # New Year's Day
        (1, 16),   # Martin Luther King Jr. Day (3rd Monday in January)
        (2, 20),   # Presidents Day (3rd Monday in February)
        (5, 29),   # Memorial Day (Last Monday in May)
        (7, 4),    # Independence Day
        (12, 25),  # Christmas
    ]
    return (date.month, date.day) in holidays

def monitor_plays_continuously():
    plays_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'plays'))
    
    logging.info(f"Monitoring plays directory: {plays_dir}")

    while True:
        try:
            # Check market hours before processing
            is_open, minutes_to_open = validate_market_hours()
            if not is_open:
                sleep_time = get_sleep_interval(minutes_to_open)
                time.sleep(sleep_time)
                continue
                
            logging.info("\n" + "="*50)
            logging.info("Checking for new and open plays...")

            # Check for expired plays in the "new" folder
            new_play_dir = os.path.join(plays_dir, 'new')
            play_files = [os.path.join(new_play_dir, f) for f in os.listdir(new_play_dir) if f.endswith('.json')]
            current_date = datetime.now().date()  # Get the current date
            
            # Handle expired plays (keeping existing functionality)
            for play_file in play_files:
                play = load_play(play_file)
                if play and 'play_expiration_date' in play:
                    expiration_date = datetime.strptime(play['play_expiration_date'], "%m/%d/%Y").date()
                    if expiration_date < current_date:
                        move_play_to_expired(play_file)  # Move expired play
                        logging.info(f"Moved expired play to expired folder: {play_file}")

            # THIS IS NEW FOR PRINTING CURRENT OPTION DATA. IF SOMETHING IS WRONG, DELETE THIS
            # Print current option data for all active plays
            for play_type in ['new', 'open']:
                play_dir = os.path.join(plays_dir, play_type)
                play_files = [os.path.join(play_dir, f) for f in os.listdir(play_dir) if f.endswith('.json')]
                
                for play_file in play_files:
                    play = load_play(play_file)
                    if play:
                        try:
                            # Format expiration date
                            exp_date = datetime.strptime(play['expiration_date'], '%m/%d/%Y').strftime('%Y-%m-%d')
                            
                            # Get option data
                            stock = yf.Ticker(play['symbol'])
                            chain = stock.option_chain(exp_date)
                            
                            # Select appropriate chain
                            options_data = chain.calls if play['trade_type'].lower() == 'call' else chain.puts
                            
                            # Filter for specific strike
                            strike = float(play['strike_price'])
                            option = options_data[options_data['strike'] == strike]
                            
                            if not option.empty:
                                current_price = stock.info.get('regularMarketPrice', 0)
                                opt = option.iloc[0]
                                
                                logging.info(f"\nPlay: {play['symbol']} {play['trade_type']} ${strike} exp:{exp_date}")
                                logging.info(f"Status: [{play_type}]")
                                logging.info(f"Stock Price: ${current_price:.2f}")
                                logging.info(f"Option Data:")
                                logging.info(f"  Bid: ${opt['bid']:.2f}")
                                logging.info(f"  Ask: ${opt['ask']:.2f}")
                                logging.info(f"  Last: ${opt['lastPrice']:.2f}")
                                logging.info(f"  Volume: {int(opt['volume'])}")
                                logging.info(f"  Open Interest: {int(opt['openInterest'])}")
                                logging.info(f"  Implied Vol: {opt['impliedVolatility']:.2%}")
                            
                        except Exception as e:
                            logging.error(f"Error fetching option data for {play['symbol']}: {str(e)}")

            # Execute trades (keeping existing functionality)
            for play_type in ['new', 'open']:
                play_dir = os.path.join(plays_dir, play_type)
                play_files = [os.path.join(play_dir, f) for f in os.listdir(play_dir) if f.endswith('.json')]
                
                for play_file in play_files:
                    if execute_trade(play_file, play_type):
                        logging.info(f"Successfully executed {play_type} play: {play_file}")
                    else:
                        logging.info(f"Conditions not met for {play_type} play: {play_file}")

            logging.info("\nCycle complete. Waiting for next cycle...")
            logging.info("="*50 + "\n")

        except Exception as e:
            logging.error(f"An error occurred during play monitoring: {e}")

        time.sleep(30)  # Wait for 30 seconds before re-evaluating

# ==================================================
# 8. ANCILLARY FUNCTIONS
# ==================================================
# Functions to support the main trade execution flow.

def capture_greeks(play, current_premium):
    """Capture Delta and Theta values for the option play at position opening"""
    try:
        # Format expiration date for yfinance
        expiration_date = datetime.strptime(play['expiration_date'], '%m/%d/%Y').strftime('%Y-%m-%d')
        
        # Get market data using existing yfinance setup
        stock = yf.Ticker(play['symbol'])
        chain = stock.option_chain(expiration_date)
        underlying_price = stock.info['regularMarketPrice']
        
        # Get appropriate chain and prepare data
        options_data = chain.calls if play['trade_type'].lower() == 'call' else chain.puts
        options_data['option_type'] = play['trade_type'].lower()
        
        # Filter for our specific strike
        strike = float(play['strike_price'])
        filtered_data = options_data[options_data['strike'] == strike]
        
        if filtered_data.empty:
            logging.error(f"No matching option found for strike {strike}")
            return None, None
            
        # Use existing calculate_greeks function from option_data_fetcher
        greeks_data = calculate_greeks(filtered_data, underlying_price, expiration_date)
        
        if not greeks_data.empty:
            delta = greeks_data.iloc[0]['delta']
            theta = greeks_data.iloc[0]['theta']
            return delta, theta
            
        return None, None
        
    except Exception as e:
        logging.error(f"Error capturing Greeks: {e}")  # Updated error message
        return None, None

if __name__ == "__main__":
    monitor_plays_continuously()