"""
Short Puts Strategy Module

This module contains functions for implementing the Short Puts trading strategy,
including option selection, IV Rank calculation, DTE calculation, and risk management.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from goldflipper.config.config import config
from goldflipper.utils.display import TerminalDisplay as display


def calculate_dte(expiration_date: str) -> int:
    """
    Calculate days to expiration (DTE) from an expiration date string.
    
    Args:
        expiration_date: Expiration date in format 'MM/DD/YYYY' or 'YYYY-MM-DD'
        
    Returns:
        int: Days to expiration (0 if already expired)
    """
    try:
        # Try MM/DD/YYYY format first
        try:
            exp_date = datetime.strptime(expiration_date, "%m/%d/%Y")
        except ValueError:
            # Try YYYY-MM-DD format
            try:
                exp_date = datetime.strptime(expiration_date, "%Y-%m-%d")
            except ValueError:
                # Try other common formats
                exp_date = datetime.strptime(expiration_date, "%m-%d-%Y")
        
        today = datetime.now().date()
        exp_date_only = exp_date.date()
        
        dte = (exp_date_only - today).days
        
        # Return 0 if expired
        return max(0, dte)
        
    except Exception as e:
        logging.error(f"Error calculating DTE for date '{expiration_date}': {str(e)}")
        display.error(f"Error calculating DTE for date '{expiration_date}': {str(e)}")
        return 0


def calculate_iv_rank(symbol: str, current_iv: float) -> Optional[float]:
    """
    Calculate IV Rank/Percentile for a symbol using 1-year historical IV data.
    
    IV Rank = (Current IV - Min IV) / (Max IV - Min IV) * 100
    
    Args:
        symbol: Stock ticker symbol (e.g., 'SPY')
        current_iv: Current implied volatility (as decimal, e.g., 0.20 for 20%)
        
    Returns:
        Optional[float]: IV Rank as percentage (0-100), or None if calculation fails
    """
    try:
        # TODO: Implement historical IV data fetching
        # For now, return None to indicate not implemented yet
        # This will be implemented in a later phase when we have historical data access
        logging.warning(f"IV Rank calculation not yet implemented for {symbol}")
        display.warning(f"IV Rank calculation not yet implemented for {symbol}")
        return None
        
    except Exception as e:
        logging.error(f"Error calculating IV Rank for {symbol}: {str(e)}")
        display.error(f"Error calculating IV Rank for {symbol}: {str(e)}")
        return None


def check_entry_conditions(
    symbol: str,
    option_data: Dict[str, Any],
    dte: int,
    delta: float,
    iv_rank: Optional[float] = None
) -> Tuple[bool, Optional[str]]:
    """
    Check if entry conditions are met for a short put position.
    
    Args:
        symbol: Stock ticker symbol
        option_data: Dictionary containing option data (strike, expiration, etc.)
        dte: Days to expiration
        delta: Option delta (absolute value for puts, typically negative)
        iv_rank: IV Rank/Percentile (optional, None if not available)
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, reason_if_invalid)
    """
    try:
        short_puts_config = config.get('short_puts', {})
        
        # Check DTE range
        dte_range = short_puts_config.get('dte_range', [35, 49])
        min_dte, max_dte = dte_range[0], dte_range[1]
        
        if not (min_dte <= dte <= max_dte):
            return False, f"DTE {dte} outside acceptable range [{min_dte}, {max_dte}]"
        
        # Check delta (use absolute value since puts have negative delta)
        target_delta = short_puts_config.get('target_delta', 0.30)
        delta_tolerance = short_puts_config.get('delta_tolerance', 0.05)
        abs_delta = abs(delta)
        
        if abs(abs_delta - target_delta) > delta_tolerance:
            return False, f"Delta {abs_delta:.3f} outside target range [{target_delta - delta_tolerance:.3f}, {target_delta + delta_tolerance:.3f}]"
        
        # Check IV Rank if available
        if iv_rank is not None:
            iv_rank_threshold = short_puts_config.get('iv_rank_threshold', 50)
            if iv_rank < iv_rank_threshold:
                return False, f"IV Rank {iv_rank:.1f}% below threshold {iv_rank_threshold}%"
        
        return True, None
        
    except Exception as e:
        logging.error(f"Error checking entry conditions: {str(e)}")
        display.error(f"Error checking entry conditions: {str(e)}")
        return False, f"Error during validation: {str(e)}"


def calculate_short_put_risk(play: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate risk metrics for a short put position.
    
    Args:
        play: Play dictionary containing strike_price and contracts
        
    Returns:
        Dict with risk metrics:
        - buying_power_required: Cash needed (strike * 100 * contracts)
        - notional_exposure: Total notional value (strike * 100 * contracts)
    """
    try:
        strike_price = float(play.get('strike_price', 0))
        contracts = int(play.get('contracts', 1))
        
        buying_power_required = strike_price * 100 * contracts
        notional_exposure = strike_price * 100 * contracts
        
        return {
            'buying_power_required': buying_power_required,
            'notional_exposure': notional_exposure
        }
        
    except Exception as e:
        logging.error(f"Error calculating short put risk: {str(e)}")
        display.error(f"Error calculating short put risk: {str(e)}")
        return {
            'buying_power_required': 0.0,
            'notional_exposure': 0.0
        }


def should_roll_position(
    play: Dict[str, Any],
    roll_dte: int = 21,
    challenge_threshold: float = 1.5
) -> Tuple[bool, Optional[str]]:
    """
    Determine if a short put position should be rolled.
    
    Args:
        play: Play dictionary containing expiration_date and entry_point
        roll_dte: DTE threshold for rolling (default: 21)
        challenge_threshold: Premium multiplier threshold for "challenged" condition (default: 1.5)
        
    Returns:
        Tuple[bool, Optional[str]]: (should_roll, reason)
    """
    try:
        expiration_date = play.get('expiration_date')
        if not expiration_date:
            return False, "No expiration date found"
        
        # Calculate current DTE
        current_dte = calculate_dte(expiration_date)
        
        # Check DTE threshold
        if current_dte <= roll_dte:
            return True, f"DTE {current_dte} <= roll threshold {roll_dte}"
        
        # Check if "challenged" (premium increased significantly)
        entry_point = play.get('entry_point', {})
        entry_credit = entry_point.get('entry_credit') or entry_point.get('entry_premium')
        
        if entry_credit:
            # Get current premium (would need to fetch from market data)
            # For now, we'll skip this check and rely on DTE only
            # TODO: Implement premium check when monitoring is active
            pass
        
        return False, None
        
    except Exception as e:
        logging.error(f"Error determining roll status: {str(e)}")
        display.error(f"Error determining roll status: {str(e)}")
        return False, f"Error during roll check: {str(e)}"

