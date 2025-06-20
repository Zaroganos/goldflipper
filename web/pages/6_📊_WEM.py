"""
Weekly Expected Moves (WEM) Analysis Tool

This page provides functionality for:
1. Viewing and managing WEM stock list
2. Calculating and displaying expected moves
3. Exporting data to Excel
4. Managing user preferences for WEM stocks
"""

import logging
from datetime import datetime
from pathlib import Path
import yaml
import time
import random
from typing import Any

# Set up logging first, before any other imports
project_root = Path(__file__).parent.parent.parent
log_dir = project_root / 'logs'
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f'wem_{datetime.now().strftime("%Y%m%d")}.log'

# Load settings to check debug mode
settings_file = project_root / 'goldflipper' / 'config' / 'settings.yaml'
settings = {}
if settings_file.exists():
    with open(settings_file, 'r') as f:
        settings = yaml.safe_load(f)

# Configure root logger with less verbose settings
logging.basicConfig(
    level=logging.INFO,  # Set root logger to INFO level
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Console handler at INFO level
    ]
)

# Create logger for this module with more detailed settings
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Default to INFO level

# Create file handler with custom formatting for important messages
file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)  # Set file handler to INFO level
file_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
)
logger.addHandler(file_handler)

# Create debug file handler for development/troubleshooting
debug_enabled = settings.get('logging', {}).get('debug', {}).get('enabled', False)
if debug_enabled:  # Only enable debug logging if debug mode is on in settings
    debug_handler = logging.FileHandler(log_dir / f'wem_debug_{datetime.now().strftime("%Y%m%d")}.log', mode='a')
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    logger.addHandler(debug_handler)

