import streamlit as st
import sys
import os
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from goldflipper.config.config import config

# Page configuration
st.set_page_config(
    page_title="GoldFlipper Trading",
    page_icon="💹",
    layout="wide"
)

def create_option_chain():
    """Create a mock option chain"""
    data = {
        'Strike': [440, 445, 450, 455, 460],
        'Bid': [12.50, 8.75, 5.25, 2.75, 1.25],
        'Ask': [12.75, 9.00, 5.50, 3.00, 1.50],
        'Volume': [150, 200, 300, 250, 100],
        'OI': [500, 750, 1000, 800, 400],
        'IV': ['25%', '24%', '23%', '22%', '21%']
    }
    return pd.DataFrame(data)

def create_position_table():
    """Create a mock positions table"""
    data = {
        'Symbol': ['SPY', 'AAPL', 'QQQ', 'NVDA', 'MSFT'],
        'Type': ['CALL', 'PUT', 'CALL', 'CALL', 'PUT'],
        'Strike': [450, 180, 380, 800, 320],
        'Expiry': ['2024-03-15', '2024-03-15', '2024-03-15', '2024-03-15', '2024-03-15'],
        'Entry': [5.25, 3.75, 8.50, 15.25, 4.50],
        'Current': [6.75, 3.25, 9.25, 16.50, 4.00],
        'P/L': ['+$150', '-$50', '+$75', '+$125', '-$50'],
        'Status': ['🟢', '🔴', '🟢', '🟢', '🔴']
    }
    return pd.DataFrame(data)

def main():
    st.title("Trading Interface")
    
    # Trading Controls
    st.subheader("Trading Controls")
    control_col1, control_col2, control_col3 = st.columns(3)
    with control_col1:
        if st.button("Start Trading", type="primary"):
            st.success("Trading system started")
    with control_col2:
        if st.button("Stop Trading"):
            st.warning("Trading system stopped")
    with control_col3:
        if st.button("Emergency Close All"):
            st.error("All positions closed")
    
    # Active Positions
    st.subheader("Active Positions")
    positions_df = create_position_table()
    st.dataframe(positions_df, use_container_width=True)
    
    # Order Entry
    st.subheader("New Order")
    order_col1, order_col2 = st.columns(2)
    with order_col1:
        symbol = st.text_input("Symbol", "SPY")
        order_type = st.selectbox("Order Type", ["Market", "Limit", "Stop", "Stop Limit"])
        side = st.selectbox("Side", ["Buy", "Sell"])
        quantity = st.number_input("Quantity", min_value=1, value=1)
    
    with order_col2:
        if order_type in ["Limit", "Stop Limit"]:
            price = st.number_input("Price", min_value=0.01, value=0.01, step=0.01)
        if order_type in ["Stop", "Stop Limit"]:
            stop_price = st.number_input("Stop Price", min_value=0.01, value=0.01, step=0.01)
        time_in_force = st.selectbox("Time In Force", ["Day", "GTC", "IOC"])
    
    if st.button("Place Order", type="primary"):
        st.success("Order placed successfully!")
    
    # Option Chain
    st.subheader("Option Chain")
    chain_df = create_option_chain()
    st.dataframe(chain_df, use_container_width=True)
    
    # Order History
    st.subheader("Order History")
    history_data = {
        'Time': ['10:15 AM', '10:00 AM', '9:45 AM', '9:30 AM', '9:15 AM'],
        'Symbol': ['SPY', 'AAPL', 'QQQ', 'NVDA', 'MSFT'],
        'Type': ['CALL', 'PUT', 'CALL', 'CALL', 'PUT'],
        'Action': ['Buy', 'Sell', 'Buy', 'Buy', 'Sell'],
        'Price': ['5.25', '3.75', '8.50', '15.25', '4.50'],
        'Status': ['✅', '✅', '✅', '✅', '✅']
    }
    st.table(pd.DataFrame(history_data))

if __name__ == "__main__":
    main() 