"""
Weekly Expected Moves (WEM) Analysis Tool

This page provides functionality for:
1. Viewing and managing WEM stock list
2. Calculating and displaying expected moves
3. Exporting data to Excel
4. Managing user preferences for WEM stocks

RECENT FIXES (2025-06-21):
==========================
- Fixed MarketDataApp provider option splitting logic to use 'side' field instead of symbol parsing
- Resolved database schema mismatch where web app used different database than command-line tools
- Added proper database path configuration in web launcher to ensure consistency
- Fixed WEM calculation displaying stock price levels instead of option premiums
- Cleared corrupted weekly cache that contained wrong option chain data
- All WEM calculations now correctly show:
  * Straddle Level: ATM call + ATM put premiums (~$10-12)
  * Strangle Level: ITM call + ITM put premiums (~$10-12) 
  * S1/S2: Stock price ± WEM Points (stock price levels ~$580-610)
- Fixed Delta 16+/- calculation to use actual delta values from option chain

NEW FEATURES (Current Session):
===============================
- Added modular Delta 16+/- quality validation system with UI controls
- Validation checks include:
  * Strike coverage and density validation
  * Strike interval quality assessment  
  * Time to expiration proximity checks
  * Delta distribution quality validation
  * Bid-ask spread quality assessment
  * Delta match accuracy validation
- User-configurable validation thresholds via sidebar controls
- Validation can be enabled/disabled and fine-tuned per user preference
- Comprehensive logging of validation results and warnings
- Graceful degradation: poor quality matches are rejected only when validation enabled

TECHNICAL DETAILS:
==================
WEM Calculation Method: Automated Full Chain Analysis with Holiday Handling
- Gets full weekly option chain for next Friday expiration (with smart holiday adjustment)
- Auto-detects ATM strike closest to current stock price
- Selects adjacent strikes for ITM options (one above/below ATM)
- Finds actual Delta 16+ (call ~0.16 delta) and Delta 16- (put ~-0.16 delta) options
- Calculates WEM Points = (Straddle + Strangle) / 2
- Additionally calculates proper Delta 16+/- values using actual option deltas
- Uses MarketDataApp provider with proper call/put separation

HOLIDAY HANDLING:
=================
- Automatically detects US market holidays (Independence Day, Christmas, etc.)
- When Friday is a holiday, adjusts expiration to Thursday (industry standard)
- Includes comprehensive fallback mechanism to try alternative expiration dates
- Handles cases like July 4th, 2025 (Friday) → July 3rd, 2025 (Thursday) expiration
- Logs all adjustments for transparency and debugging
- Covers all major US market holidays with proper weekend adjustments
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
import yaml
import time
import random
from typing import Any
from io import StringIO

# Set up logging in a Streamlit-safe way
project_root = Path(__file__).parent.parent.parent
log_dir = project_root / 'logs'  # Correct path: goldflipper/logs not goldflipper/goldflipper/logs
log_dir.mkdir(exist_ok=True)

# Load settings to check debug mode  
settings_file = project_root / 'goldflipper' / 'config' / 'settings.yaml'
settings = {}
if settings_file.exists():
    with open(settings_file, 'r') as f:
        settings = yaml.safe_load(f)

def setup_wem_logging():
    """Set up logging for WEM session - called when actually running WEM operations"""
    # Create a per-session log file with timestamp - each WEM generation gets its own log
    session_timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    log_file = log_dir / f'wem_{session_timestamp}.log'
    
    # Get or create logger for this module
    logger = logging.getLogger(__name__)
    
    # Clear any existing handlers to prevent duplication
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Prevent propagation to avoid duplication
    
    # Create file handler for this session
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')  # 'w' mode for new session
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    )
    logger.addHandler(file_handler)
    
    # Create debug file handler if debug enabled
    debug_enabled = settings.get('logging', {}).get('debug', {}).get('enabled', False)
    if debug_enabled:
        logger.setLevel(logging.DEBUG)
        debug_handler = logging.FileHandler(log_dir / f'wem_debug_{session_timestamp}.log', mode='w')
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(debug_handler)
    
    # Log session start
    logger.info("=" * 80)
    logger.info(f"WEM CALCULATION SESSION STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Session ID: {session_timestamp}")
    logger.info(f"Log File: wem_{session_timestamp}.log")
    logger.info("=" * 80)
    
    # Ensure the log gets written to disk immediately
    for handler in logger.handlers:
        handler.flush()
    
    return logger

# Create a basic logger for module-level messages (no file handler yet)
logger = logging.getLogger(__name__)
if not logger.handlers:  # Only set up basic logging if no handlers exist
    logger.setLevel(logging.INFO)
    logger.propagate = False

# Now import the rest of the modules
import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta
import sys
import os
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc

# Add the project root to the Python path
sys.path.append(str(project_root))

from goldflipper.database.connection import get_db_connection, init_db
from goldflipper.database.models import WEMStock, MarketData
from goldflipper.database.repositories import MarketDataRepository
from goldflipper.data.market.manager import MarketDataManager
from goldflipper.config.config import config
from goldflipper.utils.market_holidays import (
    is_market_holiday,
    find_next_friday_expiration,
    find_previous_friday,
    get_expiration_date_candidates,
    test_holiday_detection_ui
)

# Initialize session state for tracking newly added stocks
if 'newly_added_stocks' not in st.session_state:
    st.session_state.newly_added_stocks = set()

# Page configuration
st.set_page_config(
    page_title="Weekly Expected Moves (WEM)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add custom CSS for wider dropdowns
st.markdown("""
<style>
    div[data-testid="stMultiSelect"] {
        min-width: 300px;
    }
    div[data-testid="stMultiSelect"] > div {
        min-width: 300px;
    }
    div.stMultiSelect > div[data-baseweb="select"] > div {
        min-width: 300px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize market data manager
@st.cache_resource
def get_market_data_manager():
    """Get or create the singleton MarketDataManager instance"""
    try:
        manager = MarketDataManager()
        # Check that we have at least one working provider
        if not manager.providers:
            st.error("No market data providers are configured and enabled. Please check your settings.")
            logger.error("No market data providers available. Check settings.yaml configuration.")
            return None
        
        # Log available providers
        logger.info(f"Available market data providers: {list(manager.providers.keys())}")
        logger.info(f"Using primary provider: {manager.provider.__class__.__name__}")
        
        return manager
    except Exception as e:
        st.error(f"Failed to initialize market data manager: {str(e)}")
        logger.error(f"Failed to initialize market data manager: {str(e)}", exc_info=True)
        return None

def get_wem_stocks(session: Session, from_date=None, to_date=None, symbols=None) -> List[Dict[str, Any]]:
    """
    Get WEM stocks from database with optional filtering.
    
    Args:
        session: Database session
        from_date: Optional start date for filtering
        to_date: Optional end date for filtering
        symbols: Optional list of stock symbols to include
        
    Returns:
        List of WEM stocks as dictionaries ordered by preferred default order
    """
    query = session.query(WEMStock)
    
    # Apply date filter if provided
    if from_date and to_date:
        query = query.filter(WEMStock.last_updated >= from_date)
        query = query.filter(WEMStock.last_updated <= to_date)
    
    # Apply symbol filter if provided
    if symbols and len(symbols) > 0:
        query = query.filter(WEMStock.symbol.in_(symbols))
    
    # Execute query and convert to dictionaries
    stocks = query.all()
    stock_dicts = [stock.to_dict() for stock in stocks]
    
    # Define preferred order for display (matches default stocks order)
    preferred_order = ['SPY', 'QQQ', 'VIX', 'NKE', 'SHOP', 'DLTR', 'WMT', 'TSLA', 'COIN', 'SBUX', 'PLTR', 'AMD', 'DIS']
    
    # Sort stocks by preferred order, with any additional stocks at the end alphabetically
    def sort_key(stock_dict):
        symbol = stock_dict.get('symbol', '')
        try:
            # Return index in preferred order if found
            return (0, preferred_order.index(symbol))
        except ValueError:
            # Return high index + alphabetical sort for stocks not in preferred list
            return (1, symbol)
    
    sorted_stocks = sorted(stock_dicts, key=sort_key)
    
    logger.info(f"Retrieved {len(sorted_stocks)} WEM stocks matching filters, ordered by preference")
    
    return sorted_stocks

def get_default_wem_stocks(session: Session) -> List[Dict[str, Any]]:
    """Get default WEM stocks from database as dictionaries"""
    stocks = session.query(WEMStock).filter_by(is_default=True).all()
    return [stock.to_dict() for stock in stocks]

def get_market_data(session: Session, symbol: str, days: int = 30) -> List[MarketData]:
    """Get recent market data for a symbol"""
    repo = MarketDataRepository(session)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)
    return repo.get_price_history(symbol, start_time, end_time)

def get_latest_market_data(session: Session, symbol: str) -> Optional[MarketData]:
    """Get latest market data for a symbol"""
    repo = MarketDataRepository(session)
    return repo.get_latest_price(symbol)

def update_market_data(session: Session, symbol: str, regular_hours_only: bool = False) -> Optional[MarketData]:
    """Update market data for a symbol
    
    Args:
        session: Database session
        symbol: Stock symbol
        regular_hours_only: If True, uses regular hours close instead of extended hours
    """
    try:
        manager = get_market_data_manager()
        if not manager:
            logger.error(f"No market data manager available for {symbol}")
            st.error("Market data manager is not available. Please check your configuration.")
            return None
            
        repo = MarketDataRepository(session)
        
        # Get live price from market data provider with pricing mode
        pricing_mode = "regular hours only" if regular_hours_only else "including extended hours"
        logger.info(f"Requesting price data for {symbol} from {manager.provider.__class__.__name__} ({pricing_mode})")
        price = manager.get_stock_price(symbol, regular_hours_only)
        if price is None:
            st.warning(f"Could not get current price for {symbol}")
            logger.warning(f"Could not get price for {symbol} from any provider")
            return None
            
        # Create new market data entry
        market_data = MarketData(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            close=price,  # Use as close since it's current price
            source=f"{manager.provider.__class__.__name__}_{'regular' if regular_hours_only else 'extended'}"
        )
        
        try:
            # Get option data if available
            logger.debug(f"Attempting to get option data for {symbol}")
            option_data = manager.get_option_quote(f"{symbol}0")  # Use a dummy option to get implied vol
            if option_data:
                market_data.implied_volatility = option_data.get('implied_volatility', 0.0)
                market_data.delta = option_data.get('delta', 0.0)
                market_data.gamma = option_data.get('gamma', 0.0)
                market_data.theta = option_data.get('theta', 0.0)
                market_data.vega = option_data.get('vega', 0.0)
        except Exception as e:
            logger.warning(f"Could not get options data for {symbol}: {str(e)}")
            # Continue without options data - this is non-fatal
        
        # Save to database
        logger.debug(f"Saving market data for {symbol} to database")
        session.add(market_data)
        session.commit()
        logger.info(f"Successfully updated market data for {symbol}")
        
        return market_data
        
    except Exception as e:
        error_msg = f"Error updating market data for {symbol}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        st.error(error_msg)
        try:
            session.rollback()
        except Exception:
            pass  # Ignore rollback errors
        return None

def add_wem_stock(session: Session, symbol: str, is_default: bool = False) -> Dict[str, Any]:
    """Add a new WEM stock to database"""
    stock = WEMStock(
        symbol=symbol.upper(),
        is_default=is_default
    )
    session.add(stock)
    session.commit()
    return stock.to_dict()

def remove_wem_stock(session: Session, symbol: str) -> bool:
    """Remove a WEM stock from database"""
    stock = session.query(WEMStock).filter_by(symbol=symbol).first()
    if stock:
        session.delete(stock)
        session.commit()
        return True
    return False

def update_wem_stock(session: Session, stock_data: Dict[str, Any]) -> bool:
    """
    Update a WEM stock with new data.
    
    Args:
        session: Database session
        stock_data: Dictionary with stock data
        
    Returns:
        bool: Success or failure
    """
    symbol = stock_data.get('symbol')
    if not symbol:
        logger.error("No symbol provided for WEM stock update")
        return False
            
    logger.info(f"Updating WEM stock: {symbol}")
    
    try:
        # Find the WEM stock in the database
        wem_stock = session.query(WEMStock).filter_by(symbol=symbol).first()
        
        if not wem_stock:
            logger.warning(f"WEM stock {symbol} not found, creating new entry")
            wem_stock = WEMStock(symbol=symbol)
            session.add(wem_stock)
        
        # Initialize meta_data if it doesn't exist
        if not wem_stock.meta_data:
            wem_stock.meta_data = {}
        
        # Update all attributes, but preserve existing values for None stub data
        for key, value in stock_data.items():
            if hasattr(wem_stock, key):
                # For stub records, don't overwrite existing non-None values with None
                if value is None and hasattr(wem_stock, key) and getattr(wem_stock, key) is not None:
                    # Skip setting None over existing value (preserve is_default, etc.)
                    continue
                setattr(wem_stock, key, value)
        
        # Commit the changes
        session.commit()
        logger.info(f"Successfully updated WEM stock: {symbol}")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating WEM stock {symbol}: {str(e)}", exc_info=True)
        return False

