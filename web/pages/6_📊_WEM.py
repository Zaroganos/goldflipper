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
    Calculate the expected move for a stock based on real options data.
    
    Args:
        session: Database session
        stock_data: Dictionary with stock symbol
        
    Returns:
        dict: Dictionary with calculated WEM values
    """
    symbol = stock_data.get('symbol')
    if not symbol:
        logger.error("No symbol provided for WEM calculation")
        return None
            
    logger.info(f"Calculating expected move for {symbol}")
    
    try:
        # First try to get latest data from database
        logger.debug(f"Attempting to get latest market data for {symbol}")
        market_data = get_latest_market_data(session, symbol)
        
        # If no recent data or data is old, update it
        if not market_data or (datetime.utcnow() - market_data.timestamp).total_seconds() > 300:  # 5 minutes
            logger.info(f"Market data for {symbol} is old or missing, updating...")
            market_data = update_market_data(session, symbol)
        
        if not market_data:
            logger.error(f"No market data available for {symbol}")
            return None
        
        # Get current price
        atm_price = market_data.close
        logger.info(f"Current price for {symbol}: ${atm_price:.2f}")
        
        # Get option chain from market data provider
        manager = get_market_data_manager()
        if not manager:
            logger.error(f"No market data manager available for {symbol}")
            return None
        
        logger.info(f"Fetching option chain for {symbol}")
        chain = manager.get_option_chain(symbol)
        
        if not chain or not isinstance(chain, dict) or 'calls' not in chain or 'puts' not in chain:
            logger.error(f"Invalid option chain data for {symbol}")
            return None
        
        calls = chain['calls']
        puts = chain['puts']
        
        if calls.empty or puts.empty:
            logger.error(f"Empty option chain data for {symbol}")
            return None
            
        # Find ATM options (closest strike to current price)
        logger.debug(f"Finding ATM options at price {atm_price}")
        
        # Get closest strike to current price
        all_strikes = sorted(set(calls['strike'].tolist() + puts['strike'].tolist()))
        atm_strike = min(all_strikes, key=lambda x: abs(float(x) - atm_price))
        logger.info(f"Selected ATM strike: {atm_strike}")
        
        # Get ATM call and put
        atm_calls = calls[calls['strike'] == atm_strike]
        atm_puts = puts[puts['strike'] == atm_strike]
        
        if atm_calls.empty or atm_puts.empty:
            logger.error(f"No ATM options found for {symbol} at strike {atm_strike}")
            return None
        
        atm_call = atm_calls.iloc[0]
        atm_put = atm_puts.iloc[0]
        
        # Calculate ATM straddle mid price
        atm_call_mid = (float(atm_call['bid']) + float(atm_call['ask'])) / 2
        atm_put_mid = (float(atm_put['bid']) + float(atm_put['ask'])) / 2
        straddle_level = atm_call_mid + atm_put_mid
        
        # Find OTM options at approximately 16 delta
        logger.debug(f"Finding OTM options at ~16 delta")
        
        # Get OTM calls (higher strikes)
        otm_calls = calls[calls['strike'] > atm_strike].copy()
        if not otm_calls.empty and 'delta' in otm_calls.columns:
            # Convert to numeric and handle NaN
            otm_calls['delta'] = pd.to_numeric(otm_calls['delta'], errors='coerce')
            # Calculate distance from target delta
            otm_calls['delta_diff'] = (otm_calls['delta'] - 0.16).abs()
            # Get closest to 16 delta
            otm_call = otm_calls.nsmallest(1, 'delta_diff').iloc[0]
        else:
            # Fallback: use first OTM call
            otm_call = calls[calls['strike'] > atm_strike].iloc[0] if not calls[calls['strike'] > atm_strike].empty else None
            
        # Get OTM puts (lower strikes)
        otm_puts = puts[puts['strike'] < atm_strike].copy()
        if not otm_puts.empty and 'delta' in otm_puts.columns:
            # For puts, delta is negative, so we need absolute value
            otm_puts['delta'] = pd.to_numeric(otm_puts['delta'], errors='coerce')
            # Delta closer to -0.16
            otm_puts['delta_diff'] = (otm_puts['delta'] + 0.16).abs()  # Add because put deltas are negative
            # Get closest to -16 delta
            otm_put = otm_puts.nsmallest(1, 'delta_diff').iloc[0]
        else:
            # Fallback: use first OTM put
            otm_put = puts[puts['strike'] < atm_strike].iloc[0] if not puts[puts['strike'] < atm_strike].empty else None
            
        if otm_call is None or otm_put is None:
            logger.error(f"Could not find suitable OTM options for {symbol}")
            return None
                
        # Calculate OTM strangle mid price
        otm_call_mid = (float(otm_call['bid']) + float(otm_call['ask'])) / 2
        otm_put_mid = (float(otm_put['bid']) + float(otm_put['ask'])) / 2
        strangle_level = otm_call_mid + otm_put_mid
        
        # Calculate straddle/strangle combined value
        straddle_strangle = (straddle_level + strangle_level) / 2
        
        # Calculate WEM as half of straddle/strangle
        wem = straddle_strangle / 2
        
        # Calculate WEM spread as percentage of price
        wem_spread = wem / atm_price
        
        # Calculate price levels
        delta_16_plus = float(otm_call['strike'])
        delta_16_minus = float(otm_put['strike'])
        delta_range = delta_16_plus - delta_16_minus
        delta_range_pct = delta_range / atm_price
        
        # Log calculated values for debugging
        logger.debug(f"{symbol} ATM price: ${atm_price:.2f}")
        logger.debug(f"{symbol} ATM Call Mid: ${atm_call_mid:.2f}")
        logger.debug(f"{symbol} ATM Put Mid: ${atm_put_mid:.2f}")
        logger.debug(f"{symbol} Straddle level: ${straddle_level:.2f}")
        logger.debug(f"{symbol} OTM Call Mid: ${otm_call_mid:.2f}")
        logger.debug(f"{symbol} OTM Put Mid: ${otm_put_mid:.2f}")
        logger.debug(f"{symbol} Strangle level: ${strangle_level:.2f}")
        logger.debug(f"{symbol} Combined Straddle/Strangle: ${straddle_strangle:.2f}")
        logger.debug(f"{symbol} WEM: ${wem:.2f}")
        logger.debug(f"{symbol} WEM spread: {wem_spread:.4f}")
        logger.debug(f"{symbol} Expected range: ${atm_price-wem:.2f} to ${atm_price+wem:.2f}")
        
        # Return the calculated values with real market data
        result = {
            'atm_price': float(atm_price),
            'straddle_strangle': float(straddle_strangle),
            'straddle': float(straddle_level),
            'strangle': float(strangle_level),
            'wem': float(wem),
            'wem_spread': float(wem_spread),
            'delta_16_plus': float(delta_16_plus),
            'straddle_2': float(straddle_level),
            'straddle_1': float(strangle_level),
            'delta_16_minus': float(delta_16_minus),
            'delta_range': float(delta_range),
            'delta_range_pct': float(delta_range_pct),
            'meta_data': {
                'calculation_timestamp': datetime.utcnow().isoformat(),
                'calculation_method': 'market_data',
                'data_source': market_data.source,
                'atm_call_mid': float(atm_call_mid),
                'atm_put_mid': float(atm_put_mid),
                'otm_call_mid': float(otm_call_mid),
                'otm_put_mid': float(otm_put_mid),
                'atm_strike': float(atm_strike),
                'otm_call_strike': float(otm_call['strike']),
                'otm_put_strike': float(otm_put['strike']),
                'atm_call_delta': float(atm_call['delta']) if 'delta' in atm_call else None,
                'atm_put_delta': float(atm_put['delta']) if 'delta' in atm_put else None,
                'otm_call_delta': float(otm_call['delta']) if 'delta' in otm_call else None,
                'otm_put_delta': float(otm_put['delta']) if 'delta' in otm_put else None,
                'calculated_wem': float(wem)
            }
        }
        
        logger.info(f"Successfully calculated expected move for {symbol} using real market data")
        return result
    except Exception as e:
        logger.error(f"Error calculating expected move for {symbol}: {str(e)}", exc_info=True)
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
    
    # Ensure there's a WEM value for each stock - calculate if missing
    if 'straddle_strangle' in df.columns:
        for index, row in df.iterrows():
            symbol = row.get('symbol', 'UNKNOWN')
            if pd.isna(row.get('wem')) and not pd.isna(row.get('straddle_strangle')):
                # Calculate WEM as half of straddle_strangle
                calculated_wem = row['straddle_strangle'] / 2
                df.at[index, 'wem'] = calculated_wem
                logger.info(f"Calculated WEM for {symbol}: {calculated_wem}")
    
    # Default metrics if none provided
    default_metrics = [
        'symbol', 'atm_price', 'wem', 'straddle_strangle', 'wem_spread',
        'delta_16_plus', 'straddle_2', 'straddle_1', 'delta_16_minus',
        'delta_range', 'delta_range_pct', 'last_updated'
    ]
    
    metrics = metrics or default_metrics
    
    # Make sure we have the symbol column
    if 'symbol' not in metrics:
        metrics.insert(0, 'symbol')
    
    # Filter columns
    df = df[metrics]
    
    # Dictionary to map column names to prettier display names
    column_display_names = {
        'symbol': 'Symbol',
        'atm_price': 'ATM Price',
        'wem': 'WEM',
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
            elif metric in ['wem', 'straddle', 'strangle', 'straddle_strangle', 'delta_range', 'straddle_1', 'straddle_2', 'delta_16_plus', 'delta_16_minus']:
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
            'symbol', 'atm_price', 'wem', 'wem_spread',
            'delta_16_plus', 'straddle_2', 'straddle_1', 'delta_16_minus',
            'delta_range', 'delta_range_pct', 'straddle', 'strangle', 'straddle_strangle', 'last_updated'
        ]
        
        # For horizontal layout, filter out 'symbol' from selectable metrics
        # as it becomes the column headers
        display_metrics = all_metrics if layout == 'vertical' else [m for m in all_metrics if m != 'symbol']
        
        # Default selected metrics - all except straddle_strangle in the order from the image
        default_metrics = [
            'atm_price', 'wem', 'wem_spread', 
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