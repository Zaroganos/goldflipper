"""
Weekly Expected Moves (WEM) Analysis Tool

This page provides functionality for:
1. Viewing and managing WEM stock list
2. Calculating and displaying expected moves
3. Exporting data to Excel
4. Managing user preferences for WEM stocks
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
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
    
    The calculation uses:
    1. Current ATM straddle price
    2. Historical volatility
    3. Market implied move (from options chain)
    4. Delta-based boundaries
    """
    symbol = stock_data['symbol']
    
    # First try to get latest data from database
    market_data = get_latest_market_data(session, symbol)
    
    # If no recent data or data is old, update it
    if not market_data or (datetime.utcnow() - market_data.timestamp).total_seconds() > 300:  # 5 minutes
        market_data = update_market_data(session, symbol)
    
    if not market_data:
        return None
    
    # Get historical data for volatility calculation
    historical_data = get_market_data(session, symbol, days=20)
    
    # Calculate historical volatility (20-day)
    if len(historical_data) >= 20:
        closes = [d.close for d in historical_data]
        returns = np.diff(np.log(closes)) * 100
        hist_vol = np.std(returns) * np.sqrt(252)  # Annualized
    else:
        hist_vol = 0
    
    # Use market implied volatility if available, otherwise use historical
    iv = market_data.implied_volatility if market_data.implied_volatility else hist_vol
    
    # Calculate expected move components
    weekly_factor = np.sqrt(5/252)  # Weekly time decay factor
    weekly_vol = iv * weekly_factor
    
    # Get current price
    atm_price = market_data.close
    
    # Calculate straddle values
    straddle_strangle = atm_price * weekly_vol * 0.4  # Approximate straddle price
    
    # Calculate WEM spread (as percentage of price)
    wem_spread = weekly_vol * 0.5  # Expected 1-week move (50% of weekly vol)
    
    # Calculate delta-based moves
    delta_16_plus = atm_price * (1 + wem_spread * 1.5)  # +1.5 standard deviations
    delta_16_minus = atm_price * (1 - wem_spread * 1.5)  # -1.5 standard deviations
    
    # Calculate straddle levels
    straddle_1 = atm_price * (1 + weekly_vol * 0.3)  # 30% of weekly vol
    straddle_2 = atm_price * (1 + weekly_vol * 0.7)  # 70% of weekly vol
    
    # Calculate range values
    delta_range = delta_16_plus - delta_16_minus
    delta_range_pct = delta_range / atm_price
    
    return {
        'atm_price': atm_price,
        'straddle_strangle': straddle_strangle,
        'wem_spread': wem_spread,
        'delta_16_plus': delta_16_plus,
        'straddle_2': straddle_2,
        'straddle_1': straddle_1,
        'delta_16_minus': delta_16_minus,
        'delta_range': delta_range,
        'delta_range_pct': delta_range_pct,
        'last_updated': market_data.timestamp,
        'meta_data': {
            'historical_volatility': hist_vol,
            'implied_volatility': iv,
            'weekly_volatility': weekly_vol,
            'calculation_timestamp': datetime.utcnow().isoformat(),
            'data_source': market_data.source
        }
    }

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
            'Straddle/Strangle': stock.get('straddle_strangle'),
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
    st.title("Weekly Expected Moves (WEM)")
    
    # Initialize database if needed
    try:
        init_db()
    except Exception as e:
        st.error(f"Error initializing database: {str(e)}")
        return
    
    # Get database session
    try:
        with get_db_connection() as session:
            # Initialize session state
            if 'wem_stocks' not in st.session_state:
                st.session_state.wem_stocks = get_wem_stocks(session)
            if 'layout' not in st.session_state:
                st.session_state.layout = 'vertical'
            
            # Sidebar
            with st.sidebar:
                st.subheader("WEM Settings")
                
                # Layout Selection
                st.markdown("### Display Settings")
                layout = st.radio(
                    "Table Layout",
                    ["Vertical", "Horizontal"],
                    index=0 if st.session_state.layout == 'vertical' else 1,
                    key="layout_selection"
                )
                st.session_state.layout = layout.lower()
                
                # Stock Selection
                st.markdown("### Add Stock")
                new_stock = st.text_input("Stock Symbol")
                is_default = st.checkbox("Add as Default Stock")
                
                if st.button("Add Stock") and new_stock:
                    try:
                        stock = add_wem_stock(session, new_stock.upper(), is_default)
                        st.success(f"Added {stock['symbol']}")
                        st.session_state.wem_stocks = get_wem_stocks(session)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding stock: {str(e)}")
                
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
                            if remove_wem_stock(session, stock['symbol']):
                                st.success(f"Removed {stock['symbol']}")
                                st.session_state.wem_stocks = get_wem_stocks(session)
                                st.rerun()
                
                # Update Settings
                st.markdown("### Update Settings")
                if st.button("Update All Data"):
                    with st.spinner("Updating WEM data..."):
                        for stock in st.session_state.wem_stocks:
                            # Calculate new values
                            new_data = calculate_expected_move(session, {'symbol': stock['symbol']})
                            
                            if new_data:
                                # Update stock data
                                update_data = {
                                    'symbol': stock['symbol'],
                                    **new_data
                                }
                                if update_wem_stock(session, update_data):
                                    st.success(f"Updated {stock['symbol']}")
                                else:
                                    st.error(f"Failed to update {stock['symbol']}")
                            else:
                                st.warning(f"No market data available for {stock['symbol']}")
                        
                        st.session_state.wem_stocks = get_wem_stocks(session)
                        st.rerun()
            
            # Main Content
            if not st.session_state.wem_stocks:
                st.warning("No stocks selected. Please add stocks in the sidebar.")
            else:
                # Create and display WEM table
                wem_df = create_wem_table(st.session_state.wem_stocks, st.session_state.layout)
                
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
                        "Straddle/Strangle": st.column_config.NumberColumn(
                            "Straddle/Strangle",
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
                            format="%.2f"
                        ),
                        "Straddle 1": st.column_config.NumberColumn(
                            "Straddle 1",
                            format="%.2f"
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
                            update_data = {
                                'symbol': stock['symbol'],
                                'notes': notes
                            }
                            if update_wem_stock(session, update_data):
                                st.success("Notes updated")
                                # Refresh stock data
                                st.session_state.wem_stocks = get_wem_stocks(session)
                            else:
                                st.error("Failed to update notes")
                        
                        # Show calculation metadata if available
                        if stock.get('meta_data'):
                            st.markdown("### Calculation Details")
                            st.json(stock['meta_data'])
                
                # Export to Excel
                if st.button("Export to Excel"):
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
                    
                    st.success(f"Data exported to {excel_path}")
                
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
        st.error(f"Database error: {str(e)}")

if __name__ == "__main__":
    main() 