def calculate_expected_move(session: Session, stock_data: Dict[str, Any], regular_hours_only: bool = False, use_friday_close: bool = True) -> Dict[str, Any]:
    """
    Calculate the Weekly Expected Move (WEM) for a stock based on options data.
    
    AUTOMATED FULL CHAIN ANALYSIS METHOD:
    1. Get full weekly option chain expiring on next Friday
    2. Auto-detect ATM strike (closest to current stock price)
    3. Auto-select adjacent strikes for ITM options (no manual interval detection needed)
    4. Extract 4 required options from chain:
       - ATM Call & Put: same strike closest to current price
       - ITM Call: next adjacent strike below ATM (has intrinsic value)
       - ITM Put: next adjacent strike above ATM (has intrinsic value)
    5. Calculate WEM Points = (Straddle + Strangle) / 2
    6. Calculate WEM Spread = WEM Points / (previous Friday's closing price)
    7. Calculate expected ranges: Straddle 1/2 = Stock Price ± WEM Points
    
    Benefits of this approach:
    - No need to detect strike intervals manually
    - Works with any stock's option strike pattern automatically
    - Single API call for full chain vs multiple option quote calls
    - Consistent data from same timestamp/snapshot
    - Robust error handling for missing strikes
    
    Args:
        session: Database session
        stock_data: Dictionary with stock symbol
        regular_hours_only: If True, uses regular hours pricing instead of extended hours
        use_friday_close: If True, uses previous Friday close (standard), if False uses most recent data (testing)
        
    Returns:
        dict: Dictionary with calculated WEM values, or None if calculation fails
    """
    symbol = stock_data.get('symbol')
    if not symbol:
        logger.error("No symbol provided for WEM calculation")
        return None
            
    logger.info(f"Calculating Weekly Expected Move for {symbol}")
    
    try:
        # Step 1: Get stock price based on selected data source mode
        if use_friday_close:
            # Standard mode: Use previous Friday's close price
            logger.info(f"WEM calculation for {symbol} - using previous Friday close (standard method)")
            previous_friday_date = find_previous_friday()
            current_price = _get_previous_friday_close_price(symbol, previous_friday_date, use_cache=True)
            
            if current_price is None:
                logger.error(f"Previous Friday close price not available for {symbol} - WEM calculation cannot proceed")
                return None
            
            pricing_mode = "previous Friday close (regular hours)" if regular_hours_only else "previous Friday close (extended hours)"
            data_source = "Friday Close"
        else:
            # Testing mode: Use most recent market data
            logger.info(f"WEM calculation for {symbol} - using most recent market data (testing mode)")
            manager = get_market_data_manager()
            if not manager:
                logger.error(f"No market data manager available for {symbol}")
                return None
            
            current_price = manager.get_stock_price(symbol, regular_hours_only)
            if current_price is None:
                logger.error(f"Could not get current price for {symbol} - WEM calculation cannot proceed")
                return None
                
            current_price = float(current_price)
            pricing_mode = "most recent (regular hours)" if regular_hours_only else "most recent (extended hours)"
            data_source = "Most Recent"
        
        logger.info(f"Using {data_source} data with {pricing_mode} for {symbol}: ${current_price:.2f}")
        
        # Step 2: Find next Friday expiration date
        next_friday = find_next_friday_expiration()
        logger.info(f"Next Friday expiration: {next_friday}")
        
        # Step 3: Get weekly option chain for next Friday expiration (with holiday adjustment)
        weekly_option_chain_result = _get_weekly_option_chain(symbol, next_friday, use_friday_close)
        
        if not weekly_option_chain_result:
            logger.error(f"No weekly option chain available for {symbol} - tried multiple expiration dates around {next_friday.date()}")
            return None
        
        weekly_option_chain = weekly_option_chain_result
        
        # Extract the actual expiration date used (may be different from calculated Friday due to holidays)
        actual_expiration_date = next_friday  # Default to calculated date
        
        # Try to determine actual expiration date from the option chain data
        # This is a best-effort attempt since the API response format may vary
        try:
            # Check if there's expiration info in the option chain data
            calls = weekly_option_chain.get('calls')
            if calls is not None and not calls.empty and 'expiration' in calls.columns:
                # Get the expiration date from the first option
                exp_str = calls.iloc[0]['expiration']
                if exp_str:
                    actual_expiration_date = datetime.strptime(exp_str, '%Y-%m-%d')
                    if actual_expiration_date.date() != next_friday.date():
                        logger.info(f"📅 Detected actual expiration date {actual_expiration_date.date()} differs from calculated {next_friday.date()}")
        except Exception as e:
            logger.debug(f"Could not extract actual expiration date from option chain: {e}")
            # Keep the original calculated date
        
        calls = weekly_option_chain['calls']
        puts = weekly_option_chain['puts']
        
        if calls.empty or puts.empty:
            logger.error(f"Empty weekly option chain for {symbol}")
            return None
        
        # Step 4: Extract ATM options and calculate Delta 16+/- values
        logger.info(f"Analyzing full option chain for {symbol} to extract required options")
        
        # Extract the ATM options using the existing automated approach
        required_options = _extract_required_options_from_chain(calls, puts, current_price, symbol)
        
        if not required_options:
            logger.error(f"Could not extract required options for {symbol} from option chain - skipping stock")
            return None
        
        atm_call = required_options['atm_call']
        atm_put = required_options['atm_put']
        itm_call = required_options['itm_call']  # Keep for strangle calculation
        itm_put = required_options['itm_put']    # Keep for strangle calculation
        
        # Log the selected strikes for verification
        logger.info(f"Selected strikes for {symbol}:")
        logger.info(f"  ATM Call/Put: ${atm_call['strike']}")
        logger.info(f"  ITM Call: ${itm_call['strike']} (below ATM, for strangle)")
        logger.info(f"  ITM Put: ${itm_put['strike']} (above ATM, for strangle)")
        
        # Step 4.5: Calculate proper Delta 16+/- values using delta-based lookup
        logger.info(f"Calculating Delta 16+/- values for {symbol}")
        expiration_str = actual_expiration_date.strftime('%Y-%m-%d')
        
        # Get validation config from session state if available (will be set by UI)
        validation_config = getattr(st.session_state, 'delta_16_validation_config', None)
        
        # Debug logging for validation config
        if validation_config:
            logger.info(f"Delta 16 validation config found: enabled={validation_config.enabled}, max_deviation={validation_config.max_delta_deviation}")
        else:
            logger.warning("No delta 16 validation config found in session state")
        
        delta_16_results = calculate_delta_16_values(weekly_option_chain, expiration_str, validation_config)
        
        if delta_16_results:
            logger.info(f"  Delta 16+ Call: ${delta_16_results['delta_16_plus']['strike']} (delta: {delta_16_results['delta_16_plus']['delta']:.4f})")
            logger.info(f"  Delta 16- Put: ${delta_16_results['delta_16_minus']['strike']} (delta: {delta_16_results['delta_16_minus']['delta']:.4f})")
        else:
            logger.warning(f"Could not calculate Delta 16 values for {symbol} - delta values not available in option chain")
            logger.info("NOTE: Black-Scholes calculation method (Method 2) will be added as fallback in future update")
        
        # Step 5: Calculate Straddle (ATM call + ATM put)
        logger.debug(f"Calculating straddle using ATM strike ${atm_call['strike']}")
        
        # Calculate mid-prices for ATM options
        atm_call_mid = (float(atm_call['bid']) + float(atm_call['ask'])) / 2
        atm_put_mid = (float(atm_put['bid']) + float(atm_put['ask'])) / 2
        
        # Straddle = ATM call premium + ATM put premium
        straddle_premium = atm_call_mid + atm_put_mid
        logger.info(f"Straddle calculation: ${atm_call_mid:.2f} (call) + ${atm_put_mid:.2f} (put) = ${straddle_premium:.2f}")
        
        # Step 6: Calculate Strangle (ITM call + ITM put at adjacent strikes)
        logger.debug(f"Calculating strangle using ITM options at adjacent strikes")
        
        # Calculate mid-prices for ITM options
        itm_call_mid = (float(itm_call['bid']) + float(itm_call['ask'])) / 2
        itm_put_mid = (float(itm_put['bid']) + float(itm_put['ask'])) / 2
        
        # Strangle = ITM call premium + ITM put premium
        strangle_premium = itm_call_mid + itm_put_mid
        logger.info(f"Strangle calculation: ${itm_call_mid:.2f} (ITM call) + ${itm_put_mid:.2f} (ITM put) = ${strangle_premium:.2f}")
        
        # Store strike values for result
        atm_strike = float(atm_call['strike'])
        itm_call_strike = float(itm_call['strike'])
        itm_put_strike = float(itm_put['strike'])
        
        # Step 7: Calculate Final WEM Points
        # WEM Points = (Straddle + Strangle) / 2
        wem_points = (straddle_premium + strangle_premium) / 2
        logger.info(f"WEM Points calculation: (${straddle_premium:.2f} + ${strangle_premium:.2f}) / 2 = ${wem_points:.2f}")
        
        # Calculate additional metrics based on corrected formulas
        # WEM Spread = WEM Points / (base price for comparison)
        if use_friday_close:
            # Standard mode: Use previous Friday's close for WEM Spread calculation
            previous_friday_date = find_previous_friday()
            previous_friday_close = _get_previous_friday_close_price(symbol, previous_friday_date, use_cache=True)
            
            if previous_friday_close and previous_friday_close > 0:
                wem_spread = wem_points / previous_friday_close
                logger.info(f"WEM Spread calculation (Friday close): ${wem_points:.2f} / ${previous_friday_close:.2f} = {wem_spread:.4f}")
                spread_base_price = previous_friday_close
            else:
                # Fallback to current price if previous Friday price not available
                wem_spread = wem_points / current_price
                logger.warning(f"Previous Friday close not available for {symbol}, using current price for WEM Spread")
                spread_base_price = current_price
        else:
            # Testing mode: Use current price as base for WEM Spread calculation
            wem_spread = wem_points / current_price
            logger.info(f"WEM Spread calculation (most recent): ${wem_points:.2f} / ${current_price:.2f} = {wem_spread:.4f}")
            spread_base_price = current_price
        
        # Straddle 2 = Stock Price + WEM Points (upper expected range)
        straddle_2 = current_price + wem_points
        
        # Straddle 1 = Stock Price - WEM Points (lower expected range)  
        straddle_1 = current_price - wem_points
        
        # Calculate Delta Range using proper Delta 16 values (if available)
        if delta_16_results:
            # Use actual Delta 16 strikes for range calculation
            delta_16_plus_strike = delta_16_results['delta_16_plus']['strike']
            delta_16_minus_strike = delta_16_results['delta_16_minus']['strike']
            delta_range = delta_16_plus_strike - delta_16_minus_strike
            delta_range_pct = delta_range / current_price
            
            logger.info(f"Delta Range using proper Delta 16 values: ${delta_16_minus_strike:.2f} to ${delta_16_plus_strike:.2f} = ${delta_range:.2f}")
        else:
            # No valid delta calculation available - set to None
            # TODO: Implement Black-Scholes calculation method (Method 2) as fallback
            delta_16_plus_strike = None
            delta_16_minus_strike = None
            delta_range = None
            delta_range_pct = None
            
            logger.warning(f"Delta 16 values not available for {symbol} - Delta Range will be null")
        
        logger.info(f"Expected weekly range for {symbol}: ${straddle_1:.2f} - ${straddle_2:.2f}")
        logger.info(f"WEM Points: ${wem_points:.2f}")
        
        # Handle None values in delta range logging
        if delta_range is not None and delta_range_pct is not None:
            logger.info(f"Delta Range: ${delta_range:.2f} ({delta_range_pct:.2%})")
        else:
            logger.info(f"Delta Range: Not available (delta values missing from option chain)")
        
        # Step 8: Package results
        # Determine validation status for display
        delta_validation_status = "none"  # none, pass, warning, error
        delta_validation_message = ""
        
        if delta_16_results:
            validation_results = delta_16_results.get('validation_results', {})
            if validation_results.get('validation_enabled', False):
                quality_check = validation_results.get('quality_check', {})
                match_check = validation_results.get('match_check', {})
                
                # Check for errors (validation failures)
                total_errors = len(quality_check.get('errors', [])) + len(match_check.get('errors', []))
                total_warnings = len(quality_check.get('warnings', [])) + len(match_check.get('warnings', []))
                
                if total_errors > 0:
                    delta_validation_status = "error"
                    delta_validation_message = f"{total_errors} validation error(s)"
                elif total_warnings > 0:
                    delta_validation_status = "warning"
                    delta_validation_message = f"{total_warnings} validation warning(s)"
                else:
                    delta_validation_status = "pass"
                    delta_validation_message = "Validation passed"
        
        result = {
            'symbol': symbol,
            'atm_price': float(current_price),
            'straddle': float(straddle_premium),
            'strangle': float(strangle_premium),
            'wem_points': float(wem_points),
            'wem_spread': float(wem_spread),
            'expected_range_low': float(straddle_1),
            'expected_range_high': float(straddle_2),
            'atm_strike': float(atm_strike),
            'itm_call_strike': float(itm_call_strike),
            'itm_put_strike': float(itm_put_strike),
            'straddle_strangle': float(straddle_premium + strangle_premium),  # Combined straddle + strangle
            'delta_16_plus': float(delta_16_plus_strike) if delta_16_plus_strike is not None else None,  # Actual Delta 16+ strike
            'delta_16_minus': float(delta_16_minus_strike) if delta_16_minus_strike is not None else None,  # Actual Delta 16- strike
            'delta_range': float(delta_range) if delta_range is not None else None,
            'delta_range_pct': float(delta_range_pct) if delta_range_pct is not None else None,
            'straddle_2': float(straddle_2),  # Stock Price + WEM Points
            'straddle_1': float(straddle_1),  # Stock Price - WEM Points
            'delta_validation_status': delta_validation_status,  # For UI highlighting
            'delta_validation_message': delta_validation_message,  # For tooltips/details
            'meta_data': {
                'calculation_timestamp': datetime.now(timezone.utc).isoformat(),
                'calculation_method': 'automated_full_chain_analysis',
                'expiration_date': actual_expiration_date.isoformat(),
                'calculated_expiration_date': next_friday.isoformat(),
                'expiration_date_adjusted': actual_expiration_date.date() != next_friday.date(),
                'adjustment_reason': f"Market holiday adjustment from {next_friday.date()} to {actual_expiration_date.date()}" if actual_expiration_date.date() != next_friday.date() else None,
                'data_source': data_source.lower().replace(' ', '_'),
                'data_source_mode': data_source,
                'pricing_mode': pricing_mode,
                'use_friday_close': use_friday_close,
                'atm_call_premium': float(atm_call_mid),
                'atm_put_premium': float(atm_put_mid),
                'itm_call_premium': float(itm_call_mid),
                'itm_put_premium': float(itm_put_mid),
                'calculated_wem_points': float(wem_points),
                'stock_price_used': float(current_price),
                'spread_base_price': float(spread_base_price),
                'strikes_used': {
                    'atm': float(atm_strike),
                    'itm_call': float(itm_call_strike),
                    'itm_put': float(itm_put_strike),
                    'delta_16_plus': float(delta_16_plus_strike) if delta_16_plus_strike is not None else None,
                    'delta_16_minus': float(delta_16_minus_strike) if delta_16_minus_strike is not None else None
                },
                'delta_16_calculation': {
                    'method': 'proper_delta_lookup' if delta_16_results else 'not_available',
                    'delta_16_plus_actual_delta': float(delta_16_results['delta_16_plus']['delta']) if delta_16_results else None,
                    'delta_16_minus_actual_delta': float(delta_16_results['delta_16_minus']['delta']) if delta_16_results else None,
                    'delta_16_plus_accuracy': float(delta_16_results['delta_16_plus']['delta_accuracy']) if delta_16_results else None,
                    'delta_16_minus_accuracy': float(delta_16_results['delta_16_minus']['delta_accuracy']) if delta_16_results else None,
                    'fallback_todo': 'Black-Scholes calculation method (Method 2) to be implemented'
                },
                'previous_friday_date': previous_friday_date.isoformat() if use_friday_close else None,
                'previous_friday_close': float(previous_friday_close) if use_friday_close and 'previous_friday_close' in locals() and previous_friday_close else None,
                'option_selection_method': 'atm_and_adjacent_strikes_for_wem_plus_delta_lookup',
                'formula_notes': {
                    'wem_points': '(Straddle + Strangle) / 2',
                    'wem_spread': f'WEM Points / {data_source} Price',
                    'straddle_1': 'Stock Price - WEM Points',
                    'straddle_2': 'Stock Price + WEM Points',
                    'delta_range': 'Delta 16+ Strike - Delta 16- Strike (when delta values available)',
                    'delta_range_pct': 'Delta Range / Stock Price (when delta values available)',
                    'option_extraction': 'ATM closest to price, adjacent strikes for strangle calculation',
                    'delta_16_method': 'Direct lookup from option chain for options with delta closest to ±0.16 (if available)',
                    'primary_calculation': 'WEM based on straddle/strangle premiums',
                    'secondary_calculation': 'Delta 16 range for additional analysis',
                    'data_source_note': f'Using {data_source} data for calculation base price',
                    'expiration_handling': 'Automatically adjusts for market holidays (e.g., July 4th on Friday → Thursday expiration)',
                    'fallback_mechanism': 'Tries multiple expiration dates if primary date has no option chains available'
                }
            }
        }
        
        logger.info(f"Successfully calculated WEM Points for {symbol}: ${wem_points:.2f}")
        return result
        
    except Exception as e:
        logger.error(f"Error calculating WEM for {symbol}: {str(e)}", exc_info=True)
        return None











def _get_weekly_cache_file() -> Path:
    """
    Get the path to the weekly cache file for WEM data.
    
    Returns:
        Path: Path to the weekly cache file
    """
    project_root = Path(__file__).parent.parent.parent
    cache_dir = project_root / 'data' / 'wem_cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Use current week's Monday as cache identifier
    today = datetime.now().date()
    days_since_monday = today.weekday()
    monday_date = today - timedelta(days=days_since_monday)
    
    cache_file = cache_dir / f'wem_cache_{monday_date.strftime("%Y%m%d")}.json'
    return cache_file


def _get_from_weekly_cache(cache_key: str) -> Any:
    """
    Get data from weekly cache.
    
    Args:
        cache_key: The cache key to retrieve
        
    Returns:
        Cached data or None if not found/expired
    """
    try:
        cache_file = _get_weekly_cache_file()
        
        if not cache_file.exists():
            return None
        
        import json
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        
        if cache_key in cache_data:
            cached_item = cache_data[cache_key]
            
            # Check if cache is still valid (1 week)
            cache_time = datetime.fromisoformat(cached_item['timestamp'])
            if (datetime.now() - cache_time).days < 7:
                logger.debug(f"Cache hit for {cache_key}")
                
                # Handle DataFrame data
                if 'dataframes' in cached_item:
                    result = {}
                    for df_name, df_data in cached_item['dataframes'].items():
                        result[df_name] = pd.read_json(StringIO(df_data), orient='records')
                    return result
                else:
                    return cached_item['data']
            else:
                logger.debug(f"Cache expired for {cache_key}")
        
        return None
        
    except Exception as e:
        logger.warning(f"Error reading from weekly cache: {str(e)}")
        return None


def _save_to_weekly_cache(cache_key: str, data: Any) -> None:
    """
    Save data to weekly cache.
    
    Args:
        cache_key: The cache key to store under
        data: The data to cache
    """
    try:
        cache_file = _get_weekly_cache_file()
        
        # Load existing cache or create new
        cache_data = {}
        if cache_file.exists():
            import json
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
        
        # Prepare cache entry
        cache_entry = {
            'timestamp': datetime.now().isoformat(),
        }
        
        # Handle DataFrame data (option chains)
        if isinstance(data, dict) and all(isinstance(v, pd.DataFrame) for v in data.values()):
            cache_entry['dataframes'] = {}
            for df_name, df in data.items():
                cache_entry['dataframes'][df_name] = df.to_json(orient='records')
        else:
            cache_entry['data'] = data
        
        cache_data[cache_key] = cache_entry
        
        # Save cache
        import json
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        logger.debug(f"Cached data for {cache_key}")
        
        # Clean up old cache files
        _cleanup_old_cache_files()
        
    except Exception as e:
        logger.warning(f"Error saving to weekly cache: {str(e)}")


