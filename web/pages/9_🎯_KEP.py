"""
KEP (Key Entry Points) Analysis Page

Identifies and scores potential trade entry levels based on congruence of multiple factors.
Part of the WEM → KEP → HPS workflow for the Options Swing strategy.

Key Features:
1. Symbol selection from WEM analysis or manual entry
2. KEP Scanner Table - sortable by score
3. KEP Detail View with chart showing all levels
4. Level toggle panel for customization
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
    page_title="KEP Analysis",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import components after path setup
try:
    from web.components.kep_analysis import KEPAnalyzer, analyze_symbol_kep, batch_analyze_kep, KEPScore
    from web.components.wem_visualizations import _fetch_ohlc_data
    from goldflipper.data.indicators import FibonacciCalculator, GapDetector, EMACalculator, MarketData
except ImportError as e:
    st.error(f"Failed to import required components: {e}")
    st.stop()


# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

def init_session_state():
    """Initialize session state variables for KEP page."""
    if 'kep_candidates' not in st.session_state:
        st.session_state.kep_candidates = []
    
    if 'selected_kep' not in st.session_state:
        st.session_state.selected_kep = None
    
    if 'kep_proximity_threshold' not in st.session_state:
        st.session_state.kep_proximity_threshold = 2.0  # 2%
    
    if 'kep_level_toggles' not in st.session_state:
        st.session_state.kep_level_toggles = {
            'wem_levels': True,
            'delta_levels': True,
            '52_week': True,
            'fibonacci': True,
            'gaps': True,
            'prior_hl': True,
            'ema_200': True,
        }


init_session_state()


# ============================================================================
# DATA FETCHING UTILITIES
# ============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
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


@st.cache_data(ttl=300)
def fetch_quote_data(symbol: str) -> dict:
    """Fetch stock quote including 52-week high/low."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return {
            'High52': info.get('fiftyTwoWeekHigh'),
            'Low52': info.get('fiftyTwoWeekLow'),
            'currentPrice': info.get('currentPrice') or info.get('regularMarketPrice'),
            'previousClose': info.get('previousClose'),
        }
    except Exception as e:
        logger.warning(f"Error fetching quote for {symbol}: {e}")
        return {}


def get_ohlc_provider(period: str = "3mo"):
    """Return a function that fetches OHLC data for a symbol."""
    def provider(symbol: str) -> pd.DataFrame:
        return fetch_ohlc_cached(symbol, period=period, interval="1d")
    return provider


# ============================================================================
# KEP ANALYSIS FUNCTIONS
# ============================================================================

def run_kep_analysis(symbols: list, proximity_threshold: float = 0.02) -> list:
    """
    Run KEP analysis for a list of symbols.
    
    Args:
        symbols: List of stock symbols to analyze
        proximity_threshold: Proximity threshold for scoring (decimal)
        
    Returns:
        List of KEPScore objects
    """
    wem_data_list = st.session_state.get('wem_stocks_data', [])
    
    # Create a mapping of symbol to WEM data
    wem_map = {d.get('symbol'): d for d in wem_data_list if d.get('symbol')}
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, symbol in enumerate(symbols):
        status_text.text(f"Analyzing {symbol}...")
        progress_bar.progress((i + 1) / len(symbols))
        
        try:
            # Get WEM data if available
            wem_data = wem_map.get(symbol, {})
            
            # Fetch OHLC data
            ohlc_data = fetch_ohlc_cached(symbol, period="3mo", interval="1d")
            if ohlc_data is None or len(ohlc_data) == 0:
                logger.warning(f"No OHLC data for {symbol}")
                continue
            
            # Get current price
            current_price = None
            if wem_data.get('atm_price'):
                current_price = wem_data['atm_price']
            else:
                quote = fetch_quote_data(symbol)
                current_price = quote.get('currentPrice') or (
                    ohlc_data['Close'].iloc[-1] if not ohlc_data.empty else None
                )
            
            if not current_price:
                logger.warning(f"No price data for {symbol}")
                continue
            
            # Get quote data for 52-week H/L
            quote_data = fetch_quote_data(symbol)
            
            # Run analysis
            kep_score = analyze_symbol_kep(
                symbol=symbol,
                wem_data=wem_data,
                ohlc_data=ohlc_data,
                current_price=current_price,
                quote_data=quote_data,
                proximity_threshold=proximity_threshold
            )
            results.append(kep_score)
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            continue
    
    progress_bar.empty()
    status_text.empty()
    
    # Sort by score descending
    results.sort(key=lambda x: x.score, reverse=True)
    
    return results


# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_sidebar():
    """Render the sidebar with controls."""
    with st.sidebar:
        st.header("🎯 KEP Settings")
        
        # Proximity threshold
        st.session_state.kep_proximity_threshold = st.slider(
            "Proximity Threshold (%)",
            min_value=0.5,
            max_value=5.0,
            value=st.session_state.kep_proximity_threshold,
            step=0.5,
            help="How close price must be to a level to be considered 'at' that level"
        )
        
        st.divider()
        
        # Level toggles
        st.subheader("Level Visibility")
        
        st.session_state.kep_level_toggles['wem_levels'] = st.checkbox(
            "WEM S1/S2", 
            value=st.session_state.kep_level_toggles['wem_levels']
        )
        st.session_state.kep_level_toggles['delta_levels'] = st.checkbox(
            "Delta 16±", 
            value=st.session_state.kep_level_toggles['delta_levels']
        )
        st.session_state.kep_level_toggles['52_week'] = st.checkbox(
            "52-Week H/L", 
            value=st.session_state.kep_level_toggles['52_week']
        )
        st.session_state.kep_level_toggles['fibonacci'] = st.checkbox(
            "Fibonacci Levels", 
            value=st.session_state.kep_level_toggles['fibonacci']
        )
        st.session_state.kep_level_toggles['gaps'] = st.checkbox(
            "Gap Levels", 
            value=st.session_state.kep_level_toggles['gaps']
        )
        st.session_state.kep_level_toggles['prior_hl'] = st.checkbox(
            "Prior Day/Week H/L", 
            value=st.session_state.kep_level_toggles['prior_hl']
        )
        st.session_state.kep_level_toggles['ema_200'] = st.checkbox(
            "200 EMA", 
            value=st.session_state.kep_level_toggles['ema_200']
        )
        
        st.divider()
        
        # WEM data status
        wem_data = st.session_state.get('wem_stocks_data', [])
        if wem_data:
            st.success(f"✅ WEM data loaded: {len(wem_data)} symbols")
        else:
            st.warning("⚠️ No WEM data. Run WEM analysis first for best results.")


def render_symbol_selector():
    """Render the symbol selection section."""
    st.subheader("📊 Symbol Selection")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Get symbols from WEM data if available
        wem_symbols = [d.get('symbol') for d in st.session_state.get('wem_stocks_data', []) if d.get('symbol')]
        
        # Default symbols if no WEM data
        default_symbols = wem_symbols if wem_symbols else ['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA']
        
        selected_symbols = st.multiselect(
            "Select Symbols to Analyze",
            options=wem_symbols if wem_symbols else default_symbols,
            default=default_symbols[:5],
            help="Select symbols from WEM analysis or add custom symbols"
        )
        
        # Manual symbol entry
        manual_symbols = st.text_input(
            "Add Custom Symbols (comma-separated)",
            placeholder="e.g., TSLA, AMD, META",
            help="Add symbols not in the list above"
        )
        
        if manual_symbols:
            custom = [s.strip().upper() for s in manual_symbols.split(',') if s.strip()]
            selected_symbols = list(set(selected_symbols + custom))
    
    with col2:
        st.write("")  # Spacing
        st.write("")
        
        if st.button("🔍 Run KEP Analysis", type="primary", use_container_width=True):
            if not selected_symbols:
                st.warning("Please select at least one symbol.")
            else:
                with st.spinner("Running KEP analysis..."):
                    threshold = st.session_state.kep_proximity_threshold / 100
                    results = run_kep_analysis(selected_symbols, threshold)
                    st.session_state.kep_candidates = results
                    
                    if results:
                        st.success(f"✅ Analyzed {len(results)} symbols")
                    else:
                        st.warning("No results. Check if symbols are valid.")
    
    return selected_symbols


