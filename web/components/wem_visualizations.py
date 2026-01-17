"""
WEM Visualization Components

Provides Plotly-based visualizations for Weekly Expected Move data.
Includes market chart visualizations with WEM levels overlaid on candlestick charts.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# MARKET CHART VISUALIZATION - Candlestick with WEM Levels
# ============================================================================

def render_wem_market_chart():
    """
    Render an interactive market chart with WEM levels for a selected symbol.
    Shows candlestick OHLC data with horizontal lines for WEM price levels.
    """
    with st.expander("📈 Market Chart with WEM Levels", expanded=False):
        st.caption("Technical analysis chart with Weekly Expected Move levels overlaid")
        
        stocks_data = st.session_state.get('wem_stocks_data', [])
        if not stocks_data:
            st.info("No WEM data available. Update data first to view market charts.")
            return
        
        # Get list of symbols with valid data
        symbols = [s.get('symbol') for s in stocks_data if s.get('symbol') and s.get('atm_price')]
        if not symbols:
            st.info("No symbols with valid WEM data available.")
            return
        
        # Symbol selector
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            selected_symbol = st.selectbox(
                "Select Symbol",
                symbols,
                key="wem_chart_symbol"
            )
        
        with col2:
            period = st.selectbox(
                "Period",
                ["5d", "1mo", "3mo", "6mo", "1y"],
                index=1,
                key="wem_chart_period"
            )
        
        with col3:
            interval = st.selectbox(
                "Interval",
                ["15m", "30m", "1h", "1d"],
                index=2 if period in ["5d"] else 3,
                key="wem_chart_interval"
            )
        
        # Get WEM data for selected symbol
        wem_data = next((s for s in stocks_data if s.get('symbol') == selected_symbol), None)
        if not wem_data:
            st.warning(f"No WEM data found for {selected_symbol}")
            return
        
        # Render the chart
        _render_candlestick_with_wem_levels(selected_symbol, wem_data, period, interval)


def _fetch_ohlc_data(symbol: str, period: str = "1mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    """
    Fetch OHLC data for a symbol using yfinance.
    
    Args:
        symbol: Stock ticker symbol
        period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, etc.)
        interval: Data interval (1m, 5m, 15m, 30m, 1h, 1d, etc.)
    
    Returns:
        DataFrame with OHLC data or None if fetch fails
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)
        
        if data.empty:
            logger.warning(f"No OHLC data returned for {symbol}")
            return None
        
        # Ensure we have the required columns
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in data.columns for col in required_cols):
            logger.warning(f"Missing required OHLC columns for {symbol}")
            return None
        
        return data
        
    except Exception as e:
        logger.error(f"Error fetching OHLC data for {symbol}: {e}")
        return None


