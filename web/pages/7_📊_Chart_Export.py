"""
WEM Chart Export Page

Export interactive WEM charts as HTML files for sharing and offline viewing.
Charts can be exported individually or as a ZIP archive.
"""

import streamlit as st
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Chart Export - Goldflipper",
    page_icon="📊",
    layout="wide"
)

st.title("📊 WEM Chart Export")
st.caption("Export interactive WEM charts as HTML files")


def get_desktop_path() -> Optional[str]:
    """Get the user's desktop path."""
    if os.name == 'nt':  # Windows
        return os.path.join(os.path.expanduser("~"), "Desktop")
    else:  # macOS/Linux
        return os.path.join(os.path.expanduser("~"), "Desktop")


def fetch_ohlc_data(symbol: str, period: str = "1mo", interval: str = "1d"):
    """Fetch OHLC data for a symbol using yfinance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)
        if data.empty:
            return None
        return data
    except Exception as e:
        logger.error(f"Error fetching OHLC data for {symbol}: {e}")
        return None


def create_wem_market_chart(symbol: str, wem_data: Dict[str, Any], period: str = "1mo", interval: str = "1d"):
    """
    Create a Plotly candlestick chart with WEM levels.
    Returns the figure object for export.
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    ohlc_data = fetch_ohlc_data(symbol, period, interval)
    if ohlc_data is None or ohlc_data.empty:
        return None
    
    # Extract WEM levels
    atm_price = wem_data.get('atm_price')
    s1 = wem_data.get('straddle_1')
    s2 = wem_data.get('straddle_2')
    delta_16_plus = wem_data.get('delta_16_plus')
    delta_16_minus = wem_data.get('delta_16_minus')
    wem_points = wem_data.get('wem_points')
    
    # Create figure with volume subplot
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.8, 0.2],
        subplot_titles=(f'{symbol} - Price with WEM Levels', 'Volume')
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
    
    # Add WEM horizontal lines
    wem_lines = []
    
    if atm_price is not None:
        wem_lines.append({
            'y': atm_price,
            'color': 'rgba(255, 193, 7, 0.8)',
            'dash': 'solid',
            'name': f'ATM: ${atm_price:.2f}',
            'width': 2
        })
    
    if s2 is not None:
        wem_lines.append({
            'y': s2,
            'color': 'rgba(76, 175, 80, 0.8)',
            'dash': 'dash',
            'name': f'S2 (Upper): ${s2:.2f}',
            'width': 2
        })
    
    if s1 is not None:
        wem_lines.append({
            'y': s1,
            'color': 'rgba(244, 67, 54, 0.8)',
            'dash': 'dash',
            'name': f'S1 (Lower): ${s1:.2f}',
            'width': 2
        })
    
    if delta_16_plus is not None:
        wem_lines.append({
            'y': delta_16_plus,
            'color': 'rgba(33, 150, 243, 0.7)',
            'dash': 'dot',
            'name': f'Δ16+: ${delta_16_plus:.2f}',
            'width': 1.5
        })
    
    if delta_16_minus is not None:
        wem_lines.append({
            'y': delta_16_minus,
            'color': 'rgba(156, 39, 176, 0.7)',
            'dash': 'dot',
            'name': f'Δ16-: ${delta_16_minus:.2f}',
            'width': 1.5
        })
    
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
        # Add invisible scatter trace for legend
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
    
    # Add shaded WEM range
    if s1 is not None and s2 is not None:
        fig.add_hrect(
            y0=s1, y1=s2,
            fillcolor="rgba(100, 181, 246, 0.1)",
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
        plot_bgcolor='rgba(250,250,250,1)',
        paper_bgcolor='rgba(255,255,255,1)',
    )
    
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
    
    return fig