def render_kep_scanner_table():
    """Render the KEP scanner results table."""
    candidates = st.session_state.get('kep_candidates', [])
    
    if not candidates:
        st.info("No KEP analysis results. Run analysis above to see results.")
        return
    
    st.subheader("📋 KEP Scanner Results")
    
    # Create DataFrame for display
    table_data = []
    for kep in candidates:
        matched = ', '.join([f.get('factor', '')[:20] for f in kep.matched_factors[:3]])
        if len(kep.matched_factors) > 3:
            matched += f"... +{len(kep.matched_factors) - 3}"
        
        table_data.append({
            'Symbol': kep.symbol,
            'Price': f"${kep.current_price:.2f}",
            'Score': f"{kep.score}/{kep.max_score}",
            'Rating': kep.rating,
            'Direction': kep.direction_bias or 'NEUTRAL',
            'Nearest Level': kep.nearest_level.get('label', 'N/A') if kep.nearest_level else 'N/A',
            'Distance': f"{kep.nearest_level.get('distance_pct', 0):.1f}%" if kep.nearest_level else 'N/A',
            'Matched Factors': matched or 'None'
        })
    
    df = pd.DataFrame(table_data)
    
    # Color coding for rating
    def highlight_rating(val):
        if val == 'HIGH':
            return 'background-color: #28a745; color: white'
        elif val == 'MEDIUM':
            return 'background-color: #ffc107; color: black'
        else:
            return 'background-color: #dc3545; color: white'
    
    def highlight_direction(val):
        if val == 'CALLS':
            return 'color: #28a745; font-weight: bold'
        elif val == 'PUTS':
            return 'color: #dc3545; font-weight: bold'
        return ''
    
    # Display styled dataframe
    styled_df = df.style.map(highlight_rating, subset=['Rating'])
    styled_df = styled_df.map(highlight_direction, subset=['Direction'])
    
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True
    )
    
    # Symbol selection for detail view
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_symbol = st.selectbox(
            "Select Symbol for Detailed View",
            options=[kep.symbol for kep in candidates],
            index=0 if candidates else None
        )
    
    with col2:
        if st.button("📈 View Details", use_container_width=True):
            selected_kep = next((k for k in candidates if k.symbol == selected_symbol), None)
            if selected_kep:
                st.session_state.selected_kep = selected_kep
    
    return selected_symbol