def _cleanup_old_cache_files() -> None:
    """
    Clean up cache files older than 4 weeks to prevent accumulation.
    """
    try:
        project_root = Path(__file__).parent.parent.parent
        cache_dir = project_root / 'data' / 'wem_cache'
        
        if not cache_dir.exists():
            return
        
        cutoff_date = datetime.now() - timedelta(weeks=4)
        
        for cache_file in cache_dir.glob('wem_cache_*.json'):
            if cache_file.stat().st_mtime < cutoff_date.timestamp():
                cache_file.unlink()
                logger.debug(f"Deleted old cache file: {cache_file.name}")
                
    except Exception as e:
        logger.warning(f"Error cleaning up old cache files: {str(e)}")


def _extract_required_options_from_chain(calls: pd.DataFrame, puts: pd.DataFrame, 
                                        current_price: float, symbol: str) -> Optional[Dict[str, Any]]:
    """
    Extract the 4 required options from a full option chain for WEM calculation.
    
    This function analyzes the full option chain and extracts:
    1. ATM Call - at strike closest to current price
    2. ATM Put - at same strike as ATM call  
    3. ITM Call - at next adjacent strike below ATM (has intrinsic value)
    4. ITM Put - at next adjacent strike above ATM (has intrinsic value)
    
    Args:
        calls: DataFrame with call options from the option chain
        puts: DataFrame with put options from the option chain
        current_price: Current stock price for ATM determination
        symbol: Stock symbol for logging
        
    Returns:
        dict: Dictionary with the 4 required options, or None if any are missing
    """
    logger.debug(f"Extracting 4 required options for {symbol} from full chain")
    
    try:
        # Get all available strikes from both calls and puts
        all_strikes = sorted(set(calls['strike'].tolist() + puts['strike'].tolist()))
        logger.debug(f"Available strikes for {symbol}: {len(all_strikes)} strikes from {min(all_strikes)} to {max(all_strikes)}")
        
        if len(all_strikes) < 3:
            logger.error(f"Insufficient strikes available for {symbol}: need at least 3, found {len(all_strikes)}")
            return None
        
        # Step 1: Find ATM strike (closest to current price)
        atm_strike = min(all_strikes, key=lambda x: abs(float(x) - current_price))
        logger.debug(f"ATM strike for {symbol}: ${atm_strike} (current price: ${current_price:.2f})")
        
        # Step 2: Find adjacent strikes for ITM options
        atm_index = all_strikes.index(atm_strike)
        
        # ITM Call: one strike below ATM (next lower strike)
        if atm_index == 0:
            logger.error(f"No strike below ATM for ITM call - {symbol} ATM is at lowest available strike")
            return None
        itm_call_strike = all_strikes[atm_index - 1]
        
        # ITM Put: one strike above ATM (next higher strike)  
        if atm_index == len(all_strikes) - 1:
            logger.error(f"No strike above ATM for ITM put - {symbol} ATM is at highest available strike")
            return None
        itm_put_strike = all_strikes[atm_index + 1]
        
        logger.debug(f"Strike selection for {symbol}:")
        logger.debug(f"  ITM Call: ${itm_call_strike} (below ATM)")
        logger.debug(f"  ATM: ${atm_strike}")
        logger.debug(f"  ITM Put: ${itm_put_strike} (above ATM)")
        
        # Step 3: Extract the actual option records from the DataFrames
        
        # ATM Call and Put
        atm_calls = calls[calls['strike'] == atm_strike]
        atm_puts = puts[puts['strike'] == atm_strike]
        
        if atm_calls.empty:
            logger.error(f"No ATM call option found for {symbol} at strike ${atm_strike}")
            return None
        if atm_puts.empty:
            logger.error(f"No ATM put option found for {symbol} at strike ${atm_strike}")
            return None
            
        # ITM Call and Put
        itm_calls = calls[calls['strike'] == itm_call_strike]
        itm_puts = puts[puts['strike'] == itm_put_strike]
        
        if itm_calls.empty:
            logger.error(f"No ITM call option found for {symbol} at strike ${itm_call_strike}")
            return None
        if itm_puts.empty:
            logger.error(f"No ITM put option found for {symbol} at strike ${itm_put_strike}")
            return None
        
        # Step 4: Validate that all options have valid bid/ask prices
        atm_call = atm_calls.iloc[0]
        atm_put = atm_puts.iloc[0]
        itm_call = itm_calls.iloc[0]
        itm_put = itm_puts.iloc[0]
        
        required_fields = ['bid', 'ask', 'strike']
        for option_name, option_data in [
            ('ATM Call', atm_call), ('ATM Put', atm_put), 
            ('ITM Call', itm_call), ('ITM Put', itm_put)
        ]:
            for field in required_fields:
                if field not in option_data or pd.isna(option_data[field]):
                    logger.error(f"Missing or invalid {field} for {option_name} in {symbol}")
                    return None
                    
            # Check for valid bid/ask prices (must be > 0)
            if float(option_data['bid']) <= 0 or float(option_data['ask']) <= 0:
                logger.error(f"Invalid bid/ask prices for {option_name} in {symbol}: bid={option_data['bid']}, ask={option_data['ask']}")
                return None
        
        # Step 5: Return the extracted options
        result = {
            'atm_call': atm_call,
            'atm_put': atm_put,
            'itm_call': itm_call,
            'itm_put': itm_put
        }
        
        logger.info(f"Successfully extracted 4 required options for {symbol}")
        return result
        
    except Exception as e:
        logger.error(f"Error extracting options from chain for {symbol}: {str(e)}", exc_info=True)
        return None


def _get_weekly_option_chain(symbol: str, expiration_date: datetime, use_friday_close: bool = True) -> Dict[str, pd.DataFrame]:
    """
    Get weekly option chain for a specific expiration date using MarketData.app.
    
    This function connects to the existing MarketDataManager to retrieve option chain
    data for the specified weekly expiration date. If the primary date doesn't have
    option chains available (e.g., due to market holidays), it will try alternative
    dates in the same week.
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        expiration_date: Options expiration date (typically next Friday)
        use_friday_close: If True, uses cache (Friday close mode), if False bypasses cache (Most Recent mode)
        
    Returns:
        dict: Dictionary with 'calls' and 'puts' DataFrames containing:
            - strike: Strike price
            - bid: Bid price
            - ask: Ask price
            - volume: Trading volume
            - open_interest: Open interest
            - delta: Option delta (optional)
            - Other greeks (optional)
    """
    # Try multiple expiration dates in order of preference
    dates_to_try = get_expiration_date_candidates(expiration_date)
    
    for attempt, (candidate_date, reason) in enumerate(dates_to_try):
        logger.info(f"Attempt {attempt + 1}: Getting weekly option chain for {symbol} expiring {candidate_date.date()} ({reason})")
        
        try:
            # Check weekly cache first ONLY in Friday Close mode
            cache_key = f"weekly_option_chain:{symbol}:{candidate_date.strftime('%Y-%m-%d')}"
            cached_chain = None
            
            if use_friday_close:
                cached_chain = _get_from_weekly_cache(cache_key)
                if cached_chain:
                    logger.info(f"Retrieved {symbol} option chain from weekly cache for {candidate_date.date()} (Friday Close mode)")
                    return cached_chain
            
            # Get market data manager
            manager = get_market_data_manager()
            if not manager:
                logger.error("No market data manager available")
                continue
            
            # Format expiration date for MarketData.app API (YYYY-MM-DD format)
            expiration_str = candidate_date.strftime('%Y-%m-%d')
            logger.info(f"Requesting option chain for {symbol} with expiration {expiration_str}")
            
            # Get option chain for specific expiration date
            chain = manager.get_option_chain(symbol, expiration_str)
            
            if not chain or not isinstance(chain, dict) or 'calls' not in chain or 'puts' not in chain:
                logger.warning(f"Invalid option chain format received for {symbol} on {expiration_str}, trying next date")
                continue
            
            calls_df = chain['calls']
            puts_df = chain['puts']
            
            if calls_df.empty and puts_df.empty:
                logger.warning(f"Empty option chain received for {symbol} on {expiration_str}, trying next date")
                continue
            
            # Success! We found a valid option chain
            logger.info(f"✅ Successfully retrieved option chain for {symbol} on {expiration_str}: {len(calls_df)} calls, {len(puts_df)} puts")
            
            if candidate_date != expiration_date:
                logger.info(f"📅 Note: Using adjusted expiration date {candidate_date.date()} instead of original {expiration_date.date()} due to {reason}")
            
            # Cache the result for weekly reuse ONLY in Friday Close mode
            if use_friday_close:
                _save_to_weekly_cache(cache_key, chain)
                logger.debug(f"Cached option chain for {symbol} on {candidate_date.date()} (Friday Close mode)")
            else:
                logger.debug(f"Skipping cache save for {symbol} on {candidate_date.date()} (Most Recent mode)")
            
            return chain
            
        except Exception as e:
            logger.warning(f"Error getting option chain for {symbol} on {candidate_date.date()}: {str(e)}")
            continue
    
    # If we get here, none of the candidate dates worked
    logger.error(f"❌ Failed to retrieve option chain for {symbol} - tried {len(dates_to_try)} different expiration dates")
    return None





def _get_previous_friday_close_price(symbol: str, previous_friday_date: datetime, use_cache: bool = True) -> Optional[float]:
    """
    Get the closing price for a stock on the previous Friday using MarketData.app.
    
    This function connects to the existing MarketDataManager to retrieve historical
    price data for the previous Friday for WEM Spread calculation.
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        previous_friday_date: The previous Friday's date
        use_cache: If True, uses weekly cache (Friday close mode), if False bypasses cache (testing mode)
        
    Returns:
        float: Closing price on previous Friday, or None if not available
    """
    logger.info(f"Getting previous Friday close price for {symbol} on {previous_friday_date.date()}")
    
    try:
        # Check weekly cache first ONLY if caching is enabled
        cache_key = f"friday_close:{symbol}:{previous_friday_date.strftime('%Y-%m-%d')}"
        cached_price = None
        
        if use_cache:
            cached_price = _get_from_weekly_cache(cache_key)
            if cached_price:
                logger.info(f"Retrieved {symbol} Friday close from weekly cache: ${cached_price:.2f}")
                return cached_price
        else:
            logger.info(f"Bypassing cache for {symbol} Friday close (testing mode)")
        
        # Get market data manager
        manager = get_market_data_manager()
        if not manager:
            logger.error("No market data manager available")
            return None
        
        # Get historical data for the previous Friday
        # MarketData.app provides historical candle data
        from goldflipper.data.market.providers.marketdataapp_provider import MarketDataAppProvider
        
        # Create a direct provider instance to access historical data
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / 'goldflipper' / 'config' / 'settings.yaml'
        provider = MarketDataAppProvider(str(config_path))
        
        # Get one day of data for the previous Friday
        start_date = previous_friday_date
        end_date = previous_friday_date + timedelta(days=1)
        
        logger.info(f"Requesting historical data for {symbol} on {previous_friday_date.date()}")
        historical_data = provider.get_historical_data(symbol, start_date, end_date, interval="1d")
        
        if historical_data.empty:
            logger.warning(f"No historical data available for {symbol} on {previous_friday_date.date()}")
            # Fallback to current price if historical data not available
            current_price = manager.get_stock_price(symbol)
            if current_price:
                logger.warning(f"Using current price as fallback for {symbol}: ${current_price:.2f}")
                return float(current_price)
            return None
        
        # Get the closing price from the Friday data
        friday_close = float(historical_data.iloc[-1]['close'])
        logger.info(f"Retrieved previous Friday close for {symbol}: ${friday_close:.2f}")
        
        # Cache the result for weekly reuse ONLY if caching is enabled
        if use_cache:
            _save_to_weekly_cache(cache_key, friday_close)
            logger.debug(f"Cached Friday close for {symbol}")
        else:
            logger.debug(f"Skipping cache save for {symbol} Friday close (testing mode)")
        
        return friday_close
        
    except Exception as e:
        logger.error(f"Error getting previous Friday close for {symbol}: {str(e)}", exc_info=True)
        
        # Fallback to current price if historical data fails
        try:
            manager = get_market_data_manager()
            if manager:
                current_price = manager.get_stock_price(symbol)
                if current_price:
                    logger.warning(f"Using current price as fallback for {symbol}: ${current_price:.2f}")
                    return float(current_price)
        except Exception as fallback_error:
            logger.error(f"Fallback to current price also failed: {str(fallback_error)}")
        
        return None

