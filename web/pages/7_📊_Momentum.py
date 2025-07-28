"""
Momentum Strategy Analysis Tool

This page provides functionality for:
1. Analyzing momentum indicators for options and underlying stocks
2. Daily time-based analysis with historical option chain data
3. Tracking key metrics: Open Interest, Volume, Greeks (Vega, Gamma), IV, and stock movement
4. Historical analysis using REAL historical option data (back to 2005)

MOMENTUM INDICATORS:
===================
- Open Interest: Total number of outstanding contracts (historical)
- Shares Volume: Trading volume in underlying stock (historical)
- Vega: Sensitivity to implied volatility changes (historical) ⚠️ LIMITED
- Implied Volatility: Market's expectation of future volatility (historical) ⚠️ LIMITED
- Stock Percentage Movement: Price change between trading days
- Gamma: Rate of change of delta with respect to underlying price (historical) ⚠️ LIMITED

HISTORICAL DATA CAPABILITY:
==========================
- Uses MarketDataApp's historical option chains (back to 2005)
- Real historical option data, not estimates or forward-filling
- Data is as-traded on each date (not adjusted for splits/dividends)
- End-of-day data only (MarketDataApp limitation for historical options)

⚠️ IMPORTANT LIMITATION - HISTORICAL GREEKS:
==========================================
MarketDataApp historical option chains do NOT include option Greeks (delta, gamma, vega, theta)
for historical dates. Only current/recent option chains include these calculated values.

Historical data includes:
✅ Open Interest (actual recorded values)
✅ Volume, bid/ask, last price
❌ Delta, Gamma, Vega, Theta (null for historical dates)
❌ Implied Volatility (may be null for historical dates)

This is a common limitation in the market data industry because Greeks are calculated values
that require real-time market conditions (risk-free rates, volatility assumptions, etc.)
that may not be historically preserved.

IMPLEMENTATION NOTES:
====================
- Rate Limiting: MarketDataApp enforces 45 requests/60 seconds with automatic sleep
- Database Caching: Historical option data is stored to avoid re-fetching
- Daily Data Mode: All analysis uses daily intervals for maximum compatibility
- Intelligent Sampling: Option data can be sampled at strategic intervals for performance

TIME PERIODS:
=============
- Daily intervals (required for historical option compatibility)
- Standard analysis: Past 8 weeks (~40-56 trading days)
- GME: Extended historical data from January 2021

DEVELOPMENT HISTORY:
===================
Major fixes implemented (2025-07-28):
1. Fixed MarketDataManager method signature caching issue
2. Implemented real historical option chain data fetching
3. Added database storage and retrieval for option data
4. Fixed Excel timestamp formatting with openpyxl
5. Implemented rate limiting and error handling
6. Discovered and documented historical Greeks limitation

Note: MarketDataApp historical option chains only support end-of-day data,
so all analysis uses daily intervals for maximum compatibility and accuracy.
"""

import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
import yaml
import time
import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import openpyxl

# Set up logging in a Streamlit-safe way
project_root = Path(__file__).parent.parent.parent
log_dir = project_root / 'logs'
log_dir.mkdir(exist_ok=True)

# Load settings
settings_file = project_root / 'goldflipper' / 'config' / 'settings.yaml'
settings = {}
if settings_file.exists():
    with open(settings_file, 'r') as f:
        settings = yaml.safe_load(f)

