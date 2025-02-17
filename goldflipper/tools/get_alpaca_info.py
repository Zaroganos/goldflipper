#!/usr/bin/env python
import sys
import os
import json
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

from ..alpaca_client import get_alpaca_client
from ..utils.display import TerminalDisplay as display
from ..config.config import config

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
        # Get active account nickname for display
        active_account = config.get('alpaca', 'active_account')
        account_nickname = config.get('alpaca', 'accounts')[active_account].get(
            'nickname', active_account.replace('_', ' ').title()
        )
        
        order = client.get_order_by_id(order_id)
        return {
            'account': account_nickname,  # Add account nickname to response
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

def test_alpaca_connection():
    """Test the connection to Alpaca API and return debug info."""
    from ..alpaca_client import get_alpaca_client
    from ..config.config import config
    client = get_alpaca_client()
    active_account = config.get('alpaca', 'active_account')
    account_nickname = config.get('alpaca', 'accounts')[active_account].get(
        'nickname', active_account.replace('_', ' ').title()
    )
    
    debug_message = f"[DEBUG] test_alpaca_connection() using active_account: '{active_account}'\n"
    try:
        account = client.get_account()
        debug_message += f"[DEBUG] Returned account.status: {account.status}, buying power: {account.buying_power}"
        return True, debug_message
    except Exception as e:
        debug_message += f"[DEBUG] test_alpaca_connection() failed with error: {str(e)}"
        return False, debug_message

def main():
    """Main function to test the Alpaca info retrieval functions"""
    # Test connection
    if not test_alpaca_connection():
        return

    # Define a standard separator length
    SEP_LENGTH = 50

    # Get base plays directory
    base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plays')
    folders = ['new', 'pending-opening', 'open', 'pending-closing', 'closed', 'expired']

    display.header("Checking Plays Status...")
    
    for folder in folders:
        folder_path = os.path.join(base_dir, folder)
        if not os.path.exists(folder_path):
            continue
            
        display.header(f"\nChecking {folder.upper()} folder")
        
        # Get all JSON files in the folder
        play_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
        
        if not play_files:
            display.info(f"No plays found in {folder}")
            continue
            
        for play_file in play_files:
            file_path = os.path.join(folder_path, play_file)
            try:
                with open(file_path, 'r') as f:
                    play = json.load(f)
                
                # Create a visual separator for each play
                display.success("=" * SEP_LENGTH)  # Green top border
                display.header(f"Play: {play.get('play_name', play_file)}")
                display.success("-" * SEP_LENGTH)  # Green separator
                
                # Check if play has status and order_id
                if 'status' in play:
                    # Check for main order_id
                    if play['status'].get('order_id'):
                        order_id = play['status']['order_id']
                        display.info(f"Main Order ID: {order_id}")
                        
                        order_info = get_order_info(order_id)
                        if order_info:
                            for key, value in order_info.items():
                                key_str = f"  {key}:"
                                display.info(f"{key_str:<30} {value}")
                        else:
                            display.warning("No main order information found")
                    
                    # Check for closing_order_id
                    if play['status'].get('closing_order_id'):
                        closing_order_id = play['status']['closing_order_id']
                        display.info(f"\nClosing Order ID: {closing_order_id}")
                        
                        closing_order_info = get_order_info(closing_order_id)
                        if closing_order_info:
                            for key, value in closing_order_info.items():
                                key_str = f"  {key}:"
                                display.info(f"{key_str:<30} {value}")
                        else:
                            display.warning("No closing order information found")
                            
                    # Check for contingency_order_id
                    if play['status'].get('contingency_order_id'):
                        contingency_order_id = play['status']['contingency_order_id']
                        display.info(f"\nContingency Order ID: {contingency_order_id}")
                        
                        contingency_order_info = get_order_info(contingency_order_id)
                        if contingency_order_info:
                            for key, value in contingency_order_info.items():
                                key_str = f"  {key}:"
                                display.info(f"{key_str:<30} {value}")
                        else:
                            display.warning("No contingency order information found")
                            
                    if not any([play['status'].get('order_id'),
                              play['status'].get('closing_order_id'),
                              play['status'].get('contingency_order_id')]):
                        display.info("\nNo order IDs found in play")
                else:
                    display.info("\nNo status information found in play")
                
                # Close the play card
                display.success("=" * SEP_LENGTH + "\n")  # Green bottom border
                    
            except Exception as e:
                display.error(f"Error processing {play_file}: {str(e)}")
                continue

    # Get all positions
    display.header("\nChecking Open Positions...")
    positions = get_all_positions()
    if positions:
        for symbol, info in positions.items():
            display.success("=" * SEP_LENGTH)  # Green top border
            display.header(f"Symbol: {symbol}")
            display.success("-" * SEP_LENGTH)  # Green separator
            for key, value in info.items():
                key_str = f"  {key}:"
                display.info(f"{key_str:<30} {value}")
            display.success("=" * SEP_LENGTH + "\n")  # Green bottom border
    else:
        display.info("No open positions found")

    try:
        print("Alpaca Info Tool\n-------------------")
        print("Fetching Orders:")
        orders = get_all_orders()
        if orders:
            print(json.dumps(orders, indent=4))
        else:
            print("Failed to retrieve orders.")

        print("\nFetching Positions:")
        positions = get_all_positions()
        if positions:
            print(json.dumps(positions, indent=4))
        else:
            print("Failed to retrieve positions.")

        print("\nTesting Connection:")
        success, debug_msg = test_alpaca_connection()
        print(debug_msg)
    except Exception as exc:
        print(f"An error occurred: {exc}")
    finally:
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    # Ensure proper package resolution for relative imports in frozen mode.
    if __package__ is None:
        __package__ = "goldflipper.tools"
    main()
