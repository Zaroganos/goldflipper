import mplfinance as mpf
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Any
from .base import BaseChart

class CandlestickChart(BaseChart):
    """Candlestick chart implementation"""
    
    def validate_data(self, data: pd.DataFrame) -> None:
        """Validate OHLCV data"""
        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in data.columns for col in required_columns):
            raise ValueError(f"Data must contain columns: {required_columns}")
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("Data must have DatetimeIndex")
    
    def create(self) -> None:
        """Create the base candlestick chart"""
        # Create figure and axes
        self.figure, self.axes = mpf.plot(
            self.data,
            type='candle',
            style='charles',
            volume=True,
            returnfig=True
        )
        
    def add_overlay(self, overlay: Dict[str, Any]) -> None:
        """
        Add an overlay to the chart
        
        Args:
            overlay: Dictionary containing:
                - data: Series or DataFrame to plot
                - type: Type of overlay (e.g., 'line', 'scatter')
                - name: Name for legend
                - color: Color of overlay
        """
        if not self.figure:
            self.create()
            
        # Add overlay to main price panel
        self.axes[0].plot(
            overlay['data'].index,
            overlay['data'].values,
            label=overlay['name'],
            color=overlay.get('color', 'blue')
        )
        self.axes[0].legend()
        
    def add_indicator(self, indicator: Dict[str, Any]) -> None:
        """
        Add an indicator panel
        
        Args:
            indicator: Dictionary containing:
                - data: Series or DataFrame to plot
                - type: Type of indicator (e.g., 'line', 'histogram')
                - name: Name for legend
                - panel: Panel number for indicator
        """
        if not self.figure:
            self.create()
            
        # Create new panel for indicator
        panel = indicator.get('panel', len(self.axes))
        if panel >= len(self.axes):
            self.figure.add_subplot(len(self.axes) + 1, 1, panel + 1)
            
        # Plot indicator
        self.axes[panel].plot(
            indicator['data'].index,
            indicator['data'].values,
            label=indicator['name']
        )
        self.axes[panel].legend()
        
    def show(self) -> None:
        """Display the chart"""
        if not self.figure:
            self.create()
        plt.show()
        
    def save(self, filename: str) -> None:
        """Save chart to file"""
        if not self.figure:
            self.create()
        self.figure.savefig(filename) 