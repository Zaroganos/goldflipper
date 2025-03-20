import streamlit as st
import sys
import os
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yaml

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from goldflipper.config.config import config
from goldflipper.core import monitor_plays_continuously
from goldflipper.utils.display import TerminalDisplay as display

# Page configuration
st.set_page_config(
    page_title="GoldFlipper Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

def init_session_state():
    """Initialize session state variables"""
    if 'current_account' not in st.session_state:
        st.session_state.current_account = config.get('alpaca', 'active_account')
    if 'trading_active' not in st.session_state:
        st.session_state.trading_active = False
    if 'last_update' not in st.session_state:
        st.session_state.last_update = None

def get_account_status(account_name):
    """Get the current status of the trading account"""
    try:
        # TODO: Implement actual account status check
        return True, "Connected"
    except Exception as e:
        return False, str(e)

def get_accounts():
    """Get configured accounts from settings"""
    try:
        settings_file = Path(project_root) / 'goldflipper' / 'config' / 'settings.yaml'
        if not settings_file.exists():
            st.warning("Settings file not found. Please run the setup wizard first.")
            return {}
            
        with open(settings_file, 'r') as f:
            settings = yaml.safe_load(f)
            if not settings:
                st.warning("Settings file is empty. Please run the setup wizard first.")
                return {}
                
            accounts = settings.get('alpaca', {}).get('accounts', {})
            if not accounts:
                st.warning("No trading accounts configured. Please set up your accounts in Settings.")
                return {}
                
            return {k: v for k, v in accounts.items() if v.get('enabled', False)}
    except Exception as e:
        st.error(f"Error loading accounts: {str(e)}")
        return {}

def create_performance_chart():
    """Create a mock performance chart"""
    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='D')
    values = [100 + i * 2 + (i % 3) * 3 for i in range(len(dates))]
    df = pd.DataFrame({'Date': dates, 'Portfolio Value': values})
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['Portfolio Value'],
        mode='lines',
        name='Portfolio Value'
    ))
    fig.update_layout(
        title='Portfolio Performance (Last 30 Days)',
        xaxis_title='Date',
        yaxis_title='Value ($)',
        height=400
    )
    return fig

def create_play_status_chart():
    """Create a mock play status chart"""
    statuses = ['New', 'Pending Opening', 'Open', 'Pending Closing', 'Closed', 'Expired']
    values = [5, 2, 8, 3, 12, 1]
    
    fig = go.Figure(data=[go.Pie(
        labels=statuses,
        values=values,
        hole=.3
    )])
    fig.update_layout(
        title='Current Play Status Distribution',
        height=400
    )
    return fig

def main():
    st.title("GoldFlipper Dashboard")
    
    # Get accounts with error handling
    accounts = get_accounts()
    if not accounts:
        return
    
    # Account Selection
    selected_account = st.selectbox(
        "Select Trading Account",
        options=list(accounts.keys()),
        format_func=lambda x: accounts[x].get('nickname', x)
    )
    
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.title("GoldFlipper")
        st.markdown("---")
        
        # Account Selection
        if selected_account != st.session_state.current_account:
            st.session_state.current_account = selected_account
            st.rerun()
        
        # Account Status
        is_connected, status = get_account_status(selected_account)
        status_color = "green" if is_connected else "red"
        st.markdown(f"Status: :{status_color}[{status}]")
        
        st.markdown("---")
        
        # Quick Actions
        st.subheader("Quick Actions")
        if st.button("Create New Play", use_container_width=True):
            st.session_state.page = "create_play"
        if st.button("View/Edit Plays", use_container_width=True):
            st.session_state.page = "view_plays"
        if st.button("Trade Logger", use_container_width=True):
            st.session_state.page = "trade_logger"
        if st.button("Settings", use_container_width=True):
            st.session_state.page = "settings"
    
    # Main Content
    st.title("GoldFlipper Dashboard")
    
    # Quick Stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Total Plays", value="31", delta="+2")
    with col2:
        st.metric(label="Active Plays", value="8", delta="-1")
    with col3:
        st.metric(label="Today's P/L", value="$245.50", delta="+$45.50")
    with col4:
        st.metric(label="Win Rate", value="68%", delta="+2%")
    
    # Quick Actions
    st.subheader("Quick Actions")
    action_col1, action_col2, action_col3 = st.columns(3)
    with action_col1:
        if st.button("Create New Play", type="primary"):
            st.info("Navigating to Play Creation...")
    with action_col2:
        if st.button("View Active Positions"):
            st.info("Navigating to Trading View...")
    with action_col3:
        if st.button("Run Analysis"):
            st.info("Navigating to Analysis...")
    
    # Charts
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(create_performance_chart(), use_container_width=True)
    with chart_col2:
        st.plotly_chart(create_play_status_chart(), use_container_width=True)
    
    # Recent Activity
    st.subheader("Recent Activity")
    activity_data = {
        'Time': ['10:15 AM', '10:00 AM', '9:45 AM', '9:30 AM', '9:15 AM'],
        'Action': ['Play Closed: SPY 450C', 'New Play Created: AAPL 180P', 'Position Opened: QQQ 380C', 
                  'Play Expired: MSFT 320C', 'Play Closed: NVDA 800C'],
        'Status': ['✅', '📝', '🔄', '⏰', '✅']
    }
    st.table(pd.DataFrame(activity_data))
    
    # Market Status
    st.subheader("Market Status")
    market_col1, market_col2, market_col3 = st.columns(3)
    with market_col1:
        st.metric(label="Market Open", value="09:30 AM")
    with market_col2:
        st.metric(label="Market Close", value="04:00 PM")
    with market_col3:
        st.metric(label="Time Until Close", value="2:15:30")

if __name__ == "__main__":
    main() 