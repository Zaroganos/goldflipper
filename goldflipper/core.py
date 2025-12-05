import os
import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from goldflipper.json_parser import load_play
from goldflipper.alpaca_client import get_alpaca_client
from goldflipper.config.config import config
from goldflipper.utils.display import TerminalDisplay as display
from alpaca.trading.requests import (
    GetOptionContractsRequest, 
    LimitOrderRequest, 
    MarketOrderRequest, 
    ClosePositionRequest
)
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce, AssetStatus
from goldflipper.strategy.base import OrderAction
from alpaca.common.exceptions import APIError
import json
from goldflipper.tools.option_data_fetcher import calculate_greeks  # Currently unused. Kept for potential future analytics
from goldflipper.utils.atomic_io import atomic_write_json
from goldflipper.strategy.trailing import has_trailing_enabled, update_trailing_levels
from uuid import UUID
from typing import Optional, Dict, Any
from goldflipper.data.market.manager import MarketDataManager
from goldflipper.utils.exe_utils import get_plays_dir

# Import shared strategy modules (Phase 2 extraction)
# These imports allow core.py functions to delegate to shared modules
from goldflipper.strategy.shared.play_manager import (
    UUIDEncoder as _SharedUUIDEncoder,
    PlayManager as _SharedPlayManager,
    save_play as _shared_save_play,
    save_play_improved as _shared_save_play_improved,
    move_play_to_new as _shared_move_to_new,
    move_play_to_pending_opening as _shared_move_to_pending_opening,
    move_play_to_open as _shared_move_to_open,
    move_play_to_pending_closing as _shared_move_to_pending_closing,
    move_play_to_closed as _shared_move_to_closed,
    move_play_to_expired as _shared_move_to_expired,
    move_play_to_temp as _shared_move_to_temp,
)
from goldflipper.strategy.shared.evaluation import (
    calculate_and_store_price_levels as _shared_calc_price_levels,
    calculate_and_store_premium_levels as _shared_calc_premium_levels,
    evaluate_opening_strategy as _shared_eval_opening,
    evaluate_closing_strategy as _shared_eval_closing,
)

# ==================================================
# 1. BROKERAGE DATA RETRIEVAL
# ==================================================
# Functions to retrieve and validate data from the Alpaca brokerage API.

