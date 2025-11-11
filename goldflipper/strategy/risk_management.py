"""
Risk Management Module

This module contains functions for risk management and position sizing validation,
specifically for short puts strategy positions.
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple
from goldflipper.json_parser import load_play
from goldflipper.alpaca_client import get_alpaca_client
from goldflipper.config.config import config
from goldflipper.utils.display import TerminalDisplay as display


def get_account_buying_power() -> Optional[float]:
    """
    Get account buying power from Alpaca.
    
    Returns:
        Optional[float]: Options buying power or regular buying power, or None if error
    """
    client = get_alpaca_client()
    try:
        account = client.get_account()
        # Prefer options_buying_power if available, otherwise use buying_power
        buying_power = getattr(account, 'options_buying_power', None)
        if buying_power is None:
            buying_power = getattr(account, 'buying_power', None)
        
        if buying_power is not None:
            return float(buying_power)
        
        logging.error("Could not retrieve buying power from account")
        display.error("Could not retrieve buying power from account")
        return None
        
    except Exception as e:
        logging.error(f"Error getting account buying power: {str(e)}")
        display.error(f"Error getting account buying power: {str(e)}")
        return None


def get_portfolio_exposure() -> Dict[str, float]:
    """
    Scan all OPEN plays and calculate total buying power used and notional exposure for SHORT positions.
    
    Returns:
        Dict with keys:
        - total_bp_used: Total buying power used for SHORT positions
        - total_notional: Total notional exposure for SHORT positions
    """
    total_bp_used = 0.0
    total_notional = 0.0
    
    try:
        # Get path to plays directory
        # From goldflipper/strategy/risk_management.py, go up to project root, then into plays
        current_file_dir = os.path.dirname(os.path.abspath(__file__))  # goldflipper/strategy
        project_root = os.path.dirname(os.path.dirname(current_file_dir))  # project root
        open_folder = os.path.join(project_root, 'plays', 'open')
        
        if not os.path.exists(open_folder):
            logging.debug("No 'open' folder found, assuming no open positions")
            return {'total_bp_used': 0.0, 'total_notional': 0.0}
        
        # Scan all JSON files in open folder
        for filename in os.listdir(open_folder):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(open_folder, filename)
            try:
                play = load_play(filepath)
                if not play:
                    continue
                
                # Only count SHORT positions
                position_side = play.get('position_side', 'LONG').upper()
                if position_side != 'SHORT':
                    continue
                
                # Calculate buying power and notional for this position
                strike_price = float(play.get('strike_price', 0))
                contracts = int(play.get('contracts', 1))
                
                if strike_price > 0 and contracts > 0:
                    bp_required = strike_price * 100 * contracts
                    notional = strike_price * 100 * contracts
                    
                    total_bp_used += bp_required
                    total_notional += notional
                    
            except Exception as e:
                logging.debug(f"Error processing play file {filename} for risk calculation: {str(e)}")
                continue
        
        return {
            'total_bp_used': total_bp_used,
            'total_notional': total_notional
        }
        
    except Exception as e:
        logging.error(f"Error calculating portfolio exposure: {str(e)}")
        display.error(f"Error calculating portfolio exposure: {str(e)}")
        return {'total_bp_used': 0.0, 'total_notional': 0.0}


def validate_short_put_risk(play: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate that a short put position meets risk management requirements.
    
    Checks:
    1. Buying power requirement for the position
    2. Total capital allocation limit (max % of account)
    3. Total notional leverage limit (max 3x account value)
    
    Args:
        play: Play dictionary containing position details
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
        - is_valid: True if position passes all checks
        - error_message: None if valid, otherwise error description
    """
    try:
        # Only validate SHORT positions
        position_side = play.get('position_side', 'LONG').upper()
        if position_side != 'SHORT':
            return True, None  # No validation needed for LONG positions
        
        # Get short puts configuration
        short_puts_config = config.get('short_puts', {})
        max_capital_allocation = short_puts_config.get('max_capital_allocation', 0.50)  # Default 50%
        max_notional_leverage = short_puts_config.get('max_notional_leverage', 3.0)  # Default 3x
        
        # Calculate required buying power for this position
        strike_price = float(play.get('strike_price', 0))
        contracts = int(play.get('contracts', 1))
        
        if strike_price <= 0 or contracts <= 0:
            return False, f"Invalid strike price ({strike_price}) or contracts ({contracts})"
        
        required_bp = strike_price * 100 * contracts
        notional_exposure = strike_price * 100 * contracts  # Same as BP for cash-secured puts
        
        # Check 1: Buying power availability
        available_bp = get_account_buying_power()
        if available_bp is None:
            return False, "Could not retrieve account buying power"
        
        if required_bp > available_bp:
            return False, (f"Insufficient buying power. Required: ${required_bp:,.2f}, "
                          f"Available: ${available_bp:,.2f}")
        
        # Check 2: Capital allocation limit
        # Get account equity
        client = get_alpaca_client()
        try:
            account = client.get_account()
            account_equity = float(getattr(account, 'equity', 0))
        except Exception as e:
            logging.error(f"Error getting account equity: {str(e)}")
            account_equity = available_bp  # Fallback to buying power as approximation
        
        if account_equity <= 0:
            return False, "Could not retrieve account equity"
        
        # Get current portfolio exposure
        portfolio = get_portfolio_exposure()
        total_bp_used = portfolio['total_bp_used'] + required_bp
        max_allocation = account_equity * max_capital_allocation
        
        if total_bp_used > max_allocation:
            return False, (f"Exceeds capital allocation limit. "
                          f"Used: ${total_bp_used:,.2f}, Limit: ${max_allocation:,.2f} "
                          f"({max_capital_allocation*100:.0f}% of account)")
        
        # Check 3: Notional leverage limit
        total_notional = portfolio['total_notional'] + notional_exposure
        max_notional = account_equity * max_notional_leverage
        
        if total_notional > max_notional:
            return False, (f"Exceeds notional leverage limit. "
                          f"Notional: ${total_notional:,.2f}, Limit: ${max_notional:,.2f} "
                          f"({max_notional_leverage}x account value)")
        
        # All checks passed
        logging.info(f"Risk validation passed for {play.get('symbol', 'unknown')}: "
                    f"Required BP: ${required_bp:,.2f}, Notional: ${notional_exposure:,.2f}")
        display.info(f"Risk validation passed: Required BP: ${required_bp:,.2f}")
        return True, None
        
    except Exception as e:
        logging.error(f"Error validating short put risk: {str(e)}")
        display.error(f"Error validating short put risk: {str(e)}")
        return False, f"Error during risk validation: {str(e)}"