def create_wem_table(stocks, layout="horizontal", metrics=None, sig_figs=4, max_digits=5):
    """
    Creates an interactive table for displaying WEM data.
    
    Args:
        stocks: List of stock dictionaries with WEM data
        layout: 'horizontal' or 'vertical' layout
        metrics: List of metrics to display
        sig_figs: Number of significant figures to display
        max_digits: Maximum total digits to display (before decimal point)
        
    Returns:
        dict: Dictionary with the table data and column configuration
    """
    st.info("Creating WEM table...")
    
    if not stocks:
        st.warning("No stock data available. Try updating the data first.")
        return {"df": pd.DataFrame(), "columns": []}
    
    logger.info(f"Creating WEM table with {len(stocks)} stocks in {layout} layout")
    logger.debug(f"First stock example: {stocks[0] if stocks else 'No stocks'}")
    
    # Create DataFrame and handle any date/time fields
    df = pd.DataFrame(stocks)
    
    # Keep last_updated in ISO format, only format for display in the column config
    
    # Format numeric columns with specified formatting rules
    def format_number(x, col_name):
        """Format numbers with max digits and minimum 2 decimal places"""
        if pd.isna(x) or x is None:
            return "—"  # Em dash for missing data (more elegant than blank)
        
        # Convert to float to ensure we can format it
        try:
            num_val = float(x)
        except (ValueError, TypeError):
            return "—"  # Em dash for non-numeric data
        
        # Special handling for percentage columns
        if col_name in ['wem_spread', 'delta_range_pct']:
            return f"{num_val*100:.2f}%"
        
        # For all other numeric columns, apply consistent formatting
        # Max digits before decimal (max_digits), always show 2 decimal places minimum
        if abs(num_val) >= 10**(max_digits):
            # Number too large for max_digits, use scientific notation
            return f"{num_val:.2e}"
        else:
            # Standard formatting: always show 2 decimal places minimum
            return f"{num_val:.2f}"
    
    # Format validation status with visual indicators
    def format_validation_status(status):
        """Format validation status with emoji indicators"""
        if pd.isna(status):
            return ""
        status_str = str(status).lower()
        if status_str == "pass":
            return "✅ Pass"
        elif status_str == "warning":
            return "⚠️ Warning"
        elif status_str == "error":
            return "❌ Error"
        elif status_str == "none":
            return "➖ N/A"
        else:
            return str(status)
    
    # Apply formatting to columns
    numeric_cols = df.select_dtypes(include=['float', 'int']).columns
    for col in numeric_cols:
        # Skip validation status columns from numeric formatting
        if col not in ['delta_validation_status', 'delta_validation_message']:
            df[col] = df[col].apply(lambda x: format_number(x, col))
    
    # Format validation status column if it exists
    if 'delta_validation_status' in df.columns:
        df['delta_validation_status'] = df['delta_validation_status'].apply(format_validation_status)
    
    # Ensure there's a WEM Points value for each stock - calculate if missing
    if 'straddle_strangle' in df.columns:
        for index, row in df.iterrows():
            symbol = row.get('symbol', 'UNKNOWN')
            
            # Calculate WEM Points if missing and we have straddle_strangle data
            if (pd.isna(row.get('wem_points')) and not pd.isna(row.get('straddle_strangle'))):
                # Calculate WEM Points as half of straddle_strangle
                calculated_wem_points = row['straddle_strangle'] / 2
                df.at[index, 'wem_points'] = calculated_wem_points
                logger.info(f"Calculated WEM Points for {symbol}: {calculated_wem_points}")
    
    # Convert old 'wem' field to 'wem_points' if needed
    if 'wem' in df.columns and 'wem_points' not in df.columns:
        df['wem_points'] = df['wem']
        logger.info("Converted 'wem' field to 'wem_points'")
    
    # Available metrics for display - reordered to match user requirements
    all_metrics = [
        'symbol', 'atm_price', 'straddle', 'strangle', 'wem_points', 'wem_spread',
        'delta_16_plus', 'straddle_2', 'straddle_1', 'delta_16_minus',
        'delta_range', 'delta_range_pct', 'straddle_strangle', 'delta_validation_status', 
        'delta_validation_message', 'last_updated'
    ]
    
    # For horizontal layout, filter out 'symbol' from selectable metrics
    # as it becomes the column headers
    display_metrics = all_metrics if layout == 'vertical' else [m for m in all_metrics if m != 'symbol']
    
    # Default selected metrics matching exact user requirements:
    # ATM (6/13/25), Straddle Level, Strangle Level, WEM Points, WEM Spread, 
    # Delta 16 (+), S2, S1, Delta 16 (-), Delta Range, Delta Range %
    default_metrics = [
        'atm_price', 'straddle', 'strangle', 'wem_points', 'wem_spread', 
        'delta_16_plus', 'straddle_2', 'straddle_1', 'delta_16_minus',
        'delta_range', 'delta_range_pct'
    ]
    
    metrics = metrics or default_metrics
    
    # Make sure we have the symbol column
    if 'symbol' not in metrics:
        metrics.insert(0, 'symbol')
    
    # Filter columns - only include metrics that actually exist in the DataFrame
    available_metrics = [metric for metric in metrics if metric in df.columns]
    missing_metrics = [metric for metric in metrics if metric not in df.columns]
    
    if missing_metrics:
        logger.warning(f"Missing columns in data: {missing_metrics}")
        logger.info(f"Available columns: {df.columns.tolist()}")
    
    if not available_metrics:
        logger.error("No valid metrics found in data")
        return {"df": pd.DataFrame(), "columns": []}
    
    # Filter columns to only available ones
    df = df[available_metrics]
    metrics = available_metrics
    
    # Dictionary to map column names to prettier display names - updated for exact user requirements
    column_display_names = {
        'symbol': 'Symbol',
        'atm_price': 'ATM (6/13/25)',  # Will be dynamically updated with actual date
        'wem_points': 'WEM Points',
        'straddle': 'Straddle Level',
        'strangle': 'Strangle Level', 
        'straddle_strangle': 'Straddle/Strangle',
        'wem_spread': 'WEM Spread',
        'delta_16_plus': 'Delta 16 (+)',
        'straddle_2': 'S2',
        'straddle_1': 'S1',
        'delta_16_minus': 'Delta 16 (-)',
        'delta_range': 'Delta Range',
        'delta_range_pct': 'Delta Range %',
        'delta_validation_status': 'Δ Status',
        'delta_validation_message': 'Δ Details',
        'last_updated': 'Last Updated'
    }
    
    # Dynamically update ATM display name with previous Friday's date (when close price was recorded)
    try:
        previous_friday = find_previous_friday()
        atm_date_str = previous_friday.strftime('%m/%d')  # Format as M/D (e.g., 6/13)
        column_display_names['atm_price'] = f'ATM ({atm_date_str})'
    except Exception as e:
        logger.warning(f"Could not determine previous Friday date: {e}")
        # Keep default ATM name if date calculation fails
    
    # Configure the display based on layout
    columns = []
    
    if layout == "horizontal":
        # In horizontal layout, symbols become column headers
        # Save a copy of the original DataFrame before transposing
        original_df = df.copy()
        
        # Set the index to symbol and transpose
        df = df.set_index('symbol').T
        
        # In transposed view, the metrics become the index
        # Filter out metrics that shouldn't be displayed as rows
        valid_metrics = [m for m in metrics if m != 'symbol']
        
        # Filter rows that match our valid metrics - only include metrics that actually exist in the transposed df
        available_metrics = [m for m in valid_metrics if m in df.index]
        if available_metrics:
            df = df.loc[available_metrics]
        else:
            logger.warning(f"No valid metrics found in transposed dataframe. Available index: {list(df.index)}, Requested: {valid_metrics}")
            # Don't filter if no metrics match - show what's available
            valid_metrics = available_metrics
        
        # Rename index with pretty names
        df.index = [column_display_names.get(idx, idx.replace('_', ' ').title()) for idx in df.index]
        
        # Configure columns - each stock symbol is a column (including those with missing data)
        stock_symbols = original_df['symbol'].tolist()
        for symbol in stock_symbols:
            # For horizontal layout, all stock columns are text type to ensure proper em-dash alignment
            columns.append({
                "field": symbol,
                "headerName": symbol,
                "width": 80,  # Reduced from 120 to 80 (1/3 smaller)
                "type": "text"  # Explicitly set as text to avoid right-alignment of em-dashes
            })
    else:  # vertical layout
        # Configure columns - each metric is a column with proper formatting
        for metric in metrics:
            display_name = column_display_names.get(metric, metric.replace('_', ' ').title())
            # Reduced column widths by about 1/3
            column_width = 100 if metric in ['symbol', 'last_updated'] else 80  # Reduced from 150/120 to 100/80
            
            # Determine column type and format for display
            column_type = "text"
            column_format = None
            
            if metric == 'atm_price':
                column_type = "number"
                column_format = "$.4f"
            elif metric in ['wem_points', 'straddle', 'strangle', 'straddle_strangle', 'delta_range', 'straddle_1', 'straddle_2', 'delta_16_plus', 'delta_16_minus']:
                column_type = "number" 
                column_format = "%.4f"
            elif metric in ['wem_spread', 'delta_range_pct']:
                # For percentage columns, we've already formatted them as strings with % sign
                column_type = "text"  # Changed from "number" to "text" to preserve % sign
                column_format = None  # No format needed since we've already formatted the values
            
            columns.append({
                "field": metric,
                "headerName": display_name,
                "width": column_width,
                "type": column_type,
                "format": column_format
            })
    
    logger.info(f"Created table with {df.shape[0]} rows, {df.shape[1]} columns")
    return {"df": df, "columns": columns}

def create_stub_wem_record(symbol: str) -> Dict[str, Any]:
    """
    Create a stub WEM record for stocks where calculation failed.
    This ensures the stock appears in the table with its symbol visible.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        dict: Stub WEM record with symbol and None values for metrics
    """
    return {
        'symbol': symbol,
        'is_default': None,  # Will be preserved from existing record
        'atm_price': None,
        'straddle': None,
        'strangle': None,
        'wem_points': None,
        'wem_spread': None,
        'expected_range_low': None,
        'expected_range_high': None,
        'atm_strike': None,
        'itm_call_strike': None,
        'itm_put_strike': None,
        'straddle_strangle': None,
        'delta_16_plus': None,
        'delta_16_minus': None,
        'delta_range': None,
        'delta_range_pct': None,
        'straddle_2': None,
        'straddle_1': None,
        'delta_validation_status': "none",  # Use "none" instead of None for display
        'delta_validation_message': "Market data unavailable",
        'notes': "Calculation failed - market data unavailable",
        'meta_data': {
            'calculation_timestamp': datetime.now(timezone.utc).isoformat(),
            'calculation_failed': True,
            'failure_reason': 'Market data unavailable or calculation error',
            'stub_record': True
        }
    }

def update_all_wem_stocks(session: Session, regular_hours_only: bool = False, use_friday_close: bool = True, wem_logger=None) -> bool:
    """
    Update all WEM stocks with fresh data.
    
    Args:
        session: Database session
        regular_hours_only: If True, uses regular hours close instead of extended hours
        use_friday_close: If True, uses previous Friday close (standard), if False uses most recent data (testing)
        wem_logger: Optional logger instance for this session
        
    Returns:
        bool: Success or failure
    """
    # Use provided logger or fall back to module logger
    log = wem_logger if wem_logger else logger
    data_source = "Friday Close" if use_friday_close else "Most Recent"
    pricing_mode = "regular hours only" if regular_hours_only else "including extended hours"
    log.info(f"Starting update of all WEM stocks using {data_source} data ({pricing_mode})")
    success_count = 0
    error_count = 0
    
    # Get all stocks to update
    stocks = session.query(WEMStock).all()
    
    if not stocks:
        log.warning("No WEM stocks found to update")
        return False
    
    log.info(f"Found {len(stocks)} WEM stocks to update using {data_source} data ({pricing_mode})")
    
    # Update each stock
    for stock in stocks:
        log.info(f"Calculating WEM for {stock.symbol}")
        try:
            # Calculate new values
            new_data = calculate_expected_move(session, {'symbol': stock.symbol}, regular_hours_only, use_friday_close)
            
            if new_data:
                # Update stock data
                update_data = {
                    'symbol': stock.symbol,
                    **new_data
                }
                if update_wem_stock(session, update_data):
                    log.info(f"Successfully updated {stock.symbol}")
                    success_count += 1
                else:
                    log.error(f"Failed to update {stock.symbol}")
                    error_count += 1
            else:
                # Create stub record for failed calculation
                log.warning(f"Creating stub record for {stock.symbol} - market data unavailable")
                stub_data = create_stub_wem_record(stock.symbol)
                if update_wem_stock(session, stub_data):
                    log.info(f"Successfully created stub record for {stock.symbol}")
                    # Don't count as success since it's incomplete data, but count as processed
                    error_count += 1
                else:
                    log.error(f"Failed to save stub record for {stock.symbol}")
                    error_count += 1
            
        except Exception as e:
            error_msg = f"Error calculating WEM for {stock.symbol}: {str(e)}"
            log.error(error_msg, exc_info=True)
            # Create stub record for exception cases too
            try:
                stub_data = create_stub_wem_record(stock.symbol)
                if update_wem_stock(session, stub_data):
                    log.info(f"Created stub record for {stock.symbol} after exception")
            except Exception as stub_error:
                log.error(f"Failed to create stub record for {stock.symbol}: {stub_error}")
            error_count += 1
    
    # Clear newly added stocks tracking since we've updated everything
    if hasattr(st.session_state, 'newly_added_stocks'):
        st.session_state.newly_added_stocks.clear()
        log.info("Cleared newly added stocks tracking after update")
    
    log.info(f"WEM update completed: {success_count} succeeded, {error_count} failed")
    return success_count > 0

