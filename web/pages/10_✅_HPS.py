"""
HPS (High Probability Setups) Analysis Page

Validates KEP candidates with technical evidence to identify high-probability trade setups.
Part of the WEM → KEP → HPS workflow for the Options Swing strategy.

Key Features:
1. KEP input selection from KEP analysis or manual entry
2. Evidence Dashboard with visual checklist
3. Chart with RSI panel + EMA overlays + Volume
4. Trade Setup Card with recommended parameters
5. Export capabilities
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging
import sys

# Set up paths
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set up logging
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="HPS Analysis",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import components after path setup
try:
    from web.components.hps_analysis import (
        HPSAnalyzer, HPSResult, HPSEvidence, TradeSetup,
        analyze_hps_for_kep, batch_analyze_hps
    )
    from web.components.kep_analysis import KEPScore
    from goldflipper.data.indicators import RSICalculator, EMACalculator, MACDCalculator, MarketData
except ImportError as e:
    st.error(f"Failed to import required components: {e}")
    st.stop()


# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

def init_session_state():
    """Initialize session state variables for HPS page."""
    if 'hps_results' not in st.session_state:
        st.session_state.hps_results = []
    
    if 'selected_hps' not in st.session_state:
        st.session_state.selected_hps = None
    
    if 'trade_setups' not in st.session_state:
        st.session_state.trade_setups = []


init_session_state()


# ============================================================================
# DATA FETCHING UTILITIES
# ============================================================================

@st.cache_data(ttl=300)
def fetch_ohlc_cached(symbol: str, period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLC data with caching."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)
        if data.empty:
            return None
        return data
    except Exception as e:
        logger.error(f"Error fetching OHLC for {symbol}: {e}")
        return None


def get_ohlc_provider(period: str = "3mo"):
    """Return a function that fetches OHLC data for a symbol."""
    def provider(symbol: str) -> pd.DataFrame:
        return fetch_ohlc_cached(symbol, period=period, interval="1d")
    return provider


# ============================================================================
# HPS ANALYSIS FUNCTIONS
# ============================================================================

def run_hps_analysis_for_symbol(symbol: str, kep_data: dict = None) -> HPSResult:
    """
    Run HPS analysis for a single symbol.
    
    Args:
        symbol: Stock symbol
        kep_data: Optional KEP data dict
        
    Returns:
        HPSResult object
    """
    ohlc_data = fetch_ohlc_cached(symbol, period="3mo", interval="1d")
    if ohlc_data is None or len(ohlc_data) == 0:
        st.error(f"Could not fetch data for {symbol}")
        return None
    
    # If no KEP data provided, create minimal structure
    if kep_data is None:
        current_price = ohlc_data['Close'].iloc[-1] if not ohlc_data.empty else 0
        kep_data = {
            'symbol': symbol,
            'current_price': current_price,
            'score': 0,
            'rating': 'LOW',
            'matched_factors': [],
            'direction_bias': 'NEUTRAL',
            'nearest_level': None
        }
    
    return analyze_hps_for_kep(kep_data, ohlc_data)


def run_batch_hps_analysis(kep_candidates: list) -> list:
    """Run HPS analysis for multiple KEP candidates."""
    if not kep_candidates:
        return []
    
    # Convert KEPScore objects to dicts if needed
    kep_dicts = []
    for kep in kep_candidates:
        if hasattr(kep, 'to_dict'):
            kep_dicts.append(kep.to_dict())
        elif isinstance(kep, dict):
            kep_dicts.append(kep)
    
    return batch_analyze_hps(kep_dicts, get_ohlc_provider())


# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_sidebar():
    """Render the sidebar with controls and info."""
    with st.sidebar:
        st.header("✅ HPS Settings")
        
        # KEP data status
        kep_candidates = st.session_state.get('kep_candidates', [])
        kep_for_hps = st.session_state.get('kep_for_hps', [])
        
        if kep_for_hps:
            st.success(f"✅ {len(kep_for_hps)} KEP candidates from KEP page")
        elif kep_candidates:
            st.info(f"📊 {len(kep_candidates)} KEP candidates available")
        else:
            st.warning("⚠️ No KEP data. Run KEP analysis first for best results.")
        
        st.divider()
        
        # Evidence thresholds info
        st.subheader("📋 Evidence Criteria")
        st.markdown("""
        **HPS Evidence Checklist:**
        - ✅ **Retest** (+2): 2nd/3rd touch of level
        - ✅ **RSI Zone** (+1): <30 or >70
        - ✅ **200 EMA** (+1): Price at EMA
        - ✅ **9/21 Cross** (+1): Recent crossover
        - ✅ **Volume** (+1): Above average
        - ✅ **Candle** (+1): Reversal pattern
        - ✅ **MACD** (+1): Divergence/cross
        
        **Recommendations:**
        - 🟢 **TRADE**: Score ≥ 3
        - 🟡 **WATCH**: Score 2
        - 🔴 **SKIP**: Score < 2
        """)
        
        st.divider()
        
        # Trade parameters reference
        st.subheader("📊 Trade Parameters")
        st.markdown("""
        **From Playbook:**
        - Strike Delta: 0.3-0.5
        - Short Swing: 14-21 DTE
        - Long Swing: 28-35 DTE
        - Stop Loss: 29%
        - Take Profit: 45%
        - R-Ratio: 1:1.5
        """)


def render_kep_selector():
    """Render the KEP candidate selection section."""
    st.subheader("📊 Select KEP Candidates for HPS Analysis")
    
    # Check for KEP data from various sources
    kep_for_hps = st.session_state.get('kep_for_hps', [])
    kep_candidates = st.session_state.get('kep_candidates', [])
    
    available_keps = kep_for_hps if kep_for_hps else kep_candidates
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if available_keps:
            # Display available KEPs
            kep_options = []
            for kep in available_keps:
                if hasattr(kep, 'symbol'):
                    label = f"{kep.symbol} - Score: {kep.score}/{kep.max_score} ({kep.rating})"
                    kep_options.append((label, kep))
                elif isinstance(kep, dict):
                    symbol = kep.get('symbol', 'Unknown')
                    score = kep.get('score', 0)
                    max_score = kep.get('max_score', 0)
                    rating = kep.get('rating', 'LOW')
                    label = f"{symbol} - Score: {score}/{max_score} ({rating})"
                    kep_options.append((label, kep))
            
            selected_labels = st.multiselect(
                "Select KEP Candidates",
                options=[opt[0] for opt in kep_options],
                default=[opt[0] for opt in kep_options[:5]],  # Default to first 5
                help="Select KEP candidates to validate with HPS analysis"
            )
            
            # Get selected KEPs
            selected_keps = [kep for label, kep in kep_options if label in selected_labels]
        else:
            st.info("No KEP candidates available. You can enter symbols manually.")
            selected_keps = []
        
        # Manual symbol entry
        manual_symbols = st.text_input(
            "Or Enter Symbols Manually (comma-separated)",
            placeholder="e.g., SPY, QQQ, AAPL",
            help="Analyze symbols without KEP data (will use current price only)"
        )
    
    with col2:
        st.write("")
        st.write("")
        
        if st.button("🔍 Run HPS Analysis", type="primary", use_container_width=True):
            symbols_to_analyze = []
            kep_data_map = {}
            
            # Add selected KEPs
            for kep in selected_keps:
                if hasattr(kep, 'symbol'):
                    symbols_to_analyze.append(kep.symbol)
                    kep_data_map[kep.symbol] = kep.to_dict()
                elif isinstance(kep, dict):
                    symbol = kep.get('symbol')
                    if symbol:
                        symbols_to_analyze.append(symbol)
                        kep_data_map[symbol] = kep
            
            # Add manual symbols
            if manual_symbols:
                for symbol in manual_symbols.split(','):
                    symbol = symbol.strip().upper()
                    if symbol and symbol not in symbols_to_analyze:
                        symbols_to_analyze.append(symbol)
            
            if not symbols_to_analyze:
                st.warning("Please select KEP candidates or enter symbols.")
            else:
                with st.spinner("Running HPS analysis..."):
                    results = []
                    progress_bar = st.progress(0)
                    
                    for i, symbol in enumerate(symbols_to_analyze):
                        progress_bar.progress((i + 1) / len(symbols_to_analyze))
                        kep_data = kep_data_map.get(symbol)
                        result = run_hps_analysis_for_symbol(symbol, kep_data)
                        if result:
                            results.append(result)
                    
                    progress_bar.empty()
                    
                    # Sort results
                    priority = {'TRADE': 0, 'WATCH': 1, 'SKIP': 2}
                    results.sort(key=lambda x: (priority.get(x.recommendation, 3), -x.hps_score))
                    
                    st.session_state.hps_results = results
                    st.session_state.trade_setups = [r.trade_setup for r in results if r.trade_setup]
                    
                    if results:
                        st.success(f"✅ Analyzed {len(results)} symbols")
                    else:
                        st.warning("No results. Check if symbols are valid.")
    
    return selected_keps


def render_hps_results_table():
    """Render the HPS results table."""
    results = st.session_state.get('hps_results', [])
    
    if not results:
        st.info("No HPS analysis results. Run analysis above to see results.")
        return
    
    st.subheader("📋 HPS Analysis Results")
    
    # Summary metrics
    trade_count = sum(1 for r in results if r.recommendation == 'TRADE')
    watch_count = sum(1 for r in results if r.recommendation == 'WATCH')
    skip_count = sum(1 for r in results if r.recommendation == 'SKIP')
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Analyzed", len(results))
    with col2:
        st.metric("🟢 TRADE", trade_count)
    with col3:
        st.metric("🟡 WATCH", watch_count)
    with col4:
        st.metric("🔴 SKIP", skip_count)
    
    st.write("")
    
    # Create DataFrame for display
    table_data = []
    for hps in results:
        evidence_met = sum(1 for e in hps.evidence if e.met)
        evidence_str = f"{evidence_met}/{len(hps.evidence)}"
        
        table_data.append({
            'Symbol': hps.symbol,
            'Price': f"${hps.current_price:.2f}",
            'KEP Score': f"{hps.kep_score}",
            'HPS Score': f"{hps.hps_score:.1f}/{hps.max_hps_score:.0f}",
            'Evidence': evidence_str,
            'Recommendation': hps.recommendation,
            'Direction': hps.direction,
        })
    
    df = pd.DataFrame(table_data)
    
    # Color coding
    def style_recommendation(val):
        if val == 'TRADE':
            return 'background-color: #28a745; color: white; font-weight: bold'
        elif val == 'WATCH':
            return 'background-color: #ffc107; color: black'
        else:
            return 'background-color: #dc3545; color: white'
    
    def style_direction(val):
        if val == 'CALLS':
            return 'color: #28a745; font-weight: bold'
        elif val == 'PUTS':
            return 'color: #dc3545; font-weight: bold'
        return ''
    
    styled_df = df.style.map(style_recommendation, subset=['Recommendation'])
    styled_df = styled_df.map(style_direction, subset=['Direction'])
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    # Selection for detail view
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_symbol = st.selectbox(
            "Select Symbol for Detailed View",
            options=[hps.symbol for hps in results],
            index=0 if results else None
        )
    
    with col2:
        if st.button("📈 View Details", use_container_width=True):
            selected_hps = next((h for h in results if h.symbol == selected_symbol), None)
            if selected_hps:
                st.session_state.selected_hps = selected_hps
    
    return selected_symbol


def render_evidence_dashboard(hps_result: HPSResult):
    """Render the evidence checklist dashboard."""
    st.markdown("#### 📋 HPS Evidence Checklist")
    
    # Create columns for evidence items
    cols = st.columns(4)
    
    for i, evidence in enumerate(hps_result.evidence):
        with cols[i % 4]:
            icon = "✅" if evidence.met else "❌"
            direction_badge = ""
            if evidence.met and evidence.direction_hint:
                if evidence.direction_hint == 'CALLS':
                    direction_badge = "🟢"
                elif evidence.direction_hint == 'PUTS':
                    direction_badge = "🔴"
            
            weight_str = f"+{evidence.weight:.1f}" if evidence.met else ""
            
            bg_color = 'rgba(40, 167, 69, 0.2)' if evidence.met else 'rgba(220, 53, 69, 0.2)'
            border_color = 'rgba(40, 167, 69, 0.5)' if evidence.met else 'rgba(220, 53, 69, 0.5)'
            st.markdown(f"""
            <div style="padding: 0.75rem; border-radius: 0.5rem; 
                        background-color: {bg_color}; 
                        margin-bottom: 0.5rem; border: 1px solid {border_color};">
                <strong>{icon} {evidence.evidence_type}</strong> {direction_badge} {weight_str}<br/>
                <small style="opacity: 0.8;">{evidence.details}</small>
            </div>
            """, unsafe_allow_html=True)


def render_trade_setup_card(hps_result: HPSResult):
    """Render the trade setup recommendation card."""
    if hps_result.recommendation != 'TRADE' or not hps_result.trade_setup:
        return
    
    setup = hps_result.trade_setup
    
    st.markdown("#### 💼 Trade Setup Recommendation")
    
    direction_color = '#28a745' if setup.direction == 'CALLS' else '#dc3545'
    confidence_color = '#28a745' if setup.confidence == 'HIGH' else '#ffc107' if setup.confidence == 'MEDIUM' else '#dc3545'
    
    st.markdown(f"""
    <div style="padding: 1.5rem; border-radius: 0.5rem; background-color: rgba(128, 128, 128, 0.1); 
                border: 2px solid {direction_color}; margin: 1rem 0;">
        <h3 style="margin: 0 0 1rem 0; color: {direction_color};">
            TRADE SETUP: {hps_result.symbol} @ ${hps_result.current_price:.2f}
        </h3>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div>
                <p style="margin: 0.25rem 0;"><strong>Direction:</strong> 
                    <span style="color: {direction_color}; font-weight: bold;">{setup.direction}</span>
                </p>
                <p style="margin: 0.25rem 0;"><strong>Reason:</strong> {setup.reason}</p>
                <p style="margin: 0.25rem 0;"><strong>Confidence:</strong> 
                    <span style="color: {confidence_color}; font-weight: bold;">{setup.confidence}</span>
                </p>
            </div>
            <div>
                <p style="margin: 0.25rem 0;"><strong>Strike Delta:</strong> {setup.entry_strike_delta[0]}-{setup.entry_strike_delta[1]}</p>
                <p style="margin: 0.25rem 0;"><strong>DTE Range:</strong> {setup.dte_range[0]}-{setup.dte_range[1]} days</p>
                <p style="margin: 0.25rem 0;"><strong>R-Ratio:</strong> 1:{setup.r_ratio}</p>
            </div>
        </div>
        <hr style="margin: 1rem 0; border-color: rgba(128, 128, 128, 0.3);"/>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div style="background-color: rgba(220, 53, 69, 0.2); padding: 0.5rem; border-radius: 0.25rem; border: 1px solid rgba(220, 53, 69, 0.4);">
                <strong>🛑 Stop Loss:</strong> {setup.stop_loss_pct * 100:.0f}% of premium
            </div>
            <div style="background-color: rgba(40, 167, 69, 0.2); padding: 0.5rem; border-radius: 0.25rem; border: 1px solid rgba(40, 167, 69, 0.4);">
                <strong>🎯 Take Profit:</strong> {setup.take_profit_pct * 100:.0f}% of premium
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_hps_chart(hps_result: HPSResult):
    """Render chart with RSI subplot, EMA overlays, and volume."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    symbol = hps_result.symbol
    
    # Fetch OHLC data
    ohlc_data = fetch_ohlc_cached(symbol, period="1mo", interval="1d")
    if ohlc_data is None or ohlc_data.empty:
        st.warning(f"Could not load chart data for {symbol}")
        return
    
    df = ohlc_data.copy()
    df.columns = df.columns.str.lower()
    
    # Calculate indicators for chart
    rsi_values = None
    ema_9 = None
    ema_21 = None
    ema_200 = None
    
    try:
        # Calculate RSI
        if len(df) >= 14:
            delta = df['close'].diff()
            gains = delta.where(delta > 0, 0.0)
            losses = (-delta).where(delta < 0, 0.0)
            avg_gain = gains.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
            avg_loss = losses.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, float('nan'))
            rsi_values = 100 - (100 / (1 + rs))
        
        # Calculate EMAs
        ema_9 = df['close'].ewm(span=9, adjust=False).mean()
        ema_21 = df['close'].ewm(span=21, adjust=False).mean()
        if len(df) >= 200:
            ema_200 = df['close'].ewm(span=200, adjust=False).mean()
    except Exception as e:
        logger.warning(f"Error calculating indicators for chart: {e}")
    
    # Create figure with subplots: Price, RSI, Volume
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=(f'{symbol} - HPS Analysis', 'RSI (14)', 'Volume')
    )
    
    # 1. Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Price',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350',
        ),
        row=1, col=1
    )
    
    # Add EMA overlays
    if ema_9 is not None:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=ema_9,
                mode='lines',
                name='EMA 9',
                line=dict(color='#2196F3', width=1)
            ),
            row=1, col=1
        )
    
    if ema_21 is not None:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=ema_21,
                mode='lines',
                name='EMA 21',
                line=dict(color='#FF9800', width=1)
            ),
            row=1, col=1
        )
    
    if ema_200 is not None:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=ema_200,
                mode='lines',
                name='EMA 200',
                line=dict(color='#9C27B0', width=2)
            ),
            row=1, col=1
        )
    
    # Add current price line
    fig.add_hline(
        y=hps_result.current_price,
        line_dash='solid',
        line_color='rgba(255, 193, 7, 0.9)',
        line_width=2,
        annotation_text=f"Current: ${hps_result.current_price:.2f}",
        annotation_position="left",
        row=1, col=1
    )
    
    # 2. RSI subplot
    if rsi_values is not None:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=rsi_values,
                mode='lines',
                name='RSI',
                line=dict(color='#673AB7', width=1.5)
            ),
            row=2, col=1
        )
        
        # RSI zones
        fig.add_hline(y=70, line_dash='dash', line_color='rgba(244, 67, 54, 0.5)', row=2, col=1)
        fig.add_hline(y=30, line_dash='dash', line_color='rgba(76, 175, 80, 0.5)', row=2, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor='rgba(244, 67, 54, 0.1)', line_width=0, row=2, col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor='rgba(76, 175, 80, 0.1)', line_width=0, row=2, col=1)
    
    # 3. Volume bars
    if 'volume' in df.columns:
        colors = ['#26a69a' if c >= o else '#ef5350' 
                  for c, o in zip(df['close'], df['open'])]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['volume'],
                name='Volume',
                marker_color=colors,
                opacity=0.5
            ),
            row=3, col=1
        )
        
        # Average volume line
        avg_vol = df['volume'].rolling(20).mean()
        fig.add_trace(
            go.Scatter(
                x=df.index, y=avg_vol,
                mode='lines',
                name='Avg Volume',
                line=dict(color='#607D8B', width=1, dash='dash')
            ),
            row=3, col=1
        )
    
    # Update layout
    fig.update_layout(
        height=700,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.15,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(128,128,128,0.1)",
            font=dict(size=10)
        ),
        xaxis_rangeslider_visible=False,
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    
    # Update axes
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
    fig.update_yaxes(title_text="Price ($)", row=1, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="Volume", row=3, col=1)
    
    st.plotly_chart(fig, use_container_width=True)


def render_hps_detail_view():
    """Render detailed view for a selected HPS result."""
    selected_hps = st.session_state.get('selected_hps')
    
    if not selected_hps:
        return
    
    st.divider()
    st.subheader(f"✅ HPS Detail: {selected_hps.symbol}")
    
    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        rec_color = '#28a745' if selected_hps.recommendation == 'TRADE' else '#ffc107' if selected_hps.recommendation == 'WATCH' else '#dc3545'
        st.markdown(f"""
        <div style="padding: 1rem; border-radius: 0.5rem; background-color: {rec_color}33; border-left: 4px solid {rec_color};">
            <h3 style="margin: 0; color: {rec_color};">{selected_hps.recommendation}</h3>
            <p style="margin: 0; opacity: 0.8;">Recommendation</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.metric("HPS Score", f"{selected_hps.hps_score:.1f}/{selected_hps.max_hps_score:.0f}")
    
    with col3:
        st.metric("Current Price", f"${selected_hps.current_price:.2f}")
    
    with col4:
        dir_color = '#28a745' if selected_hps.direction == 'CALLS' else '#dc3545' if selected_hps.direction == 'PUTS' else '#6c757d'
        st.markdown(f"""
        <div style="padding: 1rem; border-radius: 0.5rem; background-color: {dir_color}33;">
            <h3 style="margin: 0; color: {dir_color};">{selected_hps.direction}</h3>
            <p style="margin: 0; opacity: 0.8;">Direction</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Trade Setup Card (if TRADE recommendation)
    render_trade_setup_card(selected_hps)
    
    # Evidence Dashboard
    render_evidence_dashboard(selected_hps)
    
    # Chart
    st.markdown("#### 📈 Technical Chart")
    render_hps_chart(selected_hps)


def render_export_section():
    """Render export options."""
    results = st.session_state.get('hps_results', [])
    
    if not results:
        return
    
    st.divider()
    
    with st.expander("📥 Export HPS Analysis", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV export
            export_data = []
            for hps in results:
                evidence_met = [e.evidence_type for e in hps.evidence if e.met]
                export_data.append({
                    'Symbol': hps.symbol,
                    'Current Price': hps.current_price,
                    'KEP Score': hps.kep_score,
                    'HPS Score': hps.hps_score,
                    'Max HPS Score': hps.max_hps_score,
                    'Recommendation': hps.recommendation,
                    'Direction': hps.direction,
                    'Evidence Met': '; '.join(evidence_met),
                    'Trade Setup': 'Yes' if hps.trade_setup else 'No',
                    'Timestamp': hps.analysis_timestamp.isoformat()
                })
            
            df_export = pd.DataFrame(export_data)
            csv = df_export.to_csv(index=False)
            
            st.download_button(
                "📄 Download CSV",
                csv,
                file_name=f"hps_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # Trade setups summary
            trade_setups = [r for r in results if r.recommendation == 'TRADE']
            if trade_setups:
                st.markdown(f"**{len(trade_setups)} Trade Setup(s) Ready:**")
                for setup in trade_setups:
                    st.markdown(f"- {setup.symbol}: {setup.direction} ({setup.trade_setup.confidence if setup.trade_setup else 'N/A'})")


# ============================================================================
# MAIN PAGE
# ============================================================================

def main():
    st.title("✅ HPS - High Probability Setups")
    st.caption("Validate KEP candidates with technical evidence to identify high-probability trades")
    
    # Check for KEP data
    kep_candidates = st.session_state.get('kep_candidates', [])
    kep_for_hps = st.session_state.get('kep_for_hps', [])
    
    if not kep_candidates and not kep_for_hps:
        st.warning("""
        **No KEP data available.** For best results:
        1. Go to the **WEM page** first and run WEM analysis
        2. Then go to the **KEP page** and run KEP analysis
        3. Return here for HPS validation
        
        You can still run HPS analysis by entering symbols manually.
        """)
    
    # Render sidebar
    render_sidebar()
    
    # KEP selection
    render_kep_selector()
    
    st.divider()
    
    # Results table
    render_hps_results_table()
    
    # Detail view
    render_hps_detail_view()
    
    # Export section
    render_export_section()


if __name__ == "__main__":
    main()