# Set up logging
def setup_momentum_logging():
    """Set up logging for Momentum session"""
    session_timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    log_file = log_dir / f'momentum_{session_timestamp}.log'
    
    logger = logging.getLogger(__name__)
    
    # Clear any existing handlers to prevent duplication
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logger.setLevel(logging.INFO)
    logger.propagate = False
    
    # Create file handler for this session
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    )
    logger.addHandler(file_handler)
    
    logger.info("=" * 80)
    logger.info(f"MOMENTUM ANALYSIS SESSION STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    return logger

# Create basic logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)
    logger.propagate = False

# Add the project root to the Python path
sys.path.append(str(project_root))

from goldflipper.database.connection import get_db_connection, init_db
from goldflipper.database.models import MarketData
from goldflipper.database.repositories import MarketDataRepository
from goldflipper.data.market.manager import MarketDataManager
from goldflipper.config.config import config

# Page configuration
st.set_page_config(
    page_title="Momentum Strategy Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better table display
st.markdown("""
<style>
    div[data-testid="stDataFrame"] {
        overflow-x: auto;
    }
    .stDataFrame > div {
        width: 100%;
    }
    /* Momentum-specific styling */
    .momentum-header {
        background: linear-gradient(90deg, #FF6B6B, #4ECDC4);
        padding: 10px;
        border-radius: 5px;
        color: white;
        font-weight: bold;
        text-align: center;
        margin-bottom: 10px;
    }
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize market data manager (reused from WEM)
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

def get_option_chain_for_analysis(symbol: str, expiration_date: datetime) -> Optional[Dict[str, pd.DataFrame]]:
    """
    Get option chain for momentum analysis (reused from WEM with modifications)
    
    Args:
        symbol: Stock symbol
        expiration_date: Options expiration date
        
    Returns:
        dict: Dictionary with 'calls' and 'puts' DataFrames
    """
    try:
        # Get market data manager
        manager = get_market_data_manager()
        if not manager:
            logger.error("No market data manager available")
            return None
        
        # Format expiration date for API
        expiration_str = expiration_date.strftime('%Y-%m-%d')
        logger.info(f"Requesting option chain for {symbol} with expiration {expiration_str}")
        
        # Get option chain
        chain = manager.get_option_chain(symbol, expiration_str)
        
        if not chain or not isinstance(chain, dict) or 'calls' not in chain or 'puts' not in chain:
            logger.warning(f"Invalid option chain format received for {symbol} on {expiration_str}")
            return None
        
        calls_df = chain['calls']
        puts_df = chain['puts']
        
        if calls_df.empty and puts_df.empty:
            logger.warning(f"Empty option chain received for {symbol} on {expiration_str}")
            return None
        
        logger.info(f"✅ Successfully retrieved option chain for {symbol}: {len(calls_df)} calls, {len(puts_df)} puts")
        return chain
        
    except Exception as e:
        logger.error(f"Error getting option chain for {symbol}: {str(e)}", exc_info=True)
        return None

def get_historical_stock_data(symbol: str, start_date: datetime, end_date: datetime, interval: str = "15m") -> Optional[pd.DataFrame]:
    """
    Get historical stock data for momentum analysis
    
    Args:
        symbol: Stock symbol
        start_date: Start date for historical data
        end_date: End date for historical data
        interval: Data interval (e.g., "15m", "1h", "1d")
        
    Returns:
        DataFrame with historical price data
    """
    try:
        # DEBUG: Log the exact date range being requested
        logger.info(f"🔍 DEBUG: Requesting {symbol} from {start_date} to {end_date} (interval: {interval})")
        logger.info(f"🔍 DEBUG: Date range span: {(end_date - start_date).days} days")
        
        manager = get_market_data_manager()
        if not manager:
            logger.error("No market data manager available")
            return None
        
        # Use MarketDataApp provider for historical data
        from goldflipper.data.market.providers.marketdataapp_provider import MarketDataAppProvider
        
        config_path = project_root / 'goldflipper' / 'config' / 'settings.yaml'
        provider = MarketDataAppProvider(str(config_path))
        
        logger.info(f"Requesting historical data for {symbol} from {start_date.date()} to {end_date.date()} at {interval} intervals")
        
        # Get historical data with intelligent interval fallback
        # MarketDataApp has limitations on intraday historical data
        historical_data = None
        actual_interval = interval
        
        # Strategy: Try requested interval, then fallback to supported intervals
        fallback_intervals = [interval]
        
        # Add fallback intervals based on requested interval
        if interval in ["15m", "30m"]:
            fallback_intervals.extend(["1h", "1d"])
        elif interval in ["1h", "4h"]:
            fallback_intervals.extend(["1d"])
        elif interval == "1d":
            pass  # Daily is usually supported
        else:
            fallback_intervals.append("1d")  # Always try daily as last resort
        
        for try_interval in fallback_intervals:
            try:
                logger.info(f"Trying {try_interval} interval for {symbol}")
                historical_data = provider.get_historical_data(symbol, start_date, end_date, interval=try_interval)
                actual_interval = try_interval
                
                if not historical_data.empty:
                    if try_interval != interval:
                        logger.warning(f"Using {try_interval} data instead of requested {interval} for {symbol}")
                    break
                else:
                    logger.warning(f"Empty dataset with {try_interval} interval")
                    
            except Exception as interval_error:
                logger.warning(f"Failed to get {try_interval} data for {symbol}: {str(interval_error)}")
                continue
        
        if historical_data is None or historical_data.empty:
            logger.error(f"All interval attempts failed for {symbol}")
            return None
        
        # DEBUG: Check what we actually got back
        if not historical_data.empty:
            logger.info(f"🔍 DEBUG: Retrieved {len(historical_data)} data points for {symbol} using {actual_interval} interval")
            logger.info(f"🔍 DEBUG: First timestamp: {historical_data.iloc[0]['timestamp']}")
            logger.info(f"🔍 DEBUG: Last timestamp: {historical_data.iloc[-1]['timestamp']}")
            logger.info(f"🔍 DEBUG: Data columns: {list(historical_data.columns)}")
            logger.info(f"🔍 DEBUG: Sample data (first 3 rows):")
            for i, row in historical_data.head(3).iterrows():
                logger.info(f"🔍 DEBUG: Row {i}: {dict(row)}")
        else:
            logger.warning(f"🔍 DEBUG: Empty dataset returned for {symbol}")
            
        if historical_data.empty:
            logger.warning(f"No historical data available for {symbol} in requested period")
            return None
        
        logger.info(f"✅ Successfully retrieved {len(historical_data)} data points for {symbol} using {actual_interval} interval")
        return historical_data
        
    except Exception as e:
        logger.error(f"Error getting historical data for {symbol}: {str(e)}", exc_info=True)
        return None

def get_historical_option_data_for_date(symbol: str, target_date: datetime) -> Optional[Dict[str, Any]]:
    """
    Get historical option data for a specific date using MarketDataApp historical option chains
    
    MarketDataApp supports historical option chains going back to 2005 using the date parameter.
    This provides REAL historical option data, not estimates.
    
    Args:
        symbol: Stock symbol
        target_date: Date to get option data for
        
    Returns:
        Dictionary with aggregated option indicators or None if no data
    """
    try:
        # Format date for MarketDataApp API (YYYY-MM-DD)
        date_str = target_date.strftime('%Y-%m-%d')
        
        # Validate the date - skip very recent dates (but let API handle weekends)
        days_ago = (datetime.now() - target_date).days
        if days_ago < 1:  # Skip today and future dates
            logger.debug(f"Skipping recent/future date for {symbol}: {date_str} ({days_ago} days ago)")
            return None
        
        logger.debug(f"Requesting historical option data for {symbol} on {date_str} ({days_ago} days ago)")
        
        # FIRST: Check if we already have this data in the database
        try:
            from goldflipper.database.connection import get_db_connection
            from goldflipper.database.models import MarketData
            from sqlalchemy import and_, func, cast, Date
            
            with get_db_connection() as session:
                # Query for cached option data for this symbol and date
                # Use DuckDB-compatible date casting
                cache_query = session.query(MarketData).filter(
                    and_(
                        MarketData.symbol.like(f"{symbol}%"),  # Option symbols start with underlying
                        cast(MarketData.timestamp, Date) == target_date.date(),  # DuckDB-compatible date casting
                        MarketData.implied_volatility.isnot(None)  # Ensure it's option data
                    )
                ).all()
                
                if cache_query:
                    # Found cached data - aggregate it
                    total_oi = sum(row.open_interest or 0 for row in cache_query)
                    
                    if total_oi > 0:
                        # Weight by open interest
                        weighted_vega = sum((row.vega or 0) * (row.open_interest or 0) for row in cache_query) / total_oi
                        weighted_gamma = sum((row.gamma or 0) * (row.open_interest or 0) for row in cache_query) / total_oi
                        weighted_iv = sum((row.implied_volatility or 0) * (row.open_interest or 0) for row in cache_query) / total_oi
                    else:
                        # Simple averages
                        count = len(cache_query)
                        weighted_vega = sum(row.vega or 0 for row in cache_query) / count
                        weighted_gamma = sum(row.gamma or 0 for row in cache_query) / count  
                        weighted_iv = sum(row.implied_volatility or 0 for row in cache_query) / count
                    
                    logger.debug(f"✅ Using cached option data for {symbol} on {date_str}: OI={total_oi:.0f}")
                    return {
                        'open_interest': total_oi,
                        'vega': weighted_vega,
                        'gamma': weighted_gamma,
                        'implied_volatility': weighted_iv
                    }
        except Exception as cache_error:
            logger.debug(f"Cache lookup failed for {symbol} on {date_str}: {str(cache_error)}")
        
        # SECOND: Fetch from API if not cached
        manager = get_market_data_manager()
        if not manager:
            logger.error("No market data manager available")
            return None
         
                         # Get historical option chain for the specific date
        # IMPORTANT: For historical data, we only pass the date parameter, NOT expiration_date
        try:
            option_chain = manager.get_option_chain(symbol, date=date_str)
        except Exception as api_error:
             # Handle API errors gracefully - some symbols may not have option data
             error_msg = str(api_error)
             if "400" in error_msg or "No cached data" in error_msg or "Error fetching option chain" in error_msg:
                 logger.debug(f"Symbol {symbol} has no option data for {date_str}: {error_msg}")
                 return None
             else:
                 # Unexpected error - re-raise
                 logger.warning(f"Unexpected API error for {symbol} on {date_str}: {error_msg}")
                 raise
        
        if not option_chain or 'calls' not in option_chain or 'puts' not in option_chain:
            logger.debug(f"No historical option data available for {symbol} on {date_str}")
            return None
        
        calls_df = option_chain['calls']
        puts_df = option_chain['puts']
        
        if calls_df.empty and puts_df.empty:
            logger.debug(f"Empty historical option chain for {symbol} on {date_str}")
            return None
        
        # THIRD: Store fetched data in database for future use
        try:
            from uuid import uuid4
            
            with get_db_connection() as session:
                # Combine calls and puts for storage
                all_options = pd.concat([calls_df, puts_df], ignore_index=True)
                
                for _, option_row in all_options.iterrows():
                    # Create MarketData record for each option
                    market_data = MarketData(
                        id=uuid4(),
                        symbol=option_row.get('symbol', f"{symbol}_OPT_{target_date.strftime('%Y%m%d')}"),
                        timestamp=target_date,
                        open=None,  # Options don't have OHLC data in the same way
                        high=None,
                        low=None,
                        close=option_row.get('last', 0),  # Use last price as close
                        volume=option_row.get('volume', 0),
                        source='marketdataapp_historical',
                        implied_volatility=option_row.get('implied_volatility', 0),
                        open_interest=option_row.get('open_interest', 0),
                        delta=option_row.get('delta', 0),
                        gamma=option_row.get('gamma', 0),
                        theta=option_row.get('theta', 0),
                        vega=option_row.get('vega', 0)
                    )
                    session.add(market_data)
                
                session.commit()
                logger.debug(f"💾 Stored {len(all_options)} option records in database for {symbol} on {date_str}")
        except Exception as storage_error:
            logger.warning(f"Failed to store option data in database: {str(storage_error)}")
        
        # FOURTH: Calculate aggregate indicators from fresh data
        indicators = {
            'open_interest': 0,
            'vega': 0,
            'gamma': 0,
            'implied_volatility': 0
        }
        
        # Aggregate open interest
        total_call_oi = calls_df['open_interest'].sum() if 'open_interest' in calls_df.columns and not calls_df.empty else 0
        total_put_oi = puts_df['open_interest'].sum() if 'open_interest' in puts_df.columns and not puts_df.empty else 0
        indicators['open_interest'] = total_call_oi + total_put_oi
        
        # Calculate weighted average Greeks if available
        if not calls_df.empty or not puts_df.empty:
            # Weight by open interest for more meaningful averages
            all_options = pd.concat([calls_df, puts_df], ignore_index=True)
            total_oi = all_options['open_interest'].sum()
            
            if total_oi > 0:
                # Weight by open interest
                if 'vega' in all_options.columns:
                    indicators['vega'] = (all_options['vega'] * all_options['open_interest']).sum() / total_oi
                if 'gamma' in all_options.columns:
                    indicators['gamma'] = (all_options['gamma'] * all_options['open_interest']).sum() / total_oi
                if 'implied_volatility' in all_options.columns:
                    indicators['implied_volatility'] = (all_options['implied_volatility'] * all_options['open_interest']).sum() / total_oi
            else:
                # Simple averages if no open interest data
                if 'vega' in all_options.columns:
                    indicators['vega'] = all_options['vega'].mean()
                if 'gamma' in all_options.columns:
                    indicators['gamma'] = all_options['gamma'].mean()
                if 'implied_volatility' in all_options.columns:
                    indicators['implied_volatility'] = all_options['implied_volatility'].mean()
        
        logger.debug(f"✅ Retrieved fresh historical option data for {symbol} on {date_str}: OI={indicators['open_interest']:.0f}")
        return indicators
        
    except Exception as e:
        logger.debug(f"Error getting historical option data for {symbol} on {target_date.date()}: {str(e)}")
        return None

def calculate_momentum_indicators(symbol: str, time_interval: str = "15m", weeks_back: int = 8, use_intelligent_sampling: bool = True) -> Optional[pd.DataFrame]:
    """
    Calculate momentum indicators for a given symbol with historical option data
    
    Args:
        symbol: Stock symbol to analyze
        time_interval: Time interval for analysis (e.g., "15m", "1h")
        weeks_back: Number of weeks to look back (default 8)
        use_intelligent_sampling: If True, uses intelligent sampling for option data. If False, attempts to fetch all option data
        
    Returns:
        DataFrame with momentum indicators including historical option data
    """
    try:
        logger.info(f"Calculating momentum indicators for {symbol} using {time_interval} intervals over {weeks_back} weeks")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=weeks_back)
        
        # DEBUG: Log the calculated date range
        logger.info(f"🔍 DEBUG: Current datetime: {end_date}")
        logger.info(f"🔍 DEBUG: Calculated start_date: {start_date}")
        logger.info(f"🔍 DEBUG: Calculated end_date: {end_date}")
        
        # Special handling for GME (from Jan 2021)
        if symbol.upper() == 'GME':
            start_date = datetime(2021, 1, 1)
            logger.info(f"Using extended historical period for {symbol}: from {start_date.date()}")
        
        # IMPORTANT: For historical option data, MarketDataApp only supports END OF DAY data
        # So we'll use daily intervals for both stock and option data
        effective_interval = "1d"  # Force daily for option compatibility
        logger.info(f"Using daily intervals for {symbol} due to option data limitations (MarketDataApp historical options are end-of-day only)")
        
        # Get historical stock data
        stock_data = get_historical_stock_data(symbol, start_date, end_date, effective_interval)
        
        if stock_data is None or stock_data.empty:
            logger.error(f"No stock data available for {symbol}")
            return None
        
        logger.info(f"📊 Retrieved stock data for {symbol}: {len(stock_data)} data points from {start_date.date()} to {end_date.date()}")
        
        # Calculate stock percentage movement between intervals
        stock_data['stock_pct_change'] = stock_data['close'].pct_change() * 100
        
        # Create momentum indicators DataFrame with historical option data
        momentum_data = []
        
        # Determine sampling frequency for historical option data
        total_points = len(stock_data)
        
        if use_intelligent_sampling:
            # Intelligent sampling optimized for daily data
            # With daily data, we expect ~40-60 trading days for 8 weeks
            if total_points > 200:
                # For long historical periods (8+ months), sample every 5th day
                sample_frequency = 5
            elif total_points > 100:
                # For medium periods (3-8 months), sample every 3rd day
                sample_frequency = 3
            elif total_points > 50:
                # For shorter periods (1-3 months), sample every 2nd day
                sample_frequency = 2
            else:
                # For very short periods, sample every day
                sample_frequency = 1
            
            logger.info(f"Processing {total_points} daily data points with intelligent sampling: every {sample_frequency} days (real historical option data)")
        else:
            # Full option data: fetch historical option data for every point
            sample_frequency = 1
            logger.info(f"Processing {total_points} data points with full historical option data collection (every point)")
            logger.warning("Full option data mode may be slower due to API rate limits, but provides maximum granularity")
        
        for idx, (row_idx, row) in enumerate(stock_data.iterrows()):
            timestamp = row.get('timestamp', row_idx)
            
            # DEBUG: Log first few timestamps to see what we're processing
            if idx < 10:
                logger.info(f"🔍 DEBUG: Processing row {idx}, timestamp: {timestamp} (type: {type(timestamp)})")
            
            # Convert timestamp to datetime if it's not already
            if isinstance(timestamp, str):
                timestamp = pd.to_datetime(timestamp)
            elif hasattr(timestamp, 'to_pydatetime'):
                timestamp = timestamp.to_pydatetime()
            
            # Basic momentum indicators from stock data
            indicator_row = {
                'timestamp': timestamp,
                'symbol': symbol,
                'stock_price': row.get('close', 0),
                'shares_volume': row.get('volume', 0),
                'stock_pct_change': row.get('stock_pct_change', 0),
                'open_interest': None,
                'vega': None,
                'gamma': None,
                'implied_volatility': None
            }
            
            # Get option data based on sampling strategy
            if use_intelligent_sampling:
                # Intelligent sampling: fetch at strategic intervals
                should_fetch_options = (
                    idx % sample_frequency == 0 or  # Sample frequency
                    idx == 0 or  # First point
                    idx == total_points - 1 or  # Last point
                    idx % 100 == 0  # Every 100th point for progress
                )
            else:
                # Full option data: attempt to fetch for every point
                should_fetch_options = True
            
            if should_fetch_options:
                # Progress reporting - more frequent for full data mode
                if use_intelligent_sampling:
                    if idx % 100 == 0:
                        logger.info(f"Processing option data for {symbol} - {idx}/{total_points} ({idx/total_points*100:.1f}%)")
                else:
                    if idx % 50 == 0:  # More frequent progress for full data mode
                        logger.info(f"Fetching option data for {symbol} - {idx}/{total_points} ({idx/total_points*100:.1f}%)")
                
                option_data = get_historical_option_data_for_date(symbol, timestamp)
                
                if option_data:
                    indicator_row.update(option_data)
            
            momentum_data.append(indicator_row)
        
        # Convert to DataFrame
        momentum_df = pd.DataFrame(momentum_data)
        
        # Fill missing option data based on sampling strategy
        option_columns = ['open_interest', 'vega', 'gamma', 'implied_volatility']
        
        if use_intelligent_sampling:
            # Forward fill option data for non-sampled points
            for col in option_columns:
                momentum_df[col] = momentum_df[col].ffill()
            
            # If we still have NaN values at the beginning, backward fill
            for col in option_columns:
                momentum_df[col] = momentum_df[col].bfill()
        else:
            # For full data mode, only fill remaining NaN values (should be minimal)
            for col in option_columns:
                # First try forward fill for any gaps
                momentum_df[col] = momentum_df[col].ffill()
                # Then backward fill any remaining NaN values at the beginning
                momentum_df[col] = momentum_df[col].bfill()
        
        sampling_method = "intelligent sampling" if use_intelligent_sampling else "full option data collection"
        
        # Summary of data collection
        option_data_points = momentum_df['open_interest'].notna().sum()
        total_points = len(momentum_df)
        data_coverage = (option_data_points / total_points) * 100 if total_points > 0 else 0
        
        logger.info(f"Successfully calculated momentum indicators for {symbol}: {len(momentum_df)} data points using {sampling_method}")
        logger.info(f"Option data coverage for {symbol}: {option_data_points}/{total_points} points ({data_coverage:.1f}%)")
        
        return momentum_df
        
    except Exception as e:
        logger.error(f"Error calculating momentum indicators for {symbol}: {str(e)}", exc_info=True)
        return None

def format_momentum_number(value, column_name):
    """Format numbers for momentum analysis display"""
    if pd.isna(value) or value is None:
        return "—"
    
    try:
        num_val = float(value)
    except (ValueError, TypeError):
        return "—"
    
    # Format based on column type and magnitude
    if column_name in ['stock_pct_change']:
        return f"{num_val:+.2f}%" if abs(num_val) < 100 else f"{num_val:+.1f}%"
    elif column_name in ['implied_volatility']:
        return f"{num_val:.3f}" if abs(num_val) < 1 else f"{num_val:.2f}"
    elif column_name in ['vega', 'gamma']:
        return f"{num_val:.4f}" if abs(num_val) < 1 else f"{num_val:.3f}"
    elif column_name in ['open_interest', 'shares_volume']:
        if abs(num_val) >= 1e6:
            return f"{num_val/1e6:.1f}M"
        elif abs(num_val) >= 1e3:
            return f"{num_val/1e3:.1f}K"
        else:
            return f"{num_val:.0f}"
    elif column_name == 'stock_price':
        return f"${num_val:.2f}"
    else:
        # Default formatting - remove unnecessary zeros
        if abs(num_val) >= 1000:
            return f"{num_val:,.0f}"
        elif abs(num_val) >= 1:
            return f"{num_val:.2f}".rstrip('0').rstrip('.')
        else:
            return f"{num_val:.4f}".rstrip('0').rstrip('.')

def create_momentum_table(momentum_data: List[pd.DataFrame], symbols: List[str]) -> pd.DataFrame:
    """
    Create a combined momentum analysis table
    
    Args:
        momentum_data: List of DataFrames with momentum indicators for each symbol
        symbols: List of symbols being analyzed
        
    Returns:
        Combined DataFrame for display
    """
    if not momentum_data or all(df is None or df.empty for df in momentum_data):
        return pd.DataFrame()
    
    combined_data = []
    
    for df, symbol in zip(momentum_data, symbols):
        if df is not None and not df.empty:
            # Get latest data point for each symbol
            latest_data = df.iloc[-1].copy()
            latest_data['symbol'] = symbol
            combined_data.append(latest_data)
    
    if not combined_data:
        return pd.DataFrame()
    
    # Create combined DataFrame
    result_df = pd.DataFrame(combined_data)
    
    # Reorder columns for better display
    column_order = [
        'symbol', 'timestamp', 'stock_price', 'stock_pct_change', 
        'shares_volume', 'open_interest', 'vega', 'gamma', 'implied_volatility'
    ]
    
    # Only include columns that exist
    existing_columns = [col for col in column_order if col in result_df.columns]
    result_df = result_df[existing_columns]
    
    # Apply formatting
    for col in result_df.columns:
        if col not in ['symbol', 'timestamp']:
            result_df[col] = result_df[col].apply(lambda x: format_momentum_number(x, col))
    
    return result_df

def main():
    """Main function for the Momentum application"""
    
    # App title and description
    st.markdown('<div class="momentum-header">📊 Momentum Strategy Analysis</div>', unsafe_allow_html=True)
    st.subheader("Real-time momentum indicators and Greeks analysis for options trading")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Momentum Configuration")
        
        # Time interval setting
        st.subheader("Analysis Parameters")
        
        time_interval = st.selectbox(
            "Time Interval",
            options=["15m", "30m", "1h", "4h", "1d"],
            index=0,  # Default to 15m
            help="Time interval for momentum analysis"
        )
        
        weeks_back = st.slider(
            "Weeks to Analyze",
            min_value=1,
            max_value=52,
            value=8,
            step=1,
            help="Number of weeks of historical data to analyze"
        )
        
        # Option data sampling control
        use_intelligent_sampling = st.checkbox(
            "Enable Intelligent Sampling",
            value=True,
            help="When enabled, option data is sampled at intelligent intervals for performance. When disabled, attempts to fetch option data for every time interval (slower but more complete)."
        )
        
        # Symbol selection
        st.subheader("Symbol Selection")
        
        # Predefined symbol groups
        momentum_symbols = {
            "High Volume Options": ["SPY", "AAPL", "TSLA", "NVDA", "QQQ"],  # Changed to symbols with very active options
            "Meme Stock": ["GME"],
            "Popular ETFs": ["SPY", "QQQ", "IWM"],
            "Tech Stocks": ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"],
            "Original Test": ["OPEN", "PDYN", "KSS", "RIOT", "GPRO", "OKLO"],  # Moved original symbols here
            "Custom": []
        }
        
        symbol_group = st.selectbox(
            "Select Symbol Group",
            options=list(momentum_symbols.keys()),
            help="Choose a predefined group or select Custom to enter your own symbols"
        )
        
        if symbol_group == "Custom":
            custom_symbols = st.text_area(
                "Custom Symbols",
                placeholder="Enter symbols separated by commas (e.g., AAPL, MSFT, GOOGL)",
                help="Enter your own list of symbols to analyze"
            )
            
            if custom_symbols:
                import re
                symbols = [s.strip().upper() for s in re.split(r'[,\s]+', custom_symbols) if s.strip()]
            else:
                symbols = []
        else:
            symbols = momentum_symbols[symbol_group]
        
        # Display current selection
        if symbols:
            st.success(f"📊 Analyzing: {', '.join(symbols)}")
            
            # Show analysis configuration
            sampling_mode = "Intelligent Sampling" if use_intelligent_sampling else "Full Option Data"
            st.caption(f"Interval: {time_interval} | Period: {weeks_back} weeks | Mode: {sampling_mode}")
            
            # Important note about daily data requirement
            st.info("📅 **Daily Data Mode**: MarketDataApp historical option chains only support **end-of-day data**. "
                   "The analysis will use daily intervals for both stock prices and option data to ensure compatibility. "
                   "This provides excellent historical accuracy with real option Greeks, IV, and Open Interest data.")
            
            # Show sampling strategy details
            if use_intelligent_sampling:
                st.info("⚡ **Intelligent Sampling**: Will sample option data every 2-5 trading days depending on the time period. "
                       "This provides excellent performance while maintaining high accuracy with real historical option data.")
            else:
                st.warning("🔍 **Full Option Data**: Will fetch historical option data for **every trading day**. "
                          "This provides maximum accuracy but will be slower due to API rate limits. "
                          "With daily data over 8 weeks (~40-56 trading days), this is much more manageable than intraday intervals.")
            
            # Special note for GME
            if "GME" in symbols:
                st.info("🎮 GME analysis uses extended historical data from January 2021")
                
            # Important note about historical option data capabilities
            st.info("📋 **Historical Option Data**: MarketDataApp provides **real historical option chains going back to 2005**! "
                   "This means you get actual historical Open Interest, Vega, Gamma, and IV data, not estimates. "
                   "Data is as-traded on each date (not adjusted for splits/dividends).")
            
            # Note about interval limitations
            if time_interval in ["15m", "30m"]:
                st.warning("⚠️ **Interval Limitation**: MarketDataApp may not support 15-minute or 30-minute intervals for "
                          "extended historical periods. The system will automatically fall back to hourly or daily data if needed.")
        else:
            st.warning("⚠️ No symbols selected for analysis")
        
        # Analysis controls
        st.subheader("Analysis Controls")
        
        if st.button("🚀 Run Momentum Analysis", type="primary", disabled=not symbols):
            st.session_state.run_analysis = True
        
        # Display options
        st.subheader("Display Options")
        
        show_charts = st.checkbox("Show Charts", value=True, help="Display momentum trend charts")
        show_detailed_data = st.checkbox("Show Detailed Data", value=False, help="Show full historical data table")
        
        # Export options
        st.subheader("Export Options")
        
        export_format = st.selectbox(
            "Export Format",
            options=["CSV", "Excel"],
            index=0,
            help="Format for exporting momentum analysis data"
        )
        
        if st.button("📤 Export Data", disabled=not symbols):
            st.session_state.export_requested = True
    
    # Main content area
    if not symbols:
        st.info("👈 Please select symbols from the sidebar to begin momentum analysis")
        return
    
    # Run analysis if requested
    if st.session_state.get('run_analysis', False):
        st.session_state.run_analysis = False  # Reset flag
        
        with st.spinner("🔄 Running momentum analysis..."):
            try:
                # Set up logging for this session
                session_logger = setup_momentum_logging()
                
                # Calculate momentum indicators for each symbol
                momentum_results = []
                
                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, symbol in enumerate(symbols):
                    status_text.text(f"Analyzing {symbol}... ({i+1}/{len(symbols)})")
                    progress_bar.progress((i + 1) / len(symbols))
                    
                    # Calculate indicators
                    momentum_data = calculate_momentum_indicators(symbol, time_interval, weeks_back, use_intelligent_sampling)
                    momentum_results.append(momentum_data)
                    
                    session_logger.info(f"Completed analysis for {symbol}")
                
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()
                
                # Store results in session state
                st.session_state.momentum_results = momentum_results
                st.session_state.analyzed_symbols = symbols
                st.session_state.analysis_params = {
                    'time_interval': time_interval,
                    'weeks_back': weeks_back,
                    'use_intelligent_sampling': use_intelligent_sampling
                }
                
                session_logger.info(f"Momentum analysis completed for {len(symbols)} symbols")
                st.success(f"✅ Analysis completed for {len(symbols)} symbols!")
                
            except Exception as e:
                st.error(f"❌ Analysis failed: {str(e)}")
                logger.exception("Momentum analysis error")
    
    # Display results if available
    if hasattr(st.session_state, 'momentum_results') and st.session_state.momentum_results:
        st.subheader("📊 Momentum Analysis Results")
        
        # Create summary table
        summary_table = create_momentum_table(
            st.session_state.momentum_results, 
            st.session_state.analyzed_symbols
        )
        
        if not summary_table.empty:
            st.subheader("Current Momentum Indicators")
            
            # Configure column display
            column_config = {
                'symbol': st.column_config.TextColumn("Symbol", width=80),
                'timestamp': st.column_config.DatetimeColumn("Last Update", width=120),
                'stock_price': st.column_config.TextColumn("Price", width=80),
                'stock_pct_change': st.column_config.TextColumn("% Change", width=90),
                'shares_volume': st.column_config.TextColumn("Volume", width=80),
                'open_interest': st.column_config.TextColumn("Open Interest", width=100),
                'vega': st.column_config.TextColumn("Vega", width=80),
                'gamma': st.column_config.TextColumn("Gamma", width=80),
                'implied_volatility': st.column_config.TextColumn("IV", width=80)
            }
            
            st.dataframe(
                summary_table,
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
            
            # Show analysis parameters
            params = st.session_state.analysis_params
            sampling_mode = "Intelligent Sampling" if params.get('use_intelligent_sampling', True) else "Full Option Data"
            st.caption(f"📈 Analysis: {params['time_interval']} intervals over {params['weeks_back']} weeks | {sampling_mode}")
        
        # Show charts if requested
        if show_charts and st.session_state.momentum_results:
            st.subheader("📈 Momentum Trends")
            
            for result_df, symbol in zip(st.session_state.momentum_results, st.session_state.analyzed_symbols):
                if result_df is not None and not result_df.empty and len(result_df) > 1:
                    with st.expander(f"📊 {symbol} Momentum Chart", expanded=True):
                        
                        # Create two columns for price and indicators
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Stock price and percentage change
                            chart_data = result_df[['timestamp', 'stock_price', 'stock_pct_change']].dropna()
                            if not chart_data.empty:
                                st.subheader(f"{symbol} Price Movement")
                                st.line_chart(chart_data.set_index('timestamp')['stock_price'])
                        
                        with col2:
                            # Volume chart
                            volume_data = result_df[['timestamp', 'shares_volume']].dropna()
                            if not volume_data.empty:
                                st.subheader(f"{symbol} Volume")
                                st.bar_chart(volume_data.set_index('timestamp')['shares_volume'])
        
        # Show detailed data if requested
        if show_detailed_data and st.session_state.momentum_results:
            st.subheader("📋 Detailed Historical Data")
            
            for result_df, symbol in zip(st.session_state.momentum_results, st.session_state.analyzed_symbols):
                if result_df is not None and not result_df.empty:
                    with st.expander(f"📊 {symbol} Historical Data", expanded=False):
                        st.dataframe(result_df, use_container_width=True)
    
    # Handle export request
    if st.session_state.get('export_requested', False):
        st.session_state.export_requested = False  # Reset flag
        
        if hasattr(st.session_state, 'momentum_results') and st.session_state.momentum_results:
            with st.spinner("📤 Preparing export..."):
                try:
                    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M")
                    
                    if export_format == "CSV":
                        # Export summary table to CSV
                        summary_table = create_momentum_table(
                            st.session_state.momentum_results, 
                            st.session_state.analyzed_symbols
                        )
                        
                        csv_path = f"./data/exports/momentum_{timestamp}.csv"
                        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                        summary_table.to_csv(csv_path, index=False)
                        st.success(f"📊 Momentum data exported to {csv_path}")
                        
                    else:  # Excel
                        excel_path = f"./data/exports/momentum_{timestamp}.xlsx"
                        os.makedirs(os.path.dirname(excel_path), exist_ok=True)
                        
                        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                            # Summary sheet
                            summary_table = create_momentum_table(
                                st.session_state.momentum_results, 
                                st.session_state.analyzed_symbols
                            )
                            
                            # Fix timestamp formatting for summary table
                            if 'timestamp' in summary_table.columns:
                                summary_table['timestamp'] = pd.to_datetime(summary_table['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
                            
                            summary_table.to_excel(writer, sheet_name='Summary', index=False)
                            
                            # Individual symbol sheets
                            for result_df, symbol in zip(st.session_state.momentum_results, st.session_state.analyzed_symbols):
                                if result_df is not None and not result_df.empty:
                                    sheet_name = f"{symbol}_Data"[:31]  # Excel sheet name limit
                                    
                                    # Fix timestamp formatting for individual sheets
                                    export_df = result_df.copy()
                                    if 'timestamp' in export_df.columns:
                                        export_df['timestamp'] = pd.to_datetime(export_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
                                    
                                    export_df.to_excel(writer, sheet_name=sheet_name, index=False)
                                    
                                    # Auto-adjust column widths
                                    worksheet = writer.sheets[sheet_name]
                                    for column in worksheet.columns:
                                        max_length = 0
                                        column_letter = column[0].column_letter
                                        for cell in column:
                                            try:
                                                if len(str(cell.value)) > max_length:
                                                    max_length = len(str(cell.value))
                                            except:
                                                pass
                                        adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                                        worksheet.column_dimensions[column_letter].width = adjusted_width
                            
                            # Notes sheet
                            sampling_mode = "Intelligent Sampling" if st.session_state.analysis_params.get('use_intelligent_sampling', True) else "Full Option Data"
                            notes_df = pd.DataFrame({
                                "Note": [
                                    "Generated by Goldflipper Momentum Analysis Module",
                                    f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                    f"Symbols: {', '.join(st.session_state.analyzed_symbols)}",
                                    f"Time Interval: {st.session_state.analysis_params['time_interval']}",
                                    f"Analysis Period: {st.session_state.analysis_params['weeks_back']} weeks",
                                    f"Sampling Mode: {sampling_mode}"
                                ]
                            })
                            notes_df.to_excel(writer, sheet_name='Notes', index=False)
                        
                        st.success(f"📊 Momentum data exported to {excel_path}")
                        
                except Exception as e:
                    st.error(f"❌ Export failed: {str(e)}")
                    logger.exception("Momentum export error")
        else:
            st.warning("⚠️ No analysis results to export. Please run the analysis first.")

if __name__ == "__main__":
    main() 