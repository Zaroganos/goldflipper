import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from goldflipper.alpaca_client import get_alpaca_client
from goldflipper.utils.display import TerminalDisplay as display
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

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
        orders = client.get_orders(status=status)
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

def test_alpaca_connection():
    """Test the connection to Alpaca API"""
    client = get_alpaca_client()
    try:
        account = client.get_account()
        display.success("Successfully connected to Alpaca API")
        display.info(f"Account Status: {account.status}")
        display.info(f"Buying Power: ${float(account.buying_power):.2f}")
        return True
    except Exception as e:
        display.error(f"Failed to connect to Alpaca API: {str(e)}")
        return False

def main():
    """Main function to test the Alpaca info retrieval functions"""
    # Test connection
    if not test_alpaca_connection():
        return

    # Get all open orders
    display.header("Checking Open Orders...")
    open_orders = get_all_orders('open')
    if open_orders:
        for order_id, info in open_orders.items():
            display.info(f"Order ID: {order_id}")
            for key, value in info.items():
                display.info(f"  {key}: {value}")
    else:
        display.info("No open orders found")

    # Get all positions
    display.header("Checking Open Positions...")
    positions = get_all_positions()
    if positions:
        for symbol, info in positions.items():
            display.info(f"Symbol: {symbol}")
            for key, value in info.items():
                display.info(f"  {key}: {value}")
    else:
        display.info("No open positions found")

if __name__ == "__main__":
    main()