def _render_candlestick_with_wem_levels(
    symbol: str, 
    wem_data: Dict[str, Any], 
    period: str = "1mo", 
    interval: str = "1d"
):
    """
    Render a Plotly candlestick chart with WEM levels as horizontal lines.
    
    Args:
        symbol: Stock ticker symbol
        wem_data: Dictionary containing WEM calculation results
        period: Data period for chart
        interval: Data interval for chart
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    # Fetch OHLC data
    with st.spinner(f"Loading chart data for {symbol}..."):
        ohlc_data = _fetch_ohlc_data(symbol, period, interval)
    
    if ohlc_data is None or ohlc_data.empty:
        st.warning(f"Could not fetch price data for {symbol}. Please try again.")
        return
    
    # Extract WEM levels
    atm_price = wem_data.get('atm_price')
    s1 = wem_data.get('straddle_1')  # Lower bound (Stock Price - WEM Points)
    s2 = wem_data.get('straddle_2')  # Upper bound (Stock Price + WEM Points)
    delta_16_plus = wem_data.get('delta_16_plus')  # Upper delta strike
    delta_16_minus = wem_data.get('delta_16_minus')  # Lower delta strike
    wem_points = wem_data.get('wem_points')
    
    # Create figure with secondary y-axis for volume
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.8, 0.2],
        subplot_titles=(f'{symbol} - Price with WEM Levels', 'Volume')
    )
    
    # Add candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=ohlc_data.index,
            open=ohlc_data['Open'],
            high=ohlc_data['High'],
            low=ohlc_data['Low'],
            close=ohlc_data['Close'],
            name='Price',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350',
            increasing_fillcolor='#26a69a',
            decreasing_fillcolor='#ef5350'
        ),
        row=1, col=1
    )
    
    # Add volume bars
    colors = ['#26a69a' if close >= open else '#ef5350' 
              for close, open in zip(ohlc_data['Close'], ohlc_data['Open'])]
    fig.add_trace(
        go.Bar(
            x=ohlc_data.index,
            y=ohlc_data['Volume'],
            name='Volume',
            marker_color=colors,
            opacity=0.5
        ),
        row=2, col=1
    )
    
    # Get x-axis range for horizontal lines
    x_start = ohlc_data.index[0]
    x_end = ohlc_data.index[-1]
    
    # Add WEM horizontal lines
    wem_lines = []
    
    # ATM Price line (current price reference)
    if atm_price is not None:
        wem_lines.append({
            'y': atm_price,
            'color': 'rgba(255, 193, 7, 0.8)',  # Amber
            'dash': 'solid',
            'name': f'ATM: ${atm_price:.2f}',
            'width': 2
        })
    
    # S2 - Upper Expected Move Bound
    if s2 is not None:
        wem_lines.append({
            'y': s2,
            'color': 'rgba(76, 175, 80, 0.8)',  # Green
            'dash': 'dash',
            'name': f'S2 (Upper): ${s2:.2f}',
            'width': 2
        })
    
    # S1 - Lower Expected Move Bound
    if s1 is not None:
        wem_lines.append({
            'y': s1,
            'color': 'rgba(244, 67, 54, 0.8)',  # Red
            'dash': 'dash',
            'name': f'S1 (Lower): ${s1:.2f}',
            'width': 2
        })
    
    # Delta 16+ (Upper probability bound)
    if delta_16_plus is not None:
        wem_lines.append({
            'y': delta_16_plus,
            'color': 'rgba(33, 150, 243, 0.7)',  # Blue
            'dash': 'dot',
            'name': f'Δ16+: ${delta_16_plus:.2f}',
            'width': 1.5
        })
    
    # Delta 16- (Lower probability bound)
    if delta_16_minus is not None:
        wem_lines.append({
            'y': delta_16_minus,
            'color': 'rgba(156, 39, 176, 0.7)',  # Purple
            'dash': 'dot',
            'name': f'Δ16-: ${delta_16_minus:.2f}',
            'width': 1.5
        })
    
    # Add horizontal lines to chart
    for line in wem_lines:
        fig.add_hline(
            y=line['y'],
            line_dash=line['dash'],
            line_color=line['color'],
            line_width=line['width'],
            annotation_text=line['name'],
            annotation_position="right",
            annotation_font_size=10,
            row=1, col=1
        )
        # Add scatter trace for legend
        fig.add_trace(
            go.Scatter(
                x=[ohlc_data.index[0]],
                y=[line['y']],
                mode='lines',
                name=line['name'],
                line=dict(color=line['color'], width=line['width'], dash=line['dash']),
                showlegend=True,
                hoverinfo='skip'
            ),
            row=1, col=1
        )
    
    # Add shaded region for expected move range (S1 to S2)
    if s1 is not None and s2 is not None:
        fig.add_hrect(
            y0=s1, y1=s2,
            fillcolor="rgba(100, 181, 246, 0.1)",  # Light blue fill
            line_width=0,
            row=1, col=1
        )
    
    # Update layout
    fig.update_layout(
        title=dict(
            text=f'{symbol} Weekly Expected Move Analysis',
            font=dict(size=16)
        ),
        xaxis_rangeslider_visible=False,
        height=650,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="rgba(128,128,128,0.3)",
            borderwidth=1,
            font=dict(size=10)
        ),
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    
    # Update axes
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(128,128,128,0.2)',
        showline=True,
        linewidth=1,
        linecolor='rgba(128,128,128,0.5)'
    )
    
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor='rgba(128,128,128,0.2)',
        showline=True,
        linewidth=1,
        linecolor='rgba(128,128,128,0.5)',
        title_text="Price ($)",
        row=1, col=1
    )
    
    fig.update_yaxes(
        title_text="Volume",
        row=2, col=1
    )
    
    # Display the chart
    st.plotly_chart(fig, use_container_width=True)
    
    # Display WEM level summary below chart
    _render_wem_level_legend(wem_data)


def _render_wem_level_legend(wem_data: Dict[str, Any]):
    """Render a legend/summary of WEM levels below the chart."""
    atm_price = wem_data.get('atm_price')
    s1 = wem_data.get('straddle_1')
    s2 = wem_data.get('straddle_2')
    delta_16_plus = wem_data.get('delta_16_plus')
    delta_16_minus = wem_data.get('delta_16_minus')
    wem_points = wem_data.get('wem_points')
    wem_spread = wem_data.get('wem_spread')
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("**Price Levels**")
        if atm_price:
            st.markdown(f"🟡 ATM: **${atm_price:.2f}**")
        if s2:
            st.markdown(f"🟢 S2 (Upper): **${s2:.2f}**")
        if s1:
            st.markdown(f"🔴 S1 (Lower): **${s1:.2f}**")
    
    with col2:
        st.markdown("**Delta Levels**")
        if delta_16_plus:
            st.markdown(f"🔵 Δ16+: **${delta_16_plus:.2f}**")
        if delta_16_minus:
            st.markdown(f"🟣 Δ16-: **${delta_16_minus:.2f}**")
    
    with col3:
        st.markdown("**WEM Metrics**")
        if wem_points:
            st.markdown(f"📊 WEM Points: **${wem_points:.2f}**")
        if wem_spread:
            st.markdown(f"📈 WEM Spread: **{wem_spread*100:.2f}%**")
    
    with col4:
        st.markdown("**Ranges**")
        if s1 and s2:
            range_pct = ((s2 - s1) / atm_price * 100) if atm_price else 0
            st.markdown(f"📐 S1-S2 Range: **${s2-s1:.2f}** ({range_pct:.1f}%)")
        if delta_16_plus and delta_16_minus:
            delta_range = delta_16_plus - delta_16_minus
            st.markdown(f"📏 Δ16 Range: **${delta_range:.2f}**")


# ============================================================================
# MULTI-SYMBOL COMPARISON CHART
# ============================================================================

def render_wem_comparison_chart():
    """
    Render a comparison chart showing multiple symbols' WEM ranges on mini-charts.
    """
    with st.expander("📊 Multi-Symbol WEM Comparison", expanded=False):
        st.caption("Compare WEM levels across multiple symbols")
        
        stocks_data = st.session_state.get('wem_stocks_data', [])
        if not stocks_data:
            st.info("No WEM data available. Update data first.")
            return
        
        # Filter symbols with valid data
        valid_stocks = [s for s in stocks_data if s.get('atm_price') and s.get('straddle_1') and s.get('straddle_2')]
        if len(valid_stocks) < 2:
            st.info("Need at least 2 symbols with complete WEM data for comparison.")
            return
        
        symbols = [s.get('symbol') for s in valid_stocks]
        
        # Let user select symbols to compare
        selected = st.multiselect(
            "Select symbols to compare (2-6 recommended)",
            symbols,
            default=symbols[:min(4, len(symbols))],
            key="wem_compare_symbols"
        )
        
        if len(selected) < 2:
            st.info("Select at least 2 symbols to compare.")
            return
        
        # Create comparison visualization
        _render_multi_symbol_wem_chart(selected, valid_stocks)


def _render_multi_symbol_wem_chart(symbols: List[str], stocks_data: List[Dict]):
    """Render a chart comparing WEM ranges across multiple symbols."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    # Create subplots - one row per symbol
    fig = make_subplots(
        rows=len(symbols), 
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.05,
        subplot_titles=symbols
    )
    
    # Add legend traces only once
    legend_added = False
    
    for i, symbol in enumerate(symbols, 1):
        stock_data = next((s for s in stocks_data if s.get('symbol') == symbol), None)
        if not stock_data:
            continue
        
        # Fetch recent price data
        ohlc = _fetch_ohlc_data(symbol, period="5d", interval="1h")
        if ohlc is None or ohlc.empty:
            continue
        
        # Add candlestick
        fig.add_trace(
            go.Candlestick(
                x=ohlc.index,
                open=ohlc['Open'],
                high=ohlc['High'],
                low=ohlc['Low'],
                close=ohlc['Close'],
                name=symbol,
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350',
                showlegend=False
            ),
            row=i, col=1
        )
        
        # Add WEM lines
        s1 = stock_data.get('straddle_1')
        s2 = stock_data.get('straddle_2')
        atm = stock_data.get('atm_price')
        
        if s2:
            fig.add_hline(y=s2, line_dash="dash", line_color="green", 
                         annotation_text=f"S2: ${s2:.0f}", row=i, col=1)
        if s1:
            fig.add_hline(y=s1, line_dash="dash", line_color="red",
                         annotation_text=f"S1: ${s1:.0f}", row=i, col=1)
        if atm:
            fig.add_hline(y=atm, line_dash="solid", line_color="orange",
                         annotation_text=f"ATM: ${atm:.0f}", row=i, col=1)
        
        # Add shaded WEM range
        if s1 and s2:
            fig.add_hrect(y0=s1, y1=s2, fillcolor="rgba(100, 181, 246, 0.1)", 
                         line_width=0, row=i, col=1)
        
        # Add legend traces only for first symbol
        if not legend_added and ohlc is not None and not ohlc.empty:
            legend_items = [
                {'name': 'ATM (Current Price)', 'color': 'orange', 'dash': 'solid'},
                {'name': 'S2 (Upper Bound)', 'color': 'green', 'dash': 'dash'},
                {'name': 'S1 (Lower Bound)', 'color': 'red', 'dash': 'dash'},
            ]
            for item in legend_items:
                fig.add_trace(
                    go.Scatter(
                        x=[ohlc.index[0]],
                        y=[atm if atm else ohlc['Close'].iloc[0]],
                        mode='lines',
                        name=item['name'],
                        line=dict(color=item['color'], width=2, dash=item['dash']),
                        showlegend=True,
                        hoverinfo='skip',
                        visible='legendonly'
                    ),
                    row=1, col=1
                )
            legend_added = True
    
    fig.update_layout(
        height=250 * len(symbols) + 50,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.05,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="rgba(128,128,128,0.3)",
            borderwidth=1,
            font=dict(size=10),
            title=dict(text="WEM Levels: ", font=dict(size=10))
        ),
        xaxis_rangeslider_visible=False
    )
    
    # Hide all range sliders
    for i in range(1, len(symbols) + 1):
        fig.update_xaxes(rangeslider_visible=False, row=i, col=1)
    
    st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# ORIGINAL TABLE-BASED VISUALIZATIONS
