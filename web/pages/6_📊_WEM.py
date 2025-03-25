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
    page_title="GoldFlipper WEM",
    page_icon="📊",
    layout="wide"
)

# Initialize market data manager
@st.cache_resource
def get_market_data_manager():
    """Get or create the singleton MarketDataManager instance"""
    return MarketDataManager()

def get_wem_stocks(session: Session) -> List[Dict[str, Any]]:
    """Get all WEM stocks from database as dictionaries"""
    stocks = session.query(WEMStock).all()
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
        repo = MarketDataRepository(session)
        
        # Get live price from market data provider
        price = manager.get_stock_price(symbol)
        if price is None:
            st.warning(f"Could not get current price for {symbol}")
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
            option_data = manager.get_option_quote(f"{symbol}0")  # Use a dummy option to get implied vol
            if option_data:
                market_data.implied_volatility = option_data.get('implied_volatility', 0.0)
                market_data.delta = option_data.get('delta', 0.0)
                market_data.gamma = option_data.get('gamma', 0.0)
                market_data.theta = option_data.get('theta', 0.0)
                market_data.vega = option_data.get('vega', 0.0)
        except Exception as e:
            st.warning(f"Could not get options data for {symbol}: {str(e)}")
            # Continue without options data
        
        # Save to database
        session.add(market_data)
        session.commit()
        
        return market_data
        
    except Exception as e:
        st.error(f"Error updating market data for {symbol}: {str(e)}")
        session.rollback()
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
    """Update WEM stock data"""
    try:
        stock = session.query(WEMStock).filter_by(symbol=stock_data['symbol']).first()
        if not stock:
            return False
            
        # Update stock attributes
        for key, value in stock_data.items():
            if hasattr(stock, key):
                setattr(stock, key, value)
        
        session.commit()
        return True
    except Exception as e:
        st.error(f"Error updating stock data: {str(e)}")
        session.rollback()
        return False