# Test logging
logger.info("=== WEM Page Starting ===")

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
        List of WEM stocks as dictionaries
    """
    query = session.query(WEMStock)
    
    # Apply date filter if provided
    if from_date and to_date:
        query = query.filter(WEMStock.last_updated >= from_date)
        query = query.filter(WEMStock.last_updated <= to_date)
    
    # Apply symbol filter if provided
    if symbols and len(symbols) > 0:
        query = query.filter(WEMStock.symbol.in_(symbols))
    
    # Order by symbol for consistency
    query = query.order_by(WEMStock.symbol)
    
    # Execute query and convert to dictionaries
    stocks = query.all()
    logger.info(f"Retrieved {len(stocks)} WEM stocks matching filters")
    
    return [stock.to_dict() for stock in stocks]

def get_default_wem_stocks(session: Session) -> List[Dict[str, Any]]:
    """Get default WEM stocks from database as dictionaries"""
    stocks = session.query(WEMStock).filter_by(is_default=True).all()
    return [stock.to_dict() for stock in stocks]

def get_market_data(session: Session, symbol: str, days: int = 30) -> List[MarketData]:
    """Get recent market data for a symbol"""
    repo = MarketDataRepository(session)
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    return repo.get_price_history(symbol, start_time, end_time)

def get_latest_market_data(session: Session, symbol: str) -> Optional[MarketData]:
    """Get latest market data for a symbol"""
    repo = MarketDataRepository(session)
    return repo.get_latest_price(symbol)

def update_market_data(session: Session, symbol: str) -> Optional[MarketData]:
    """Update market data for a symbol"""
    try:
        manager = get_market_data_manager()
        if not manager:
            logger.error(f"No market data manager available for {symbol}")
            st.error("Market data manager is not available. Please check your configuration.")
            return None
            
        repo = MarketDataRepository(session)
        
        # Get live price from market data provider
        logger.info(f"Requesting price data for {symbol} from {manager.provider.__class__.__name__}")
        price = manager.get_stock_price(symbol)
        if price is None:
            st.warning(f"Could not get current price for {symbol}")
            logger.warning(f"Could not get price for {symbol} from any provider")
            return None
            
        # Create new market data entry
        market_data = MarketData(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            close=price,  # Use as close since it's current price
            source=manager.provider.__class__.__name__  # Use class name instead of attribute
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
        
        # Handle computed fields that might not exist in the database schema
        computed_fields = ['wem', 'straddle', 'strangle']
        
        # Process each computed field
        for field in computed_fields:
            if field in stock_data:
                field_value = stock_data.pop(field)  # Remove from dict to avoid SQLAlchemy errors
                
                # Store in meta_data as a fallback
                if isinstance(wem_stock.meta_data, dict):
                    wem_stock.meta_data[f'calculated_{field}'] = field_value
                
                # Also try to set the attribute directly if it exists
                if hasattr(wem_stock, field) and not isinstance(getattr(wem_stock, field), type(None)):
                    setattr(wem_stock, field, field_value)
        
        # Update other attributes
        for key, value in stock_data.items():
            if hasattr(wem_stock, key):
                setattr(wem_stock, key, value)
        
        # Commit the changes
        session.commit()
        logger.info(f"Successfully updated WEM stock: {symbol}")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating WEM stock {symbol}: {str(e)}", exc_info=True)
        return False

def calculate_expected_move(session: Session, stock_data: Dict[str, Any]) -> Dict[str, Any]:
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
        
    Returns:
        dict: Dictionary with calculated WEM values, or None if calculation fails
    """
    symbol = stock_data.get('symbol')
    if not symbol:
        logger.error("No symbol provided for WEM calculation")
        return None
            
    logger.info(f"Calculating Weekly Expected Move for {symbol}")
    
    try:
        # Step 1: Get current stock price
        logger.debug(f"Getting current market data for {symbol}")
        market_data = get_latest_market_data(session, symbol)
        
        # Update market data if it's stale (older than 5 minutes)
        if not market_data or (datetime.utcnow() - market_data.timestamp).total_seconds() > 300:
            logger.info(f"Market data for {symbol} is stale, updating...")
            market_data = update_market_data(session, symbol)
        
        if not market_data:
            logger.error(f"No market data available for {symbol}")
            return None
        
        current_price = market_data.close
        logger.info(f"Current price for {symbol}: ${current_price:.2f}")
        
        # Step 2: Find next Friday expiration date
        next_friday = _find_next_friday_expiration()
        logger.info(f"Next Friday expiration: {next_friday}")
        
        # Step 3: Get weekly option chain for next Friday expiration
        weekly_option_chain = _get_weekly_option_chain(symbol, next_friday)
        
        if not weekly_option_chain:
            logger.error(f"No weekly option chain available for {symbol} expiring {next_friday}")
            return None
        
        calls = weekly_option_chain['calls']
        puts = weekly_option_chain['puts']
        
        if calls.empty or puts.empty:
            logger.error(f"Empty weekly option chain for {symbol}")
            return None
        
        # Step 4: Extract and validate the 4 required options from full chain
        logger.info(f"Analyzing full option chain for {symbol} to extract required options")
        
        # Extract the 4 required options using the new automated approach
        required_options = _extract_required_options_from_chain(calls, puts, current_price, symbol)
        
        if not required_options:
            logger.error(f"Could not extract required options for {symbol} from option chain - skipping stock")
            return None
        
        atm_call = required_options['atm_call']
        atm_put = required_options['atm_put']
        itm_call = required_options['itm_call']
        itm_put = required_options['itm_put']
        
        # Log the selected strikes for verification
        logger.info(f"Selected strikes for {symbol}:")
        logger.info(f"  ATM Call/Put: ${atm_call['strike']}")
        logger.info(f"  ITM Call: ${itm_call['strike']} (below ATM)")
        logger.info(f"  ITM Put: ${itm_put['strike']} (above ATM)")
        
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
        # WEM Spread = WEM Points / (previous Friday's closing price)
        previous_friday_date = _find_previous_friday()
        previous_friday_close = _get_previous_friday_close_price(symbol, previous_friday_date)
        
        if previous_friday_close and previous_friday_close > 0:
            wem_spread = wem_points / previous_friday_close
            logger.info(f"WEM Spread calculation: ${wem_points:.2f} / ${previous_friday_close:.2f} = {wem_spread:.4f}")
        else:
            # Fallback to current price if previous Friday price not available
            wem_spread = wem_points / current_price
            logger.warning(f"Previous Friday close not available for {symbol}, using current price for WEM Spread")
        
        # Straddle 2 = Stock Price + WEM Points (upper expected range)
        straddle_2 = current_price + wem_points
        
        # Straddle 1 = Stock Price - WEM Points (lower expected range)  
        straddle_1 = current_price - wem_points
        
        # Delta Range = Delta 16 Positive - Delta 16 Negative
        delta_range = itm_put_strike - itm_call_strike
        
        # Delta Range % = Delta Range / Stock Price
        delta_range_pct = delta_range / current_price
        
        logger.info(f"Expected weekly range for {symbol}: ${straddle_1:.2f} - ${straddle_2:.2f}")
        logger.info(f"WEM Points: ${wem_points:.2f}")
        logger.info(f"Delta Range: ${delta_range:.2f} ({delta_range_pct:.2%})")
        
        # Step 8: Package results
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
            'delta_16_plus': float(itm_put_strike),  # Upper bound (ITM put strike)
            'delta_16_minus': float(itm_call_strike),  # Lower bound (ITM call strike)
            'delta_range': float(delta_range),
            'delta_range_pct': float(delta_range_pct),
            'straddle_2': float(straddle_2),  # Stock Price + WEM Points
            'straddle_1': float(straddle_1),  # Stock Price - WEM Points
            'meta_data': {
                'calculation_timestamp': datetime.utcnow().isoformat(),
                'calculation_method': 'automated_full_chain_analysis',
                'expiration_date': next_friday.isoformat(),
                'data_source': market_data.source,
                'atm_call_premium': float(atm_call_mid),
                'atm_put_premium': float(atm_put_mid),
                'itm_call_premium': float(itm_call_mid),
                'itm_put_premium': float(itm_put_mid),
                'calculated_wem_points': float(wem_points),
                'strikes_used': {
                    'atm': float(atm_strike),
                    'itm_call': float(itm_call_strike),
                    'itm_put': float(itm_put_strike)
                },
                'previous_friday_date': previous_friday_date.isoformat(),
                'previous_friday_close': float(previous_friday_close) if previous_friday_close else None,
                'option_selection_method': 'adjacent_strikes_from_full_chain',
                'formula_notes': {
                    'wem_points': '(Straddle + Strangle) / 2',
                    'wem_spread': 'WEM Points / Previous Friday Close Price',
                    'straddle_1': 'Stock Price - WEM Points',
                    'straddle_2': 'Stock Price + WEM Points',
                    'delta_range': 'Delta 16+ - Delta 16-',
                    'delta_range_pct': 'Delta Range / Stock Price',
                    'option_extraction': 'ATM closest to price, ITM adjacent strikes'
                }
            }
        }
        
        logger.info(f"Successfully calculated WEM Points for {symbol}: ${wem_points:.2f}")
        return result
        
    except Exception as e:
        logger.error(f"Error calculating WEM for {symbol}: {str(e)}", exc_info=True)
        return None