def check_export_validation(wem_stocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Check for export validation issues: newly added stocks and stale data.
    
    Args:
        wem_stocks: List of WEM stock dictionaries
        
    Returns:
        dict: Validation results with warnings and recommended actions
    """
    validation_result = {
        'has_warnings': False,
        'newly_added_count': 0,
        'stale_data_count': 0,
        'stale_symbols': [],
        'warning_type': None,  # 'new_stocks', 'stale_data', 'both'
        'message': '',
        'actions': []
    }
    
    # Check for newly added stocks without WEM data
    newly_added_stocks = getattr(st.session_state, 'newly_added_stocks', set())
    if newly_added_stocks:
        validation_result['newly_added_count'] = len(newly_added_stocks)
        validation_result['has_warnings'] = True
    
    # Check for stale data (older than 1 week)
    week_ago = datetime.now() - timedelta(weeks=1)
    stale_symbols = []
    
    for stock in wem_stocks:
        last_updated = stock.get('last_updated')
        if last_updated:
            try:
                # Parse ISO format only (everything should be in ISO format now)
                if isinstance(last_updated, str):
                    update_time = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                elif isinstance(last_updated, datetime):
                    update_time = last_updated
                else:
                    continue  # Skip if unexpected type
                
                # Make timezone-naive for comparison
                if hasattr(update_time, 'tzinfo') and update_time.tzinfo:
                    update_time = update_time.replace(tzinfo=None)
                
                if update_time < week_ago:
                    stale_symbols.append(stock['symbol'])
                    
            except Exception as e:
                logger.warning(f"Could not parse last_updated for {stock.get('symbol', 'unknown')}: {e}")
                # Treat unparseable dates as stale to be safe
                stale_symbols.append(stock.get('symbol', 'unknown'))
    
    if stale_symbols:
        validation_result['stale_data_count'] = len(stale_symbols)
        validation_result['stale_symbols'] = stale_symbols
        validation_result['has_warnings'] = True
    
    # Determine warning type and message
    if validation_result['newly_added_count'] > 0 and validation_result['stale_data_count'] > 0:
        validation_result['warning_type'] = 'both'
        validation_result['message'] = f"New ticker symbols have been added and {len(stale_symbols)} stocks have data older than 1 week. Update recommended before export."
        validation_result['actions'] = ['Update', 'Proceed Anyway', 'Cancel']
    elif validation_result['newly_added_count'] > 0:
        validation_result['warning_type'] = 'new_stocks'
        validation_result['message'] = "New ticker symbols have been added, however, market data has not been updated. Are you sure you wish to continue?"
        validation_result['actions'] = ['Update', 'Cancel']
    elif validation_result['stale_data_count'] > 0:
        validation_result['warning_type'] = 'stale_data'
        validation_result['message'] = f"{len(stale_symbols)} stocks have data older than 1 week. Update recommended before export."
        validation_result['actions'] = ['Update', 'Proceed Anyway', 'Cancel']
    
    return validation_result

def setup_logging():
    """Set up logging for the WEM module"""
    # This function ensures logging is properly configured for the module
    # Actual logging configuration is already done at the module level
    logger.info("WEM module logging configured")
    
    # Check if we need to enable debug level
    debug_enabled = settings.get('logging', {}).get('debug', {}).get('enabled', False)
    if debug_enabled and logger.level != logging.DEBUG:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled for WEM module")
    
    return logger

class Delta16ValidationConfig:
    """Configuration class for Delta 16+/- validation checks"""
    def __init__(self):
        self.enabled = True
        self.max_delta_deviation = 0.03  # Maximum allowed deviation from target delta (3%)
        self.min_strike_count = 5  # Minimum number of strikes required
        self.max_strike_interval = 10.0  # Maximum average strike interval
        self.min_days_to_expiry = 1  # Minimum days to expiration
        self.min_delta_std = 0.05  # Minimum delta standard deviation for good distribution
        self.max_bid_ask_spread_pct = 0.10  # Maximum bid-ask spread as % of mid price (10%)
        self.min_coverage_ratio = 0.8  # Minimum ratio of acceptable options on both sides

def validate_delta_16_quality(calls_df: pd.DataFrame, puts_df: pd.DataFrame, 
                             expiration_date: str, config: Delta16ValidationConfig) -> Dict[str, Any]:
    """
    Perform quality validation checks on Delta 16+/- calculation inputs.
    
    Args:
        calls_df: DataFrame with call options
        puts_df: DataFrame with put options  
        expiration_date: Expiration date string (YYYY-MM-DD)
        config: Validation configuration object
        
    Returns:
        dict: Validation results with pass/fail status and details
    """
    results = {
        'overall_pass': True,
        'checks': {},
        'warnings': [],
        'errors': []
    }
    
    if not config.enabled:
        results['checks']['validation_disabled'] = {'pass': True, 'message': 'Validation checks disabled'}
        return results
    
    logger.info("Running Delta 16+/- quality validation checks")
    
    try:
        # Check 1: Strike Coverage and Density
        all_strikes = sorted(set(calls_df['strike'].tolist() + puts_df['strike'].tolist()))
        strike_count = len(all_strikes)
        
        if strike_count < config.min_strike_count:
            results['checks']['strike_count'] = {
                'pass': False, 
                'value': strike_count,
                'threshold': config.min_strike_count,
                'message': f'Insufficient strikes: {strike_count} < {config.min_strike_count}'
            }
            results['overall_pass'] = False
            results['errors'].append(f'Insufficient strike coverage: {strike_count} strikes')
        else:
            results['checks']['strike_count'] = {
                'pass': True,
                'value': strike_count, 
                'message': f'Adequate strike count: {strike_count}'
            }
        
        # Check 2: Strike Interval Quality
        if len(all_strikes) > 1:
            strike_intervals = [all_strikes[i+1] - all_strikes[i] for i in range(len(all_strikes)-1)]
            avg_interval = sum(strike_intervals) / len(strike_intervals)
            
            if avg_interval > config.max_strike_interval:
                results['checks']['strike_interval'] = {
                    'pass': False,
                    'value': avg_interval,
                    'threshold': config.max_strike_interval,
                    'message': f'Strike intervals too wide: {avg_interval:.2f} > {config.max_strike_interval}'
                }
                results['warnings'].append(f'Wide strike intervals may reduce delta accuracy: {avg_interval:.2f}')
            else:
                results['checks']['strike_interval'] = {
                    'pass': True,
                    'value': avg_interval,
                    'message': f'Good strike interval: {avg_interval:.2f}'
                }
        
        # Check 3: Time to Expiration
        try:
            exp_date = datetime.strptime(expiration_date, '%Y-%m-%d')
            days_to_expiry = (exp_date - datetime.now()).days
            
            if days_to_expiry < config.min_days_to_expiry:
                results['checks']['time_to_expiry'] = {
                    'pass': False,
                    'value': days_to_expiry,
                    'threshold': config.min_days_to_expiry,
                    'message': f'Too close to expiration: {days_to_expiry} days'
                }
                results['warnings'].append(f'Very close to expiration: {days_to_expiry} days - delta behavior may be unstable')
            else:
                results['checks']['time_to_expiry'] = {
                    'pass': True,
                    'value': days_to_expiry,
                    'message': f'Good time to expiry: {days_to_expiry} days'
                }
        except Exception as e:
            results['warnings'].append(f'Could not parse expiration date: {e}')
        
        # Check 4: Delta Distribution Quality
        valid_calls = calls_df[calls_df['delta'].notna() & (calls_df['delta'] > 0)]
        valid_puts = puts_df[puts_df['delta'].notna() & (puts_df['delta'] < 0)]
        
        if not valid_calls.empty:
            call_delta_std = valid_calls['delta'].std()
            if call_delta_std < config.min_delta_std:
                results['checks']['call_delta_distribution'] = {
                    'pass': False,
                    'value': call_delta_std,
                    'threshold': config.min_delta_std,
                    'message': f'Poor call delta distribution: std={call_delta_std:.4f}'
                }
                results['warnings'].append(f'Limited call delta variation: {call_delta_std:.4f}')
            else:
                results['checks']['call_delta_distribution'] = {
                    'pass': True,
                    'value': call_delta_std,
                    'message': f'Good call delta distribution: std={call_delta_std:.4f}'
                }
        
        if not valid_puts.empty:
            put_delta_std = valid_puts['delta'].abs().std()  # Use absolute values for puts
            if put_delta_std < config.min_delta_std:
                results['checks']['put_delta_distribution'] = {
                    'pass': False,
                    'value': put_delta_std,
                    'threshold': config.min_delta_std,
                    'message': f'Poor put delta distribution: std={put_delta_std:.4f}'
                }
                results['warnings'].append(f'Limited put delta variation: {put_delta_std:.4f}')
            else:
                results['checks']['put_delta_distribution'] = {
                    'pass': True,
                    'value': put_delta_std,
                    'message': f'Good put delta distribution: std={put_delta_std:.4f}'
                }
        
        # Check 5: Bid-Ask Spread Quality
        def check_spread_quality(df, option_type):
            if 'bid' in df.columns and 'ask' in df.columns:
                valid_options = df[(df['bid'] > 0) & (df['ask'] > df['bid'])]
                if not valid_options.empty:
                    spreads = (valid_options['ask'] - valid_options['bid']) / ((valid_options['ask'] + valid_options['bid']) / 2)
                    avg_spread_pct = spreads.mean()
                    
                    if avg_spread_pct > config.max_bid_ask_spread_pct:
                        results['checks'][f'{option_type}_spread_quality'] = {
                            'pass': False,
                            'value': avg_spread_pct,
                            'threshold': config.max_bid_ask_spread_pct,
                            'message': f'Wide {option_type} spreads: {avg_spread_pct:.2%}'
                        }
                        results['warnings'].append(f'Wide {option_type} bid-ask spreads: {avg_spread_pct:.2%}')
                    else:
                        results['checks'][f'{option_type}_spread_quality'] = {
                            'pass': True,
                            'value': avg_spread_pct,
                            'message': f'Good {option_type} spread quality: {avg_spread_pct:.2%}'
                        }
        
        check_spread_quality(calls_df, 'call')
        check_spread_quality(puts_df, 'put')
        
        # Summary
        total_checks = len(results['checks'])
        passed_checks = sum(1 for check in results['checks'].values() if check['pass'])
        results['summary'] = {
            'total_checks': total_checks,
            'passed_checks': passed_checks,
            'pass_rate': passed_checks / total_checks if total_checks > 0 else 0
        }
        
        logger.info(f"Validation complete: {passed_checks}/{total_checks} checks passed")
        
    except Exception as e:
        logger.error(f"Error during validation: {str(e)}", exc_info=True)
        results['errors'].append(f'Validation error: {str(e)}')
        results['overall_pass'] = False
    
    return results

def validate_delta_16_matches(delta_16_plus_option: pd.Series, delta_16_minus_option: pd.Series, 
                             config: Delta16ValidationConfig) -> Dict[str, Any]:
    """
    Validate the quality of specific Delta 16+/- option matches.
    
    Args:
        delta_16_plus_option: Selected call option (pandas Series)
        delta_16_minus_option: Selected put option (pandas Series)
        config: Validation configuration
        
    Returns:
        dict: Validation results for the specific matches
    """
    results = {
        'overall_pass': True,
        'delta_plus_accuracy': None,
        'delta_minus_accuracy': None,
        'warnings': [],
        'errors': []
    }
    
    if not config.enabled:
        return results
    
    TARGET_CALL_DELTA = 0.16
    TARGET_PUT_DELTA = -0.16
    
    # Check Delta 16+ accuracy
    call_delta_diff = abs(float(delta_16_plus_option['delta']) - TARGET_CALL_DELTA)
    results['delta_plus_accuracy'] = call_delta_diff
    
    if call_delta_diff > config.max_delta_deviation:
        results['overall_pass'] = False
        results['errors'].append(
            f'Delta 16+ match too inaccurate: {call_delta_diff:.4f} > {config.max_delta_deviation:.4f} '
            f'(found: {delta_16_plus_option["delta"]:.4f}, target: {TARGET_CALL_DELTA})'
        )
    
    # Check Delta 16- accuracy  
    put_delta_diff = abs(float(delta_16_minus_option['delta']) - TARGET_PUT_DELTA)
    results['delta_minus_accuracy'] = put_delta_diff
    
    if put_delta_diff > config.max_delta_deviation:
        results['overall_pass'] = False
        results['errors'].append(
            f'Delta 16- match too inaccurate: {put_delta_diff:.4f} > {config.max_delta_deviation:.4f} '
            f'(found: {delta_16_minus_option["delta"]:.4f}, target: {TARGET_PUT_DELTA})'
        )
    
    # Check for asymmetric accuracy
    accuracy_ratio = max(call_delta_diff, put_delta_diff) / min(call_delta_diff, put_delta_diff) if min(call_delta_diff, put_delta_diff) > 0 else float('inf')
    if accuracy_ratio > 3.0:  # One side is 3x worse than the other
        results['warnings'].append(
            f'Asymmetric delta accuracy: call={call_delta_diff:.4f}, put={put_delta_diff:.4f}'
        )
    
    return results

def calculate_delta_16_values(option_chain_dict: Dict[str, pd.DataFrame], expiration_date: str, 
                             validation_config: Optional[Delta16ValidationConfig] = None) -> Optional[Dict[str, Any]]:
    """
    Calculate Delta 16+ (call) and Delta 16- (put) using direct lookup method from option chain.
    
    This is the most accurate method when delta values are available in the option chain
    as it uses actual market-derived deltas that incorporate real implied volatilities,
    volatility smile/skew effects, and current market conditions.
    
    Args:
        option_chain_dict: Dictionary containing option data:
            {
                'calls': pd.DataFrame with columns ['strike', 'delta', 'bid', 'ask', ...],
                'puts': pd.DataFrame with columns ['strike', 'delta', 'bid', 'ask', ...]
            }
        expiration_date: Specific expiration date to filter options (YYYY-MM-DD format)
        validation_config: Optional validation configuration object
    
    Returns:
        dict: {
            'delta_16_plus': {'strike': float, 'delta': float, 'price': float, ...},
            'delta_16_minus': {'strike': float, 'delta': float, 'price': float, ...},
            'validation_results': {...}  # Validation check results
        } or None if calculation fails
    """
    logger.info(f"Calculating Delta 16+/- values for expiration {expiration_date}")
    
    # Use default validation config if none provided
    if validation_config is None:
        validation_config = Delta16ValidationConfig()
        validation_config.enabled = False  # Default to disabled for backward compatibility
        logger.info("No validation config provided - using default disabled config")
    else:
        logger.info(f"Using provided validation config: enabled={validation_config.enabled}")
    
    try:
        calls_df = option_chain_dict.get('calls')
        puts_df = option_chain_dict.get('puts')
        
        if calls_df is None or puts_df is None or calls_df.empty or puts_df.empty:
            logger.error("Missing or empty option chain data for delta calculation")
            return None
        
        # Check if delta column exists
        if 'delta' not in calls_df.columns or 'delta' not in puts_df.columns:
            logger.warning("Delta values not available in option chain - cannot calculate proper Delta 16 values")
            return None
        
        # Run quality validation checks first
        validation_results = validate_delta_16_quality(calls_df, puts_df, expiration_date, validation_config)
        
        # If validation is enabled and fails, return None
        if validation_config.enabled and not validation_results['overall_pass']:
            logger.error("Delta 16+/- validation failed:")
            for error in validation_results['errors']:
                logger.error(f"  - {error}")
            for warning in validation_results['warnings']:
                logger.warning(f"  - {warning}")
            return None
        
        # Log validation warnings even if overall pass
        for warning in validation_results['warnings']:
            logger.warning(f"Delta 16+/- validation warning: {warning}")
        
        # Filter out options with missing or invalid delta values
        valid_calls = calls_df[calls_df['delta'].notna() & (calls_df['delta'] > 0)]
        valid_puts = puts_df[puts_df['delta'].notna() & (puts_df['delta'] < 0)]
        
        if valid_calls.empty or valid_puts.empty:
            logger.error("No valid options with delta values found")
            return None
        
        # Target delta values
        TARGET_CALL_DELTA = 0.16
        TARGET_PUT_DELTA = -0.16
        
        # Find Delta 16+ (Call with delta closest to +0.16)
        call_delta_diffs = (valid_calls['delta'] - TARGET_CALL_DELTA).abs()
        delta_16_plus_idx = call_delta_diffs.idxmin()
        delta_16_plus_option = valid_calls.loc[delta_16_plus_idx]
        
        # Find Delta 16- (Put with delta closest to -0.16)
        put_delta_diffs = (valid_puts['delta'] - TARGET_PUT_DELTA).abs()
        delta_16_minus_idx = put_delta_diffs.idxmin()
        delta_16_minus_option = valid_puts.loc[delta_16_minus_idx]
        
        # Validate the specific matches
        match_validation = validate_delta_16_matches(delta_16_plus_option, delta_16_minus_option, validation_config)
        
        # If match validation fails and validation is enabled, return None
        if validation_config.enabled and not match_validation['overall_pass']:
            logger.error("Delta 16+/- match validation failed:")
            for error in match_validation['errors']:
                logger.error(f"  - {error}")
            return None
        
        # Log match validation warnings
        for warning in match_validation['warnings']:
            logger.warning(f"Delta 16+/- match warning: {warning}")
        
        # Quality validation - ensure we found reasonable matches
        call_delta_diff = abs(float(delta_16_plus_option['delta']) - TARGET_CALL_DELTA)
        put_delta_diff = abs(float(delta_16_minus_option['delta']) - TARGET_PUT_DELTA)
        
        # Log the accuracy of our matches
        logger.info(f"Delta 16+ match accuracy: {call_delta_diff:.4f} (target: {TARGET_CALL_DELTA}, found: {delta_16_plus_option['delta']:.4f})")
        logger.info(f"Delta 16- match accuracy: {put_delta_diff:.4f} (target: {TARGET_PUT_DELTA}, found: {delta_16_minus_option['delta']:.4f})")
        
        # Calculate mid prices for the delta 16 options
        delta_16_plus_price = (float(delta_16_plus_option['bid']) + float(delta_16_plus_option['ask'])) / 2
        delta_16_minus_price = (float(delta_16_minus_option['bid']) + float(delta_16_minus_option['ask'])) / 2
        
        # Package results
        results = {
            'delta_16_plus': {
                'strike': float(delta_16_plus_option['strike']),
                'delta': float(delta_16_plus_option['delta']),
                'price': delta_16_plus_price,
                'bid': float(delta_16_plus_option['bid']),
                'ask': float(delta_16_plus_option['ask']),
                'type': 'call',
                'delta_accuracy': call_delta_diff  # How close to exact 0.16
            },
            'delta_16_minus': {
                'strike': float(delta_16_minus_option['strike']),
                'delta': float(delta_16_minus_option['delta']),
                'price': delta_16_minus_price,
                'bid': float(delta_16_minus_option['bid']),
                'ask': float(delta_16_minus_option['ask']),
                'type': 'put',
                'delta_accuracy': put_delta_diff  # How close to exact -0.16
            },
            'validation_results': {
                'quality_check': validation_results,
                'match_check': match_validation,
                'validation_enabled': validation_config.enabled
            }
        }
        
        logger.info(f"Successfully calculated Delta 16 values:")
        logger.info(f"  Delta 16+ Call: Strike ${results['delta_16_plus']['strike']}, Delta {results['delta_16_plus']['delta']:.4f}")
        logger.info(f"  Delta 16- Put: Strike ${results['delta_16_minus']['strike']}, Delta {results['delta_16_minus']['delta']:.4f}")
        
        if validation_config.enabled:
            logger.info(f"  Validation: {validation_results['summary']['passed_checks']}/{validation_results['summary']['total_checks']} checks passed")
        
        return results
        
    except Exception as e:
        logger.error(f"Error calculating Delta 16 values: {str(e)}", exc_info=True)
        return None


def calculate_risk_reversal_spread(delta_16_results: Dict[str, Any]) -> Optional[float]:
    """
    Calculate the risk reversal spread (Call IV - Put IV) from Delta 16+/- results
    
    Args:
        delta_16_results: Output from calculate_delta_16_values()
    
    Returns:
        float: Risk reversal spread in volatility terms, or None if data unavailable
    """
    try:
        delta_16_plus = delta_16_results.get('delta_16_plus', {})
        delta_16_minus = delta_16_results.get('delta_16_minus', {})
        
        call_iv = delta_16_plus.get('implied_vol')
        put_iv = delta_16_minus.get('implied_vol')
        
        if call_iv is None or put_iv is None:
            logger.warning("Implied volatility data missing for risk reversal calculation")
            return None
        
        rr_spread = float(call_iv) - float(put_iv)
        logger.info(f"Risk reversal spread: {rr_spread:.4f} (Call IV - Put IV)")
        return rr_spread
        
    except Exception as e:
        logger.error(f"Error calculating risk reversal spread: {str(e)}")
        return None




def main():
    """Main function for the WEM application"""
    setup_logging()
    
    # App title and description
    st.title("📊 Weekly Expected Moves (WEM)")
    st.subheader("Options-derived expected price ranges for the upcoming week")
    
    # Get available symbols from database for the symbol selector (at top level for broader scope)
    try:
        with get_db_connection() as db_session:
            all_wem_stocks = db_session.query(WEMStock).all()
            # Create formatted options showing which are default stocks
            stock_options = []
            default_symbols = []
            all_symbols = []
            
            for stock in sorted(all_wem_stocks, key=lambda x: x.symbol):
                symbol = stock.symbol
                all_symbols.append(symbol)
                if stock.is_default:
                    stock_options.append(f"⭐ {symbol}")  # Star for default stocks
                    default_symbols.append(symbol)
                else:
                    stock_options.append(f"   {symbol}")  # Spaces for alignment
            
            # For the actual filtering, we need the clean symbol names
            available_symbols = all_symbols
            
    except Exception as e:
        st.error(f"Error loading stock symbols: {str(e)}")
        available_symbols = []
        default_symbols = []
        stock_options = []
    
    # Sidebar configuration
    with st.sidebar:
        st.header("WEM Configuration")
        
        # Data source and pricing mode toggles - DEFINE FIRST before any buttons that use them
        st.subheader("Data Source & Pricing")
        
        # Initialize data source setting in session state if not exists
        if 'use_friday_close' not in st.session_state:
            # Default to Friday Close (the "right" way)
            st.session_state.use_friday_close = True
        
        # Data source toggle
        use_friday_close = st.checkbox(
            "Use Friday Close Data",
            value=st.session_state.use_friday_close,
            key="data_source_checkbox",
            help="When enabled, uses previous Friday's close price for WEM calculations (standard method). When disabled, uses most recent market data (for testing purposes)."
        )
        
        # Update session state when checkbox changes
        st.session_state.use_friday_close = use_friday_close
        
        # Initialize regular hours setting in session state if not exists
        if 'regular_hours_only' not in st.session_state:
            # Try to get default from settings, fallback to False
            default_regular_hours = settings.get('wem', {}).get('pricing', {}).get('default_regular_hours_only', False)
            st.session_state.regular_hours_only = default_regular_hours
        
        regular_hours_only = st.checkbox(
            "Use Regular Hours Close Only",
            value=st.session_state.regular_hours_only,
            key="regular_hours_checkbox",
            help="When enabled, uses last regular trading session close (4:00 PM ET) instead of extended hours pricing. Applies to both Friday Close and Most Recent data modes."
        )
        
        # Update session state when checkbox changes
        st.session_state.regular_hours_only = regular_hours_only
        
        # Add informational text about the data source and pricing mode
        data_source_text = "Friday Close" if use_friday_close else "Most Recent"
        pricing_mode_text = "Regular Hours" if regular_hours_only else "Extended Hours"
        st.caption(f"📊 **{data_source_text}** data using **{pricing_mode_text}** pricing")
        
        if use_friday_close:
            st.caption("✅ Standard WEM calculation using previous Friday's close price")
        else:
            st.caption("🧪 Testing mode using most recent market data")
        
        # Delta 16 Validation Controls - MOVED TO TOP so config is available for WEM button
        st.subheader("Delta 16+/- Validation")
        
        # Get validation defaults from settings
        validation_defaults = settings.get('wem', {}).get('validation', {})
        validation_enabled_default = validation_defaults.get('enabled_by_default', False)
        threshold_defaults = validation_defaults.get('default_thresholds', {})
        
        # Enable/disable validation
        validation_enabled = st.checkbox(
            "Enable Delta 16+/- Quality Validation",
            value=validation_enabled_default,
            help="Enable quality checks for Delta 16+/- calculations to ensure accurate results"
        )
        
        # Set default values for validation parameters from settings
        max_delta_deviation = threshold_defaults.get('max_delta_deviation', 0.03)
        min_strike_count = threshold_defaults.get('min_strike_count', 5)
        max_strike_interval = threshold_defaults.get('max_strike_interval', 10.0)
        min_days_to_expiry = threshold_defaults.get('min_days_to_expiry', 1)
        min_delta_std = threshold_defaults.get('min_delta_std', 0.05)
        max_bid_ask_spread = threshold_defaults.get('max_bid_ask_spread_pct', 0.10)
        
        # Advanced validation settings (only show if validation is enabled)
        if validation_enabled:
            with st.expander("Advanced Validation Settings", expanded=False):
                st.caption("Fine-tune validation thresholds for Delta 16+/- calculations")
                
                max_delta_deviation = st.slider(
                    "Max Delta Deviation",
                    min_value=0.01,
                    max_value=0.10,
                    value=max_delta_deviation,
                    step=0.01,
                    format="%.2f",
                    help="Maximum allowed deviation from target delta (0.16/-0.16)"
                )
                
                min_strike_count = st.slider(
                    "Min Strike Count",
                    min_value=3,
                    max_value=20,
                    value=min_strike_count,
                    step=1,
                    help="Minimum number of option strikes required"
                )
                
                max_strike_interval = st.slider(
                    "Max Strike Interval",
                    min_value=1.0,
                    max_value=25.0,
                    value=max_strike_interval,
                    step=1.0,
                    format="%.1f",
                    help="Maximum average strike price interval"
                )
                
                min_days_to_expiry = st.slider(
                    "Min Days to Expiry",
                    min_value=0,
                    max_value=7,
                    value=min_days_to_expiry,
                    step=1,
                    help="Minimum days until expiration (0 = allow same day)"
                )
                
                min_delta_std = st.slider(
                    "Min Delta Std Dev",
                    min_value=0.01,
                    max_value=0.20,
                    value=min_delta_std,
                    step=0.01,
                    format="%.2f",
                    help="Minimum delta standard deviation for good distribution"
                )
                
                max_bid_ask_spread = st.slider(
                    "Max Bid-Ask Spread %",
                    min_value=0.05,
                    max_value=0.50,
                    value=max_bid_ask_spread,
                    step=0.01,
                    format="%.2f",
                    help="Maximum bid-ask spread as percentage of mid price"
                )
        
        # Create and store validation config in session state
        if validation_enabled:
            validation_config = Delta16ValidationConfig()
            validation_config.enabled = True
            validation_config.max_delta_deviation = max_delta_deviation
            validation_config.min_strike_count = min_strike_count
            validation_config.max_strike_interval = max_strike_interval
            validation_config.min_days_to_expiry = min_days_to_expiry
            validation_config.min_delta_std = min_delta_std
            validation_config.max_bid_ask_spread_pct = max_bid_ask_spread
        else:
            validation_config = Delta16ValidationConfig()
            validation_config.enabled = False
        
        # Store in session state for use in calculations
        st.session_state.delta_16_validation_config = validation_config
        
        # Show current validation status
        if validation_enabled:
            st.success("✅ Delta 16+/- validation enabled")
            st.caption(f"📊 Current thresholds: Max deviation {max_delta_deviation:.2f}, Min strikes {min_strike_count}")
        else:
            st.info("⚠️ Delta 16+/- validation disabled - calculations will accept any closest match")

        # Show debug tools only when debug mode is enabled
        debug_enabled = settings.get('logging', {}).get('debug', {}).get('enabled', False)
        if debug_enabled:
            st.subheader("🔧 Debug Tools")
            st.caption("Debug mode is enabled - additional testing tools available")
            
            # Holiday detection test button (debug mode only)
            if st.button("🧪 Test Holiday Detection", help="Test the market holiday detection system (Debug Mode)"):
                test_holiday_detection_ui()
        
        # Add a button to update WEM data - MOVED AFTER validation config setup
        if st.button("Update WEM Data", help="Fetch latest options data and calculate WEM"):
            with st.spinner("Updating WEM data..."):
                try:
                    # Set up logging for this WEM session
                    session_logger = setup_wem_logging()
                    data_source_text = "Friday Close" if use_friday_close else "Most Recent"
                    pricing_mode_text = "regular hours" if regular_hours_only else "extended hours"
                    session_logger.info(f"Starting WEM data update using {data_source_text} data with {pricing_mode_text} pricing...")
                    
                    # Use the database session within a context manager
                    with get_db_connection() as db_session:
                        update_all_wem_stocks(db_session, regular_hours_only, use_friday_close, session_logger)
                    
                    session_logger.info(f"WEM data update completed using {data_source_text} data with {pricing_mode_text} pricing")
                    
                    # Log session end
                    session_logger.info("=" * 80)
                    session_logger.info(f"WEM CALCULATION SESSION ENDED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    session_logger.info("=" * 80)
                    
                    st.success(f"WEM data updated successfully using {data_source_text} data with {pricing_mode_text} pricing!")
                    # Rerun the app to show updated data
                    time.sleep(1)  # Small delay to ensure UI updates
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update WEM data: {str(e)}")
                    if 'session_logger' in locals():
                        session_logger.exception("WEM update error")

        # Stock management section
        st.subheader("Stock Management")
        
        # Unified add stock section
        st.write("**Add Stocks**")
        
        # Single text area that handles both single and multiple stocks
        with st.form("add_stocks_form"):
            stock_symbols = st.text_area(
                "Stock Symbols",
                placeholder="Enter one or more symbols (e.g., AAPL or SPY, QQQ, TSLA, META, NVDA)",
                height=68,
                key="stock_symbols_input",
                help="Enter single symbol (AAPL) or multiple symbols separated by commas/spaces"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                is_default = st.checkbox("Add as Default Stocks", key="add_default")
            with col2:
                auto_select = st.checkbox(
                    "Auto-select for display", 
                    value=True, 
                    key="auto_select",
                    help="Automatically add newly added stocks to the current display selection"
                )
            
            submit_button = st.form_submit_button("Add Stocks", type="primary")
            
            if submit_button and stock_symbols:
                try:
                    # Parse symbols from text (handle commas, spaces, newlines)
                    import re
                    symbols_to_add = re.findall(r'[A-Za-z]+', stock_symbols.upper())
                    symbols_to_add = list(set(symbols_to_add))  # Remove duplicates
                    
                    if not symbols_to_add:
                        st.warning("No valid stock symbols found in input")
                    else:
                        with get_db_connection() as db_session:
                            added_count = 0
                            skipped_count = 0
                            error_count = 0
                            newly_added_symbols = []  # Track newly added symbols
                            
                            # Show progress for multiple stocks
                            if len(symbols_to_add) > 1:
                                progress_bar = st.progress(0)
                                status_text = st.empty()
                            
                            for i, symbol in enumerate(symbols_to_add):
                                if len(symbols_to_add) > 1:
                                    status_text.text(f"Processing {symbol}... ({i+1}/{len(symbols_to_add)})")
                                    progress_bar.progress((i + 1) / len(symbols_to_add))
                                
                                try:
                                    # Check if stock already exists
                                    existing = db_session.query(WEMStock).filter_by(symbol=symbol).first()
                                    if existing:
                                        logger.info(f"Stock {symbol} already exists, skipping")
                                        skipped_count += 1
                                    else:
                                        add_wem_stock(db_session, symbol, is_default)
                                        logger.info(f"Added {symbol} to WEM stocks")
                                        added_count += 1
                                        newly_added_symbols.append(symbol)
                                        
                                        # Track newly added stocks for export validation
                                        st.session_state.newly_added_stocks.add(symbol)
                                        
                                except Exception as stock_error:
                                    logger.error(f"Error adding stock {symbol}: {stock_error}")
                                    error_count += 1
                            
                            # Clear progress indicators if shown
                            if len(symbols_to_add) > 1:
                                progress_bar.empty()
                                status_text.empty()
                            
                            # Auto-select newly added stocks if requested
                            if auto_select and newly_added_symbols:
                                # Initialize selected_symbols if it doesn't exist
                                if 'selected_symbols' not in st.session_state:
                                    st.session_state.selected_symbols = []
                                
                                # Add newly added symbols to current selection (avoid duplicates)
                                current_selection = set(st.session_state.selected_symbols)
                                new_symbols_set = set(newly_added_symbols)
                                updated_selection = list(current_selection.union(new_symbols_set))
                                st.session_state.selected_symbols = updated_selection
                                
                                logger.info(f"Auto-selected {len(newly_added_symbols)} newly added stocks for display")
                            
                            # Show summary
                            if added_count > 0:
                                symbols_text = ', '.join(newly_added_symbols)
                                if len(newly_added_symbols) == 1:
                                    st.success(f"✅ Added {symbols_text} to WEM stocks")
                                else:
                                    st.success(f"✅ Added {added_count} new stocks: {symbols_text}")
                                
                                if auto_select and newly_added_symbols:
                                    st.success(f"🎯 Auto-selected new stocks for display")
                                
                                st.info("💡 Remember to click 'Update WEM Data' to calculate market data for new stocks")
                            
                            if skipped_count > 0:
                                st.info(f"ℹ️ Skipped {skipped_count} stocks (already exist)")
                            if error_count > 0:
                                st.warning(f"⚠️ Failed to add {error_count} stocks (check logs)")
                            
                            if added_count > 0:
                                time.sleep(0.5)
                                st.rerun()
                                
                except Exception as e:
                    st.error(f"Error processing symbols: {str(e)}")
                    logger.exception("Error in add stocks operation")
        
        # Remove stock section
        st.write("**Remove Stock**")
        
        # Bulk remove non-default stocks
        if available_symbols:
            non_default_symbols = [s for s in available_symbols if s not in default_symbols]
            if non_default_symbols:
                st.write("**Bulk Remove Non-Default Stocks**")
                st.caption(f"Found {len(non_default_symbols)} custom stocks: {', '.join(non_default_symbols[:5])}{' ...' if len(non_default_symbols) > 5 else ''}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Remove All Custom Stocks", type="secondary"):
                        # Double confirmation for safety
                        if 'confirm_bulk_remove' not in st.session_state:
                            st.session_state.confirm_bulk_remove = True
                            st.warning(f"⚠️ This will remove ALL {len(non_default_symbols)} custom stocks! Click 'Confirm Bulk Removal' to proceed.")
                            st.rerun()
                
                with col2:
                    # Show confirm button only if we're in confirmation state
                    if st.session_state.get('confirm_bulk_remove'):
                        if st.button("✅ Confirm Bulk Removal", type="primary"):
                            try:
                                with get_db_connection() as db_session:
                                    removed_count = 0
                                    error_count = 0
                                    
                                    # Progress bar for bulk removal
                                    progress_bar = st.progress(0)
                                    status_text = st.empty()
                                    
                                    for i, symbol in enumerate(non_default_symbols):
                                        status_text.text(f"Removing {symbol}... ({i+1}/{len(non_default_symbols)})")
                                        progress_bar.progress((i + 1) / len(non_default_symbols))
                                        
                                        try:
                                            if remove_wem_stock(db_session, symbol):
                                                removed_count += 1
                                                logger.info(f"Removed custom stock {symbol}")
                                                
                                                # Remove from current selection if selected
                                                if 'selected_symbols' in st.session_state and symbol in st.session_state.selected_symbols:
                                                    st.session_state.selected_symbols.remove(symbol)
                                            else:
                                                error_count += 1
                                                logger.warning(f"Failed to remove {symbol} - not found")
                                        except Exception as e:
                                            error_count += 1
                                            logger.error(f"Error removing {symbol}: {str(e)}")
                                    
                                    # Clear progress indicators
                                    progress_bar.empty()
                                    status_text.empty()
                                    
                                    # Clear confirmation state
                                    if 'confirm_bulk_remove' in st.session_state:
                                        del st.session_state.confirm_bulk_remove
                                    
                                    # Show results
                                    if removed_count > 0:
                                        st.success(f"✅ Successfully removed {removed_count} custom stocks")
                                    if error_count > 0:
                                        st.warning(f"⚠️ Failed to remove {error_count} stocks (check logs)")
                                    
                                    # Rerun to refresh the UI
                                    if removed_count > 0:
                                        time.sleep(1)
                                        st.rerun()
                                        
                            except Exception as e:
                                st.error(f"Error during bulk removal: {str(e)}")
                                logger.exception("Error in bulk remove operation")
                                
                                # Clear confirmation state on error
                                if 'confirm_bulk_remove' in st.session_state:
                                    del st.session_state.confirm_bulk_remove
                
                # Add cancel option
                if st.session_state.get('confirm_bulk_remove'):
                    if st.button("❌ Cancel", type="secondary"):
                        del st.session_state.confirm_bulk_remove
                        st.rerun()
                
                st.divider()
        
        # Individual stock removal
        st.write("**Remove Individual Stock**")
        if available_symbols:
            # Create options showing default/custom status
            remove_options = []
            for symbol in available_symbols:
                if symbol in default_symbols:
                    remove_options.append(f"⭐ {symbol} (default)")
                else:
                    remove_options.append(f"📈 {symbol} (custom)")
            
            selected_to_remove = st.selectbox(
                "Select Stock to Remove",
                options=[""] + remove_options,  # Empty option to prevent accidental selection
                help="⚠️ This will permanently remove the stock and all its WEM data"
            )
            
            if selected_to_remove:
                # Extract clean symbol from formatted option
                symbol_to_remove = selected_to_remove.split(" ")[1]  # Get symbol after emoji
                is_default_stock = "(default)" in selected_to_remove
                
                # Show warning and confirmation
                if is_default_stock:
                    st.warning(f"⚠️ **{symbol_to_remove}** is a default stock!")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"🗑️ Remove {symbol_to_remove}", type="primary"):
                        # Double confirmation for safety
                        if 'confirm_remove' not in st.session_state:
                            st.session_state.confirm_remove = symbol_to_remove
                            st.warning(f"⚠️ Click 'Confirm Removal' to permanently delete {symbol_to_remove}")
                            st.rerun()
                
                with col2:
                    # Show confirm button only if we're in confirmation state
                    if st.session_state.get('confirm_remove') == symbol_to_remove:
                        if st.button(f"✅ Confirm Removal", type="secondary"):
                            try:
                                with get_db_connection() as db_session:
                                    if remove_wem_stock(db_session, symbol_to_remove):
                                        st.success(f"✅ Successfully removed {symbol_to_remove} from WEM stocks")
                                        # Clear confirmation state
                                        if 'confirm_remove' in st.session_state:
                                            del st.session_state.confirm_remove
                                        # Also remove from current selection if selected
                                        if 'selected_symbols' in st.session_state and symbol_to_remove in st.session_state.selected_symbols:
                                            st.session_state.selected_symbols.remove(symbol_to_remove)
                                        # Rerun to refresh the UI
                                        time.sleep(0.5)
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Failed to remove {symbol_to_remove} - stock not found")
                            except Exception as e:
                                st.error(f"Error removing stock: {str(e)}")
                                logger.exception(f"Error removing stock {symbol_to_remove}")
                
                # Cancel confirmation if user selects a different stock
                if st.session_state.get('confirm_remove') and st.session_state.confirm_remove != symbol_to_remove:
                    del st.session_state.confirm_remove
                    
        else:
            st.info("No stocks available to remove")
        


        # Date range for data display
        st.subheader("Data Filtering")
        date_range = st.date_input(
            "Date Range",
            value=(datetime.now() - timedelta(days=7), datetime.now()),
            help="Filter stocks by last updated date"
        )
        
        # Available symbols are now loaded at the top level for broader scope
        
        # Symbol selector with multiselect
        if available_symbols:
            # Initialize default selection if not set
            if 'selected_symbols' not in st.session_state:
                st.session_state.selected_symbols = default_symbols if default_symbols else available_symbols[:10]
            
            # Allow "Select All" and "Select Defaults" shortcuts
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Select All", help="Select all available stocks"):
                    st.session_state.selected_symbols = available_symbols
                    st.rerun()
            with col2:
                if st.button("Select Defaults", help="Select only default stocks") and default_symbols:
                    st.session_state.selected_symbols = default_symbols
                    st.rerun()
            with col3:
                if st.button("Clear All", help="Clear all selections"):
                    st.session_state.selected_symbols = []
                    st.rerun()
            
            # Create mapping between formatted options and clean symbols
            option_to_symbol = {}
            symbol_to_option = {}
            for stock_option in stock_options:
                clean_symbol = stock_option.replace("⭐ ", "").replace("   ", "")
                option_to_symbol[stock_option] = clean_symbol
                symbol_to_option[clean_symbol] = stock_option
            
            # Convert current session state symbols to formatted options for display
            default_selected_options = [symbol_to_option.get(sym, sym) for sym in st.session_state.selected_symbols if sym in symbol_to_option]
            
            # Main multiselect widget with formatted options
            selected_options = st.multiselect(
                "Select Stocks to Display",
                options=stock_options,
                default=default_selected_options,
                key="symbols_multiselect",
                help="⭐ = Default stocks | Choose which stocks to include in WEM calculations and display"
            )
            
            # Convert selected formatted options back to clean symbols
            selected_symbols = [option_to_symbol[option] for option in selected_options]
            
            # Update session state with current selection
            st.session_state.selected_symbols = selected_symbols
            
            # Use selected symbols
            symbols = selected_symbols
            
            # Show selection summary
            if symbols:
                # Count default vs non-default in selection
                selected_defaults = [s for s in symbols if s in default_symbols]
                selected_non_defaults = [s for s in symbols if s not in default_symbols]
                
                summary_parts = []
                if selected_defaults:
                    summary_parts.append(f"⭐ {len(selected_defaults)} default")
                if selected_non_defaults:
                    summary_parts.append(f"📈 {len(selected_non_defaults)} custom")
                
                summary_text = " + ".join(summary_parts)
                stock_list = ', '.join(symbols[:5]) + (' ...' if len(symbols) > 5 else '')
                
                st.caption(f"📊 Selected: {len(symbols)} stocks ({summary_text}) - {stock_list}")
            else:
                st.warning("⚠️ No stocks selected - please select at least one stock")
                
        else:
            st.warning("No WEM stocks found in database. Please add stocks first.")
            symbols = []
        
        # Add helpful tip about symbol selection
        if available_symbols and len(available_symbols) > 5:
            st.caption("💡 **Tip**: Use the selection buttons above for quick filtering, or manually select individual stocks from the dropdown.")
        
        # Display options
        st.subheader("Display Options")
        
        # Add significant figures setting
        sig_figs = st.slider(
            "Significant Figures",
            min_value=2,
            max_value=8,
            value=4,
            step=1,
            help="Number of significant figures to display for numeric values"
        )
        
        # Add maximum digits setting
        max_digits = st.slider(
            "Max Digits (before decimal)",
            min_value=3,
            max_value=8,
            value=5,
            step=1,
            help="Maximum digits before decimal point (larger numbers use scientific notation)"
        )
        
        layout = st.radio(
            "Table Layout",
            options=["horizontal", "vertical"],
            index=0,  # Default to horizontal
            help="Horizontal shows stocks as columns, vertical as rows"
        )
        
        # Available metrics for display - reordered to match user requirements
        all_metrics = [
            'symbol', 'atm_price', 'straddle', 'strangle', 'wem_points', 'wem_spread',
            'delta_16_plus', 'straddle_2', 'straddle_1', 'delta_16_minus',
            'delta_range', 'delta_range_pct', 'straddle_strangle', 'last_updated'
        ]
        
        # For horizontal layout, filter out 'symbol' from selectable metrics
        # as it becomes the column headers
        display_metrics = all_metrics if layout == 'vertical' else [m for m in all_metrics if m != 'symbol']
        
        # Default selected metrics matching exact user requirements:
        # ATM (6/13/25), Straddle Level, Strangle Level, WEM Points, WEM Spread, 
        # Delta 16 (+), S2, S1, Delta 16 (-), Delta Range, Delta Range %
        default_metrics = [
            'atm_price', 'straddle', 'strangle', 'wem_points', 'wem_spread', 
            'delta_16_plus', 'straddle_2', 'straddle_1', 'delta_16_minus',
            'delta_range', 'delta_range_pct'
        ]
        if layout == 'vertical':
            default_metrics.insert(0, 'symbol')
        
        selected_metrics = st.multiselect(
            "Metrics to Display",
            options=display_metrics,
            default=default_metrics,
            help="Select which metrics to display in the table. You can reorder metrics by selecting/deselecting them."
        )
        
        st.caption("💡 Tip: You can reorder columns by selecting/deselecting them in the desired order.")
        
        # For vertical layout, ensure symbol is always included
        if layout == 'vertical' and 'symbol' not in selected_metrics:
            selected_metrics.insert(0, 'symbol')
        
        # Export options
        st.subheader("Export Options")
        
        # Get export defaults from settings
        export_defaults = settings.get('wem', {}).get('export', {})
        default_format = export_defaults.get('default_format', 'Excel')
        format_options = ["CSV", "Excel"]
        default_index = format_options.index(default_format) if default_format in format_options else 1
        
        export_format = st.selectbox(
            "Export Format",
            options=format_options,
            index=default_index,
            help="Select export format"
        )
        
        # Store export format in session state for access outside sidebar
        st.session_state.export_format = export_format
        
        # Export button (will be handled after data is loaded)
        export_data_requested = st.button("Export Data", help="Export WEM data to file")
        if export_data_requested:
            st.session_state.export_requested = True
        
        # Initialize wem_df as None so we can check if it exists before export
        wem_df = None
        
    # Main content setup - Get data within context manager
    try:
        # Get WEM stocks from database within a context manager
        with get_db_connection() as db_session:
            # Check if wem_stocks table exists, if not initialize the database
            from sqlalchemy import inspect
            inspector = inspect(db_session.bind)
            existing_tables = inspector.get_table_names()
            
            if 'wem_stocks' not in existing_tables:
                logger.warning("wem_stocks table not found, initializing database...")
                st.warning("⚠️ WEM database not initialized. Setting up tables...")
                
                # Initialize the database
                from goldflipper.database.connection import init_db
                init_db(force=False)
                
                # Add default stocks
                default_stocks = ['SPY', 'QQQ', 'VIX', 'NKE', 'SHOP', 'DLTR', 'WMT', 'TSLA', 'COIN', 'SBUX', 'PLTR', 'AMD', 'DIS']
                for symbol in default_stocks:
                    try:
                        add_wem_stock(db_session, symbol, is_default=True)
                        logger.info(f"Added default stock: {symbol}")
                    except Exception as stock_error:
                        logger.warning(f"Failed to add {symbol}: {stock_error}")
                
                st.success("✅ Database initialized successfully!")
                st.info("Please refresh the page to load the WEM data.")
                return
            
            # Get WEM stocks from database
            date_start, date_end = date_range
            date_end = datetime.combine(date_end, datetime.max.time())  # End of the selected day
            
            # Add a day to include the end date in the range
            date_end += timedelta(days=1)
            
            wem_stocks = get_wem_stocks(
                db_session, 
                from_date=date_start,
                to_date=date_end,
                symbols=symbols
            )
            
            # Debug logging for missing stocks
            if symbols:
                found_symbols = {stock['symbol'] for stock in wem_stocks}
                missing_symbols = set(symbols) - found_symbols
                if missing_symbols:
                    logger.warning(f"Selected symbols not found in database: {missing_symbols}")
                    logger.info(f"Found symbols: {found_symbols}")
                    logger.info(f"Selected symbols: {set(symbols)}")
            
            if not wem_stocks:
                st.warning("No WEM data found. Please update the data first.")
            else:
                # Convert to list of dictionaries
                stocks_data = wem_stocks  # Already a list of dictionaries
                
                # If there are selected symbols that aren't in the data, add stub records for them
                if symbols:
                    found_symbols = {stock['symbol'] for stock in stocks_data}
                    missing_symbols = set(symbols) - found_symbols
                    if missing_symbols:
                        logger.info(f"Adding stub display records for missing symbols: {missing_symbols}")
                        for missing_symbol in missing_symbols:
                            stub_display_record = create_stub_wem_record(missing_symbol)
                            # Add last_updated in ISO format to match database records
                            stub_display_record['last_updated'] = datetime.now(timezone.utc).isoformat()
                            stocks_data.append(stub_display_record)
                
                # Create WEM table
                wem_df = create_wem_table(stocks_data, layout=layout, metrics=selected_metrics, sig_figs=sig_figs, max_digits=max_digits)
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        logger.exception("Error getting WEM data")
        wem_df = None
    
    # Handle export request from sidebar with validation
    if hasattr(st.session_state, 'export_requested') and st.session_state.export_requested:
        st.session_state.export_requested = False  # Reset the flag
        
        if wem_df is None:
            st.error("No data available to export. Please update the WEM data first.")
        else:
            # Check for export validation issues
            validation = check_export_validation(wem_stocks if 'wem_stocks' in locals() else [])
            
            if validation['has_warnings']:
                # Show validation warning dialog
                st.warning("⚠️ Export Validation Warning")
                st.write(validation['message'])
                
                # Show additional details for stale data
                if validation['stale_symbols']:
                    with st.expander("View stale data details", expanded=False):
                        st.write(f"**Stocks with data older than 1 week:** {', '.join(validation['stale_symbols'])}")
                
                # Show action buttons based on warning type
                col_count = len(validation['actions'])
                cols = st.columns(col_count)
                
                with cols[0]:  # Update button (always first)
                    if st.button("🔄 Update Data", type="primary", key="export_update"):
                        # Trigger WEM data update
                        with st.spinner("Updating WEM data..."):
                            try:
                                session_logger = setup_wem_logging()
                                data_source_text = "Friday Close" if st.session_state.get('use_friday_close', True) else "Most Recent"
                                pricing_mode_text = "regular hours" if st.session_state.get('regular_hours_only', False) else "extended hours"
                                session_logger.info(f"Starting WEM data update from export validation using {data_source_text} data with {pricing_mode_text} pricing...")
                                
                                with get_db_connection() as db_session:
                                    update_all_wem_stocks(db_session, st.session_state.get('regular_hours_only', False), 
                                                         st.session_state.get('use_friday_close', True), session_logger)
                                
                                session_logger.info(f"WEM data update completed from export validation")
                                st.success("✅ Data updated successfully! Export will proceed automatically.")
                                
                                # Set flag to proceed with export after update
                                st.session_state.export_after_update = True
                                time.sleep(1)
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"Update failed: {str(e)}")
                                if 'session_logger' in locals():
                                    session_logger.exception("WEM update error during export validation")
                
                # Proceed Anyway button (for stale data warnings)
                if 'Proceed Anyway' in validation['actions']:
                    with cols[1 if col_count == 3 else -1]:
                        if st.button("⚠️ Proceed Anyway", type="secondary", key="export_proceed"):
                            st.session_state.export_forced = True
                            st.rerun()
                
                # Cancel button (always last)
                with cols[-1]:
                    if st.button("❌ Cancel", key="export_cancel"):
                        st.info("Export cancelled.")
                        st.stop()
                        
                # Don't proceed with export if we showed warnings
                st.stop()
            
            # Check if we should proceed after update or forced export
            proceed_with_export = (
                not validation['has_warnings'] or 
                st.session_state.get('export_after_update', False) or 
                st.session_state.get('export_forced', False)
            )
            
            # Clear the flags
            if 'export_after_update' in st.session_state:
                del st.session_state.export_after_update
            if 'export_forced' in st.session_state:
                del st.session_state.export_forced
            
            if proceed_with_export:
                with st.spinner("Preparing export..."):
                    try:
                        # Get the current timestamp for the filename
                        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M")
                        export_format = getattr(st.session_state, 'export_format', 'CSV')
                        
                        if export_format == "CSV":
                            # Export to CSV
                            csv_path = f"./data/exports/{timestamp}_export.csv"
                            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                            
                            wem_df['df'].to_csv(csv_path)
                            st.success(f"Data exported to {csv_path}")
                            
                        else:  # Excel
                            # Export to Excel with template formatting
                            excel_path = f"./data/exports/{timestamp}_export.xlsx"
                            os.makedirs(os.path.dirname(excel_path), exist_ok=True)
                            
                            try:
                                export_wem_excel_formatted(wem_df, excel_path, symbols, timestamp)
                                st.success(f"Data exported to {excel_path}")
                            except Exception as export_error:
                                logger.exception("Formatted Excel export failed, falling back to basic export")
                                # Fallback to basic Excel export if formatted export fails
                                with pd.ExcelWriter(excel_path) as writer:
                                    wem_df['df'].to_excel(writer, sheet_name='WEM Data')
                                    
                                    # Write notes to second sheet
                                    notes_df = pd.DataFrame({
                                        "Note": ["Generated by Goldflipper WEM Module", 
                                                 f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                                 f"Symbols: {', '.join(symbols) if symbols else 'All'}"]
                                    })
                                    notes_df.to_excel(writer, sheet_name='Notes', index=False)
                                
                                st.success(f"Data exported to {excel_path} (basic format)")
                    except Exception as e:
                        st.error(f"Export failed: {str(e)}")
                        logger.exception("Export error")

    # Display the table if data is available
    if 'wem_df' in locals() and wem_df is not None:
        # Display the table
        with st.container():
            st.subheader("Weekly Expected Moves")
            
            # Show current calculation settings
            current_data_source = "Friday Close" if st.session_state.get('use_friday_close', True) else "Most Recent"
            current_pricing = "Regular Hours" if st.session_state.get('regular_hours_only', False) else "Extended Hours"
            
            st.info(f"📊 **Current WEM Settings**: {current_data_source} data using {current_pricing} pricing")
            
            # Show validation status information
            if hasattr(st.session_state, 'delta_16_validation_config') and st.session_state.delta_16_validation_config.enabled:
                validation_info = st.expander("🔍 Delta 16+/- Validation Status", expanded=False)
                with validation_info:
                    st.info("✅ **Quality validation is ENABLED** for Delta 16+/- calculations")
                    st.write("**How validation works:**")
                    st.write("• **❌ Errors**: Validation failures that block calculation entirely")
                    st.write("• **⚠️ Warnings**: Quality issues detected but calculation proceeds")
                    st.write("• **✅ Pass**: All validation checks passed successfully")
                    st.write("• **➖ N/A**: No delta values available in option chain")
                    
                    st.write("**Active validation checks:**")
                    config = st.session_state.delta_16_validation_config
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"• Max delta deviation: **{config.max_delta_deviation:.2f}**")
                        st.write(f"• Min strike count: **{config.min_strike_count}**")
                        st.write(f"• Max strike interval: **${config.max_strike_interval:.1f}**")
                    with col2:
                        st.write(f"• Min days to expiry: **{config.min_days_to_expiry}**")
                        st.write(f"• Min delta std dev: **{config.min_delta_std:.2f}**")
                        st.write(f"• Max bid-ask spread: **{config.max_bid_ask_spread_pct:.1%}**")
                    
                    st.caption("💡 **Why you see deltas with warnings**: Warnings indicate potential quality issues but still allow calculation. Only errors completely block delta calculation.")
            else:
                st.info("⚠️ **Validation disabled** - Delta 16+/- values use closest available matches regardless of quality")
            
            if layout == "horizontal":
                # Filter only the rows that exist in the transposed dataframe
                valid_metrics = [metric for metric in selected_metrics if metric in wem_df['df'].index]
                
                # Apply the filter if we have valid metrics
                if valid_metrics:
                    filtered_df = wem_df['df'].loc[valid_metrics]
                    wem_df['df'] = filtered_df
                elif selected_metrics:  # Only warn if metrics were actually requested
                    logger.warning(f"No valid metrics to display in horizontal mode. Requested: {selected_metrics}, Available: {list(wem_df['df'].index)}")
                # If no specific metrics selected, show all available data
            
            else:  # vertical
                # For vertical layout, filter the requested columns
                visible_cols = selected_metrics
                
                try:
                    # Make sure all requested columns exist in the DataFrame
                    existing_cols = [col for col in visible_cols if col in wem_df['df'].columns]
                    if existing_cols:
                        filtered_df = wem_df['df'][existing_cols]
                        wem_df['df'] = filtered_df
                    else:
                        logger.warning("No valid columns to display in vertical mode")
                except Exception as e:
                    logger.error(f"Error filtering columns: {str(e)}")
                    # Continue with unfiltered dataframe
            
            # Calculate dynamic height based on actual data
            # Base height for headers + padding, plus row height for each data row
            num_rows = len(wem_df['df'])
            dynamic_height = min(max(200, 50 + (num_rows * 35)), 600)  # Min 200px, max 600px, ~35px per row
            
            # Prepare column configuration with conditional styling
            column_config = {}
            for col in wem_df['columns']:
                if col.get("type") == "number":
                    column_config[col["field"]] = st.column_config.NumberColumn(
                        col["headerName"],
                        width=col["width"],
                        format=col["format"]
                    )
                else:
                    column_config[col["field"]] = st.column_config.Column(
                        col["headerName"],
                        width=col["width"]
                    )
            
            # Special handling for validation status columns
            if 'delta_validation_status' in wem_df['df'].columns:
                column_config['delta_validation_status'] = st.column_config.Column(
                    "Δ Status",
                    width=80,
                    help="Delta 16+/- validation status: ✅ Pass, ⚠️ Warning, ❌ Error, ➖ N/A"
                )
            
            if 'delta_validation_message' in wem_df['df'].columns:
                column_config['delta_validation_message'] = st.column_config.Column(
                    "Δ Details",
                    width=120,
                    help="Detailed validation message for Delta 16+/- calculations"
                )
            
            # Style the dataframe with dynamic sizing
            st.dataframe(
                wem_df['df'],
                use_container_width=True,
                hide_index=False,  # Show index for horizontal layout
                height=dynamic_height,  # Dynamic height based on content
                column_config=column_config
            )
            
            # Add validation summary if validation is enabled
            if hasattr(st.session_state, 'delta_16_validation_config') and st.session_state.delta_16_validation_config.enabled:
                # Count validation statuses
                if 'delta_validation_status' in wem_df['df'].columns:
                    status_counts = {}
                    for status in wem_df['df']['delta_validation_status']:
                        if pd.notna(status):
                            clean_status = str(status).split(' ')[-1].lower()  # Extract status after emoji
                            status_counts[clean_status] = status_counts.get(clean_status, 0) + 1
                    
                    if status_counts:
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            if 'pass' in status_counts:
                                st.success(f"✅ {status_counts['pass']} Passed")
                        with col2:
                            if 'warning' in status_counts:
                                st.warning(f"⚠️ {status_counts['warning']} Warnings")
                        with col3:
                            if 'error' in status_counts:
                                st.error(f"❌ {status_counts['error']} Errors")
                        with col4:
                            if 'n/a' in status_counts:
                                st.info(f"➖ {status_counts['n/a']} N/A")

def export_wem_excel_formatted(wem_df, excel_path, symbols, timestamp):
    """
    Export WEM data to Excel with formatting that matches the WEM 2025 Template.
    
    Args:
        wem_df: Dictionary with 'df' (DataFrame) and 'columns' (column config)
        excel_path: Path where to save the Excel file
        symbols: List of stock symbols
        timestamp: Timestamp string for notes
    """
    from goldflipper.utils.market_holidays import find_previous_friday
    
    # Create Excel writer with xlsxwriter engine for formatting
    with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # Define subtle alternating colors for better readability
        alt_color_1 = '#FFFFFF'  # White
        alt_color_2 = '#F8F9FA'  # Very light gray
        
        # Define formats matching the template with borders
        # Header format for stock symbols (xl68 equivalent) - slightly enhanced
        header_format = workbook.add_format({
            'font_name': 'Aptos Narrow',
            'font_size': 11,
            'bold': True,  # Add bold for ticker symbols
            'align': 'center',
            'valign': 'top',
            'font_color': 'black',
            'bg_color': '#E8E8E8',  # Light gray background to distinguish as header
            'border': 1,
            'border_color': '#D3D3D3'
        })
        
        # Row label format (xl68 equivalent) - subtle header styling
        row_label_format = workbook.add_format({
            'font_name': 'Aptos Narrow', 
            'font_size': 11,
            'bold': True,  # Add bold for metric names
            'align': 'center',
            'valign': 'top',
            'font_color': 'black',
            'bg_color': '#F5F5F5',  # Very light gray background
            'border': 1,
            'border_color': '#D3D3D3'
        })
        
        # Data cell format - right aligned (xl69 equivalent)
        data_format = workbook.add_format({
            'font_name': 'Aptos Narrow',
            'font_size': 11,
            'align': 'right',
            'font_color': 'black',
            'bg_color': 'white',
            'border': 1,
            'border_color': '#D3D3D3'
        })
        
        # Alternating data formats for columns/rows
        data_format_alt = workbook.add_format({
            'font_name': 'Aptos Narrow',
            'font_size': 11,
            'align': 'right',
            'font_color': 'black',
            'bg_color': alt_color_2,
            'border': 1,
            'border_color': '#D3D3D3'
        })
        
        # Number format with commas (xl71 equivalent) - suppress trailing zeros
        number_format = workbook.add_format({
            'font_name': 'Aptos Narrow',
            'font_size': 11,
            'align': 'right',
            'font_color': 'black',
            'bg_color': 'white',
            'border': 1,
            'border_color': '#D3D3D3',
            'num_format': '#,##0.##'  # Suppress trailing zeros in decimals
        })
        
        number_format_alt = workbook.add_format({
            'font_name': 'Aptos Narrow',
            'font_size': 11,
            'align': 'right',
            'font_color': 'black',
            'bg_color': alt_color_2,
            'border': 1,
            'border_color': '#D3D3D3',
            'num_format': '#,##0.##'  # Suppress trailing zeros in decimals
        })
        
        # Percentage format (xl72 equivalent) - suppress trailing zeros
        percent_format = workbook.add_format({
            'font_name': 'Aptos Narrow',
            'font_size': 11,
            'align': 'right',
            'font_color': 'black',
            'bg_color': 'white',
            'border': 1,
            'border_color': '#D3D3D3',
            'num_format': '0.##%'  # Suppress trailing zeros in percentage decimals
        })
        
        percent_format_alt = workbook.add_format({
            'font_name': 'Aptos Narrow',
            'font_size': 11,
            'align': 'right',
            'font_color': 'black',
            'bg_color': alt_color_2,
            'border': 1,
            'border_color': '#D3D3D3',
            'num_format': '0.##%'  # Suppress trailing zeros in percentage decimals
        })
        
        # 3 decimal percentage format for delta range % - suppress trailing zeros
        percent_3dec_format = workbook.add_format({
            'font_name': 'Aptos Narrow',
            'font_size': 11,
            'align': 'right',
            'font_color': 'black',
            'bg_color': 'white',
            'border': 1,
            'border_color': '#D3D3D3',
            'num_format': '0.###%'  # Suppress trailing zeros up to 3 decimal places
        })
        
        percent_3dec_format_alt = workbook.add_format({
            'font_name': 'Aptos Narrow',
            'font_size': 11,
            'align': 'right',
            'font_color': 'black',
            'bg_color': alt_color_2,
            'border': 1,
            'border_color': '#D3D3D3',
            'num_format': '0.###%'  # Suppress trailing zeros up to 3 decimal places
        })
        
        # Header formats with alternating colors - enhanced for ticker symbols
        header_format_alt = workbook.add_format({
            'font_name': 'Aptos Narrow',
            'font_size': 11,
            'bold': True,  # Add bold for ticker symbols
            'align': 'center',
            'valign': 'top',
            'font_color': 'black',
            'bg_color': '#ECECEC',  # Slightly different gray for alternating
            'border': 1,
            'border_color': '#D3D3D3'
        })
        
        # Center-aligned formats for em-dashes (missing data)
        center_format = workbook.add_format({
            'font_name': 'Aptos Narrow',
            'font_size': 11,
            'align': 'center',
            'font_color': 'black',
            'bg_color': 'white',
            'border': 1,
            'border_color': '#D3D3D3'
        })
        
        center_format_alt = workbook.add_format({
            'font_name': 'Aptos Narrow',
            'font_size': 11,
            'align': 'center',
            'font_color': 'black',
            'bg_color': alt_color_2,
            'border': 1,
            'border_color': '#D3D3D3'
        })
        
        # Notes header format (xl75 equivalent)
        notes_header_format = workbook.add_format({
            'font_name': 'Aptos Narrow',
            'font_size': 11,
            'align': 'center',
            'font_color': 'black',
            'bg_color': '#D8D8D8',
            'bold': True,
            'border': 1,
            'border_color': '#D3D3D3'
        })
        
        # Notes content format (xl78 equivalent)
        notes_content_format = workbook.add_format({
            'font_name': 'Arial',
            'font_size': 11,
            'align': 'left',
            'valign': 'top',
            'text_wrap': True,
            'border': 1,
            'border_color': '#D3D3D3'
        })
        
        # Create worksheet
        worksheet = writer.sheets.get('WEM Data')
        if worksheet is None:
            worksheet = workbook.add_worksheet('WEM Data')
        

        # Set column widths matching template
        worksheet.set_column(0, 0, 12)  # First column (labels) - wider
        for i in range(1, len(symbols) + 1):
            worksheet.set_column(i, i, 8)  # Stock symbol columns
        
        # Get the actual ATM date from previous Friday
        try:
            previous_friday = find_previous_friday()
            atm_date_str = previous_friday.strftime('%m/%d/%y')  # Format as M/D/YY (e.g., 6/13/25)
            atm_label = f'ATM ({atm_date_str})'
        except Exception as e:
            logger.warning(f"Could not determine previous Friday date: {e}")
            atm_label = 'ATM (date)'
        
        # Determine if we're working with horizontal or vertical layout
        df = wem_df['df']
        is_horizontal = isinstance(df.index, pd.Index) and not df.index.name == 'symbol'
        
        if is_horizontal:
            # Write stock symbols as column headers (row 0) with alternating colors
            for col_idx, symbol in enumerate(symbols):
                if symbol in df.columns:
                    # Alternate column colors
                    header_fmt = header_format_alt if col_idx % 2 == 1 else header_format
                    worksheet.write(0, col_idx + 1, symbol, header_fmt)
            
            # Define the metric order and their formatting
            metric_formats = {
                atm_label: (data_format, data_format_alt),
                'Straddle Level': (data_format, data_format_alt),
                'Strangle Level': (data_format, data_format_alt),
                'WEM Points': (number_format, number_format_alt),
                'WEM Spread': (percent_format, percent_format_alt),
                'Delta 16 (+)': (data_format, data_format_alt),
                'S2': (data_format, data_format_alt),
                'S1': (data_format, data_format_alt),
                'Delta 16 (-)': (data_format, data_format_alt),
                'Delta Range': (data_format, data_format_alt),
                'Delta Range %': (percent_3dec_format, percent_3dec_format_alt)
            }
            
            # Write row labels and data
            row_idx = 1
            for metric_display_name in metric_formats.keys():
                # Find the corresponding row in the dataframe - try different matching strategies
                matching_rows = []
                
                # Try exact match first
                if metric_display_name in df.index:
                    matching_rows = [metric_display_name]
                else:
                    # Try partial match
                    for idx in df.index:
                        if metric_display_name.replace(atm_label, 'ATM') in str(idx) or \
                           str(idx).replace('ATM (6/13/25)', 'ATM').replace('ATM (dd/mm/yy)', 'ATM') in metric_display_name:
                            matching_rows = [idx]
                            break
                
                if matching_rows:
                    row_data = df.loc[matching_rows[0]]
                    
                    # Write row label
                    worksheet.write(row_idx, 0, metric_display_name, row_label_format)
                    
                    # Write data for each symbol with alternating column colors
                    for col_idx, symbol in enumerate(symbols):
                        if symbol in row_data.index:
                            value = row_data[symbol]
                            if pd.notna(value):
                                # Check if value is an em-dash (missing data) - use center format
                                if isinstance(value, str) and value == '—':
                                    cell_format = center_format_alt if col_idx % 2 == 1 else center_format
                                    worksheet.write(row_idx, col_idx + 1, value, cell_format)
                                else:
                                    # Apply appropriate formatting with alternating colors
                                    base_format, alt_format = metric_formats[metric_display_name]
                                    cell_format = alt_format if col_idx % 2 == 1 else base_format
                                    
                                    # Convert percentage strings back to numbers for proper Excel formatting
                                    if isinstance(value, str) and '%' in value:
                                        try:
                                            numeric_value = float(value.replace('%', '')) / 100
                                            worksheet.write(row_idx, col_idx + 1, numeric_value, cell_format)
                                        except:
                                            worksheet.write(row_idx, col_idx + 1, value, cell_format)
                                    else:
                                        worksheet.write(row_idx, col_idx + 1, value, cell_format)
                
                row_idx += 1
        
        else:  # Vertical layout
            # Write column headers with alternating colors
            for col_idx, col_info in enumerate(wem_df['columns']):
                header_fmt = row_label_format  # Use row_label_format for metric names
                # Update ATM column name if it exists
                header_name = col_info['headerName']
                if 'ATM (' in header_name and header_name != atm_label:
                    header_name = atm_label
                worksheet.write(0, col_idx, header_name, header_fmt)
            
            # Write data rows with alternating row colors
            for row_idx, (_, row) in enumerate(df.iterrows()):
                for col_idx, col_info in enumerate(wem_df['columns']):
                    field = col_info['field']
                    if field in row.index:
                        value = row[field]
                        if pd.notna(value):
                            # Check if value is an em-dash (missing data) - use center format
                            is_alt_row = row_idx % 2 == 1
                            
                            if isinstance(value, str) and value == '—':
                                cell_format = center_format_alt if is_alt_row else center_format
                                worksheet.write(row_idx + 1, col_idx, value, cell_format)
                            else:
                                # Determine format based on field type with alternating colors
                                if field in ['wem_points']:
                                    cell_format = number_format_alt if is_alt_row else number_format
                                elif field in ['wem_spread']:
                                    cell_format = percent_format_alt if is_alt_row else percent_format
                                elif field in ['delta_range_pct']:
                                    cell_format = percent_3dec_format_alt if is_alt_row else percent_3dec_format
                                else:
                                    cell_format = data_format_alt if is_alt_row else data_format
                                
                                # Convert percentage strings back to numbers for proper Excel formatting
                                if isinstance(value, str) and '%' in value:
                                    try:
                                        numeric_value = float(value.replace('%', '')) / 100
                                        worksheet.write(row_idx + 1, col_idx, numeric_value, cell_format)
                                    except:
                                        worksheet.write(row_idx + 1, col_idx, value, cell_format)
                                else:
                                    worksheet.write(row_idx + 1, col_idx, value, cell_format)
        
        # Add Notes section at the bottom
        notes_row = row_idx + 2 if 'row_idx' in locals() else len(df) + 2
        
        # Notes header spanning multiple columns
        num_cols = len(symbols) + 1 if is_horizontal else len(wem_df['columns'])
        worksheet.merge_range(notes_row, 0, notes_row, num_cols - 1, 'Notes', notes_header_format)
        
        # Notes content
        notes_content = f"1.) Generated by Goldflipper WEM Module\n" \
                       f"Date: {timestamp}\n" \
                       f"Symbols: {', '.join(symbols) if symbols else 'All'}\n" \
                       f"Layout: {'Horizontal' if is_horizontal else 'Vertical'}\n" \
                       f"ATM Data Date: {atm_date_str if 'atm_date_str' in locals() else 'N/A'}"
        
        worksheet.merge_range(notes_row + 1, 0, notes_row + 5, num_cols - 1, notes_content, notes_content_format)
        
        # Set row heights
        worksheet.set_default_row(15)  # 15pt row height matching template

if __name__ == "__main__":
    main() 