def calculate_expected_move(session: Session, stock_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate expected move for a stock using actual market data.
    
    Formulas:
    - Delta Negative/Positive: (0.1570 - 0.1690)
    - Straddle Level = 1 ATM CALL + 1 ATM PUT (at identical strike)
    - Strangle Level = 1 OTM CALL + 1 OTM PUT
    - WEM = (Straddle + Strangle)/2
    - WEM Spread = Stock Price / Straddle/Strangle Level
    - Straddle 2 = Stock Price + WEM
    - Straddle 1 = Stock Price - WEM
    - Delta Range = Delta 16 Positive - Delta 16 Negative
    - Delta Range % = Delta range / stock price
    """
    symbol = stock_data['symbol']
    logger.info(f"Starting WEM calculation for {symbol}")
    
    try:
        # First try to get latest data from database
        logger.debug(f"Attempting to get latest market data for {symbol}")
        market_data = get_latest_market_data(session, symbol)
        
        # If no recent data or data is old, update it
        if not market_data or (datetime.utcnow() - market_data.timestamp).total_seconds() > 300:  # 5 minutes
            logger.info(f"Market data for {symbol} is old or missing, updating...")
            market_data = update_market_data(session, symbol)
        
        if not market_data:
            error_msg = f"No market data available for {symbol}"
            logger.error(error_msg)
            st.error(error_msg)
            return None
        
        # Get current price
        atm_price = market_data.close
        logger.info(f"Current price for {symbol}: ${atm_price:.2f}")
        
        # Get option data from market data provider
        logger.debug(f"Getting market data manager for {symbol}")
        manager = get_market_data_manager()
        
        # Get option chain for the symbol
        logger.info(f"Fetching option chain for {symbol}")
        try:
            chain = manager.get_option_chain(symbol)
            logger.debug(f"Option chain response received for {symbol}")
            
            # Log the chain data structure
            logger.debug(f"Chain data structure: {type(chain)}")
            if isinstance(chain, dict):
                logger.debug(f"Chain keys: {chain.keys()}")
                if 'calls' in chain:
                    logger.debug(f"Calls DataFrame columns: {chain['calls'].columns}")
                    logger.debug(f"Calls DataFrame shape: {chain['calls'].shape}")
                    logger.debug(f"Calls DataFrame head:\n{chain['calls'].head()}")
                if 'puts' in chain:
                    logger.debug(f"Puts DataFrame columns: {chain['puts'].columns}")
                    logger.debug(f"Puts DataFrame shape: {chain['puts'].shape}")
                    logger.debug(f"Puts DataFrame head:\n{chain['puts'].head()}")
            
        except Exception as e:
            error_msg = f"Error fetching option chain for {symbol}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            st.error(error_msg)
            return None
        
        if not chain:
            error_msg = f"Failed to get option chain data for {symbol}"
            logger.error(error_msg)
            st.error(error_msg)
            return None
            
        if not isinstance(chain, dict) or 'calls' not in chain or 'puts' not in chain:
            error_msg = f"Invalid option chain format for {symbol}"
            logger.error(error_msg)
            logger.debug(f"Chain data: {chain}")
            st.error(error_msg)
            return None
            
        if chain['calls'].empty or chain['puts'].empty:
            error_msg = f"Empty option chain data for {symbol}"
            logger.error(error_msg)
            logger.debug(f"Calls DataFrame: {chain['calls'].head() if not chain['calls'].empty else 'Empty'}")
            logger.debug(f"Puts DataFrame: {chain['puts'].head() if not chain['puts'].empty else 'Empty'}")
            st.error(error_msg)
            return None
            
        # Find ATM options (closest strike to current price)
        calls = chain['calls']
        puts = chain['puts']
        
        # Log available columns
        logger.debug(f"Calls columns: {calls.columns}")
        logger.debug(f"Puts columns: {puts.columns}")
        
        # Verify required columns exist
        required_columns = ['strike', 'bid', 'ask', 'delta']
        missing_columns = []
        for col in required_columns:
            if col not in calls.columns:
                missing_columns.append(f"calls.{col}")
            if col not in puts.columns:
                missing_columns.append(f"puts.{col}")
        
        if missing_columns:
            error_msg = f"Missing required columns for {symbol}: {', '.join(missing_columns)}"
            logger.error(error_msg)
            st.error(error_msg)
            return None
        
        # Get ATM straddle (CALL + PUT at same strike)
        atm_strike = round(atm_price)
        logger.info(f"Looking for ATM options at strike {atm_strike}")
        
        # Log available strikes
        logger.debug(f"Available call strikes: {sorted(calls['strike'].unique())}")
        logger.debug(f"Available put strikes: {sorted(puts['strike'].unique())}")
        logger.debug(f"Looking for ATM strike: {atm_strike}")
        
        try:
            # Fix the pandas Series boolean comparison
            atm_call_mask = calls['strike'] == atm_strike
            atm_put_mask = puts['strike'] == atm_strike
            
            # Log the masks
            logger.debug(f"ATM call mask: {atm_call_mask}")
            logger.debug(f"ATM put mask: {atm_put_mask}")
            
            atm_calls = calls[atm_call_mask]
            atm_puts = puts[atm_put_mask]
            
            if atm_calls.empty:
                error_msg = f"No ATM calls found for {symbol} at strike {atm_strike}"
                logger.error(error_msg)
                logger.debug(f"Available call strikes: {sorted(calls['strike'].unique())}")
                st.error(error_msg)
                return None
                
            if atm_puts.empty:
                error_msg = f"No ATM puts found for {symbol} at strike {atm_strike}"
                logger.error(error_msg)
                logger.debug(f"Available put strikes: {sorted(puts['strike'].unique())}")
                st.error(error_msg)
                return None
            
            atm_call = atm_calls.iloc[0]
            atm_put = atm_puts.iloc[0]
            
        except Exception as e:
            error_msg = f"Error finding ATM options for {symbol}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            logger.debug(f"Calls DataFrame:\n{calls.head()}")
            logger.debug(f"Puts DataFrame:\n{puts.head()}")
            st.error(error_msg)
            return None
        
        # Get OTM strangle (CALL + PUT at ~16 delta)
        logger.debug(f"Finding OTM options for {symbol}")
        try:
            # Log the data before filtering
            logger.debug(f"Original calls DataFrame:\n{calls.head()}")
            logger.debug(f"Original puts DataFrame:\n{puts.head()}")
            logger.debug(f"ATM strike: {atm_strike}")
            
            # Convert strike to float to avoid type issues
            atm_strike = float(atm_strike)
            
            # Create masks for OTM options
            try:
                otm_calls_mask = calls['strike'].astype(float) > atm_strike
                otm_puts_mask = puts['strike'].astype(float) < atm_strike
                
                # Log the masks
                logger.debug(f"OTM calls mask:\n{otm_calls_mask}")
                logger.debug(f"OTM puts mask:\n{otm_puts_mask}")
                
                # Apply masks to get OTM options
                otm_calls = calls[otm_calls_mask].copy()
                otm_puts = puts[otm_puts_mask].copy()
                
                # Log the filtered data
                logger.debug(f"OTM calls DataFrame:\n{otm_calls.head()}")
                logger.debug(f"OTM puts DataFrame:\n{otm_puts.head()}")
                
            except Exception as e:
                error_msg = f"Error creating OTM masks for {symbol}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                logger.debug(f"Calls DataFrame dtypes: {calls.dtypes}")
                logger.debug(f"Puts DataFrame dtypes: {puts.dtypes}")
                logger.debug(f"Strike column sample - Calls: {calls['strike'].head()}")
                logger.debug(f"Strike column sample - Puts: {puts['strike'].head()}")
                st.error(error_msg)
                return None
            
            if otm_calls.empty or otm_puts.empty:
                error_msg = f"Could not find OTM options for {symbol}"
                logger.error(error_msg)
                logger.debug(f"OTM calls available: {len(otm_calls)}")
                logger.debug(f"OTM puts available: {len(otm_puts)}")
                logger.debug(f"Available call strikes: {sorted(calls['strike'].unique())}")
                logger.debug(f"Available put strikes: {sorted(puts['strike'].unique())}")
                st.error(error_msg)
                return None
            
            # Calculate absolute difference from target delta
            logger.debug(f"Calculating delta differences for {symbol}")
            try:
                # Convert delta to float and handle any potential NaN values
                otm_calls['delta'] = pd.to_numeric(otm_calls['delta'], errors='coerce')
                otm_puts['delta'] = pd.to_numeric(otm_puts['delta'], errors='coerce')
                
                # Log delta values before calculation
                logger.debug(f"OTM calls delta values:\n{otm_calls['delta'].head()}")
                logger.debug(f"OTM puts delta values:\n{otm_puts['delta'].head()}")
                
                # Calculate delta differences
                otm_calls['delta_diff'] = abs(otm_calls['delta'] - 0.16)
                otm_puts['delta_diff'] = abs(otm_puts['delta'] + 0.16)  # Note the + because put deltas are negative
                
                # Log the calculated differences
                logger.debug(f"OTM calls delta differences:\n{otm_calls['delta_diff'].head()}")
                logger.debug(f"OTM puts delta differences:\n{otm_puts['delta_diff'].head()}")
                
            except Exception as e:
                error_msg = f"Error calculating delta differences for {symbol}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                logger.debug(f"OTM calls delta values: {otm_calls['delta'].unique()}")
                logger.debug(f"OTM puts delta values: {otm_puts['delta'].unique()}")
                st.error(error_msg)
                return None
            
            # Get the options closest to 16 delta
            try:
                # Sort by delta difference and get the closest
                otm_call = otm_calls.nsmallest(1, 'delta_diff').iloc[0] if not otm_calls.empty else None
                otm_put = otm_puts.nsmallest(1, 'delta_diff').iloc[0] if not otm_puts.empty else None
                
                # Log the selected options
                if otm_call is not None:
                    logger.debug(f"Selected OTM call: Strike={otm_call['strike']}, Delta={otm_call['delta']:.3f}, Delta Diff={otm_call['delta_diff']:.3f}")
                if otm_put is not None:
                    logger.debug(f"Selected OTM put: Strike={otm_put['strike']}, Delta={otm_put['delta']:.3f}, Delta Diff={otm_put['delta_diff']:.3f}")
                
            except Exception as e:
                error_msg = f"Error finding closest delta options for {symbol}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                logger.debug(f"OTM calls DataFrame:\n{otm_calls.head()}")
                logger.debug(f"OTM puts DataFrame:\n{otm_puts.head()}")
                st.error(error_msg)
                return None
            
            if not otm_call or not otm_put:
                error_msg = f"Could not find options close to 16 delta for {symbol}"
                logger.error(error_msg)
                logger.debug(f"Available deltas for calls: {otm_calls['delta'].unique()}")
                logger.debug(f"Available deltas for puts: {otm_puts['delta'].unique()}")
                st.error(error_msg)
                return None
            
        except Exception as e:
            error_msg = f"Error processing OTM options for {symbol}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            logger.debug(f"Calls DataFrame:\n{calls.head()}")
            logger.debug(f"Puts DataFrame:\n{puts.head()}")
            st.error(error_msg)
            return None
        
        # Debug logging
        logger.info(f"\nDebug - {symbol} Data:")
        logger.info(f"ATM Price: {atm_price}")
        logger.info(f"ATM Strike: {atm_strike}")
        logger.info(f"ATM Call: Strike={atm_call['strike']}, Mid={(float(atm_call['bid']) + float(atm_call['ask']))/2:.2f}, Delta={atm_call['delta']:.3f}")
        logger.info(f"ATM Put: Strike={atm_put['strike']}, Mid={(float(atm_put['bid']) + float(atm_put['ask']))/2:.2f}, Delta={atm_put['delta']:.3f}")
        logger.info(f"OTM Call: Strike={otm_call['strike']}, Mid={(float(otm_call['bid']) + float(otm_call['ask']))/2:.2f}, Delta={otm_call['delta']:.3f}")
        logger.info(f"OTM Put: Strike={otm_put['strike']}, Mid={(float(otm_put['bid']) + float(otm_put['ask']))/2:.2f}, Delta={otm_put['delta']:.3f}")
        
        # Calculate straddle and strangle levels using mid prices
        logger.debug(f"Calculating straddle and strangle levels for {symbol}")
        try:
            atm_call_mid = (float(atm_call['bid']) + float(atm_call['ask'])) / 2
            atm_put_mid = (float(atm_put['bid']) + float(atm_put['ask'])) / 2
            straddle_level = atm_call_mid + atm_put_mid

            otm_call_mid = (float(otm_call['bid']) + float(otm_call['ask'])) / 2
            otm_put_mid = (float(otm_put['bid']) + float(otm_put['ask'])) / 2
            strangle_level = otm_call_mid + otm_put_mid
            
            # Calculate WEM as average of straddle and strangle
            wem = (straddle_level + strangle_level) / 2
            
            # Calculate WEM spread as percentage
            wem_spread = (wem / atm_price) * 100
            
            # Calculate delta-based moves (16 delta levels)
            delta_16_plus = atm_price * (1 + 0.1690)  # Using 0.1690 for positive delta
            delta_16_minus = atm_price * (1 - 0.1570)  # Using 0.1570 for negative delta
            
            # Calculate straddle levels
            straddle_2 = atm_price + wem
            straddle_1 = atm_price - wem
            
            # Calculate range values
            delta_range = delta_16_plus - delta_16_minus
            delta_range_pct = (delta_range / atm_price) * 100
            
        except Exception as e:
            error_msg = f"Error calculating WEM values for {symbol}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            st.error(error_msg)
            return None
        
        # Debug logging
        logger.info(f"\nCalculated Values:")
        logger.info(f"ATM Straddle Components:")
        logger.info(f"  - ATM Call Mid: ${atm_call_mid:.2f}")
        logger.info(f"  - ATM Put Mid: ${atm_put_mid:.2f}")
        logger.info(f"  = Straddle Level: ${straddle_level:.2f}")
        
        logger.info(f"\nOTM Strangle Components:")
        logger.info(f"  - OTM Call Mid: ${otm_call_mid:.2f}")
        logger.info(f"  - OTM Put Mid: ${otm_put_mid:.2f}")
        logger.info(f"  = Strangle Level: ${strangle_level:.2f}")
        
        logger.info(f"\nFinal Calculations:")
        logger.info(f"WEM = (Straddle + Strangle)/2 = ${wem:.2f}")
        logger.info(f"WEM Spread = (WEM/Price)*100 = {wem_spread:.2f}%")
        logger.info(f"Expected Price Range: ${straddle_1:.2f} to ${straddle_2:.2f}")
        logger.info(f"Delta-Based Range: ${delta_16_minus:.2f} to ${delta_16_plus:.2f}")
        logger.info(f"Delta Range %: {delta_range_pct:.2f}%")
        
        return {
            'atm_price': atm_price,
            'wem': wem,
            'wem_spread': wem_spread / 100,  # Store as decimal for consistency
            'delta_16_plus': delta_16_plus,
            'straddle_2': straddle_2,
            'straddle_1': straddle_1,
            'delta_16_minus': delta_16_minus,
            'delta_range': delta_range,
            'delta_range_pct': delta_range_pct / 100,  # Store as decimal for consistency
            'last_updated': market_data.timestamp,
            'meta_data': {
                'straddle_level': straddle_level,
                'strangle_level': strangle_level,
                'atm_call_bid': atm_call['bid'],
                'atm_call_ask': atm_call['ask'],
                'atm_put_bid': atm_put['bid'],
                'atm_put_ask': atm_put['ask'],
                'otm_call_bid': otm_call['bid'],
                'otm_call_ask': otm_call['ask'],
                'otm_put_bid': otm_put['bid'],
                'otm_put_ask': otm_put['ask'],
                'calculation_timestamp': datetime.utcnow().isoformat(),
                'data_source': market_data.source
            }
        }
        
    except Exception as e:
        error_msg = f"Error calculating WEM for {symbol}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        st.error(error_msg)
        return None

def create_wem_table(stocks: List[Dict[str, Any]], layout: str = 'vertical') -> pd.DataFrame:
    """Create a DataFrame for WEM stocks"""
    data = []
    for stock in stocks:
        # Parse last_updated if it's a string
        last_updated = stock.get('last_updated')
        if isinstance(last_updated, str):
            try:
                last_updated = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                last_updated = None
        
        # Store raw numeric values
        row = {
            'Symbol': stock['symbol'],
            'ATM': stock.get('atm_price'),
            'WEM': stock.get('wem'),  # Added WEM column
            'WEM Spread': stock.get('wem_spread', 0) * 100 if stock.get('wem_spread') is not None else None,  # Convert to percentage
            'Delta 16 (+)': stock.get('delta_16_plus'),
            'Straddle 2': stock.get('straddle_2'),
            'Straddle 1': stock.get('straddle_1'),
            'Delta 16 (-)': stock.get('delta_16_minus'),
            'Delta Range': stock.get('delta_range'),
            'Delta Range %': stock.get('delta_range_pct', 0) * 100 if stock.get('delta_range_pct') is not None else None,  # Convert to percentage
            'Last Updated': last_updated
        }
        data.append(row)
    
    df = pd.DataFrame(data)
    
    # Transform to horizontal layout if requested
    if layout == 'horizontal':
        df = df.set_index('Symbol').transpose()
    
    return df

def main():
    logger.info("=== Starting WEM Page Main Function ===")
    
    try:
        st.title("Weekly Expected Moves (WEM)")
        
        # Initialize database if needed
        try:
            logger.debug("Initializing database...")
            init_db()
            logger.info("Database initialized successfully")
        except Exception as e:
            error_msg = f"Error initializing database: {str(e)}"
            logger.error(error_msg, exc_info=True)
            st.error(error_msg)
            return
        
        # Get database session
        try:
            logger.debug("Getting database connection...")
            with get_db_connection() as session:
                # Initialize session state
                if 'wem_stocks' not in st.session_state:
                    logger.debug("Initializing WEM stocks in session state")
                    st.session_state.wem_stocks = get_wem_stocks(session)
                    logger.info(f"Loaded {len(st.session_state.wem_stocks)} WEM stocks")
                
                if 'layout' not in st.session_state:
                    logger.debug("Initializing layout in session state")
                    st.session_state.layout = 'vertical'
                
                if 'visible_columns' not in st.session_state:
                    logger.debug("Initializing visible columns in session state")
                    st.session_state.visible_columns = {
                        'Symbol': True,
                        'ATM': True,
                        'WEM': True,
                        'WEM Spread': True,
                        'Delta 16 (+)': True,
                        'Straddle 2': True,
                        'Straddle 1': True,
                        'Delta 16 (-)': True,
                        'Delta Range': True,
                        'Delta Range %': True,
                        'Last Updated': True
                    }
                
                # Sidebar
                with st.sidebar:
                    logger.debug("Rendering sidebar...")
                    st.subheader("WEM Settings")
                    
                    # Layout Selection
                    st.markdown("### Display Settings")
                    layout = st.radio(
                        "Table Layout",
                        ["Vertical", "Horizontal"],
                        index=0 if st.session_state.layout == 'vertical' else 1,
                        key="layout_selection"
                    )
                    if layout.lower() != st.session_state.layout:
                        logger.info(f"Layout changed from {st.session_state.layout} to {layout.lower()}")
                    st.session_state.layout = layout.lower()
                    
                    # Column Visibility Settings
                    st.markdown("### Column Visibility")
                    for col in st.session_state.visible_columns:
                        st.session_state.visible_columns[col] = st.checkbox(
                            col,
                            value=st.session_state.visible_columns[col],
                            key=f"col_{col}"
                        )
                    
                    # Stock Selection
                    st.markdown("### Add Stock")
                    new_stock = st.text_input("Stock Symbol")
                    is_default = st.checkbox("Add as Default Stock")
                    
                    if st.button("Add Stock") and new_stock:
                        logger.info(f"Attempting to add new stock: {new_stock.upper()}")
                        try:
                            stock = add_wem_stock(session, new_stock.upper(), is_default)
                            logger.info(f"Successfully added stock: {stock['symbol']}")
                            st.success(f"Added {stock['symbol']}")
                            st.session_state.wem_stocks = get_wem_stocks(session)
                            st.rerun()
                        except Exception as e:
                            error_msg = f"Error adding stock {new_stock}: {str(e)}"
                            logger.error(error_msg, exc_info=True)
                            st.error(error_msg)
                    
                    # Display current stocks
                    st.markdown("### Tracked Stocks")
                    for stock in st.session_state.wem_stocks:
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.write(stock['symbol'])
                        with col2:
                            if stock.get('is_default'):
                                st.write("(Default)")
                        with col3:
                            if st.button("Remove", key=f"remove_{stock['symbol']}"):
                                logger.info(f"Attempting to remove stock: {stock['symbol']}")
                                if remove_wem_stock(session, stock['symbol']):
                                    logger.info(f"Successfully removed stock: {stock['symbol']}")
                                    st.success(f"Removed {stock['symbol']}")
                                    st.session_state.wem_stocks = get_wem_stocks(session)
                                    st.rerun()
                    
                    # Update Settings
                    st.markdown("### Update Settings")
                    if st.button("Update All Data"):
                        logger.info("Starting update of all WEM data")
                        with st.spinner("Updating WEM data..."):
                            for stock in st.session_state.wem_stocks:
                                logger.info(f"Calculating WEM for {stock['symbol']}")
                                try:
                                    # Calculate new values
                                    new_data = calculate_expected_move(session, {'symbol': stock['symbol']})
                                    
                                    if new_data:
                                        # Update stock data
                                        update_data = {
                                            'symbol': stock['symbol'],
                                            **new_data
                                        }
                                        if update_wem_stock(session, update_data):
                                            logger.info(f"Successfully updated {stock['symbol']}")
                                            st.success(f"Updated {stock['symbol']}")
                                        else:
                                            error_msg = f"Failed to update {stock['symbol']}"
                                            logger.error(error_msg)
                                            st.error(error_msg)
                                    else:
                                        error_msg = f"No market data available for {stock['symbol']}"
                                        logger.warning(error_msg)
                                        st.warning(error_msg)
                                except Exception as e:
                                    error_msg = f"Error calculating WEM for {stock['symbol']}: {str(e)}"
                                    logger.error(error_msg, exc_info=True)
                                    st.error(error_msg)
                            
                            st.session_state.wem_stocks = get_wem_stocks(session)
                            st.rerun()
                
                # Main Content
                if not st.session_state.wem_stocks:
                    logger.warning("No stocks selected")
                    st.warning("No stocks selected. Please add stocks in the sidebar.")
                else:
                    logger.debug(f"Creating WEM table with {len(st.session_state.wem_stocks)} stocks")
                    # Create and display WEM table
                    wem_df = create_wem_table(st.session_state.wem_stocks, st.session_state.layout)
                    
                    # Filter columns based on visibility settings
                    visible_cols = [col for col, visible in st.session_state.visible_columns.items() if visible]
                    wem_df = wem_df[visible_cols]
                    
                    # Style the dataframe
                    st.dataframe(
                        wem_df,
                        use_container_width=True,
                        hide_index=False,  # Show index for horizontal layout
                        column_config={
                            "Symbol": st.column_config.TextColumn(
                                "Symbol",
                                width="small",
                            ),
                            "ATM": st.column_config.NumberColumn(
                                "ATM",
                                format="$%.2f"
                            ),
                            "WEM": st.column_config.NumberColumn(
                                "WEM",
                                format="%.3f"
                            ),
                            "WEM Spread": st.column_config.NumberColumn(
                                "WEM Spread",
                                format="%.3f%%"
                            ),
                            "Delta 16 (+)": st.column_config.NumberColumn(
                                "Delta 16 (+)",
                                format="%.2f"
                            ),
                            "Straddle 2": st.column_config.NumberColumn(
                                "Straddle 2",
                                format="%.3f"
                            ),
                            "Straddle 1": st.column_config.NumberColumn(
                                "Straddle 1",
                                format="%.3f"
                            ),
                            "Delta 16 (-)": st.column_config.NumberColumn(
                                "Delta 16 (-)",
                                format="%.2f"
                            ),
                            "Delta Range": st.column_config.NumberColumn(
                                "Delta Range",
                                format="%.2f"
                            ),
                            "Delta Range %": st.column_config.NumberColumn(
                                "Delta Range %",
                                format="%.3f%%"
                            ),
                            "Last Updated": st.column_config.DatetimeColumn(
                                "Last Updated",
                                format="MM/DD/YY HH:mm:ss"
                            ),
                        }
                    )
                    
                    # Notes Section
                    st.subheader("Stock Notes")
                    for stock in st.session_state.wem_stocks:
                        with st.expander(f"Notes for {stock['symbol']}"):
                            notes = st.text_area(
                                "Analysis Notes",
                                value=stock.get('notes', ''),
                                key=f"notes_{stock['symbol']}",
                                placeholder="Enter analysis notes (support/resistance levels, divergence, gaps, etc.)"
                            )
                            
                            if notes != stock.get('notes'):
                                logger.info(f"Updating notes for {stock['symbol']}")
                                try:
                                    update_data = {
                                        'symbol': stock['symbol'],
                                        'notes': notes
                                    }
                                    if update_wem_stock(session, update_data):
                                        logger.info(f"Successfully updated notes for {stock['symbol']}")
                                        st.success("Notes updated")
                                        # Refresh stock data
                                        st.session_state.wem_stocks = get_wem_stocks(session)
                                    else:
                                        error_msg = f"Failed to update notes for {stock['symbol']}"
                                        logger.error(error_msg)
                                        st.error(error_msg)
                                except Exception as e:
                                    error_msg = f"Error updating notes for {stock['symbol']}: {str(e)}"
                                    logger.error(error_msg, exc_info=True)
                                    st.error(error_msg)
                            
                            # Show calculation metadata if available
                            if stock.get('meta_data'):
                                st.markdown("### Calculation Details")
                                st.json(stock['meta_data'])
                    
                    # Export to Excel
                    if st.button("Export to Excel"):
                        logger.info("Starting Excel export")
                        try:
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            excel_path = project_root / 'exports' / f'wem_export_{timestamp}.xlsx'
                            excel_path.parent.mkdir(exist_ok=True)
                            
                            # Create Excel writer
                            with pd.ExcelWriter(excel_path) as writer:
                                # Write WEM data
                                wem_df.to_excel(writer, sheet_name='WEM Data')
                                
                                # Write notes to second sheet
                                notes_data = pd.DataFrame([
                                    {'Stock': stock['symbol'], 'Notes': stock['notes']}
                                    for stock in st.session_state.wem_stocks
                                    if stock.get('notes')  # Only include non-empty notes
                                ])
                                if not notes_data.empty:
                                    notes_data.to_excel(writer, sheet_name='Analysis Notes', index=False)
                                
                                # Write calculation metadata to third sheet
                                meta_data = pd.DataFrame([
                                    {
                                        'Stock': stock['symbol'],
                                        **stock.get('meta_data', {'calculation_timestamp': None})
                                    }
                                    for stock in st.session_state.wem_stocks
                                ])
                                meta_data.to_excel(writer, sheet_name='Calculation Details', index=False)
                            
                            logger.info(f"Successfully exported data to {excel_path}")
                            st.success(f"Data exported to {excel_path}")
                        except Exception as e:
                            error_msg = f"Error exporting to Excel: {str(e)}"
                            logger.error(error_msg, exc_info=True)
                            st.error(error_msg)
                    
                    # Additional Analysis
                    st.subheader("Additional Analysis")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### Price Distribution")
                        # TODO: Add price distribution chart using market data
                        
                    with col2:
                        st.markdown("### Historical Moves")
                        # TODO: Add historical moves chart using market data
        
        except Exception as e:
            error_msg = f"Database error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            st.error(error_msg)
    
    except Exception as e:
        error_msg = f"Unexpected error in main function: {str(e)}"
        logger.error(error_msg, exc_info=True)
        st.error(error_msg)
    
    logger.info("=== WEM Page Main Function Completed ===")

if __name__ == "__main__":
    main() 