def _find_next_friday_expiration() -> datetime:
    """
    Find the next Friday for weekly options expiration.
    
    Weekly options typically expire on Fridays. This function finds the next 
    Friday from the current date.
    
    Returns:
        datetime: Next Friday's date
    """
    today = datetime.now().date()
    days_ahead = 4 - today.weekday()  # Friday is weekday 4 (Monday=0)
    
    if days_ahead <= 0:  # Today is Friday or weekend, get next Friday
        days_ahead += 7
    
    next_friday = today + timedelta(days=days_ahead)
    logger.debug(f"Next Friday expiration calculated: {next_friday}")
    
    return datetime.combine(next_friday, datetime.min.time())


def _find_previous_friday() -> datetime:
    """
    Find the previous Friday for WEM Spread calculation.
    
    WEM Spread uses the previous Friday's closing price as the denominator.
    This function finds the most recent Friday before today.
    
    Returns:
        datetime: Previous Friday's date
    """
    today = datetime.now().date()
    days_back = today.weekday() + 3  # Monday=0, so Friday would be 4 days back from Monday
    
    if today.weekday() == 4:  # If today is Friday
        days_back = 7  # Get last Friday
    elif today.weekday() < 4:  # Monday-Thursday
        days_back = today.weekday() + 3  # Days back to last Friday
    else:  # Weekend (Saturday=5, Sunday=6)
        days_back = today.weekday() - 4  # Days back to last Friday
    
    previous_friday = today - timedelta(days=days_back)
    logger.debug(f"Previous Friday calculated: {previous_friday}")
    
    return datetime.combine(previous_friday, datetime.min.time())


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
                        result[df_name] = pd.read_json(df_data, orient='records')
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


