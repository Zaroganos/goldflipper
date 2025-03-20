import streamlit as st
import sys
import os
from pathlib import Path
import subprocess
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from goldflipper.config.config import config

# Page configuration
st.set_page_config(
    page_title="GoldFlipper Home",
    page_icon="🏠",
    layout="wide"
)

def create_performance_chart():
    """Create a mock performance chart for the last 30 days"""
    dates = [(datetime.now() - timedelta(days=x)).strftime('%Y-%m-%d') for x in range(30)]
    values = [100 + x * 2 for x in range(30)]  # Mock data
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=values, mode='lines', name='Portfolio Value'))
    fig.update_layout(title='Portfolio Performance (Last 30 Days)', height=300)
    return fig

def create_play_status_chart():
    """Create a mock pie chart of play statuses"""
    labels = ['Active', 'Pending', 'Closed', 'Expired']
    values = [30, 20, 40, 10]  # Mock data
    fig = go.Figure(data=[go.Pie(labels=labels, values=values)])
    fig.update_layout(title='Play Status Distribution', height=300)
    return fig

def run_command(cmd):
    """Run a command in a new window"""
    try:
        if os.name == 'nt':  # Windows
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:  # Unix-like systems
            subprocess.Popen(['gnome-terminal', '--'] + cmd)
    except Exception as e:
        st.error(f"Error: {str(e)}")

def main():
    st.title("Welcome to GoldFlipper")
    
    # Quick Stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Plays", "150")
    with col2:
        st.metric("Active Plays", "30")
    with col3:
        st.metric("Today's P/L", "$1,234.56")
    with col4:
        st.metric("Win Rate", "65%")
    
    # Quick Actions
    st.subheader("Quick Actions")
    action_col1, action_col2, action_col3 = st.columns(3)
    with action_col1:
        if st.button("Create New Play", use_container_width=True):
            run_command(['cmd', '/k', 'cd', '/d', os.path.join(project_root, "tools"), '&', 'python', 'play_creation_tool.py'])
    with action_col2:
        if st.button("View Active Positions", use_container_width=True):
            st.switch_page("pages/2_💹_Trading.py")
    with action_col3:
        if st.button("Run Analysis", use_container_width=True):
            st.switch_page("pages/3_📈_Analysis.py")
    
    # Charts
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(create_performance_chart(), use_container_width=True)
    with chart_col2:
        st.plotly_chart(create_play_status_chart(), use_container_width=True)
    
    # Recent Activity
    st.subheader("Recent Activity")
    recent_data = {
        'Time': ['10:30 AM', '10:15 AM', '10:00 AM', '09:45 AM', '09:30 AM'],
        'Action': ['Closed Play', 'Opened Position', 'Created Play', 'Modified Play', 'Closed Play'],
        'Symbol': ['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA'],
        'Status': ['Success', 'Success', 'Success', 'Success', 'Success']
    }
    st.dataframe(pd.DataFrame(recent_data), use_container_width=True)
    
    # Market Status
    st.subheader("Market Status")
    status_col1, status_col2, status_col3 = st.columns(3)
    with status_col1:
        st.metric("Market Open", "09:30 AM")
    with status_col2:
        st.metric("Market Close", "04:00 PM")
    with status_col3:
        st.metric("Time Until Close", "5h 30m")
    
    # Main Menu
    st.markdown("---")
    st.subheader("Main Menu")
    
    # Create two columns for buttons
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Trading Operations")
        if st.button("Fetch Option Data", use_container_width=True):
            run_command(['cmd', '/k', 'cd', '/d', os.path.join(project_root, "tools"), '&', 'python', 'option_data_fetcher.py'])
            
        if st.button("Launch Trading System", use_container_width=True):
            run_command(['cmd', '/k', 'python', '-m', 'goldflipper.run'])
            
        if st.button("Auto Play Creator", use_container_width=True):
            run_command(['cmd', '/k', 'cd', '/d', os.path.join(project_root, "tools"), '&', 'python', 'auto_play_creator.py'])
            
        if st.button("Get Alpaca Info", use_container_width=True):
            run_command(['cmd', '/k', 'cd', '/d', os.path.join(project_root, "tools"), '&', 'python', 'get_alpaca_info.py'])
            
        if st.button("Upload Template", use_container_width=True):
            run_command(['cmd', '/k', 'cd', '/d', os.path.join(project_root, "tools"), '&', 'python', 'play-csv-ingestion-tool.py'])
    
    with col2:
        st.subheader("Management & Analysis")
        if st.button("View / Edit Current Plays", use_container_width=True):
            run_command(['cmd', '/k', 'cd', '/d', os.path.join(project_root, "tools"), '&', 'python', 'view_plays.py'])
            
        if st.button("Upkeep and Status", use_container_width=True):
            run_command(['cmd', '/k', 'cd', '/d', os.path.join(project_root, "tools"), '&', 'python', 'system_status.py'])
            
        if st.button("Configuration", use_container_width=True):
            st.switch_page("pages/4_⚙️_Settings.py")
            
        if st.button("Open Chart", use_container_width=True):
            run_command(['cmd', '/k', 'cd', '/d', os.path.join(project_root, "chart"), '&', 'python', 'chart_viewer.py'])
            
        if st.button("Trade Logger", use_container_width=True):
            run_command(['cmd', '/k', 'cd', '/d', os.path.join(project_root, "logging"), '&', 'python', 'trade_logger_ui.py'])
            
        if st.button("Manage Service", use_container_width=True):
            if os.name != 'nt':
                st.error("Service management is available on Windows only.")
                return
                
            try:
                import win32serviceutil
                win32serviceutil.QueryServiceStatus("GoldFlipperService")
                service_installed = True
                message = "You are about to STOP and UNINSTALL the GoldFlipper Service."
                mode = "remove"
            except Exception:
                service_installed = False
                message = "You are about to INSTALL the Goldflipper Service and automatically start it."
                mode = "install"
                
            if st.button("Confirm Service Action", use_container_width=True):
                if mode == "install":
                    final_command = "python -m goldflipper.run --mode install; Start-Sleep -Seconds 2; net start GoldFlipperService"
                else:
                    final_command = "net stop GoldFlipperService; python -m goldflipper.run --mode remove"
                ps_command = f"Start-Process powershell -ArgumentList '-NoProfile -Command \"{final_command}\"' -Verb RunAs"
                subprocess.Popen(["powershell", "-Command", ps_command])
                st.success(f"{'Uninstallation' if service_installed else 'Installation'} initiated. Changes will require a reboot to apply.")

if __name__ == "__main__":
    main() 