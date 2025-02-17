import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

import yfinance as yf
from ..chart.candlestick import CandlestickChart
from ..data.indicators.ema import EMACalculator
from ..data.indicators.macd import MACDCalculator
from ..data.indicators.ttm_squeeze import TTMSqueezeCalculator
from ..utils.display import TerminalDisplay as display
import logging
import pandas as pd
from ..data.indicators.base import MarketData
import yaml

def validate_period_interval(period: str, interval: str) -> tuple[bool, str]:
    """Validate if period and interval combination is valid"""
    # Maximum periods for different intervals
    interval_limits = {
        '1m': '7d',
        '2m': '60d',
        '5m': '60d',
        '15m': '60d',
        '30m': '60d',
        '60m': '730d',
        '90m': '60d',
        '1h': '730d',
        '1d': 'max',
        '5d': 'max',
        '1wk': 'max',
        '1mo': 'max',
        '3mo': 'max'
    }
    
    # Convert period to days for comparison
    period_days = {
        '1d': 1, '5d': 5, '1mo': 30, '3mo': 90, '6mo': 180,
        '1y': 365, '2y': 730, '5y': 1825, '10y': 3650,
        'ytd': 365, 'max': 9999
    }
    
    if period not in period_days:
        return False, f"Invalid period. Valid periods are: {', '.join(period_days.keys())}"
        
    if interval not in interval_limits:
        return False, f"Invalid interval. Valid intervals are: {', '.join(interval_limits.keys())}"
    
    # Check if period exceeds interval limit
    if interval in ['1m', '2m', '5m', '15m', '30m', '90m'] and period_days[period] > 60:
        return False, f"Period too long for {interval} interval. Maximum is 60 days."
    elif interval in ['60m', '1h'] and period_days[period] > 730:
        return False, f"Period too long for {interval} interval. Maximum is 730 days."
        
    return True, ""

def get_user_input():
    """Get user input for chart parameters"""
    while True:
        try:
            ticker = input("\nEnter ticker symbol (or 'q' to quit): ").upper()
            if ticker.lower() == 'q':
                return None
                
            period = input("Enter time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max): ")
            interval = input("Enter interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo): ")
            
            # Validate period and interval combination
            is_valid, message = validate_period_interval(period, interval)
            if not is_valid:
                print(message)
                continue
                
            return ticker, period, interval
            
        except Exception as e:
            print(f"Error: {str(e)}")
            print("Please try again...")

def prepare_data(data: pd.DataFrame) -> pd.DataFrame:
    """Prepare data for charting by ensuring correct column names"""
    # Map yfinance column names to expected names
    column_map = {
        'Open': 'Open',
        'High': 'High',
        'Low': 'Low',
        'Close': 'Close',
        'Volume': 'Volume'
    }
    
    # Rename columns if necessary
    for expected, actual in column_map.items():
        if actual in data.columns and expected != actual:
            data = data.rename(columns={actual: expected})
            
    return data

def load_chart_settings():
    """Load chart settings from settings.yaml"""
    try:
        # Get the absolute path to the config directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(os.path.dirname(current_dir), 'config')
        settings_path = os.path.join(config_dir, 'settings.yaml')
        
        print(f"Attempting to load settings from: {settings_path}")  # Debug print
        
        if not os.path.exists(settings_path):
            print(f"Settings file not found at: {settings_path}")
            return {}
            
        with open(settings_path, 'r') as f:
            settings = yaml.safe_load(f)
            return settings.get('chart_viewer', {})
            
    except Exception as e:
        print(f"Error loading settings: {str(e)}")
        return {}

def create_chart_with_indicators(data: pd.DataFrame, market_data: MarketData, settings: dict):
    """Create chart with indicators based on settings"""
    chart = CandlestickChart(data)
    
    indicators = settings.get('indicators', {})
    if not indicators.get('enabled', True):
        return chart
        
    # Add EMAs if enabled
    ema_settings = indicators.get('ema', {})
    if ema_settings.get('enabled', True):
        ema_calc = EMACalculator(market_data, periods=ema_settings.get('periods', [9, 21, 55, 200]))
        emas = ema_calc.calculate()
        
        for i, period in enumerate(ema_settings.get('periods', [])):
            color = ema_settings.get('colors', [])[i] if i < len(ema_settings.get('colors', [])) else None
            chart.add_overlay({
                'data': emas[f'ema_{period}'],
                'type': 'line',
                'name': f'EMA-{period}',
                'color': color
            })
    
    # Add MACD if enabled
    macd_settings = indicators.get('macd', {})
    if macd_settings.get('enabled', True):
        macd_calc = MACDCalculator(
            market_data,
            fast_period=macd_settings.get('fast_period', 12),
            slow_period=macd_settings.get('slow_period', 26),
            signal_period=macd_settings.get('signal_period', 9)
        )
        macd_data = macd_calc.calculate()
        
        chart.add_indicator({
            'data': macd_data['macd_line'],
            'type': 'line',
            'name': 'MACD',
            'panel': 2
        })
    
    return chart

def main():
    """Main function to display interactive charts"""
    # Load settings
    settings = load_chart_settings()
    
    while True:
        # Get user input
        inputs = get_user_input()
        if not inputs:
            break
            
        ticker, period, interval = inputs
        
        try:
            # Get data
            stock = yf.Ticker(ticker)
            data = stock.history(period=period, interval=interval)
            
            if data.empty:
                print(f"No data available for {ticker}")
                continue
                
            # Prepare data
            data = prepare_data(data)
            
            # Create MarketData object for indicators
            market_data = MarketData(
                high=data['High'],
                low=data['Low'],
                close=data['Close'],
                volume=data['Volume'],
                period=20  # Default period for indicators
            )
            
            # Create chart with indicators based on settings
            chart = create_chart_with_indicators(data, market_data, settings)
            
            # Show chart
            chart.show()
            
        except Exception as e:
            print(f"Error creating chart: {str(e)}")
            logging.exception("Error in chart creation")
            continue

if __name__ == "__main__":
    if __package__ is None:
        __package__ = "goldflipper.chart"
    main() 