def render_kep_detail_view():
    """Render detailed view for a selected KEP."""
    selected_kep = st.session_state.get('selected_kep')
    
    if not selected_kep:
        return
    
    st.divider()
    st.subheader(f"🎯 KEP Detail: {selected_kep.symbol}")
    
    # Score summary cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        rating_color = '#28a745' if selected_kep.rating == 'HIGH' else '#ffc107' if selected_kep.rating == 'MEDIUM' else '#dc3545'
        st.markdown(f"""
        <div style="padding: 1rem; border-radius: 0.5rem; background-color: {rating_color}33; border-left: 4px solid {rating_color};">
            <h3 style="margin: 0; color: {rating_color};">{selected_kep.rating}</h3>
            <p style="margin: 0; opacity: 0.8;">KEP Rating</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.metric("Score", f"{selected_kep.score}/{selected_kep.max_score}")
    
    with col3:
        st.metric("Current Price", f"${selected_kep.current_price:.2f}")
    
    with col4:
        direction_color = '#28a745' if selected_kep.direction_bias == 'CALLS' else '#dc3545' if selected_kep.direction_bias == 'PUTS' else '#6c757d'
        st.markdown(f"""
        <div style="padding: 1rem; border-radius: 0.5rem; background-color: {direction_color}33;">
            <h3 style="margin: 0; color: {direction_color};">{selected_kep.direction_bias or 'NEUTRAL'}</h3>
            <p style="margin: 0; opacity: 0.8;">Direction Bias</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Matched factors
    if selected_kep.matched_factors:
        st.markdown("#### 🎯 Matched Congruence Factors")
        
        factor_cols = st.columns(min(len(selected_kep.matched_factors), 4))
        for i, factor in enumerate(selected_kep.matched_factors):
            with factor_cols[i % 4]:
                direction_icon = "⬆️" if factor.get('direction') == 'above' else "⬇️"
                st.markdown(f"""
                <div style="padding: 0.5rem; border-radius: 0.25rem; background-color: rgba(128, 128, 128, 0.15); margin-bottom: 0.5rem; border: 1px solid rgba(128, 128, 128, 0.3);">
                    <strong>{factor.get('factor', 'Unknown')}</strong><br/>
                    ${factor.get('level', 0):.2f} {direction_icon}<br/>
                    <small style="opacity: 0.7;">{factor.get('distance_pct', 0):.2f}% away</small>
                </div>
                """, unsafe_allow_html=True)
    
    # Confluence zones
    if selected_kep.confluence_zones:
        st.markdown("#### 🔄 Confluence Zones")
        for zone in selected_kep.confluence_zones[:3]:
            levels_str = ', '.join(zone.get('levels', [])[:3])
            st.markdown(f"""
            - **${zone['low']:.2f} - ${zone['high']:.2f}** ({zone['level_count']} levels)
              - Levels: {levels_str}
            """)
    
    # Chart with levels
    render_kep_chart(selected_kep)
    
    # All levels table
    with st.expander("📊 All Calculated Levels", expanded=False):
        levels_data = []
        for key, value in selected_kep.all_levels.items():
            if isinstance(value, (int, float)) and value > 0:
                distance = selected_kep.current_price - value
                distance_pct = (distance / selected_kep.current_price) * 100
                levels_data.append({
                    'Level': key.replace('_', ' ').title(),
                    'Price': f"${value:.2f}",
                    'Distance': f"${distance:.2f}",
                    'Distance %': f"{distance_pct:.2f}%",
                    'Position': 'Above' if distance > 0 else 'Below'
                })
        
        if levels_data:
            levels_df = pd.DataFrame(levels_data)
            levels_df = levels_df.sort_values('Price', ascending=False)
            st.dataframe(levels_df, use_container_width=True, hide_index=True)


def render_kep_chart(kep_score: KEPScore):
    """Render a chart with KEP levels overlaid."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    symbol = kep_score.symbol
    
    # Fetch OHLC data
    ohlc_data = fetch_ohlc_cached(symbol, period="1mo", interval="1d")
    if ohlc_data is None or ohlc_data.empty:
        st.warning(f"Could not load chart data for {symbol}")
        return
    
    # Create figure
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.8, 0.2],
        subplot_titles=(f'{symbol} - KEP Levels Analysis', 'Volume')
    )
    
    # Add candlestick
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
        ),
        row=1, col=1
    )
    
    # Add volume
    colors = ['#26a69a' if c >= o else '#ef5350' 
              for c, o in zip(ohlc_data['Close'], ohlc_data['Open'])]
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
    
    # Level configurations with colors
    level_configs = {
        'wem_s1': {'color': 'rgba(244, 67, 54, 0.8)', 'dash': 'dash', 'name': 'WEM S1', 'toggle': 'wem_levels'},
        'wem_s2': {'color': 'rgba(76, 175, 80, 0.8)', 'dash': 'dash', 'name': 'WEM S2', 'toggle': 'wem_levels'},
        'delta_16_plus': {'color': 'rgba(33, 150, 243, 0.7)', 'dash': 'dot', 'name': 'Δ16+', 'toggle': 'delta_levels'},
        'delta_16_minus': {'color': 'rgba(156, 39, 176, 0.7)', 'dash': 'dot', 'name': 'Δ16-', 'toggle': 'delta_levels'},
        'high_52': {'color': 'rgba(255, 152, 0, 0.8)', 'dash': 'solid', 'name': '52w High', 'toggle': '52_week'},
        'low_52': {'color': 'rgba(255, 152, 0, 0.8)', 'dash': 'solid', 'name': '52w Low', 'toggle': '52_week'},
        'fib_382': {'color': 'rgba(121, 85, 72, 0.6)', 'dash': 'dashdot', 'name': 'Fib 38.2%', 'toggle': 'fibonacci'},
        'fib_500': {'color': 'rgba(121, 85, 72, 0.6)', 'dash': 'dashdot', 'name': 'Fib 50%', 'toggle': 'fibonacci'},
        'fib_618': {'color': 'rgba(121, 85, 72, 0.6)', 'dash': 'dashdot', 'name': 'Fib 61.8%', 'toggle': 'fibonacci'},
        'ema_200': {'color': 'rgba(0, 188, 212, 0.8)', 'dash': 'solid', 'name': '200 EMA', 'toggle': 'ema_200'},
        'prior_day_high': {'color': 'rgba(158, 158, 158, 0.6)', 'dash': 'dot', 'name': 'Prev Day High', 'toggle': 'prior_hl'},
        'prior_day_low': {'color': 'rgba(158, 158, 158, 0.6)', 'dash': 'dot', 'name': 'Prev Day Low', 'toggle': 'prior_hl'},
    }
    
    toggles = st.session_state.kep_level_toggles
    
    # Add horizontal lines for levels
    for level_key, config in level_configs.items():
        # Check toggle
        if not toggles.get(config.get('toggle'), True):
            continue
        
        level_price = kep_score.all_levels.get(level_key)
        if level_price and isinstance(level_price, (int, float)) and level_price > 0:
            fig.add_hline(
                y=level_price,
                line_dash=config['dash'],
                line_color=config['color'],
                line_width=1.5,
                annotation_text=f"{config['name']}: ${level_price:.2f}",
                annotation_position="right",
                annotation_font_size=9,
                row=1, col=1
            )
    
    # Add current price line
    fig.add_hline(
        y=kep_score.current_price,
        line_dash='solid',
        line_color='rgba(255, 193, 7, 0.9)',
        line_width=2,
        annotation_text=f"Current: ${kep_score.current_price:.2f}",
        annotation_position="left",
        row=1, col=1
    )
    
    # Shade confluence zones
    for zone in kep_score.confluence_zones[:2]:
        fig.add_hrect(
            y0=zone['low'],
            y1=zone['high'],
            fillcolor="rgba(100, 181, 246, 0.15)",
            line_width=0,
            row=1, col=1
        )
    
    # Update layout
    fig.update_layout(
        title=dict(text=f'{symbol} KEP Analysis - Score: {kep_score.score}/{kep_score.max_score}', font=dict(size=16)),
        xaxis_rangeslider_visible=False,
        height=600,
        showlegend=False,
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)', title_text="Price ($)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    
    st.plotly_chart(fig, use_container_width=True)


def render_export_section():
    """Render export options."""
    candidates = st.session_state.get('kep_candidates', [])
    
    if not candidates:
        return
    
    st.divider()
    
    with st.expander("📥 Export KEP Analysis", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV export
            export_data = []
            for kep in candidates:
                export_data.append({
                    'Symbol': kep.symbol,
                    'Current Price': kep.current_price,
                    'Score': kep.score,
                    'Max Score': kep.max_score,
                    'Rating': kep.rating,
                    'Direction Bias': kep.direction_bias,
                    'Nearest Level': kep.nearest_level.get('label') if kep.nearest_level else '',
                    'Nearest Level Price': kep.nearest_level.get('price') if kep.nearest_level else '',
                    'Matched Factors': '; '.join([f.get('factor', '') for f in kep.matched_factors]),
                })
            
            df_export = pd.DataFrame(export_data)
            csv = df_export.to_csv(index=False)
            
            st.download_button(
                "📄 Download CSV",
                csv,
                file_name=f"kep_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # HPS handoff button
            if st.button("➡️ Send to HPS Analysis", use_container_width=True):
                st.session_state.kep_for_hps = candidates
                st.info("KEP data ready for HPS analysis. Navigate to the HPS page.")


# ============================================================================
# MAIN PAGE
# ============================================================================

def main():
    st.title("🎯 KEP - Key Entry Points Analysis")
    st.caption("Identify high-probability entry levels based on congruence of multiple factors")
    
    # Check for WEM data
    wem_data = st.session_state.get('wem_stocks_data', [])
    if not wem_data:
        st.warning("""
        **No WEM data loaded.** For best results:
        1. Go to the **WEM page** first
        2. Run WEM analysis for your target symbols
        3. Return here for KEP analysis
        
        You can still run KEP analysis without WEM data, but WEM levels will not be included.
        """)
    
    # Render sidebar
    render_sidebar()
    
    # Symbol selection
    render_symbol_selector()
    
    st.divider()
    
    # KEP Scanner Table
    render_kep_scanner_table()
    
    # Detail view
    render_kep_detail_view()
    
    # Export section
    render_export_section()


if __name__ == "__main__":
    main()