def create_comparison_chart(symbols: List[str], stocks_data: List[Dict]):
    """Create a multi-symbol comparison chart."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    fig = make_subplots(
        rows=len(symbols), 
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.05,
        subplot_titles=symbols
    )
    
    # Add legend traces only once (on first row)
    legend_added = False
    
    for i, symbol in enumerate(symbols, 1):
        stock_data = next((s for s in stocks_data if s.get('symbol') == symbol), None)
        if not stock_data:
            continue
        
        ohlc = fetch_ohlc_data(symbol, period="5d", interval="1h")
        if ohlc is None or ohlc.empty:
            continue
        
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
        xaxis_rangeslider_visible=False,
        plot_bgcolor='rgba(250,250,250,1)',
        paper_bgcolor='rgba(255,255,255,1)',
    )
    
    for i in range(1, len(symbols) + 1):
        fig.update_xaxes(rangeslider_visible=False, row=i, col=1)
    
    return fig


def export_chart_to_html(fig, filepath: str, include_plotlyjs: str = 'cdn') -> bool:
    """Export a Plotly figure to HTML file."""
    try:
        fig.write_html(
            filepath,
            include_plotlyjs=include_plotlyjs,
            full_html=True,
            config={'displayModeBar': True, 'scrollZoom': True}
        )
        return True
    except Exception as e:
        logger.error(f"Failed to export chart to {filepath}: {e}")
        return False


def create_charts_zip(charts: Dict[str, Any], output_path: str) -> bool:
    """Create a ZIP file containing multiple HTML chart files."""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export each chart to temp directory
            for name, fig in charts.items():
                html_path = os.path.join(temp_dir, f"{name}.html")
                export_chart_to_html(fig, html_path, include_plotlyjs='cdn')
            
            # Create ZIP file
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for name in charts.keys():
                    html_path = os.path.join(temp_dir, f"{name}.html")
                    if os.path.exists(html_path):
                        zipf.write(html_path, f"{name}.html")
            
            return True
    except Exception as e:
        logger.error(f"Failed to create charts ZIP: {e}")
        return False


# Main UI
def main():
    stocks_data = st.session_state.get('wem_stocks_data', [])
    
    if not stocks_data:
        st.warning("⚠️ No WEM data available. Please go to the WEM page and update data first.")
        st.info("Navigate to **6_📊_WEM** page, add your symbols, and click **Update WEM Data**.")
        return
    
    # Filter symbols with valid data
    valid_stocks = [s for s in stocks_data if s.get('atm_price') and s.get('symbol')]
    if not valid_stocks:
        st.warning("No symbols with valid WEM data available for export.")
        return
    
    symbols = [s.get('symbol') for s in valid_stocks]
    
    st.markdown("---")
    
    # Export settings
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📈 Export Settings")
        
        export_type = st.radio(
            "Export Type",
            ["Single Symbol Chart", "Multiple Symbol Charts (ZIP)", "Comparison Chart"],
            horizontal=True
        )
        
        if export_type == "Single Symbol Chart":
            selected_symbol = st.selectbox("Select Symbol", symbols)
        elif export_type == "Multiple Symbol Charts (ZIP)":
            selected_symbols = st.multiselect(
                "Select Symbols to Export",
                symbols,
                default=symbols[:min(5, len(symbols))]
            )
        else:  # Comparison
            selected_symbols = st.multiselect(
                "Select Symbols for Comparison (2-6 recommended)",
                symbols,
                default=symbols[:min(4, len(symbols))]
            )
        
        period = st.selectbox(
            "Chart Period",
            ["5d", "1mo", "3mo", "6mo", "1y"],
            index=1
        )
        
        interval = st.selectbox(
            "Chart Interval",
            ["15m", "30m", "1h", "1d"],
            index=2 if period == "5d" else 3
        )
    
    with col2:
        st.subheader("💾 Save Location")
        
        save_to_desktop = st.checkbox("Save to Desktop", value=True)
        desktop_path = get_desktop_path()
        
        if save_to_desktop and desktop_path:
            st.caption(f"Desktop: `{desktop_path}`")
        
        # Export directory
        export_dir = "./data/exports/charts"
        os.makedirs(export_dir, exist_ok=True)
    
    st.markdown("---")
    
    # Preview section
    st.subheader("👁️ Chart Preview")
    
    if export_type == "Single Symbol Chart":
        wem_data = next((s for s in valid_stocks if s.get('symbol') == selected_symbol), None)
        if wem_data:
            with st.spinner(f"Loading chart for {selected_symbol}..."):
                fig = create_wem_market_chart(selected_symbol, wem_data, period, interval)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning(f"Could not create chart for {selected_symbol}")
    
    elif export_type == "Comparison Chart" and len(selected_symbols) >= 2:
        with st.spinner("Loading comparison chart..."):
            fig = create_comparison_chart(selected_symbols, valid_stocks)
            st.plotly_chart(fig, use_container_width=True)
    
    elif export_type == "Multiple Symbol Charts (ZIP)" and selected_symbols:
        st.info(f"📦 {len(selected_symbols)} charts will be exported to a ZIP file")
        # Show first chart as preview
        first_symbol = selected_symbols[0]
        wem_data = next((s for s in valid_stocks if s.get('symbol') == first_symbol), None)
        if wem_data:
            with st.spinner(f"Preview: {first_symbol}..."):
                fig = create_wem_market_chart(first_symbol, wem_data, period, interval)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption(f"Preview of {first_symbol} (1 of {len(selected_symbols)})")
    
    st.markdown("---")
    
    # Export button
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("📥 Export Charts", type="primary", use_container_width=True):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            with st.spinner("Generating charts..."):
                try:
                    if export_type == "Single Symbol Chart":
                        # Export single chart
                        wem_data = next((s for s in valid_stocks if s.get('symbol') == selected_symbol), None)
                        if wem_data:
                            fig = create_wem_market_chart(selected_symbol, wem_data, period, interval)
                            if fig:
                                filename = f"WEM_{selected_symbol}_{timestamp}.html"
                                filepath = os.path.join(export_dir, filename)
                                
                                if export_chart_to_html(fig, filepath):
                                    msg = f"✅ Chart exported to `{filepath}`"
                                    
                                    # Copy to desktop if requested
                                    if save_to_desktop and desktop_path:
                                        desktop_file = os.path.join(desktop_path, filename)
                                        try:
                                            shutil.copy2(filepath, desktop_file)
                                            msg += f"\n📁 Also saved to Desktop: `{desktop_file}`"
                                        except Exception as e:
                                            msg += f"\n⚠️ Could not save to Desktop: {e}"
                                    
                                    st.success(msg)
                                else:
                                    st.error("Failed to export chart")
                    
                    elif export_type == "Multiple Symbol Charts (ZIP)":
                        if not selected_symbols:
                            st.warning("Please select at least one symbol")
                        else:
                            # Generate all charts
                            charts = {}
                            progress = st.progress(0)
                            
                            for i, symbol in enumerate(selected_symbols):
                                wem_data = next((s for s in valid_stocks if s.get('symbol') == symbol), None)
                                if wem_data:
                                    fig = create_wem_market_chart(symbol, wem_data, period, interval)
                                    if fig:
                                        charts[f"WEM_{symbol}"] = fig
                                progress.progress((i + 1) / len(selected_symbols))
                            
                            if charts:
                                filename = f"WEM_Charts_{timestamp}.zip"
                                filepath = os.path.join(export_dir, filename)
                                
                                if create_charts_zip(charts, filepath):
                                    msg = f"✅ {len(charts)} charts exported to `{filepath}`"
                                    
                                    if save_to_desktop and desktop_path:
                                        desktop_file = os.path.join(desktop_path, filename)
                                        try:
                                            shutil.copy2(filepath, desktop_file)
                                            msg += f"\n📁 Also saved to Desktop: `{desktop_file}`"
                                        except Exception as e:
                                            msg += f"\n⚠️ Could not save to Desktop: {e}"
                                    
                                    st.success(msg)
                                else:
                                    st.error("Failed to create ZIP file")
                            else:
                                st.error("No charts could be generated")
                    
                    else:  # Comparison chart
                        if len(selected_symbols) < 2:
                            st.warning("Please select at least 2 symbols for comparison")
                        else:
                            fig = create_comparison_chart(selected_symbols, valid_stocks)
                            
                            symbols_str = "_".join(selected_symbols[:3])
                            if len(selected_symbols) > 3:
                                symbols_str += f"_and_{len(selected_symbols) - 3}_more"
                            
                            filename = f"WEM_Comparison_{symbols_str}_{timestamp}.html"
                            filepath = os.path.join(export_dir, filename)
                            
                            if export_chart_to_html(fig, filepath):
                                msg = f"✅ Comparison chart exported to `{filepath}`"
                                
                                if save_to_desktop and desktop_path:
                                    desktop_file = os.path.join(desktop_path, filename)
                                    try:
                                        shutil.copy2(filepath, desktop_file)
                                        msg += f"\n📁 Also saved to Desktop: `{desktop_file}`"
                                    except Exception as e:
                                        msg += f"\n⚠️ Could not save to Desktop: {e}"
                                
                                st.success(msg)
                            else:
                                st.error("Failed to export comparison chart")
                
                except Exception as e:
                    st.error(f"Export failed: {str(e)}")
                    logger.exception("Chart export error")
    
    # Info section
    st.markdown("---")
    st.markdown("""
    ### ℹ️ About Interactive HTML Charts
    
    Exported charts are fully interactive HTML files that can be:
    - **Opened in any web browser** without internet (Plotly.js is embedded or loaded from CDN)
    - **Zoomed, panned, and inspected** with hover tooltips
    - **Shared via email or messaging** as attachments
    - **Embedded in reports or presentations**
    
    **Chart Levels:**
    - 🟡 **ATM** - Current At-The-Money price
    - 🟢 **S2** - Upper expected move bound (Stock Price + WEM Points)
    - 🔴 **S1** - Lower expected move bound (Stock Price - WEM Points)
    - 🔵 **Δ16+** - Upper delta 16 strike (call)
    - 🟣 **Δ16-** - Lower delta 16 strike (put)
    - 🔲 **Shaded area** - Expected move range (S1 to S2)
    """)


if __name__ == "__main__":
    main()
else:
    main()
