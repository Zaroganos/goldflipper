from abc import ABC, abstractmethod
import mplfinance as mpf
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Any

class BaseChart(ABC):
    """Base class for all charts"""
    
    def __init__(self, data: pd.DataFrame):
        """
        Initialize chart with data
        
        Args:
            data: DataFrame with OHLCV data (must have datetime index)
        """
        self.validate_data(data)
        self.data = data
        self.figure = None
        self.axes = None
        self.overlays = []
        self.indicators = []
        
    @abstractmethod
    def validate_data(self, data: pd.DataFrame) -> None:
        """Validate input data format"""
        pass
        
    @abstractmethod
    def create(self) -> None:
        """Create the base chart"""
        pass
        
    @abstractmethod
    def add_overlay(self, overlay: Any) -> None:
        """Add an overlay to the chart (e.g., EMAs)"""
        pass
        
    @abstractmethod
    def add_indicator(self, indicator: Any) -> None:
        """Add an indicator panel (e.g., MACD, RSI)"""
        pass
        
    @abstractmethod
    def show(self) -> None:
        """Display the chart"""
        pass
        
    @abstractmethod
    def save(self, filename: str) -> None:
        """Save chart to file"""
        pass 