def _get_weekly_option_chain(symbol: str, expiration_date: datetime) -> Dict[str, pd.DataFrame]:
    """
    Get weekly option chain for a specific expiration date using MarketData.app.
    
    This function connects to the existing MarketDataManager to retrieve option chain
    data for the specified weekly expiration date.
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        expiration_date: Options expiration date (next Friday)
        
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
    logger.info(f"Getting weekly option chain for {symbol} expiring {expiration_date.date()}")
    
    try:
        # Check weekly cache first
        cache_key = f"weekly_option_chain:{symbol}:{expiration_date.strftime('%Y-%m-%d')}"
        cached_chain = _get_from_weekly_cache(cache_key)
        
        if cached_chain:
            logger.info(f"Retrieved {symbol} option chain from weekly cache")
            return cached_chain
        
        # Get market data manager
        manager = get_market_data_manager()
        if not manager:
            logger.error("No market data manager available")
            return None
        
        # Format expiration date for MarketData.app API (YYYY-MM-DD format)
        expiration_str = expiration_date.strftime('%Y-%m-%d')
        logger.info(f"Requesting option chain for {symbol} with expiration {expiration_str}")
        
        # Get option chain for specific expiration date
        chain = manager.get_option_chain(symbol, expiration_str)
        
        if not chain or not isinstance(chain, dict) or 'calls' not in chain or 'puts' not in chain:
            logger.error(f"Invalid option chain format received for {symbol}")
            return None
        
        calls_df = chain['calls']
        puts_df = chain['puts']
        
        if calls_df.empty and puts_df.empty:
            logger.warning(f"Empty option chain received for {symbol} on {expiration_str}")
            return None
        
        logger.info(f"Retrieved option chain for {symbol}: {len(calls_df)} calls, {len(puts_df)} puts")
        
        # Cache the result for weekly reuse
        _save_to_weekly_cache(cache_key, chain)
        
        return chain
        
    except Exception as e:
        logger.error(f"Error getting weekly option chain for {symbol}: {str(e)}", exc_info=True)
        return None


def _get_previous_friday_close_price(symbol: str, previous_friday_date: datetime) -> Optional[float]:
    """
    Get the closing price for a stock on the previous Friday using MarketData.app.
    
    This function connects to the existing MarketDataManager to retrieve historical
    price data for the previous Friday for WEM Spread calculation.
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        previous_friday_date: The previous Friday's date
        
    Returns:
        float: Closing price on previous Friday, or None if not available
    """
    logger.info(f"Getting previous Friday close price for {symbol} on {previous_friday_date.date()}")
    
    try:
        # Check weekly cache first
        cache_key = f"friday_close:{symbol}:{previous_friday_date.strftime('%Y-%m-%d')}"
        cached_price = _get_from_weekly_cache(cache_key)
        
        if cached_price:
            logger.info(f"Retrieved {symbol} Friday close from weekly cache: ${cached_price:.2f}")
            return cached_price
        
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
        
        # Cache the result for weekly reuse
        _save_to_weekly_cache(cache_key, friday_close)
        
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

def create_wem_table(stocks, layout="horizontal", metrics=None, sig_figs=4):
    """
    Creates an interactive table for displaying WEM data.
    
    Args:
        stocks: List of stock dictionaries with WEM data
        layout: 'horizontal' or 'vertical' layout
        metrics: List of metrics to display
        sig_figs: Number of significant figures to display
        
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
    
    # Parse the last_updated field if it exists and is a string
    if 'last_updated' in df.columns and df['last_updated'].dtype == 'object':
        df['last_updated'] = pd.to_datetime(df['last_updated'])
        df['last_updated'] = df['last_updated'].dt.strftime('%Y-%m-%d %H:%M')
    
    # Format numeric columns with specified significant figures
    numeric_cols = df.select_dtypes(include=['float', 'int']).columns
    for col in numeric_cols:
        if col in ['wem_spread', 'delta_range_pct']:
            # Format percentage values with percent sign
            df[col] = df[col].apply(lambda x: f"{x*100:.{sig_figs-2}f}%" if pd.notnull(x) else x)
        else:
            df[col] = df[col].apply(lambda x: round(x, sig_figs-1) if pd.notnull(x) else x)
    
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
    
    # Default metrics using WEM Points terminology
    default_metrics = [
        'symbol', 'atm_price', 'wem_points', 'straddle_strangle', 'wem_spread',
        'delta_16_plus', 'straddle_2', 'straddle_1', 'delta_16_minus',
        'delta_range', 'delta_range_pct', 'last_updated'
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
    
    # Dictionary to map column names to prettier display names
    column_display_names = {
        'symbol': 'Symbol',
        'atm_price': 'ATM Price',
        'wem_points': 'WEM Points',
        'straddle': 'Straddle',
        'strangle': 'Strangle',
        'straddle_strangle': 'Straddle/Strangle',
        'wem_spread': 'WEM Spread %',
        'delta_16_plus': 'Delta 16+',
        'straddle_2': 'Straddle 2',
        'straddle_1': 'Straddle 1',
        'delta_16_minus': 'Delta 16-',
        'delta_range': 'Delta Range',
        'delta_range_pct': 'Delta Range %',
        'last_updated': 'Last Updated'
    }
    
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
        
        # Filter rows that match our valid metrics
        df = df.loc[valid_metrics]
        
        # Rename index with pretty names
        df.index = [column_display_names.get(idx, idx.replace('_', ' ').title()) for idx in df.index]
        
        # Configure columns - each stock symbol is a column
        stock_symbols = original_df['symbol'].tolist()
        for symbol in stock_symbols:
            columns.append({
                "field": symbol,
                "headerName": symbol,
                "width": 120
            })
    else:  # vertical layout
        # Configure columns - each metric is a column with proper formatting
        for metric in metrics:
            display_name = column_display_names.get(metric, metric.replace('_', ' ').title())
            column_width = 150 if metric in ['symbol', 'last_updated'] else 120
            
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

def update_all_wem_stocks(session: Session) -> bool:
    """
    Update all WEM stocks with fresh data.
    
    Args:
        session: Database session
        
    Returns:
        bool: Success or failure
    """
    logger.info("Starting update of all WEM stocks")
    success_count = 0
    error_count = 0
    
    # Get all stocks to update
    stocks = session.query(WEMStock).all()
    
    if not stocks:
        logger.warning("No WEM stocks found to update")
        return False
    
    logger.info(f"Found {len(stocks)} WEM stocks to update")
    
    # Update each stock
    for stock in stocks:
        logger.info(f"Calculating WEM for {stock.symbol}")
        try:
            # Calculate new values
            new_data = calculate_expected_move(session, {'symbol': stock.symbol})
            
            if new_data:
                # Update stock data
                update_data = {
                    'symbol': stock.symbol,
                    **new_data
                }
                if update_wem_stock(session, update_data):
                    logger.info(f"Successfully updated {stock.symbol}")
                    success_count += 1
                else:
                    logger.error(f"Failed to update {stock.symbol}")
                    error_count += 1
            else:
                logger.warning(f"No market data available for {stock.symbol}")
                error_count += 1
            
        except Exception as e:
            error_msg = f"Error calculating WEM for {stock.symbol}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            error_count += 1
    
    logger.info(f"WEM update completed: {success_count} succeeded, {error_count} failed")
    return success_count > 0

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

def main():
    """Main function for the WEM application"""
    setup_logging()
    
    # App title and description
    st.title("📊 Weekly Expected Moves (WEM)")
    st.subheader("Options-derived expected price ranges for the upcoming week")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("WEM Configuration")
        
        # Add a button to update WEM data
        if st.button("Update WEM Data", help="Fetch latest options data and calculate WEM"):
            logger.info("Updating WEM data...")
            with st.spinner("Updating WEM data..."):
                try:
                    # Use the database session within a context manager
                    with get_db_connection() as db_session:
                        update_all_wem_stocks(db_session)
                    
                    st.success("WEM data updated successfully!")
                    # Rerun the app to show updated data
                    time.sleep(1)  # Small delay to ensure UI updates
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update WEM data: {str(e)}")
                    logger.exception("WEM update error")
        
        # Add stock section
        st.subheader("Add New Stock")
        with st.form("add_stock_form"):
            new_symbol = st.text_input("Stock Symbol", key="new_stock_symbol")
            is_default = st.checkbox("Add as Default Stock", key="new_stock_default")
            
            submit_button = st.form_submit_button("Add Stock")
            
            if submit_button and new_symbol:
                try:
                    symbol = new_symbol.strip().upper()
                    with get_db_connection() as db_session:
                        # Check if stock already exists
                        existing = db_session.query(WEMStock).filter_by(symbol=symbol).first()
                        if existing:
                            st.warning(f"Stock {symbol} already exists. Not adding.")
                        else:
                            add_wem_stock(db_session, symbol, is_default)
                            st.success(f"Added {symbol} to WEM stocks")
                            # Calculate WEM values for the new stock
                            with st.spinner(f"Calculating WEM for {symbol}..."):
                                new_data = calculate_expected_move(db_session, {'symbol': symbol})
                                if new_data:
                                    update_data = {'symbol': symbol, **new_data}
                                    update_wem_stock(db_session, update_data)
                                    st.success(f"WEM data calculated for {symbol}")
                    
                    # Rerun to show the new stock
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error adding stock: {str(e)}")
                    logger.exception(f"Error adding stock {new_symbol}")
        
        # Date range for data display
        st.subheader("Data Filtering")
        date_range = st.date_input(
            "Date Range",
            value=(datetime.now() - timedelta(days=7), datetime.now()),
            help="Filter stocks by last updated date"
        )
        
        # Symbol filter
        symbol_filter = st.text_input(
            "Symbol Filter", 
            value="",
            help="Enter stock symbols separated by commas (e.g., AAPL,MSFT,GOOG)"
        )
        
        symbols = [s.strip().upper() for s in symbol_filter.split(',')] if symbol_filter else []
        
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
        
        layout = st.radio(
            "Table Layout",
            options=["horizontal", "vertical"],
            index=0,  # Default to horizontal
            help="Horizontal shows stocks as columns, vertical as rows"
        )
        
        # Available metrics for display
        all_metrics = [
            'symbol', 'atm_price', 'wem_points', 'wem_spread',
            'delta_16_plus', 'straddle_2', 'straddle_1', 'delta_16_minus',
            'delta_range', 'delta_range_pct', 'straddle', 'strangle', 'straddle_strangle', 'last_updated'
        ]
        
        # For horizontal layout, filter out 'symbol' from selectable metrics
        # as it becomes the column headers
        display_metrics = all_metrics if layout == 'vertical' else [m for m in all_metrics if m != 'symbol']
        
        # Default selected metrics using WEM Points
        default_metrics = [
            'atm_price', 'wem_points', 'wem_spread', 
            'delta_16_plus', 'straddle_2', 'straddle_1', 'delta_16_minus',
            'delta_range', 'delta_range_pct', 'last_updated'
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
        export_format = st.selectbox(
            "Export Format",
            options=["CSV", "Excel"],
            index=0,
            help="Select export format"
        )
        
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
            
            if not wem_stocks:
                st.warning("No WEM data found. Please update the data first.")
            else:
                # Convert to list of dictionaries
                stocks_data = wem_stocks  # Already a list of dictionaries
                
                # Create WEM table
                wem_df = create_wem_table(stocks_data, layout=layout, metrics=selected_metrics, sig_figs=sig_figs)
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        logger.exception("Error getting WEM data")
        wem_df = None
    
    if st.button("Export Data") and wem_df is not None:
        with st.spinner("Preparing export..."):
            try:
                # Get the current timestamp for the filename
                timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M")
                
                if export_format == "CSV":
                    # Export to CSV
                    csv_path = f"./data/exports/{timestamp}_export.csv"
                    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                    
                    wem_df['df'].to_csv(csv_path)
                    st.success(f"Data exported to {csv_path}")
                    
                else:  # Excel
                    # Export to Excel
                    excel_path = f"./data/exports/{timestamp}_export.xlsx"
                    os.makedirs(os.path.dirname(excel_path), exist_ok=True)
                    
                    with pd.ExcelWriter(excel_path) as writer:
                        # Write WEM data
                        wem_df['df'].to_excel(writer, sheet_name='WEM Data')
                        
                        # Write notes to second sheet
                        notes_df = pd.DataFrame({
                            "Note": ["Generated by Goldflipper WEM Module", 
                                     f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                     f"Symbols: {', '.join(symbols) if symbols else 'All'}"]
                        })
                        notes_df.to_excel(writer, sheet_name='Notes', index=False)
                    
                    st.success(f"Data exported to {excel_path}")
            except Exception as e:
                st.error(f"Export failed: {str(e)}")
                logger.exception("Export error")

    # Display the table if data is available
    if 'wem_df' in locals() and wem_df is not None:
        # Display the table
        with st.container():
            st.subheader("Weekly Expected Moves")
            
            if layout == "horizontal":
                # Filter only the rows that exist in the transposed dataframe
                valid_metrics = [metric for metric in selected_metrics if metric in wem_df['df'].index]
                
                # Apply the filter if we have valid metrics
                if valid_metrics:
                    filtered_df = wem_df['df'].loc[valid_metrics]
                    wem_df['df'] = filtered_df
                else:
                    logger.warning("No valid metrics to display in horizontal mode")
            
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
            
            # Style the dataframe
            st.dataframe(
                wem_df['df'],
                use_container_width=True,
                hide_index=False,  # Show index for horizontal layout
                height=800,  # Add height parameter to allow table to expand vertically
                column_config={
                    col["field"]: (
                        st.column_config.NumberColumn(
                            col["headerName"],
                            width=col["width"],
                            format=col["format"]
                        ) if col.get("type") == "number" else
                        st.column_config.Column(
                            col["headerName"],
                            width=col["width"]
                        )
                    ) for col in wem_df['columns']
                }
            )

if __name__ == "__main__":
    main() 