# ============================================================================

def render_wem_visualizations():
    """
    Render the WEM visualization section with tabs for different chart types.
    Reads data from st.session_state.wem_stocks_data.
    """
    with st.expander("📊 WEM Visualizations", expanded=False):
        st.caption("Visual analysis of Weekly Expected Move data")
        
        stocks_data = st.session_state.get('wem_stocks_data', [])
        if not stocks_data:
            st.info("No WEM data available for visualization. Update data first.")
            return
        
        viz_tab1, viz_tab2, viz_tab3 = st.tabs(["📈 Expected Range", "📊 WEM Spread", "🎯 Delta Range"])
        
        viz_df = pd.DataFrame(stocks_data)
        viz_df = viz_df[viz_df['atm_price'].notna()]
        
        if viz_df.empty:
            st.info("No data with valid ATM prices for visualization.")
            return
        
        with viz_tab1:
            _render_expected_range_chart(viz_df)
        
        with viz_tab2:
            _render_wem_spread_chart(viz_df)
        
        with viz_tab3:
            _render_delta_range_chart(viz_df)


def _render_expected_range_chart(viz_df: pd.DataFrame):
    """Render the Expected Price Range (S1 to S2) chart."""
    st.markdown("**Expected Price Range (S1 to S2)**")
    try:
        import plotly.graph_objects as go
        range_df = viz_df[['symbol', 'atm_price', 'straddle_1', 'straddle_2']].dropna()
        if range_df.empty:
            st.info("No data available for range chart.")
            return
        
        fig = go.Figure()
        for _, row in range_df.iterrows():
            fig.add_trace(go.Bar(
                x=[row['symbol']], 
                y=[row['straddle_2'] - row['straddle_1']],
                base=row['straddle_1'], 
                marker_color='rgba(55, 128, 191, 0.7)', 
                showlegend=False
            ))
            fig.add_trace(go.Scatter(
                x=[row['symbol']], 
                y=[row['atm_price']], 
                mode='markers',
                marker=dict(size=10, color='red', symbol='diamond'), 
                showlegend=False
            ))
        fig.update_layout(title="Weekly Expected Move Range", height=400)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.info(f"Range chart unavailable: {e}")


