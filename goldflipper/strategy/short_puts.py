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
from goldflipper.data.market.manager import MarketDataManager
from goldflipper.tools.option_data_fetcher import calculate_greeks


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


def calculate_iv_rank(symbol: str, current_iv: float, market_data_manager: Optional[MarketDataManager] = None) -> Optional[float]:
    """
    Calculate IV Rank/Percentile for a symbol using current option chain data across multiple expirations.
    
    IV Rank = (Current IV - Min IV) / (Max IV - Min IV) * 100
    
    This implementation uses MarketDataManager to sample IV from ATM put options across 
    available expiration dates to build a distribution. This is a practical approximation 
    since true 1-year historical IV data may not be easily accessible.
    
    Args:
        symbol: Stock ticker symbol (e.g., 'SPY')
        current_iv: Current implied volatility (as decimal, e.g., 0.20 for 20%)
        market_data_manager: Optional MarketDataManager instance (creates new one if not provided)
        
    Returns:
        Optional[float]: IV Rank as percentage (0-100), or None if calculation fails
    """
    try:
        # Initialize MarketDataManager if not provided
        if market_data_manager is None:
            market_data_manager = MarketDataManager()
        
        # Get current stock price to find ATM options
        current_price = market_data_manager.get_stock_price(symbol)
        if not current_price:
            logging.warning(f"Could not get current price for {symbol} to calculate IV Rank")
            display.warning(f"Could not get current price for {symbol} to calculate IV Rank")
            return None
        
        # Get available expiration dates using MarketDataManager
        available_dates = market_data_manager.get_option_expirations(symbol)
        if not available_dates or len(available_dates) < 2:
            logging.warning(f"Insufficient expiration dates ({len(available_dates) if available_dates else 0}) for {symbol} IV Rank calculation")
            display.warning(f"Insufficient expiration dates for {symbol} IV Rank calculation")
            return None
        
        # Collect IV values from ATM puts across multiple expirations
        # MarketDataApp returns IV as decimal (e.g., 0.20 for 20%)
        iv_values = []
        max_expirations_to_check = min(12, len(available_dates))  # Check up to 12 expirations
        
        for exp_date in available_dates[:max_expirations_to_check]:
            try:
                # Get option chain for this expiration using provider directly
                # (MarketDataManager doesn't expose get_option_chain, but provider does)
                chain = market_data_manager.provider.get_option_chain(symbol, expiration_date=exp_date)
                puts = chain.get('puts')
                
                if puts is None or puts.empty:
                    continue
                
                # Find ATM put (closest strike to current price)
                # For IV Rank, we want strikes very close to ATM (within 2% of current price)
                strike_tolerance = current_price * 0.02  # 2% tolerance
                atm_puts = puts[(puts['strike'] >= current_price - strike_tolerance) & 
                               (puts['strike'] <= current_price + strike_tolerance)]
                
                if atm_puts.empty:
                    # If no puts within tolerance, use closest strike (prefer OTM)
                    strike_diff = (puts['strike'] - current_price).abs()
                    closest_idx = strike_diff.idxmin()
                    atm_puts = puts.loc[[closest_idx]]
                
                if not atm_puts.empty:
                    # Get implied volatility (standardized column name is 'implied_volatility')
                    # MarketDataApp returns IV as decimal (0.20 = 20%)
                    iv_value = atm_puts.iloc[0].get('implied_volatility')
                    if iv_value is not None:
                        # Convert to float and check for valid value
                        try:
                            iv_float = float(iv_value)
                            # Check for NaN and ensure positive
                            if iv_float == iv_float and iv_float > 0:  # Not NaN and positive
                                # Convert to percentage for consistency (0.20 -> 20.0)
                                iv_values.append(iv_float * 100)
                        except (ValueError, TypeError):
                            continue
                
            except Exception as e:
                logging.debug(f"Error getting IV from expiration {exp_date} for {symbol}: {str(e)}")
                continue
        
        if len(iv_values) < 3:
            logging.warning(f"Insufficient IV data points ({len(iv_values)}) for {symbol} IV Rank calculation")
            display.warning(f"Insufficient IV data points for {symbol} IV Rank calculation")
            return None
        
        # Calculate IV Rank
        min_iv = min(iv_values)
        max_iv = max(iv_values)
        
        if max_iv == min_iv:
            # All IV values are the same
            logging.warning(f"All IV values are identical for {symbol}, cannot calculate IV Rank")
            return 50.0  # Return middle value if all IVs are the same
        
        # Normalize current_iv to percentage format (all IV values are now in percentage)
        # MarketDataApp returns IV as decimal (0.20 = 20%), so if current_iv < 1.0, it's decimal
        if current_iv < 1.0:
            # Assume current_iv is in decimal form (0.20), convert to percentage (20.0)
            current_iv_pct = current_iv * 100
        else:
            # Assume current_iv is already in percentage form (20.0)
            current_iv_pct = current_iv
        
        # Calculate IV Rank: (Current IV - Min IV) / (Max IV - Min IV) * 100
        # All values are now in percentage format
        iv_rank = ((current_iv_pct - min_iv) / (max_iv - min_iv)) * 100
        
        # Clamp to 0-100 range
        iv_rank = max(0.0, min(100.0, iv_rank))
        
        logging.info(f"IV Rank for {symbol}: {iv_rank:.1f}% (Current IV: {current_iv_pct:.1f}%, Min: {min_iv:.1f}%, Max: {max_iv:.1f}%, Samples: {len(iv_values)})")
        display.info(f"IV Rank for {symbol}: {iv_rank:.1f}%")
        
        return iv_rank
        
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


