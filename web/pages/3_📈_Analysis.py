import streamlit as st
import sys
import os
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from goldflipper.config.config import config

# Page configuration
st.set_page_config(
    page_title="Goldflipper Analysis",
    page_icon="📈",
    layout="wide"
)

def create_performance_metrics():
    """Create mock performance metrics"""
    return {
        'Total Trades': 156,
        'Winning Trades': 98,
        'Losing Trades': 58,
        'Win Rate': '62.8%',
        'Average Win': '$245.50',
        'Average Loss': '-$125.75',
        'Profit Factor': 1.95,
        'Max Drawdown': '-12.5%',
        'Sharpe Ratio': 1.85,
        'Sortino Ratio': 2.12
    }

def create_equity_curve():
    """Create a mock equity curve"""
    dates = pd.date_range(start=datetime.now() - timedelta(days=90), end=datetime.now(), freq='D')
    values = [10000 + i * 50 + (i % 7) * 100 for i in range(len(dates))]
    df = pd.DataFrame({'Date': dates, 'Portfolio Value': values})
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['Portfolio Value'],
        mode='lines',
        name='Portfolio Value'
    ))
    fig.update_layout(
        title='Equity Curve (Last 90 Days)',
        xaxis_title='Date',
        yaxis_title='Portfolio Value ($)',
        height=400
    )
    return fig

def create_trade_distribution():
    """Create a mock trade distribution chart"""
    data = {
        'Strategy': ['Options Swings', 'Spreads', 'Scalping', 'Day Trading'],
        'Trades': [45, 30, 25, 20],
        'P/L': [12000, 8000, 5000, 3000]
    }
    df = pd.DataFrame(data)
    
    fig = go.Figure(data=[
        go.Bar(name='Number of Trades', x=df['Strategy'], y=df['Trades']),
        go.Bar(name='P/L ($)', x=df['Strategy'], y=df['P/L'])
    ])
    fig.update_layout(
        title='Trade Distribution by Strategy',
        barmode='group',
        height=400
    )
    return fig

def create_monthly_performance():
    """Create a mock monthly performance table"""
    data = {
        'Month': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        'Trades': [25, 28, 22, 30, 26, 25],
        'Win Rate': ['65%', '68%', '63%', '70%', '67%', '65%'],
        'P/L': ['$2,450', '$2,850', '$2,150', '$3,200', '$2,750', '$2,450'],
        'ROI': ['+12.5%', '+14.2%', '+10.8%', '+16.0%', '+13.8%', '+12.3%']
    }
    return pd.DataFrame(data)

def main():
    st.title("Trading Analysis")
    
    # Performance Metrics
    st.subheader("Performance Metrics")
    metrics = create_performance_metrics()
    
    # Create columns based on the number of metrics
    num_metrics = len(metrics)
    num_cols = min(5, num_metrics)  # Limit to 5 columns max
    cols = st.columns(num_cols)
    
    # Display metrics in columns
    for i, (key, value) in enumerate(metrics.items()):
        col_idx = i % num_cols  # Use modulo to wrap around if we have more metrics than columns
        with cols[col_idx]:
            st.metric(key, value)
    
    # Charts
    st.subheader("Performance Analysis")
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(create_equity_curve(), use_container_width=True)
    with chart_col2:
        st.plotly_chart(create_trade_distribution(), use_container_width=True)
    
    # Monthly Performance
    st.subheader("Monthly Performance")
    monthly_df = create_monthly_performance()
    st.dataframe(monthly_df, use_container_width=True)
    
    # Strategy Analysis
    st.subheader("Strategy Analysis")
    strategy_col1, strategy_col2 = st.columns(2)
    with strategy_col1:
        st.markdown("### Best Performing Strategy")
        st.markdown("""
        **Options Swings**
        - Total Trades: 45
        - Win Rate: 68.9%
        - Average P/L: $266.67
        - Max Drawdown: -8.5%
        """)
    with strategy_col2:
        st.markdown("### Areas for Improvement")
        st.markdown("""
        **Day Trading**
        - Total Trades: 20
        - Win Rate: 55.0%
        - Average P/L: $150.00
        - Max Drawdown: -15.2%
        """)
    
    # Risk Analysis
    st.subheader("Risk Analysis")
    risk_col1, risk_col2, risk_col3 = st.columns(3)
    with risk_col1:
        st.metric("Average Daily Drawdown", "-2.5%")
    with risk_col2:
        st.metric("Value at Risk (95%)", "-$1,250")
    with risk_col3:
        st.metric("Expected Shortfall", "-$1,850")

if __name__ == "__main__":
    main() 