def _render_wem_spread_chart(viz_df: pd.DataFrame):
    """Render the WEM Spread % Comparison chart."""
    st.markdown("**WEM Spread % Comparison**")
    try:
        import plotly.express as px
        spread_df = viz_df[['symbol', 'wem_spread']].dropna()
        if spread_df.empty:
            st.info("No data available for spread chart.")
            return
        
        spread_df = spread_df.copy()
        spread_df['wem_spread_pct'] = spread_df['wem_spread'] * 100
        spread_df = spread_df.sort_values('wem_spread_pct', ascending=True)
        
        fig = px.bar(
            spread_df, 
            x='wem_spread_pct', 
            y='symbol', 
            orientation='h',
            color='wem_spread_pct', 
            color_continuous_scale='RdYlGn_r'
        )
        fig.update_layout(height=max(400, len(spread_df) * 25))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.info(f"Spread chart unavailable: {e}")


def _render_delta_range_chart(viz_df: pd.DataFrame):
    """Render the Delta 16 Range Analysis chart."""
    st.markdown("**Delta 16 Range Analysis**")
    try:
        import plotly.graph_objects as go
        delta_df = viz_df[['symbol', 'atm_price', 'delta_16_plus', 'delta_16_minus']].dropna()
        if delta_df.empty:
            st.info("No data available for delta chart.")
            return
        
        fig = go.Figure()
        for _, row in delta_df.iterrows():
            fig.add_trace(go.Scatter(
                x=[row['symbol']], 
                y=[row['atm_price']], 
                mode='markers',
                error_y=dict(
                    type='data', 
                    symmetric=False,
                    array=[row['delta_16_plus'] - row['atm_price']],
                    arrayminus=[row['atm_price'] - row['delta_16_minus']]
                ),
                marker=dict(size=12, color='darkblue'), 
                showlegend=False
            ))
        fig.update_layout(title="Delta 16 Range by Symbol", height=400)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.info(f"Delta chart unavailable: {e}")