def find_short_put_option(
    symbol: str,
    target_dte: int = 45,
    target_delta: float = 0.30,
    iv_rank_threshold: float = 50.0,
    market_data_manager: Optional[MarketDataManager] = None
) -> Optional[Dict[str, Any]]:
    """
    Find a short put option matching the strategy criteria.
    
    Args:
        symbol: Stock ticker symbol (e.g., 'SPY')
        target_dte: Target days to expiration (default: 45)
        target_delta: Target delta for puts (default: 0.30)
        iv_rank_threshold: Minimum IV Rank/Percentile required (default: 50.0)
        market_data_manager: Optional MarketDataManager instance (creates new one if not provided)
        
    Returns:
        Optional[Dict[str, Any]]: Option data dictionary with keys:
            - strike_price: Strike price
            - expiration_date: Expiration date (YYYY-MM-DD format)
            - expiration_date_formatted: Expiration date (MM/DD/YYYY format)
            - delta: Option delta
            - iv_rank: IV Rank percentage
            - implied_volatility: Implied volatility
            - bid: Bid price
            - ask: Ask price
            - mid: Mid price
            - option_contract_symbol: OCC option symbol
            Or None if no matching option found
    """
    try:
        # Initialize MarketDataManager if not provided
        if market_data_manager is None:
            market_data_manager = MarketDataManager()
        
        # Get configuration
        short_puts_config = config.get('short_puts', {})
        dte_range = short_puts_config.get('dte_range', [35, 49])
        delta_tolerance = short_puts_config.get('delta_tolerance', 0.05)
        
        # Get current stock price
        current_price = market_data_manager.get_stock_price(symbol)
        if not current_price:
            logging.error(f"Could not get current price for {symbol}")
            display.error(f"Could not get current price for {symbol}")
            return None
        
        # Get available expiration dates
        available_dates = market_data_manager.get_option_expirations(symbol)
        if not available_dates:
            logging.warning(f"No expiration dates available for {symbol}")
            display.warning(f"No expiration dates available for {symbol}")
            return None
        
        # Filter expirations by DTE range
        min_dte, max_dte = dte_range[0], dte_range[1]
        candidate_expirations = []
        
        for exp_date_str in available_dates:
            try:
                # Convert expiration date to datetime
                if isinstance(exp_date_str, str):
                    # Try YYYY-MM-DD format first
                    try:
                        exp_date = datetime.strptime(exp_date_str, '%Y-%m-%d')
                    except ValueError:
                        # Try MM/DD/YYYY format
                        try:
                            exp_date = datetime.strptime(exp_date_str, '%m/%d/%Y')
                        except ValueError:
                            continue
                else:
                    exp_date = exp_date_str
                
                dte = calculate_dte(exp_date.strftime('%Y-%m-%d'))
                if min_dte <= dte <= max_dte:
                    candidate_expirations.append((exp_date_str, dte))
            except Exception as e:
                logging.debug(f"Error processing expiration {exp_date_str}: {str(e)}")
                continue
        
        if not candidate_expirations:
            logging.warning(f"No expirations found in DTE range [{min_dte}, {max_dte}] for {symbol}")
            display.warning(f"No expirations found in DTE range [{min_dte}, {max_dte}] for {symbol}")
            return None
        
        # Sort by DTE (closest to target first)
        candidate_expirations.sort(key=lambda x: abs(x[1] - target_dte))
        
        # Try each expiration to find matching options
        best_option = None
        best_delta_diff = float('inf')
        
        for exp_date_str, dte in candidate_expirations:
            try:
                # Get option chain for this expiration
                chain = market_data_manager.provider.get_option_chain(symbol, expiration_date=exp_date_str)
                if not chain or 'puts' not in chain:
                    continue
                
                puts = chain.get('puts')
                if puts is None or puts.empty:
                    continue
                
                # Convert expiration date to proper format for calculate_greeks
                if isinstance(exp_date_str, str):
                    try:
                        exp_dt = datetime.strptime(exp_date_str, '%Y-%m-%d')
                    except ValueError:
                        try:
                            exp_dt = datetime.strptime(exp_date_str, '%m/%d/%Y')
                        except ValueError:
                            continue
                    exp_date_for_greeks = exp_dt.strftime('%Y-%m-%d')
                else:
                    exp_dt = exp_date_str
                    exp_date_for_greeks = exp_dt.strftime('%Y-%m-%d')
                
                # Use Greeks from provider if available, otherwise calculate as fallback
                puts_with_greeks = puts.copy()
                
                # Check if delta is already available from provider (MarketDataApp provides it)
                has_delta = 'delta' in puts_with_greeks.columns
                delta_values_valid = False
                
                if has_delta:
                    # Check if delta values are valid (not all zeros or None)
                    delta_col = puts_with_greeks['delta']
                    if delta_col is not None and not delta_col.empty:
                        # Check if there are any non-zero, non-null values
                        valid_deltas = delta_col.dropna()
                        if len(valid_deltas) > 0 and (valid_deltas != 0).any():
                            delta_values_valid = True
                            logging.debug(f"Using delta from MarketDataApp provider for {symbol} expiration {exp_date_str}")
                
                # Only calculate Greeks if not available from provider
                if not delta_values_valid:
                    try:
                        logging.debug(f"Delta not available from provider, calculating Greeks for {symbol} expiration {exp_date_str}")
                        # Ensure puts DataFrame has required columns
                        # Add option_type column if missing
                        if 'option_type' not in puts_with_greeks.columns:
                            puts_with_greeks['option_type'] = 'put'
                        
                        # Calculate Greeks as fallback
                        puts_with_greeks = calculate_greeks(puts_with_greeks, current_price, exp_date_for_greeks)
                    except Exception as e:
                        logging.warning(f"Error calculating Greeks for {symbol} expiration {exp_date_str}: {str(e)}")
                        continue
                
                # Filter puts by delta tolerance
                valid_puts = []
                for idx, row in puts_with_greeks.iterrows():
                    delta = row.get('delta')
                    if delta is None:
                        continue
                    
                    # Use absolute value for delta comparison (puts have negative delta)
                    abs_delta = abs(float(delta))
                    delta_diff = abs(abs_delta - target_delta)
                    
                    if delta_diff <= delta_tolerance:
                        valid_puts.append((idx, row, delta_diff))
                
                # Find best option from valid puts (closest to target delta)
                for idx, row, delta_diff in valid_puts:
                    # Get IV for IV Rank calculation
                    iv = row.get('impliedVolatility') or row.get('implied_volatility')
                    if iv is None:
                        continue
                    
                    # Convert IV to decimal if needed
                    iv_float = float(iv)
                    if iv_float > 1.0:  # If in percentage form, convert to decimal
                        iv_float = iv_float / 100.0
                    
                    # Calculate IV Rank
                    iv_rank = calculate_iv_rank(symbol, iv_float, market_data_manager)
                    
                    # Check IV Rank threshold
                    if iv_rank is None or iv_rank < iv_rank_threshold:
                        continue
                    
                    # Check if this is the best option so far (closest delta to target)
                    if delta_diff < best_delta_diff:
                        best_delta_diff = delta_diff
                        
                        # Get bid/ask/mid prices
                        bid = float(row.get('bid', 0.0))
                        ask = float(row.get('ask', 0.0))
                        mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else float(row.get('lastPrice', 0.0))
                        
                        # Build OCC option symbol
                        strike = float(row['strike'])
                        strike_tenths_cents = int(round(strike * 1000))
                        padded_strike = f"{strike_tenths_cents:08d}"
                        option_type = "P"
                        occ_symbol = f"{symbol}{exp_dt.strftime('%y%m%d')}{option_type}{padded_strike}"
                        
                        best_option = {
                            'strike_price': str(strike),
                            'expiration_date': exp_date_str,
                            'expiration_date_formatted': exp_dt.strftime('%m/%d/%Y'),
                            'dte': dte,
                            'delta': float(row['delta']),
                            'abs_delta': abs_delta,
                            'iv_rank': iv_rank,
                            'implied_volatility': iv_float,
                            'bid': bid,
                            'ask': ask,
                            'mid': mid,
                            'option_contract_symbol': occ_symbol,
                            'symbol': symbol
                        }
                
            except Exception as e:
                logging.warning(f"Error processing expiration {exp_date_str} for {symbol}: {str(e)}")
                continue
        
        if best_option:
            logging.info(f"Found matching short put option for {symbol}: Strike {best_option['strike_price']}, "
                        f"DTE {best_option['dte']}, Delta {best_option['abs_delta']:.3f}, IV Rank {best_option['iv_rank']:.1f}%")
            display.success(f"Found matching short put: {best_option['option_contract_symbol']} "
                          f"(Strike: {best_option['strike_price']}, DTE: {best_option['dte']}, "
                          f"Delta: {best_option['abs_delta']:.3f}, IV Rank: {best_option['iv_rank']:.1f}%)")
            return best_option
        else:
            logging.warning(f"No matching short put option found for {symbol} with criteria: "
                          f"DTE [{min_dte}, {max_dte}], Delta {target_delta}±{delta_tolerance}, IV Rank >{iv_rank_threshold}%")
            display.warning(f"No matching short put option found for {symbol}")
            return None
            
    except Exception as e:
        logging.error(f"Error finding short put option for {symbol}: {str(e)}")
        display.error(f"Error finding short put option for {symbol}: {str(e)}")
        return None