def get_order_info(order_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific order.
    
    Args:
        order_id (str): The Alpaca order ID
        
    Returns:
        Optional[Dict]: Order information including status, filled quantity, 
                       filled price, and other relevant details
    """
    client = get_alpaca_client()
    try:
        order = client.get_order_by_id(order_id)
        return {
            'id': str(order.id),
            'status': order.status,
            'filled_qty': order.filled_qty,
            'filled_avg_price': order.filled_avg_price,
            'created_at': order.created_at,
            'updated_at': order.updated_at,
            'submitted_at': order.submitted_at,
            'filled_at': order.filled_at,
            'expired_at': order.expired_at,
            'canceled_at': order.canceled_at,
            'failed_at': order.failed_at,
            'replaced_at': order.replaced_at,
            'replaced_by': order.replaced_by,
            'replaces': order.replaces
        }
    except Exception as e:
        logging.error(f"Error getting order info: {str(e)}")
        display.error(f"Error getting order info: {str(e)}")
        return None

def get_position_info(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific position.
    
    Args:
        symbol (str): The symbol of the position (e.g., 'AAPL_123456C00380000')
        
    Returns:
        Optional[Dict]: Position information including quantity, 
                       current price, and other relevant details
    """
    client = get_alpaca_client()
    try:
        position = client.get_open_position(symbol)
        return {
            'symbol': position.symbol,
            'qty': position.qty,
            'avg_entry_price': position.avg_entry_price,
            'current_price': position.current_price,
            'lastday_price': position.lastday_price,
            'unrealized_pl': position.unrealized_pl,
            'unrealized_plpc': position.unrealized_plpc,
            'market_value': position.market_value,
            'cost_basis': position.cost_basis
        }
    except Exception as e:
        logging.error(f"Error getting position info: {str(e)}")
        display.error(f"Error getting position info: {str(e)}")
        return None

def get_all_orders(status: str = 'open') -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Get all orders with a specific status.
    
    Args:
        status (str): Order status to filter by ('open', 'closed', 'all')
        
    Returns:
        Optional[Dict]: Dictionary of order IDs mapping to their information
    """
    client = get_alpaca_client()
    try:
        # The new API doesn't use status as a parameter
        # Instead, we should filter the results after getting them
        orders = client.get_orders()
        
        # Filter orders based on status parameter
        if status != 'all':
            orders = [order for order in orders if order.status == status]
            
        return {
            str(order.id): {
                'symbol': order.symbol,
                'status': order.status,
                'filled_qty': order.filled_qty,
                'filled_avg_price': order.filled_avg_price,
                'created_at': order.created_at
            }
            for order in orders
        }
    except Exception as e:
        logging.error(f"Error getting orders: {str(e)}")
        display.error(f"Error getting orders: {str(e)}")
        return None

def get_all_positions() -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Get information about all open positions.
    
    Returns:
        Optional[Dict]: Dictionary of symbols mapping to their position information
    """
    client = get_alpaca_client()
    try:
        positions = client.get_all_positions()
        return {
            position.symbol: {
                'qty': position.qty,
                'avg_entry_price': position.avg_entry_price,
                'current_price': position.current_price,
                'unrealized_pl': position.unrealized_pl,
                'market_value': position.market_value
            }
            for position in positions
        }
    except Exception as e:
        logging.error(f"Error getting positions: {str(e)}")
        display.error(f"Error getting positions: {str(e)}")
        return None

# ==================================================
# 2. MARKET DATA RETRIEVAL
# ==================================================
# Functions to fetch market data using the abstracted market data system.

# Add at the top of the file
_market_data_manager = None  # Global singleton instance

def get_market_data_manager() -> MarketDataManager:
    """Get or create the singleton MarketDataManager instance"""
    global _market_data_manager
    if _market_data_manager is None:
        _market_data_manager = MarketDataManager()
    return _market_data_manager

def get_stock_price(symbol: str) -> Optional[float]:
    """Get current stock price."""
    market_data = get_market_data_manager()  # Use singleton instance
    cache_key = f"stock_price:{symbol}"
    cached = market_data.cache.get(cache_key)

    if cached:
        return cached
        
    try:
        price = market_data.get_stock_price(symbol)
        if price is not None:
            # Convert to float if it's a pandas Series
            if hasattr(price, 'item'):
                price = float(price.item())
            logging.info(f"Got fresh stock price for {symbol}: ${price:.2f}")
            return price
            
        logging.error(f"No price data available for {symbol}")
        return None
        
    except Exception as e:
        logging.error(f"Error getting stock price for {symbol}: {str(e)}")
        return None

def get_option_data(option_contract_symbol: str) -> Optional[Dict[str, float]]:
    """Get current option data."""
    market_data = get_market_data_manager()  # Use singleton instance
    cache_key = f"option_quote:{option_contract_symbol}"
    cached = market_data.cache.get(cache_key)
    
    if cached:
        return cached
    
    logging.info(f"CACHE MISS: Fetching fresh option data for {option_contract_symbol}")
    try:
        option_data = market_data.get_option_quote(option_contract_symbol)
        if option_data:
            logging.info(f"Got fresh option data for {option_contract_symbol}")
            return option_data
            
        logging.error(f"No option data available for {option_contract_symbol}")
        return None
        
    except Exception as e:
        logging.error(f"Error getting option data for {option_contract_symbol}: {str(e)}")
        return None


# ==================================================
# 3. STRATEGY EVALUATION
# ==================================================
# Functions to evaluate whether the market conditions meet the strategy criteria based on trade type.

def calculate_and_store_premium_levels(play, option_data):
    """
    Calculate and store TP/SL premium levels in the play data using correct entry price.
    
    Thin wrapper that delegates to strategy.shared.evaluation module.
    """
    _shared_calc_premium_levels(play, option_data)

def calculate_and_store_price_levels(play, entry_stock_price):
    """
    Calculate and store TP/SL stock price levels in the play data.
    
    Thin wrapper that delegates to strategy.shared.evaluation module.
    """
    _shared_calc_price_levels(play, entry_stock_price)

class UUIDEncoder(_SharedUUIDEncoder):
    """
    Custom JSON encoder to handle UUID objects and pandas Series.
    
    Thin wrapper that inherits from strategy.shared.play_manager.UUIDEncoder.
    Kept for backward compatibility with existing code.
    """
    pass

def save_play(play, play_file):
    """
    Save the updated play data to the specified file.
    
    Thin wrapper that delegates to strategy.shared.play_manager module.
    """
    _shared_save_play(play, play_file)


def save_play_improved(play, play_file):
    """
    Improved atomic save for play data (non-breaking: used only by trailing flow).
    
    Thin wrapper that delegates to strategy.shared.play_manager module.
    """
    return _shared_save_play_improved(play, play_file)

def evaluate_opening_strategy(symbol, play):
    """
    Evaluate if opening conditions are met based on stock price and entry point.
    
    Thin wrapper that delegates to strategy.shared.evaluation module.
    """
    return _shared_eval_opening(symbol, play, get_stock_price_fn=get_stock_price)

def evaluate_closing_strategy(symbol, play, play_file=None):
    """
    Evaluate if closing conditions are met.
    
    Thin wrapper that delegates to strategy.shared.evaluation module.
    
    Supports:
    - Mixed conditions (e.g., TP by stock price, SL by premium %)
    - Multiple conditions (both stock price AND premium % for either TP or SL)
    - Contingency stop loss with primary and backup conditions
    - Stock price absolute value
    - Stock price percentage movement
    - Option premium percentage
    
    Args:
        symbol: The underlying symbol
        play: The play data dictionary
        play_file: Optional path to play file - if provided, will save play after calculating missing targets
    
    Returns:
        Dict with condition flags (should_close, is_profit, is_primary_loss, is_contingency_loss, sl_type)
    """
    return _shared_eval_closing(
        symbol, 
        play, 
        play_file,
        get_stock_price_fn=get_stock_price,
        get_option_data_fn=get_option_data,
        save_play_fn=save_play_improved
    )

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
        display.success(f"Option contract found: {contracts[0].symbol}")
        return contracts[0]
    else:
        logging.error(f"No option contract found for {symbol} with given parameters")
        display.error(f"No option contract found for {symbol} with given parameters")
        return None

def open_position(play, play_file):
    client = get_alpaca_client()
    contract = get_option_contract(play)
    
    if not contract:
        logging.error("Failed to retrieve option contract. Aborting order placement.")
        display.error("Failed to retrieve option contract. Aborting order placement.")
        return False
    
    # Initialize status if it doesn't exist
    if 'status' not in play:
        play['status'] = {}
        
    # Update all status fields at once in a single dictionary update
    play['status'].update({
        'order_id': None,
        'order_status': None,
        'position_exists': False,
    })
    
    # Get current stock price before opening position
    entry_stock_price = get_stock_price(play['symbol'])
    if entry_stock_price is None:
        logging.error("Failed to get current stock price. Aborting order placement.")
        display.error("Failed to get current stock price. Aborting order placement.")
        return False
    
    # Calculate and store price movement levels
    calculate_and_store_price_levels(play, entry_stock_price)
    
    # Get current premium before opening position
    option_data = get_option_data(play['option_contract_symbol'])
    if option_data is None:
        logging.error("Failed to get current option premium. Aborting order placement.")
        display.error("Failed to get current option premium. Aborting order placement.")
        return False
        
    # Get entry premium based on entry order type
    entry_order_type = play.get('entry_point', {}).get('order_type', 'limit at bid')
    
    if entry_order_type == 'limit at bid':
        entry_premium = option_data.get('bid', 0.0)
    elif entry_order_type == 'limit at ask':
        entry_premium = option_data.get('ask', 0.0)
    elif entry_order_type == 'limit at mid':
        entry_premium = option_data.get('mid', 0.0)
    else:  # 'limit at last' or 'market'
        entry_premium = option_data.get('last', 0.0)
        
    # Store the entry premium in the play data's entry_point object
    if 'entry_point' not in play:
        play['entry_point'] = {}
    play['entry_point']['entry_premium'] = entry_premium
    logging.info(f"Entry premium ({entry_order_type}): ${entry_premium:.4f}")
    display.price(f"Entry premium ({entry_order_type}): ${entry_premium:.4f}")
        
    # Calculate and store TP/SL levels if using premium percentages
    calculate_and_store_premium_levels(play, option_data)
    
    # Capture Greeks and update logging
    try:
        logging.debug("Capturing Greeks...")
        # NEW: Get Greeks directly from option data
        delta = option_data['delta']
        theta = option_data['theta']
        
        # Initialize logging section if it doesn't exist
        if 'logging' not in play:
            play['logging'] = {}
        
        # Update all logging fields at once
        play['logging'].update({
            'delta_atOpen': delta if delta is not None else 0.0,
            'theta_atOpen': theta if theta is not None else 0.0,
            'datetime_atOpen': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            'price_atOpen': entry_stock_price,
            'premium_atOpen': entry_premium
        })
        
        if delta is not None and theta is not None:
            if delta == 0.0 and theta == 0.0:
                logging.warning(f"Greeks at entry - Delta: {delta:.4f}, Theta: {theta:.4f} (API returned zero values)")
                display.warning(f"Greeks at entry - Delta: {delta:.4f}, Theta: {theta:.4f} (API returned zero values)")
            else:
                logging.info(f"Greeks at entry - Delta: {delta:.4f}, Theta: {theta:.4f}")
                # display.info(f"Greeks at entry - Delta: {delta:.4f}, Theta: {theta:.4f}")
        else:
            logging.warning("Greeks calculation returned None values")
            display.warning("Greeks calculation returned None values")
    except Exception as e:
        logging.error(f"Error during Greeks capture: {str(e)}")
        display.error(f"Error during Greeks capture: {str(e)}")
        
        # Always create logging section even if Greeks capture fails
        # This ensures opening data is recorded even when API fails
        if 'logging' not in play:
            play['logging'] = {}
        
        play['logging'].update({
            'delta_atOpen': 0.0,
            'theta_atOpen': 0.0,
            'datetime_atOpen': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            'price_atOpen': entry_stock_price,
            'premium_atOpen': entry_premium
        })
        
        logging.warning("Greeks capture failed, opening data recorded but with zero Greeks")
        display.warning("Greeks capture failed, opening data recorded but with zero Greeks")
        # Continue with position opening even if Greeks capture fails
    
    # Determine order side based on action field (supports sell_puts STO and other short strategies)
    action_str = play.get('action', 'BTO').upper()
    try:
        order_action = OrderAction.from_string(action_str)
        order_side = OrderSide.BUY if order_action.is_buy() else OrderSide.SELL
    except (ValueError, AttributeError):
        # Default to BUY for backward compatibility
        order_action = OrderAction.BUY_TO_OPEN
        order_side = OrderSide.BUY
        logging.warning(f"Invalid or missing action '{action_str}', defaulting to BTO (BUY)")
    
    side_str = "BUY" if order_side == OrderSide.BUY else "SELL"
    logging.info(f"Opening position for {play['contracts']} contracts of {contract.symbol} (action: {action_str}, side: {side_str})")
    # display.info(f"Opening position for {play['contracts']} contracts of {contract.symbol}")
    
    try:
        # Create appropriate order request based on order type
        order_type = play.get('entry_point', {}).get('order_type', 'limit at bid')  # Default to limit at bid
        is_limit_order = order_type != 'market'
        
        if is_limit_order:
            # Get limit price based on order type
            if order_type == 'limit at bid':
                limit_price = option_data.get('bid', 0.0)
            elif order_type == 'limit at ask':
                limit_price = option_data.get('ask', 0.0)
            elif order_type == 'limit at mid':
                limit_price = option_data.get('mid', 0.0)
            else:
                limit_price = option_data.get('last', 0.0)
                
            # Apply bid price settings if applicable
            if order_type == 'limit at bid' and not config.get('orders', 'bid_price_settings', 'entry', default=True):
                limit_price = option_data.get('last', 0.0)
                logging.info(f"Bid price settings disabled, using last traded price for limit order: ${limit_price:.2f}")
                # display.info(f"Bid price settings disabled, using last traded price for limit order: ${limit_price:.2f}")
            else:
                logging.info(f"Using {order_type} price for limit order: ${limit_price:.2f}")
                # display.info(f"Using {order_type} price for limit order: ${limit_price:.2f}")
                
            # Round limit price to 2 decimal places
            limit_price = round(limit_price, 2)
            order_req = LimitOrderRequest(
                symbol=contract.symbol,
                qty=play['contracts'],
                limit_price=limit_price,
                side=order_side,
                type=OrderType.LIMIT,
                time_in_force=TimeInForce.DAY,
            )
            logging.info(f"Creating limit {side_str} order with limit price: ${limit_price:.2f}")
            # display.info(f"Creating limit {side_str} order with limit price: ${limit_price:.2f}")
            display.status(f"Submitting {'LIMIT' if is_limit_order else 'MARKET'} {side_str} order for {play['contracts']} {contract.symbol}")
        else:
            order_req = MarketOrderRequest(
                symbol=contract.symbol,
                qty=play['contracts'],
                side=order_side,
                type=OrderType.MARKET,
                time_in_force=TimeInForce.DAY,
            )
            logging.info(f"Creating market {side_str} order")
            # display.info(f"Creating market {side_str} order")
            display.status(f"Submitting {'LIMIT' if is_limit_order else 'MARKET'} {side_str} order for {play['contracts']} {contract.symbol}")
            
        response = client.submit_order(order_req)
        logging.info(f"Order submitted: {response}")
        # display.info(f"Order submitted: {response}")
        
        # Update status fields all at once after order placement
        play['status'].update({
            'order_id': str(response.id),  # Convert UUID to string
            'order_status': response.status,
            'play_status': 'PENDING-OPENING' if is_limit_order else 'OPEN'
        })
        
        # Handle different order types appropriately
        if is_limit_order:
            save_play(play, play_file)
            move_play_to_pending_opening(play_file)
            logging.info("Play moved to PENDING-OPENING state upon limit order placement")
            # display.info("Play moved to PENDING-OPENING state upon limit order placement")
        else:
            # For market orders, save and move to OPEN
            save_play(play, play_file)
            new_filepath = move_play_to_open(play_file)
            logging.info("Play moved to OPEN state upon market order placement")
            # display.info("Play moved to OPEN state upon market order placement")
            
            # Handle conditional plays here for market orders
            handle_conditional_plays(play, new_filepath)
            logging.info(f"Conditional OCO / OTO plays handled for {new_filepath}")
            # display.info(f"Conditional OCO / OTO plays handled for {new_filepath}")
        
        return True
        
    except Exception as e:
        logging.error(f"Error placing order: {e}")
        display.error(f"Error placing order: {e}")
        return False

def close_position(play, close_conditions, play_file):
    """Close position based on the triggered conditions."""
    client = get_alpaca_client()
    contract_symbol = play.get('option_contract_symbol')
    
    if not contract_symbol:
        logging.error("Option contract symbol not found in play. Cannot close position.")
        display.error("Option contract symbol not found in play file. Cannot close position.")
        return False
    
    qty = play.get('contracts', 1)  # Default to 1 if not specified
    
    # Determine closing order side based on entry action
    # Long positions (BTO) close with SELL, Short positions (STO) close with BUY
    entry_action_str = play.get('action', 'BTO').upper()
    try:
        entry_action = OrderAction.from_string(entry_action_str)
        # Get the closing action from the entry action
        closing_action = entry_action.get_closing_action()
        close_side = OrderSide.BUY if closing_action.is_buy() else OrderSide.SELL
    except (ValueError, AttributeError):
        # Default to SELL for backward compatibility (closing long positions)
        close_side = OrderSide.SELL
        logging.warning(f"Invalid action '{entry_action_str}', defaulting to SELL for close")
    
    close_side_str = "BUY" if close_side == OrderSide.BUY else "SELL"
    logging.info(f"Closing position with {close_side_str} order (entry was {entry_action_str})")
    
    try:
        # Initialize closing status
        play['status']['closing_order_id'] = None
        play['status']['closing_order_status'] = None
        play['status']['contingency_order_id'] = None
        play['status']['contingency_order_status'] = None
    
        # Get current market data for logging
        current_stock_price = get_stock_price(play['symbol'])
        
        option_data = get_option_data(play['option_contract_symbol'])
        current_premium = option_data['premium'] if option_data else None
    
        # Determine close type and condition
        close_type = (
            'TP' if close_conditions['is_profit'] 
            else 'SL(C)' if close_conditions['is_contingency_loss']
            else 'SL'
        )
        
        # Determine close condition based on what triggered the close
        close_condition = None
        if close_conditions['is_profit']:
            if play['take_profit'].get('stock_price') or play['take_profit'].get('stock_price_pct'):
                close_condition = 'stock_pct' if play['take_profit'].get('stock_price_pct') else 'stock'
            else:
                close_condition = 'premium_pct'
        else:
            if play['stop_loss'].get('stock_price') or play['stop_loss'].get('stock_price_pct'):
                close_condition = 'stock_pct' if play['stop_loss'].get('stock_price_pct') else 'stock'
            else:
                close_condition = 'premium_pct'
        
        # Initialize logging section if it doesn't exist
        if 'logging' not in play:
            play['logging'] = {}
            
        # Update logging data
        play['logging'].update({
            'datetime_atClose': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            'price_atClose': current_stock_price if current_stock_price is not None else 0.0,
            'premium_atClose': current_premium if current_premium is not None else 0.0,
            'close_type': close_type,
            'close_condition': close_condition
        })
    
        # Save initial closing status
        save_play(play, play_file)
    
        # ---- TAKE PROFIT HANDLING ----
        if close_conditions['is_profit']:
            # Get fresh option data
            option_data = get_option_data(play['option_contract_symbol'])
            if option_data is None:
                logging.error("Failed to get current option data.")
                display.error("Failed to get current option data.")
                return False
    
            # Determine limit price based on TP order type
            if play['take_profit'].get('order_type') == 'limit at last':
                limit_price = current_premium
                logging.info(f"Using last traded price for TP limit order: ${limit_price:.2f}")
                # display.info(f"Using last traded price for TP limit order: ${limit_price:.2f}")
            elif play['take_profit'].get('order_type') == 'limit at ask':
                if config.get('orders', 'bid_price_settings', 'take_profit', default=True):
                    if option_data and option_data.get('ask') is not None:
                        limit_price = option_data['ask']
                        logging.info(f"Using ask price for TP limit order: ${limit_price:.2f}")
                        # display.info(f"Using ask price for TP limit order: ${limit_price:.2f}")
                    else:
                        logging.error("Failed to get ask price. Falling back to TP target price.")
                        display.error("Failed to get ask price. Falling back to TP target price.")
                        limit_price = play['take_profit']['TP_option_prem']
                else:
                    limit_price = play['take_profit']['TP_option_prem']
            elif play['take_profit'].get('order_type') == 'limit at mid':
                if config.get('orders', 'bid_price_settings', 'take_profit', default=True):
                    if option_data and option_data.get('bid') is not None and option_data.get('ask') is not None:
                        limit_price = (option_data['bid'] + option_data['ask']) / 2
                        logging.info(f"Using mid price for TP limit order: ${limit_price:.2f}")
                        # display.info(f"Using mid price for TP limit order: ${limit_price:.2f}")
                    else:
                        logging.error("Failed to get bid/ask prices for mid calculation. Falling back to TP target price.")
                        display.error("Failed to get bid/ask prices for mid calculation. Falling back to TP target price.")
                        limit_price = play['take_profit']['TP_option_prem']
                else:
                    limit_price = play['take_profit']['TP_option_prem']
            elif play['take_profit'].get('order_type') == 'limit at bid':
                if config.get('orders', 'bid_price_settings', 'take_profit', default=True):
                    if option_data and option_data.get('bid') is not None:
                        limit_price = option_data['bid']
                        logging.info(f"Using current bid price for TP limit order: ${limit_price:.2f}")
                        # display.info(f"Using current bid price for TP limit order: ${limit_price:.2f}")
                    else:
                        logging.error("Failed to get bid price. Falling back to TP target price.")
                        display.error("Failed to get bid price. Falling back to TP target price.")
                        limit_price = play['take_profit']['TP_option_prem']
                else:
                    limit_price = play['take_profit']['TP_option_prem']
            else:
                logging.warning(f"Unknown TP order type: {play['take_profit'].get('order_type')}. Falling back to TP target price.")
                display.warning(f"Unknown TP order type: {play['take_profit'].get('order_type')}. Falling back to TP target price.")
                limit_price = play['take_profit']['TP_option_prem']
    
            # Build order for take profit if limit order requested
            if play['take_profit'].get('order_type', '').lower().startswith("limit"):
                limit_price = round(limit_price, 2)
                order_req = LimitOrderRequest(
                    symbol=contract_symbol,
                    qty=qty,
                    limit_price=limit_price,
                    side=close_side,
                    type=OrderType.LIMIT,
                    time_in_force=TimeInForce.DAY,
                )
                logging.info(f"Creating take profit limit {close_side_str} order at ${limit_price:.2f}")
                # display.info(f"Creating take profit limit {close_side_str} order at ${limit_price:.2f}")
                display.status(f"Submitting TAKE PROFIT LIMIT {close_side_str} order for {contract_symbol} at ${limit_price:.2f}")
                response = client.submit_order(order_req)
                
                # Add PENDING-CLOSING transition for limit orders
                play['status'].update({
                    'closing_order_id': str(response.id),
                    'closing_order_status': response.status,
                    'play_status': 'PENDING-CLOSING'
                })
                save_play(play, play_file)
                move_play_to_pending_closing(play_file)
                logging.info("Play moved to PENDING-CLOSING state for TP limit order")
                # display.info("Play moved to PENDING-CLOSING state for TP limit order")
            else:
                response = client.close_position(
                    symbol_or_asset_id=contract_symbol,
                    close_options=ClosePositionRequest(qty=str(qty))
                )
                logging.info("Creating take profit market sell order")
                # display.info("Creating take profit market sell order")
                display.status(f"Submitting TAKE PROFIT MARKET SELL order for {contract_symbol}")
                
                # Move directly to CLOSED for market orders
                play['status']['position_exists'] = False
                save_play(play, play_file)
                move_play_to_closed(play_file)
                logging.info("Play moved to CLOSED state for market TP order")
                # display.info("Play moved to CLOSED state for market TP order")
        
        # Stop loss handling
        else:
            # Ensure we have current option data for stop loss processing
            if option_data is None:
                option_data = get_option_data(play['option_contract_symbol'])
                if option_data is None:
                    logging.error("Failed to get current option data for stop loss.")
                    display.error("Failed to get current option data for stop loss.")
                    return False
                current_premium = option_data.get('premium')
    
            # Handle contingency stop loss first
            if play['stop_loss'].get('SL_type', '').upper() == 'CONTINGENCY':
                # Cancel all existing orders as a contingency measure
                try:
                    client.cancel_all_orders()
                    logging.info("Cancelled all existing orders")
                    # display.info("Cancelled all existing orders")
                except Exception as e:
                    logging.warning(f"Error canceling existing orders: {e}")
                    display.warning(f"Error canceling existing orders: {e}")
                
                # If backup condition is met, use market order
                if close_conditions['is_contingency_loss']:
                    response = client.close_position(
                        symbol_or_asset_id=contract_symbol,
                        close_options=ClosePositionRequest(qty=str(qty))
                    )
                    logging.info("Creating contingency market sell order")
                    display.warning(f"Submitting CONTINGENCY STOP LOSS MARKET SELL order for {contract_symbol}")
                    
                    # Move directly to CLOSED for market orders
                    play['status']['position_exists'] = False
                    save_play(play, play_file)
                    move_play_to_closed(play_file)
                    logging.info("Play designated as CLOSED for contingency market SL order")
                    # display.info("Play moved to CLOSED state for contingency market SL order")
                    
                # If only primary condition is met, use limit order
                elif close_conditions['is_primary_loss']:
                    if play['stop_loss'].get('order_type') == 'limit at last':
                        limit_price = current_premium
                        logging.info(f"Using last traded price for primary SL limit order: ${limit_price:.2f}")
                        # display.info(f"Using last traded price for primary SL limit order: ${limit_price:.2f}")
                    elif play['stop_loss'].get('order_type') == 'limit at ask':
                        if config.get('orders', 'bid_price_settings', 'stop_loss', default=True):
                            if option_data and option_data.get('ask') is not None:
                                limit_price = option_data['ask']
                                logging.info(f"Using ask price for primary SL limit order: ${limit_price:.2f}")
                                # display.info(f"Using ask price for primary SL limit order: ${limit_price:.2f}")
                            else:
                                logging.error("Failed to get ask price. Falling back to SL target premium.")
                                display.error("Failed to get ask price. Falling back to SL target premium.")
                                limit_price = play['stop_loss']['SL_option_prem']
                        else:
                            limit_price = play['stop_loss']['SL_option_prem']
                    elif play['stop_loss'].get('order_type') == 'limit at mid':
                        if config.get('orders', 'bid_price_settings', 'stop_loss', default=True):
                            if option_data and option_data.get('bid') is not None and option_data.get('ask') is not None:
                                limit_price = (option_data['bid'] + option_data['ask']) / 2
                                logging.info(f"Using mid price for primary SL limit order: ${limit_price:.2f}")
                                # display.info(f"Using mid price for primary SL limit order: ${limit_price:.2f}")
                            else:
                                logging.error("Failed to get bid/ask prices for mid calculation. Falling back to SL target premium.")
                                display.error("Failed to get bid/ask prices for mid calculation. Falling back to SL target premium.")
                                limit_price = play['stop_loss']['SL_option_prem']
                        else:
                            limit_price = play['stop_loss']['SL_option_prem']
                    elif play['stop_loss'].get('order_type') == 'limit at bid':
                        if config.get('orders', 'bid_price_settings', 'stop_loss', default=True):
                            if option_data and option_data.get('bid') is not None:
                                limit_price = option_data['bid']
                                logging.info(f"Using current bid price for primary SL limit order: ${limit_price:.2f}")
                                # display.info(f"Using current bid price for primary SL limit order: ${limit_price:.2f}")
                            else:
                                logging.error("Failed to get bid price. Falling back to SL target premium.")
                                display.error("Failed to get bid price. Falling back to SL target premium.")
                                limit_price = play['stop_loss']['SL_option_prem']
                        else:
                            limit_price = play['stop_loss']['SL_option_prem']
                    else:
                        logging.warning(f"Unknown SL order type: {play['stop_loss'].get('order_type')}. Falling back to SL target premium.")
                        display.warning(f"Unknown SL order type: {play['stop_loss'].get('order_type')}. Falling back to SL target premium.")
                        limit_price = play['stop_loss']['SL_option_prem']
    
                    limit_price = round(limit_price, 2)
                    order_req = LimitOrderRequest(
                        symbol=contract_symbol,
                        qty=qty,
                        limit_price=limit_price,
                        side=close_side,
                        type=OrderType.LIMIT,
                        time_in_force=TimeInForce.DAY,
                    )
                    logging.info(f"Creating primary SL limit {close_side_str} order at ${limit_price:.2f}")
                    # display.info(f"Creating primary SL limit {close_side_str} order at ${limit_price:.2f}")
                    display.status(f"Submitting Primary Stop Loss (LIMIT {close_side_str}) order for {contract_symbol} at ${limit_price:.2f}")
                    response = client.submit_order(order_req)
                    
                    # Add PENDING-CLOSING transition for limit orders
                    play['status'].update({
                        'closing_order_id': str(response.id),
                        'closing_order_status': response.status,
                    })
                    save_play(play, play_file)
                    move_play_to_pending_closing(play_file)
                    logging.info("Play moved to PENDING-CLOSING state for limit SL order")
                    # display.info("Play moved to PENDING-CLOSING state for limit SL order")
            
            # Now handle regular (non-contingency) limit stop loss
            elif play['stop_loss'].get('SL_type', '').upper() == 'LIMIT':
                sl_order = play['stop_loss'].get('order_type', '').lower()
                if sl_order == 'limit at last':
                    limit_price = current_premium
                    logging.info(f"Using last traded price for SL limit order: ${limit_price:.2f}")
                    # display.info(f"Using last traded price for SL limit order: ${limit_price:.2f}")
                elif sl_order == 'limit at ask':
                    if config.get('orders', 'bid_price_settings', 'stop_loss', default=True):
                        if option_data and option_data.get('ask') is not None:
                            limit_price = option_data['ask']
                            logging.info(f"Using ask price for SL limit order: ${limit_price:.2f}")
                            # display.info(f"Using ask price for SL limit order: ${limit_price:.2f}")
                        else:
                            logging.error("Failed to get ask price. Falling back to SL target premium.")
                            display.error("Failed to get ask price. Falling back to SL target premium.")
                            limit_price = play['stop_loss']['SL_option_prem']
                    else:
                        limit_price = play['stop_loss']['SL_option_prem']
                elif sl_order == 'limit at mid':
                    if config.get('orders', 'bid_price_settings', 'stop_loss', default=True):
                        if option_data and option_data.get('bid') is not None and option_data.get('ask') is not None:
                            limit_price = (option_data['bid'] + option_data['ask']) / 2
                            logging.info(f"Using mid price for SL limit order: ${limit_price:.2f}")
                            # display.info(f"Using mid price for SL limit order: ${limit_price:.2f}")
                        else:
                            logging.error("Failed to get bid/ask prices for mid calculation. Falling back to SL target premium.")
                            display.error("Failed to get bid/ask prices for mid calculation. Falling back to SL target premium.")
                            limit_price = play['stop_loss']['SL_option_prem']
                    else:
                        limit_price = play['stop_loss']['SL_option_prem']
                elif sl_order == 'limit at bid':
                    if config.get('orders', 'bid_price_settings', 'stop_loss', default=True):
                        if option_data and option_data.get('bid') is not None:
                            limit_price = option_data['bid']
                            logging.info(f"Using current bid price for SL limit order: ${limit_price:.2f}")
                            # display.info(f"Using current bid price for SL limit order: ${limit_price:.2f}")
                        else:
                            logging.error("Failed to get bid price. Falling back to SL target premium.")
                            display.error("Failed to get bid price. Falling back to SL target premium.")
                            limit_price = play['stop_loss']['SL_option_prem']
                    else:
                        limit_price = play['stop_loss']['SL_option_prem']
                else:
                    logging.warning(f"Unrecognized SL order type '{sl_order}' for LIMIT SL type. Falling back to SL target premium.")
                    limit_price = play['stop_loss']['SL_option_prem']
                
                # Round limit price to 2 decimal places
                limit_price = round(limit_price, 2)
                order_req = LimitOrderRequest(
                    symbol=contract_symbol,
                    qty=qty,
                    limit_price=limit_price,
                    side=close_side,
                    type=OrderType.LIMIT,
                    time_in_force=TimeInForce.DAY,
                )
                logging.info(f"Creating stop loss limit {close_side_str} order at ${limit_price:.2f}")
                # display.info(f"Creating stop loss limit {close_side_str} order at ${limit_price:.2f}")
                display.status(f"Submitting STOP LOSS LIMIT {close_side_str} order for {contract_symbol} at ${limit_price:.2f}")
                response = client.submit_order(order_req)
                
                # Add PENDING-CLOSING transition for limit orders
                play['status'].update({
                    'closing_order_id': str(response.id),
                    'closing_order_status': response.status,
                })
                save_play(play, play_file)
                move_play_to_pending_closing(play_file)
                logging.info("Play moved to PENDING-CLOSING state for limit SL order")
                # display.info("Play moved to PENDING-CLOSING state for limit SL order")
            
            # For regular market stop loss
            else:
                # For SL_type 'STOP' or any other types, use a market order
                response = client.close_position(
                    symbol_or_asset_id=contract_symbol,
                    close_options=ClosePositionRequest(qty=str(qty))
                )
                logging.info("Creating stop loss market sell order")
                display.warning(f"Submitting STOP LOSS MARKET SELL order for {contract_symbol}")
                
                # Move directly to CLOSED for market orders
                play['status']['position_exists'] = False
                save_play(play, play_file)
                move_play_to_closed(play_file)
                logging.info("Play moved to CLOSED state for market SL order")
                # display.info("Play moved to CLOSED state for market SL order")
        
        logging.info(f"Order submitted: {response}")
        # display.info(f"Order submitted: {response}")
        
        return True

    except Exception as e:
        logging.error(f"Error closing position: {e}")
        display.error(f"Error closing position: {e}")
        return False

def monitor_and_manage_position(play, play_file):
    """Monitor and manage an open position."""
    try:
        # First verify position status for pending plays
        if play.get('status', {}).get('play_status') in ['PENDING-OPENING', 'PENDING-CLOSING']:
            if not manage_pending_plays(None, single_play=(play, play_file)):
                logging.info("Position not yet established, skipping monitoring")
                # display.info("Position not yet established, skipping monitoring")
                return True  # Return True to continue monitoring on next cycle

        client = get_alpaca_client()
        
        # Verify play status is appropriate for monitoring
        if play.get('status', {}).get('play_status') not in ['OPEN', 'PENDING-CLOSING']:
            logging.info(f"Play status {play.get('status', {}).get('play_status')} not appropriate for monitoring")
            # display.info(f"Play status {play.get('status', {}).get('play_status')} not appropriate for monitoring")
            return True
            
        # First verify position status
        if not manage_pending_plays(None, single_play=(play, play_file)):
            logging.info("Position not yet established, skipping monitoring")
            # display.info("Position not yet established, skipping monitoring")
            return True  # Return True to continue monitoring on next cycle
            
        contract_symbol = play.get('option_contract_symbol')
        underlying_symbol = play.get('symbol')
        
        if not contract_symbol or not underlying_symbol:
            logging.error("Missing required symbols")
            display.error("Play file is missing required symbols")
            return False

        # Get current market data
        market_data = None
        current_premium = None
        
        # Check if we need stock price monitoring
        if play['take_profit'].get('stock_price') is not None or play['stop_loss'].get('stock_price') is not None or \
           play['take_profit'].get('stock_price_pct') is not None or play['stop_loss'].get('stock_price_pct') is not None:
            try:
                current_price = get_stock_price(underlying_symbol)
                if current_price is None or current_price <= 0:
                    logging.error(f"Could not get valid stock price for {underlying_symbol}")
                    display.error(f"Could not get valid stock price for {underlying_symbol}")
                    return False
                    
                logging.info(f"Current stock price for {underlying_symbol}: ${current_price:.2f}")
                # display.info(f"Current stock price for {underlying_symbol}: ${current_price:.2f}")
            except Exception as e:
                logging.error(f"Error getting stock price: {e}")
                display.error(f"Error getting stock price: {e}")
                return False

        # Check if we need premium monitoring
        if play['take_profit'].get('premium_pct') is not None or play['stop_loss'].get('premium_pct') is not None:
            option_data = get_option_data(play['option_contract_symbol'])
            if option_data is None:
                logging.error("Failed to get current option premium.")
                display.error("Failed to get current option premium.")
                return False
                
            current_premium = option_data['premium']
            logging.info(f"Current option premium for {contract_symbol}: ${current_premium:.4f}")
            # display.info(f"Current option premium for {contract_symbol}: ${current_premium:.4f}")
        
            # Log premium targets if using limit orders
            if play['take_profit'].get('order_type') == 'limit' and play['take_profit'].get('TP_option_prem'):
                logging.info(f"TP limit order target: ${play['take_profit']['TP_option_prem']:.4f}")
                # display.info(f"TP limit order target: ${play['take_profit']['TP_option_prem']:.4f}")
            
            # Log stop loss targets
            sl_type = play['stop_loss'].get('SL_type', 'STOP')
            if sl_type == 'CONTINGENCY':
                if play['stop_loss'].get('SL_option_prem'):
                    logging.info(f"Primary SL limit order target: ${play['stop_loss']['SL_option_prem']:.4f}")
                    # display.info(f"Primary SL limit order target: ${play['stop_loss']['SL_option_prem']:.4f}")
                if play['stop_loss'].get('contingency_SL_option_prem'):
                    logging.info(f"Backup SL market order target: ${play['stop_loss']['contingency_SL_option_prem']:.4f}")
                    # display.info(f"Backup SL market order target: ${play['stop_loss']['contingency_SL_option_prem']:.4f}")
            elif play['stop_loss'].get('order_type') == 'limit' and play['stop_loss'].get('SL_option_prem'):
                logging.info(f"SL limit order target: ${play['stop_loss']['SL_option_prem']:.4f}")
                # display.info(f"SL limit order target: ${play['stop_loss']['SL_option_prem']:.4f}")

        # Verify position is still open
        position = client.get_open_position(contract_symbol)
        if position is None:
            logging.info(f"Position {contract_symbol} closed.")
            # display.info(f"Position {contract_symbol} closed.")
            return True

        # Update trailing states (no behavior change unless enabled)
        try:
            current_price_for_trailing = locals().get('current_price', None)
            trail_changed = update_trailing_levels(play, current_price_for_trailing, current_premium)
            # Optional: Log current trailing levels for visibility
            if has_trailing_enabled(play) and trail_changed:
                tp_state = (play.get('take_profit') or {}).get('trail_state') or {}
                sl_state = (play.get('stop_loss') or {}).get('trail_state') or {}
                tp_level = tp_state.get('current_trail_level')
                sl_level = sl_state.get('current_trail_level')
                if tp_level is not None:
                    logging.info(f"Current trailing TP level: ${tp_level:.2f}")
                    # display.info(f"Current trailing TP level: ${tp_level:.2f}")
                if sl_level is not None:
                    logging.info(f"Current trailing SL level: ${sl_level:.2f}")
                    # display.info(f"Current trailing SL level: ${sl_level:.2f}")
                # Provide concise console feedback when trailing levels change
                msg_parts = []
                if tp_level is not None:
                    msg_parts.append(f"TP {tp_level:.2f}")
                if sl_level is not None:
                    msg_parts.append(f"SL {sl_level:.2f}")
                if msg_parts:
                    display.status("Trailing updated: " + ", ".join(msg_parts))
                # Persist trail state immediately to avoid loss on restart (use improved atomic saver)
                try:
                    save_play_improved(play, play_file)
                except Exception as e:
                    logging.warning(f"Failed to persist trailing state: {e}")
        except Exception as e:
            logging.warning(f"Trailing update skipped: {e}")

        # Evaluate closing conditions
        close_conditions = evaluate_closing_strategy(underlying_symbol, play, play_file)
        if close_conditions['should_close']:
            close_attempts = 0
            max_attempts = 3
            
            while close_attempts < max_attempts:
                logging.info(f"Attempting to close position: Attempt {close_attempts + 1}")
                # display.info(f"Attempting to close position: Attempt {close_attempts + 1}")
                if close_position(play, close_conditions, play_file):
                    logging.info("Position closed successfully")
                    # display.info("Position closed successfully")
                    return True
                close_attempts += 1
                logging.warning(f"Close attempt {close_attempts} failed. Retrying...")
                display.warning(f"Position Close attempt {close_attempts} failed. Retrying...")
                time.sleep(2)
            
            logging.error("Failed to close position after maximum attempts")
            display.error("Failed to close position after exhausting retry attempts")
            return False

        return True
    except Exception as e:
        logging.error(f"Error monitoring position: {e}")
        display.error(f"Error monitoring position: {e}")
        return False

# ==================================================
# 5. MOVE PLAY TO APPROPRIATE FOLDER
# ==================================================
# Functions to move a play file to the appropriate plays folder after execution or upon conditional trigger.

# Move to NEW (for OTO triggered plays)
def move_play_to_new(play_file):
    """
    Move play to NEW folder and update status.
    
    Thin wrapper that delegates to strategy.shared.play_manager module.
    """
    return _shared_move_to_new(play_file)

# Move to PENDING-OPENING (for plays whose BUY condition has hit but limit order has not yet been filled)
def move_play_to_pending_opening(play_file):
    """
    Move play to PENDING-OPENING folder and update status.
    
    Thin wrapper that delegates to strategy.shared.play_manager module.
    """
    return _shared_move_to_pending_opening(play_file)

def move_play_to_open(play_file):
    """
    Move play to OPEN folder and update status.
    
    Thin wrapper that delegates to strategy.shared.play_manager module.
    """
    return _shared_move_to_open(play_file)

# Move to PENDING-CLOSING (for plays whose SELL condition has hit but limit order has not yet been filled)
def move_play_to_pending_closing(play_file):
    """
    Move play to PENDING-CLOSING folder and update status.
    
    Thin wrapper that delegates to strategy.shared.play_manager module.
    """
    return _shared_move_to_pending_closing(play_file)

# Move to CLOSED (for plays whose TP or SL condition has hit)
def move_play_to_closed(play_file):
    """
    Move play to CLOSED folder and update status.
    
    Thin wrapper that delegates to strategy.shared.play_manager module.
    """
    return _shared_move_to_closed(play_file)

# Move to EXPIRED (for plays which have expired, and OCO triggered plays)
def move_play_to_expired(play_file):
    """
    Move play to EXPIRED folder and update status.
    
    Thin wrapper that delegates to strategy.shared.play_manager module.
    """
    return _shared_move_to_expired(play_file)

# Move to TEMP (for plays recycled by OCO or held for later activation)
def move_play_to_temp(play_file):
    """
    Move play to TEMP folder and update status for recycling.
    
    Thin wrapper that delegates to strategy.shared.play_manager module.
    """
    return _shared_move_to_temp(play_file)

# ==================================================
# 6. MAIN TRADE EXECUTION FLOW
# ==================================================
# Main function to orchestrate the strategy execution using the loaded plays.

def execute_trade(play_file, play_type):
    """Execute trade with improved error handling and fault tolerance."""
    try:
        logging.info(f"Executing {play_type} play: {play_file}")
        # display.info(f"Executing {play_type} play: {play_file}")
        
        play = load_play(play_file)
        if play is None:
            logging.error(f"Failed to load play {play_file}. Skipping to next play.")
            display.error(f"Failed to load play {play_file}. Skipping to next play.")
            return True  # Return True to continue with next play
        
        # Basic validation
        symbol = play.get("symbol")
        trade_type = play.get("trade_type", "").upper()
        if not symbol or trade_type not in ["CALL", "PUT"]:
            logging.error(f"Play {play_file} is missing required fields. Skipping to next play.")
            display.error(f"Play {play_file} is missing required fields. Skipping to next play.")
            return True  # Return True to continue with next play
            
        # For PENDING plays, check status before proceeding
        if play.get('status', {}).get('play_status') in ['PENDING-OPENING', 'PENDING-CLOSING']:
            try:
                if not manage_pending_plays(None, single_play=(play, play_file)):
                    logging.warning(f"Position status check failed for {play_file}. Will retry next cycle.")
                    display.warning(f"Position status check failed for {play_file}. Will retry next cycle.")
                    return True  # Return True to continue with next play
            except Exception as e:
                logging.error(f"Error checking position status: {str(e)}. Continuing to next play.")
                display.error(f"Error checking position status: {str(e)}. Continuing to next play.")
                return True
        
        # Validate order types
        try:
            if not validate_play_order_types(play):
                logging.error(f"Invalid order types in {play_file}. Skipping to next play.")
                display.error(f"Invalid order types in {play_file}. Skipping to next play.")
                return True
        except Exception as e:
            logging.error(f"Error validating order types: {str(e)}. Continuing to next play.")
            display.error(f"Error validating order types: {str(e)}. Continuing to next play.")
            return True
        
        # OPENING a Play
        if play_type == "new":
            try:
                if evaluate_opening_strategy(symbol, play):
                    try:
                        success = open_position(play, play_file)
                        return True
                    except Exception as e:
                        logging.error(f"Error opening position: {str(e)}. Will retry next cycle.")
                        display.error(f"Error opening position: {str(e)}. Will retry next cycle.")
                    return True
            except Exception as e:
                logging.error(f"Error during opening strategy: {str(e)}. Continuing to next play.")
                display.error(f"Error during opening strategy: {str(e)}. Continuing to next play.")
                return True
                
        # MONITORING an Open Play
        elif play_type == "open":
            try:
                monitor_and_manage_position(play, play_file)
            except Exception as e:
                if "position does not exist" in str(e):
                    logging.warning(f"Position no longer exists for {play_file}. Moving to closed.")
                    display.warning(f"Position no longer exists for {play_file}. Designating as closed.")
                    try:
                        move_play_to_closed(play_file)
                    except Exception as move_err:
                        logging.error(f"Error moving play to closed: {str(move_err)}")
                        display.error(f"Error designating play as closed: {str(move_err)}")
                else:
                    logging.error(f"Error monitoring position: {str(e)}. Will retry next cycle.")
                    display.error(f"Error monitoring position: {str(e)}. Will retry next cycle.")
                return True
                
        # Handle Expired Play
        elif play_type == "expired":
            try:
                move_play_to_expired(play_file)
            except Exception as e:
                logging.error(f"Error moving play to expired: {str(e)}. Will retry next cycle.")
                display.error(f"Error designating play as expired: {str(e)}. Will retry next cycle.")
            return True
            
        return True  # Always return True to continue with next play
        
    except Exception as e:
        logging.error(f"Unexpected error in execute_trade: {str(e)}. Continuing to next play.")
        display.error(f"Unexpected error in execute_trade: {str(e)}. Continuing to next play.")
        return True  # Return True to continue with next play

def validate_play_order_types(play):
    """Validate order types in play data."""
    valid_types = ['market', 'limit at bid', 'limit at last', 'limit at ask', 'limit at mid']
    
    # Validate entry order type
    entry_point = play.get('entry_point', {})
    entry_type = entry_point.get('order_type')
    if entry_type is None:
        logging.error("Missing order_type in entry_point")
        display.error("Missing order type for Position Entry")
        return False
    if entry_type not in valid_types:
        logging.error(f"Invalid entry_point order_type: {entry_type}")
        display.error(f"Invalid Position Entry order type: {entry_type}")
        return False
    
    # Validate take profit order type
    tp = play.get('take_profit', {})
    tp_type = tp.get('order_type')
    if tp_type is not None and tp_type not in valid_types:
        logging.error(f"Invalid take_profit order_type: {tp_type}")
        display.error(f"Invalid Take Profit order type: {tp_type}")
        return False
    
    # Validate stop loss order type(s)
    sl = play.get('stop_loss', {})
    sl_type = sl.get('SL_type')
    sl_order_type = sl.get('order_type')
    
    if sl_type == 'CONTINGENCY':
        if not isinstance(sl_order_type, list) or len(sl_order_type) != 2:
            logging.error("Contingency stop loss must have array of two order types")
            display.error("Contingency-style Stop Loss must consist of two order types")
            return False
        # First order must be a limit order, second must be market
        if not (sl_order_type[0].startswith('limit') and sl_order_type[1] == 'market'):
            logging.error("Contingency stop loss must have ['limit at bid/ask/mid/last', 'market'] order types")
            display.error("Contingency-style Stop Loss must consist of ['limit at bid/ask/mid/last', 'market'] order types")
            return False
    elif sl_order_type is not None and sl_order_type not in valid_types:
        logging.error(f"Invalid stop_loss order_type: {sl_order_type}")
        display.error(f"Invalid Stop Loss order type: {sl_order_type}")
        return False
    
    return True

# ==================================================
# 7. CONTINUOUS MONITORING AND EXECUTION
# ==================================================
# Monitor the plays directory continuously and execute plays as conditions are met.

def get_sleep_interval(minutes_to_open):
    """Return appropriate sleep interval based on time to market open."""
    if minutes_to_open > 240:    # More than 4 hours
        return 900               # Check every 15 minutes
    elif minutes_to_open > 120:  # More than 2 hours
        return 600               # Check every 10 minutes
    elif minutes_to_open > 30:   # More than 30 minutes
        return 240               # Check every 4 minutes
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
        # display.info("Market hours validation disabled")
        logging.info("Market hours validation disabled")
        return True, 0
        
    try:
        market_tz = ZoneInfo(config.get('market_hours', 'timezone', default='America/New_York'))
    except Exception as e:
        error_msg = f"Invalid timezone configuration: {e}. Defaulting to America/New_York"
        display.error(error_msg)
        logging.error(error_msg)
        market_tz = ZoneInfo('America/New_York')
    
    current_time = datetime.now(market_tz)
    current_time_only = current_time.time()
    
    # Check for holidays first
    if is_market_holiday(current_time.date()):
        next_market_day = current_time + timedelta(days=1)
        while is_market_holiday(next_market_day.date()) or next_market_day.weekday() >= 5:
            next_market_day += timedelta(days=1)
            
        try:
            start_time = config.get('market_hours', 'regular_hours', 'start', default='09:30')
            next_market_day = next_market_day.replace(
                hour=int(start_time.split(':')[0]),
                minute=int(start_time.split(':')[1]),
                second=0
            )
        except (ValueError, AttributeError) as e:
            error_msg = f"Invalid market start time format: {e}. Using default 09:30"
            display.error(error_msg)
            logging.error(error_msg)
            next_market_day = next_market_day.replace(hour=9, minute=30, second=0)
            
        wait_hours = (next_market_day - current_time).total_seconds() / 3600
        # display.info(f"Market is closed for holiday. Current time in {market_tz}: {current_time_only}")
        logging.info(f"Market closed (holiday). Next open: {next_market_day}")
        return False, int(wait_hours * 60)
    
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
            error_msg = f"Invalid market start time format: {e}. Using default 09:30"
            display.error(error_msg)
            logging.error(error_msg)
            next_market_day = next_market_day.replace(hour=9, minute=30, second=0)
            
        wait_hours = (next_market_day - current_time).total_seconds() / 3600
        # display.info(f"Market is closed for the weekend. Current time in {market_tz}: {current_time_only}")
        logging.info(f"Market closed (weekend). Next open: {next_market_day}")
        return False, int(wait_hours * 60)
    
    try:
        market_open = datetime.strptime(config.get('market_hours', 'regular_hours', 'start', default='09:30'), '%H:%M').time()
        market_close = datetime.strptime(config.get('market_hours', 'regular_hours', 'end', default='16:00'), '%H:%M').time()
    except ValueError as e:
        error_msg = f"Invalid time format in configuration: {e}. Using default market hours"
        display.error(error_msg)
        logging.error(error_msg)
        market_open = datetime.strptime('09:30', '%H:%M').time()
        market_close = datetime.strptime('16:00', '%H:%M').time()
    
    # Check if within regular market hours
    is_market_open = market_open <= current_time_only <= market_close
    
    # If it's 4:17 PM (within a 30-second window), handle pending plays
    cleanup_time = datetime.strptime('16:17', '%H:%M').time()
    cleanup_window_start = (datetime.combine(datetime.today(), cleanup_time) - timedelta(seconds=15)).time()
    cleanup_window_end = (datetime.combine(datetime.today(), cleanup_time) + timedelta(seconds=45)).time()
    
    if cleanup_window_start <= current_time_only <= cleanup_window_end:
        logging.info("Market closed (4:15 PM). Processing end-of-day pending plays...")
        display.info("Market closed (4:15 PM). Processing end-of-day pending plays...")
        handle_end_of_day_pending_plays()
    
    # Handle extended hours if enabled
    if not is_market_open and config.get('market_hours', 'extended_hours', 'enabled', default=False):
        try:
            pre_market = datetime.strptime(config.get('market_hours', 'extended_hours', 'pre_market_start', default='04:00'), '%H:%M').time()
            after_market = datetime.strptime(config.get('market_hours', 'extended_hours', 'after_market_end', default='20:00'), '%H:%M').time()
            is_market_open = pre_market <= current_time_only <= after_market
        except ValueError as e:
            error_msg = f"Invalid extended hours format: {e}. Using default extended hours"
            display.error(error_msg)
            logging.error(error_msg)
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
        
        # display.info(f"Market is closed. Current time in {market_tz}: {current_time_only}")
        logging.info(f"Market closed. Next open: {next_open}")
        return False, wait_minutes
        
    logging.info(f"Market open. Current time: {current_time_only}")
    return True, 0

def handle_api_error(e, operation):
    """Handle API errors with appropriate logging and display."""
    # NOTE: Currently unused; reserved for potential centralized API error handling.
    error_msg = f"API error during {operation}: {str(e)}"
    display.error(error_msg)
    logging.error(error_msg)
    
    if hasattr(e, 'status_code'):
        display.error(f"Status Code: {e.status_code}")
        logging.error(f"Status Code: {e.status_code}")
    
    if hasattr(e, 'response'):
        display.error(f"Response: {e.response.text}")
        logging.error(f"Response: {e.response.text}")

def handle_execution_error(e, operation, retry_count=0):
    """Handle execution errors with retry logic."""
    error_msg = f"Error during {operation} (attempt {retry_count + 1}/{MAX_RETRIES}): {str(e)}"
    display.error(error_msg)
    logging.error(error_msg)
    
    if retry_count < MAX_RETRIES:
        wait_time = 2 ** retry_count  # Exponential backoff
        display.warning(f"Retrying in {wait_time} seconds...")
        logging.warning(f"Retrying in {wait_time} seconds...")
        time.sleep(wait_time)
        return True
    else:
        display.error(f"Max retries ({MAX_RETRIES}) reached for {operation}")
        logging.error(f"Max retries ({MAX_RETRIES}) reached for {operation}")
        return False

def is_market_holiday(date):
    """Check if given date is a US market holiday.
    - This is simplified.
    - Early closing days are not listed.
    - Holidays fall on different days each year. This is not reflected here.
    - This should really be separated out into a separate file. """
    holidays = [
        (1, 1),    # New Year's Day
        (1, 20),   # Martin Luther King Jr. Day (3rd Monday in January)
        (2, 17),   # Presidents Day (3rd Monday in February)
        (4, 18),   # Good Friday
        (5, 26),   # Memorial Day (Last Monday in May)
        (7, 4),    # Independence Day
        (9, 1),    # Labor Day (1st Monday in September)
        (11, 27),  # Thanksgiving Day (4th Thursday in November)
        (12, 25),  # Christmas Day
    ]
    return (date.month, date.day) in holidays

########################################################
# ****************-={ MAIN LOOP }=-********************
########################################################    
def monitor_plays_continuously():
    """Main monitoring loop for all plays"""
    # Use exe-aware path for plays directory (persists next to exe in frozen mode)
    plays_dir = str(get_plays_dir())
    market_data = get_market_data_manager()
    
    from goldflipper.utils.json_fixer import PlayFileFixer
    json_fixer = PlayFileFixer()
    
    logging.info(f"Monitoring plays directory: {plays_dir}")

    while True:
        try:
            market_data.start_new_cycle()
            logging.info("Starting new monitoring cycle")
            
            # Check market hours before processing
            is_open, minutes_to_open = validate_market_hours()
            if not is_open:
                sleep_time = get_sleep_interval(minutes_to_open)
                display.status(f"Market is CLOSED. Next check in {sleep_time} seconds.")
                time.sleep(sleep_time)
                continue
                
            display.success("Market is OPEN. Monitoring starting.")
            # display.header("Checking for new and open plays...")
            logging.info("Checking for new and open plays")

            # Check for expired plays in the "new" folder
            new_play_dir = os.path.join(plays_dir, 'new')
            play_files = [os.path.join(new_play_dir, f) for f in os.listdir(new_play_dir) if f.endswith('.json')]
            current_date = datetime.now().date()
            
            # Handle expired plays
            for play_file in play_files:
                play = load_play(play_file)
                if play and 'play_expiration_date' in play:
                    expiration_date = datetime.strptime(play['play_expiration_date'], "%m/%d/%Y").date()
                    if expiration_date < current_date:
                        move_play_to_expired(play_file)
                        display.warning(f"Moved expired play to expired folder: {play_file}")
                        logging.warning(f"Play has expired: {play_file}")

            # Manage pending plays first
            manage_pending_plays(plays_dir)

            # Print current option data for all active plays
            for play_type in ['new', 'open', 'pending-opening', 'pending-closing']:
                play_dir = os.path.join(plays_dir, play_type)
                if not os.path.exists(play_dir):
                    continue
                
                play_files = [os.path.join(play_dir, f) for f in os.listdir(play_dir) if f.endswith('.json')]
                
                for play_file in play_files:
                    play = load_play(play_file)
                    if play:
                        try:
                            # Get current stock price
                            current_price = get_stock_price(play['symbol'])
                            if current_price is None or current_price <= 0:
                                logging.error(f"Could not get valid share price for {play['symbol']}")
                                display.error(f"Could not get valid share price for {play['symbol']}")
                                continue

                            # Get current option data
                            option_data = get_option_data(play['option_contract_symbol'])
                            if option_data is None:
                                logging.error(f"Could not get option data for {play['option_contract_symbol']}")
                                display.error(f"Could not get option data for {play['option_contract_symbol']}")
                                continue
                            
                            # Log detailed data to file
                            logging.info(f"Play data for {play['symbol']}: "
                                       f"Type={play_type}, "
                                       f"Strike=${play['strike_price']}, "
                                       f"Exp={play['expiration_date']}, "
                                       f"Stock=${current_price:.2f}, "
                                       f"Bid=${option_data['bid']:.2f}, "
                                       f"Ask=${option_data['ask']:.2f}")

                            # Display formatted data to terminal
                            play_name = play.get('play_name', 'N/A')
                            border = "+" + "-" * 60 + "+"
                            header_text = play_name
                            display.status(border, show_timestamp=False)
                            display.status(f"|{header_text:^60}|", show_timestamp=False)
                            display.status(border, show_timestamp=False)
                            display.status(
                                f"Play: {play['symbol']} {play['trade_type']} "
                                f"{play['strike_price']} Strike {play['expiration_date']} Expiration"
                            )

                            # Map play types to display methods and colors
                            status_display = {
                                'new': (display.info, 'info'),
                                'pending-opening': (display.info, 'info'),
                                'open': (display.success, 'success'),
                                'pending-closing': (display.warning, 'warning'),
                                'closed': (display.status, 'status'),
                                'expired': (display.error, 'error'),
                                'temp': (display.info, 'info')
                            }
                            
                            # Get the appropriate display method and color for the current play type
                            display_method, color = status_display.get(play_type.lower(), (display.status, 'status'))
                            
                            play_status = play.get('status', {}).get('play_status')
                            play_expiration_date = play.get('play_expiration_date')
                            
                            # Create status message with color
                            status_msg = f"Status: [{play_type}]"
                            if play_expiration_date and play_status in ('TEMP', 'NEW'):
                                status_msg = f"Status: [{play_type}], Play expires: {play_expiration_date}"
                            
                            # Display with appropriate method
                            display_method(status_msg, show_timestamp=False)

                            display.price(f"Stock price: ${current_price:.2f}")
                            display.price(
                                f"Option premium: Bid ${option_data['bid']:.2f} "
                                f"Ask ${option_data['ask']:.2f} Last ${option_data['premium']:.2f}"
                            )
                            display.status(border, show_timestamp=False)

                            
                        except Exception as e:
                            error_msg = f"Error fetching market data for {play['symbol']}: {str(e)}"
                            display.error(error_msg)
                            logging.error(error_msg)

            # Execute trades
            for play_type in ['new', 'open']:
                play_dir = os.path.join(plays_dir, play_type)
                play_files = [os.path.join(play_dir, f) for f in os.listdir(play_dir) if f.endswith('.json')]
                
                for play_file in play_files:
                    if execute_trade(play_file, play_type):
                        msg = f"Successfully processed {play_type} play: {play_file}"
                        display.status(msg)
                        logging.info(msg)
                    else:
                        msg = f"Conditions not met for {play_type} play: {play_file}"
                        # display.info(msg)
                        logging.info(msg)

            display.header("Cycle complete. Waiting for next cycle...")
            logging.info("Cycle complete. Waiting for next cycle")
            
            # Run JSON fixer after the cycle completes but before the sleep
            # Use a small delay to ensure all file operations from the cycle are complete
            json_fix_delay = 3  # seconds to wait before running JSON fixer
            polling_interval = config.get('monitoring', 'polling_interval', default=30)
            
            if json_fix_delay < polling_interval:  # Only run if there's enough time before next cycle
                time.sleep(json_fix_delay)  # Short delay before running the fixer
                
                try:
                    fixed_count = json_fixer.check_and_fix_all_plays()
                    if fixed_count > 0:
                        logging.info(f"JSON fixer repaired {fixed_count} corrupted play files")
                        # display.info(f"JSON fixer repaired {fixed_count} corrupted play files")
                except Exception as e:
                    error_msg = f"Error in JSON fixer: {str(e)}"
                    logging.error(error_msg)
                    display.error(error_msg)
                    
                # Adjust remaining sleep time
                remaining_sleep = max(0, polling_interval - json_fix_delay)
                time.sleep(remaining_sleep)
            else:
                # Full polling interval if no time for JSON fixer
                time.sleep(polling_interval)

        except Exception as e:
            error_msg = f"An error occurred during play monitoring: {e}"
            display.error(error_msg)
            logging.error(error_msg)

            # Wait for the configured interval before the next cycle
            polling_interval = config.get('monitoring', 'polling_interval', default=30)
            time.sleep(polling_interval)

# ==================================================
# 8. ANCILLARY FUNCTIONS
# ==================================================
# Functions to support the main trade execution flow.

def verify_position_exists(play):
    """Verify position exists with retries"""
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            client = get_alpaca_client()
            position = client.get_open_position(play.get('option_contract_symbol'))
            if position:
                return True
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        except Exception as e:
            logging.error(f"Position verification attempt {attempt + 1} failed: {e}")
            display.error(f"Verifying position, attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    return False

def handle_conditional_plays(play, play_file):
    """Handle OCO and OTO, aka OSO, triggers after position is confirmed open."""
    if play.get('status', {}).get('conditionals_handled'):
        return

    display.status(
        f"| OCO | OSO |: evaluating trigger conditions for {play.get('symbol', '')} "
        f"{play.get('option_contract_symbol', '')}"
    )
        
    # Verify position exists
    if not verify_position_exists(play):
        logging.error("Position not verified. Delaying conditional handling.")
        display.error("Position could not be verified. Delaying conditional handling.")
        return False
    
    # Get trigger data directly from conditional_plays
    oco_triggers = play.get('conditional_plays', {}).get('OCO_triggers', [])
    oto_triggers = play.get('conditional_plays', {}).get('OTO_triggers', [])
    
    # Handle legacy format conversion
    if play.get('conditional_plays', {}).get('OCO_trigger'):
        old_trigger = play['conditional_plays'].pop('OCO_trigger')
        oco_triggers.append(old_trigger)
        play['conditional_plays']['OCO_triggers'] = oco_triggers
        
    if play.get('conditional_plays', {}).get('OTO_trigger'):
        old_trigger = play['conditional_plays'].pop('OTO_trigger')
        oto_triggers.append(old_trigger)
        play['conditional_plays']['OTO_triggers'] = oto_triggers
    
    # If no triggers exist, mark as handled and return
    if not oco_triggers and not oto_triggers:
        play['status']['conditionals_handled'] = True
        save_play(play, play_file)
        return True
    
    success = True
    plays_base_dir = os.path.abspath(os.path.dirname(os.path.dirname(play_file)))
    
    # Handle OCO triggers
    for oco_trigger in oco_triggers:
        display.status(f"OCO: processing trigger {oco_trigger}")
        # 1) If trigger is still NEW, expire it
        new_path = os.path.join(plays_base_dir, 'new', oco_trigger)
        if os.path.exists(new_path):
            try:
                if not move_play_to_expired(new_path):
                    success = False
                    logging.error(f"Failed to move OCO trigger to expired: {oco_trigger}")
                    display.error(f"Failed to move OCO trigger to expired: {oco_trigger}")
            except Exception as e:
                logging.error(f"Failed to process OCO trigger {oco_trigger}: {e}")
                display.error(f"Failed to process OCO trigger {oco_trigger}: {e}")
                success = False
            continue

        # 2) If trigger is PENDING-OPENING, cancel broker order and move to TEMP
        pending_opening_path = os.path.join(plays_base_dir, 'pending-opening', oco_trigger)
        if os.path.exists(pending_opening_path):
            try:
                # Load play to get order_id
                with open(pending_opening_path, 'r') as f:
                    pending_play = json.load(f)

                order_id = pending_play.get('status', {}).get('order_id')
                if not order_id:
                    logging.warning(f"OCO pending-opening play missing order_id, moving to TEMP: {oco_trigger}")
                    move_play_to_temp(pending_opening_path)
                    continue

                client = get_alpaca_client()
                try:
                    order = client.get_order_by_id(order_id)
                except Exception as e:
                    logging.error(f"Failed to fetch order for OCO pending-opening play {oco_trigger}: {e}")
                    display.error(f"Failed to fetch order for OCO pending-opening play {oco_trigger}: {e}")
                    success = False
                    continue

                order_status = getattr(order, 'status', None) or order.get('status') if isinstance(order, dict) else None

                # If already filled, do not recycle; let normal flow handle it
                if order_status == 'filled':
                    logging.warning(f"OCO pending-opening play has already filled, cannot recycle: {oco_trigger}")
                    display.warning(f"OCO pending-opening play has already filled; cannot be recycled: {oco_trigger}")
                    success = False
                    continue

                # Attempt to cancel the order
                cancel_success = False
                try:
                    # Prefer explicit cancel by id; fall back if SDK differs
                    if hasattr(client, 'cancel_order_by_id'):
                        client.cancel_order_by_id(order_id)
                        cancel_success = True
                    elif hasattr(client, 'cancel_order'):
                        client.cancel_order(order_id)
                        cancel_success = True
                    else:
                        logging.error("Alpaca client has no cancel_order[_by_id] method")
                except Exception as e:
                    logging.error(f"Failed to cancel OCO pending-opening order {order_id} for {oco_trigger}: {e}")
                    display.error(f"Failed to cancel OCO pending-opening order for {oco_trigger}")

                if cancel_success:
                    logging.info(f"Cancelled pending-opening OCO order {order_id} for {oco_trigger}")
                    # display.info(f"Cancelled pending-opening OCO order for {oco_trigger}")
                    # Move the play to TEMP for recycling
                    move_play_to_temp(pending_opening_path)
                else:
                    # If cancel did not throw but not confirmed, still try to move cautiously if not filled
                    if order_status in ['canceled', 'expired', 'rejected']:
                        move_play_to_temp(pending_opening_path)
                        logging.info(f"Order already {order_status}. Moved OCO pending-opening play to TEMP: {oco_trigger}")
                        # display.info(f"Order already {order_status}. Moved OCO pending-opening play to TEMP: {oco_trigger}")
                    else:
                        success = False
                        logging.error(f"Could not cancel OCO pending-opening play: {oco_trigger}")
                        display.error(f"Could not cancel OCO pending-opening play: {oco_trigger}")
            except Exception as e:
                logging.error(f"Failed to recycle OCO pending-opening play {oco_trigger}: {e}")
                display.error(f"Failed to recycle OCO pending-opening play {oco_trigger}: {e}")
                success = False
    
    # Handle OTO triggers (move from temp to new)
    for oto_trigger in oto_triggers:
        display.status(f"OTO: activating trigger {oto_trigger}")
        temp_path = os.path.join(plays_base_dir, 'temp', oto_trigger)
        new_path = os.path.join(plays_base_dir, 'new', oto_trigger)
        
        try:
            if os.path.exists(temp_path):
                # Move the file from temp to new
                move_play_to_new(temp_path)
                logging.info(f"Moved OTO trigger from temp to new: {oto_trigger}")
                # display.info(f"Moved OTO trigger from temp to new: {oto_trigger}")
            else:
                logging.error(f"OTO trigger file not found in temp folder: {oto_trigger}")
                display.error(f"Conditional OTO play could not be found: {oto_trigger}")
                success = False
        except Exception as e:
            logging.error(f"Failed to move OTO trigger {oto_trigger}: {e}")
            display.error(f"Failed to process OTO trigger {oto_trigger}: {e}")
            success = False
    
    play['status']['conditionals_handled'] = success
    save_play(play, play_file)
    
    logging.info(f"Conditional OCO / OTO plays handled for {play_file}")
    # display.info(f"Conditional OCO / OTO plays handled for {play_file}")
    
    return success

def reload_oco_peers(play, play_file):
    """Optionally reload OCO peers from TEMP to NEW after this play is closed.

    Controlled by config: options_swings.conditional_plays.reload_oco_peers (default False).
    Only moves plays that currently exist in the TEMP folder.
    """
    try:
        if not config.get('options_swings', 'conditional_plays', 'reload_oco_peers', default=False):
            return

        oco_triggers = play.get('conditional_plays', {}).get('OCO_triggers', [])
        if not oco_triggers:
            return

        plays_base_dir = os.path.abspath(os.path.dirname(os.path.dirname(play_file)))
        reloaded = []
        for oco_trigger in oco_triggers:
            temp_path = os.path.join(plays_base_dir, 'temp', oco_trigger)
            if os.path.exists(temp_path):
                try:
                    move_play_to_new(temp_path)
                    reloaded.append(oco_trigger)
                except Exception as e:
                    logging.error(f"Failed to auto-reload OCO peer {oco_trigger}: {e}")
                    display.error(f"Failed to auto-reload OCO peer {oco_trigger}: {e}")

        if reloaded:
            summary = ", ".join(reloaded)
            logging.info(f"OCO auto-reload: moved from TEMP->NEW: [{summary}]")
            # display.info(f"OCO auto-reload: TEMP->NEW for {len(reloaded)} play(s): [{summary}]")
    except Exception as e:
        logging.error(f"Error in reload_oco_peers: {e}")
        display.error(f"Error in reloading OCO peers: {e}")

def validate_bid_price(bid_price, symbol, fallback_price):
    """
    Validate bid price to ensure it's reasonable.
    
    Args:
        bid_price (float): The bid price to validate
        symbol (str): Symbol for logging
        fallback_price (float): Price to use if bid is invalid
        
    Returns:
        float: Valid bid price or fallback price
    """
    if bid_price is None or bid_price <= 0:
        logging.warning(f"Invalid bid price ({bid_price}) for {symbol}. Using fallback price.")
        display.warning(f"Invalid bid price ({bid_price}) for {symbol}. Using fallback price.")
        return fallback_price
        
    # Check if bid is suspiciously low compared to fallback
    if fallback_price > 0 and bid_price < (fallback_price * 0.5):
        logging.warning(f"Bid price (${bid_price:.2f}) is less than 50% of fallback price (${fallback_price:.2f})")
        display.warning(f"Bid price (${bid_price:.2f}) is less than 50% of fallback price (${fallback_price:.2f})")
        return fallback_price
        
    return bid_price

def handle_end_of_day_pending_plays():
    """Move pending plays back to their previous states at market close."""
    try:
        # Handle pending-opening plays
        pending_opening_dir = os.path.join(os.getcwd(), 'plays', 'pending-opening')
        if os.path.exists(pending_opening_dir):
            play_files = [os.path.join(pending_opening_dir, f) for f in os.listdir(pending_opening_dir) 
                         if f.endswith('.json')]
                         
            for play_file in play_files:
                try:
                    # Load play data first and verify it's valid
                    play = load_play(play_file)
                    if not play:
                        logging.error(f"Failed to load play data from {play_file}")
                        display.error(f"Failed to load play data from {play_file}")
                        continue
                    
                    # Update play status before moving
                    play['status'].update({
                        'order_id': None,
                        'order_status': None,
                        'play_status': 'NEW'
                    })
                    
                    # Save updated play data
                    if not save_play(play, play_file):
                        logging.error(f"Failed to save updated play data for {play_file}")
                        display.error(f"Failed to update play data for {play_file}")
                        continue
                    
                    # Move the play back to new
                    try:
                        move_play_to_new(play_file)
                        logging.info(f"Successfully moved play back to new: {play_file}")
                        # display.info(f"Successfully moved play back to new: {play_file}")
                    except Exception as e:
                        logging.error(f"Error moving play to new: {e}")
                        display.error(f"Error designating play as 'new': {e}")
                        
                except Exception as e:
                    logging.error(f"Error processing pending-opening play {play_file}: {e}")
                    display.error(f"Error processing pending-opening play {play_file}: {e}")

        # Handle pending-closing plays
        pending_closing_dir = os.path.join(os.getcwd(), 'plays', 'pending-closing')
        if os.path.exists(pending_closing_dir):
            play_files = [os.path.join(pending_closing_dir, f) for f in os.listdir(pending_closing_dir) 
                         if f.endswith('.json')]
                         
            for play_file in play_files:
                try:
                    # Load play data first and verify it's valid
                    play = load_play(play_file)
                    if not play:
                        logging.error(f"Failed to load play data from {play_file}")
                        display.error(f"Failed to load play data from {play_file}")
                        continue
                    
                    # Update play status before moving
                    play['status'].update({
                        'closing_order_id': None,
                        'closing_order_status': None,
                        'play_status': 'OPEN'
                    })
                    
                    # Save updated play data
                    if not save_play(play, play_file):
                        logging.error(f"Failed to save updated play data for {play_file}")
                        display.error(f"Failed to update play data for {play_file}")
                        continue
                    
                    # Move the play back to open
                    try:
                        move_play_to_open(play_file)
                        logging.info(f"Successfully moved play back to open: {play_file}")
                        # display.info(f"Successfully moved play back to open: {play_file}")
                    except Exception as e:
                        logging.error(f"Error moving play to open: {e}")
                        display.error(f"Error designating play as 'open': {e}")
                        
                except Exception as e:
                    logging.error(f"Error processing pending-closing play {play_file}: {e}")
                    display.error(f"Error processing pending-closing play {play_file}: {e}")

    except Exception as e:
        logging.error(f"Error handling end of day pending plays: {e}")
        display.error(f"Error handling end of day pending plays: {e}")

def manage_pending_plays(plays_dir, single_play=None):
    """
    Manage plays in pending-opening and pending-closing directories.
    Can handle either all pending plays or a single specified play.
    
    Args:
        plays_dir: Base directory containing play folders
        single_play: Optional; tuple of (play_data, play_file) to check single play
    
    Returns:
        bool: True if position exists/verified, False if position check failed
    """
    if single_play:
        play, play_file = single_play
        current_status = play.get('status', {}).get('play_status')
        if current_status not in ['PENDING-OPENING', 'PENDING-CLOSING']:
            return True  # Not a pending play, no action needed
    else:
        display.header("Managing pending plays...")
        logging.info("Managing pending plays")

    for pending_type in ['pending-opening', 'pending-closing']:
        # For single play mode, only process if it matches the current type
        if single_play:
            play, play_file = single_play
            if play.get('status', {}).get('play_status').lower() != pending_type:
                continue
            plays_to_process = [(play, play_file)]
        else:
            pending_dir = os.path.join(plays_dir, pending_type)
            if not os.path.exists(pending_dir):
                continue
            play_files = [os.path.join(pending_dir, f) for f in os.listdir(pending_dir) if f.endswith('.json')]
            plays_to_process = [(load_play(pf), pf) for pf in play_files if load_play(pf)]

        for play, play_file in plays_to_process:
            try:
                client = get_alpaca_client()
                contract_symbol = play.get('option_contract_symbol')
                
                # Handle pending-opening plays
                if pending_type == 'pending-opening':
                    order_id = play.get('status', {}).get('order_id')
                    if not order_id:
                        logging.error(f"No order ID found for pending-opening play: {play_file}")
                        continue

                    try:
                        order = client.get_order_by_id(order_id)
                        display.info(f"Pending-opening {contract_symbol}: order status = {order.status}")
                        if order.status == 'filled':
                            # Verify position exists
                            try:
                                position = client.get_open_position(contract_symbol)
                                if position is None:
                                    logging.error(f"Order filled but position not found for {contract_symbol}")
                                    display.error(f"Order filled, but position not found for {contract_symbol}")
                                    if single_play:
                                        return False
                                    continue
                                
                                play['status']['position_exists'] = True
                                save_play(play, play_file)
                                new_filepath = move_play_to_open(play_file)
                                if new_filepath:
                                    logging.info(f"Order filled and position verified, moved to open: {play_file}")
                                    display.success(f"Order filled and position verified: {play_file}")
                                    
                                    # Handle conditional plays after successful move to open
                                    handle_conditional_plays(play, new_filepath)
                                    
                                    if single_play:
                                        return True
                                
                            except Exception as e:
                                logging.error(f"Error verifying position: {str(e)}")
                                display.error(f"Error verifying position: {str(e)}")
                                if single_play:
                                    return False
                                continue
                                
                        elif order.status in ['canceled', 'expired', 'rejected']:
                            move_play_to_new(play_file)
                            logging.info(f"Order {order.status}, moved back to new: {play_file}")
                            display.info(f"Order {order.status}, moved back to new: {play_file}")
                            if single_play:
                                return False
                    except Exception as e:
                        logging.error(f"Error checking order status for {play_file}: {str(e)}")
                        display.error(f"Error checking order status for {play_file}: {str(e)}")
                        if single_play:
                            return False

                # Handle pending-closing plays
                elif pending_type == 'pending-closing':
                    order_id = play.get('status', {}).get('closing_order_id')
                    if not order_id:
                        logging.error(f"No closing order ID found for pending-closing play: {play_file}")
                        continue

                    try:
                        order = client.get_order_by_id(order_id)
                        display.info(f"Pending-closing {contract_symbol}: order status = {order.status}")
                        if order.status == 'filled':
                            # Verify position is closed
                            try:
                                position = client.get_open_position(contract_symbol)
                                if position is not None:
                                    logging.error(f"Closing order filled but position still exists for {contract_symbol}")
                                    display.error(f"Closing order filled, but position still exists for {contract_symbol}")
                                    if single_play:
                                        return False
                                    continue
                                
                                play['status']['position_exists'] = False
                                save_play(play, play_file)
                                move_play_to_closed(play_file)
                                # Optionally auto-reload OCO peers from TEMP to NEW
                                reload_oco_peers(play, play_file)
                                logging.info(f"Closing order filled and position closed, moved to closed: {play_file}")
                                display.success(f"Closing order filled and position closed: {play_file}")
                                if single_play:
                                    return True
                                
                            except Exception as e:
                                if "position does not exist" in str(e):
                                    # This is expected for a closing play
                                    play['status']['position_exists'] = False
                                    save_play(play, play_file)
                                    move_play_to_closed(play_file)
                                    # Optionally auto-reload OCO peers from TEMP to NEW
                                    reload_oco_peers(play, play_file)
                                    logging.info(f"Position confirmed closed, moved to closed: {play_file}")
                                    display.success(f"Position confirmed closed: {play_file}")
                                    if single_play:
                                        return True
                                else:
                                    logging.error(f"Error verifying position closure: {str(e)}")
                                    display.error(f"Error verifying position closure: {str(e)}")
                                    if single_play:
                                        return False
                                    continue
                                
                        elif order.status in ['canceled', 'expired', 'rejected']:
                            move_play_to_open(play_file)
                            logging.info(f"Closing order {order.status}, moved back to open: {play_file}")
                            display.info(f"Closing order {order.status}, moved back to open: {play_file}")
                            if single_play:
                                return False
                                
                    except Exception as e:
                        logging.error(f"Error checking closing order status for {play_file}: {str(e)}")
                        display.error(f"Error checking closing order status for {play_file}: {str(e)}")
                        if single_play:
                            return False

            except Exception as e:
                logging.error(f"Error managing pending play {play_file}: {str(e)}")
                display.error(f"Error managing pending play {play_file}: {str(e)}")
                if single_play:
                    return False

    return True  # Return True for both batch processing and if single play was processed without errors

if __name__ == "__main__":
    monitor_plays_continuously()