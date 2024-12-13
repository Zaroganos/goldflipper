import pandas as pd
import numpy as np
from typing import Dict, Any
from .base import IndicatorCalculator, MarketData

class TTMSqueezeCalculator(IndicatorCalculator):
    """Calculator for TTM Squeeze indicator"""
    
    def __init__(self, market_data: MarketData, bb_mult: float = 2.0, kc_mult: float = 1.5):
        super().__init__(market_data)
        self.bb_mult = bb_mult  # Bollinger Bands multiplier
        self.kc_mult = kc_mult  # Keltner Channel multiplier
    
    def _calculate_bollinger_bands(self) -> tuple:
        """Calculate Bollinger Bands"""
        typical_price = (self.data.high + self.data.low + self.data.close) / 3
        sma = typical_price.rolling(window=self.data.period).mean()
        std = typical_price.rolling(window=self.data.period).std()
        
        upper_bb = sma + (self.bb_mult * std)
        lower_bb = sma - (self.bb_mult * std)
        
        return upper_bb, lower_bb
    
    def _calculate_keltner_channels(self) -> tuple:
        """Calculate Keltner Channels"""
        typical_price = (self.data.high + self.data.low + self.data.close) / 3
        ema = typical_price.ewm(span=self.data.period).mean()
        atr = self._calculate_atr()
        
        upper_kc = ema + (self.kc_mult * atr)
        lower_kc = ema - (self.kc_mult * atr)
        
        return upper_kc, lower_kc
    
    def _calculate_atr(self) -> pd.Series:
        """Calculate Average True Range"""
        high_low = self.data.high - self.data.low
        high_close = np.abs(self.data.high - self.data.close.shift())
        low_close = np.abs(self.data.low - self.data.close.shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        
        return true_range.rolling(window=self.data.period).mean()
    
    def _calculate_momentum(self) -> pd.Series:
        """Calculate momentum for squeeze"""
        lowest_low = self.data.low.rolling(window=self.data.period).min()
        highest_high = self.data.high.rolling(window=self.data.period).max()
        
        momentum = (self.data.close - ((highest_high + lowest_low) / 2))
        normalized_momentum = momentum / self.data.close * 100
        
        return normalized_momentum
    
    def calculate(self) -> Dict[str, pd.Series]:
        """
        Calculate TTM Squeeze indicator values
        
        Returns:
            Dict containing:
            - 'squeeze_on': Boolean indicating squeeze condition
            - 'momentum': Current momentum value
            - 'momentum_increasing': Boolean indicating increasing momentum
        """
        upper_bb, lower_bb = self._calculate_bollinger_bands()
        upper_kc, lower_kc = self._calculate_keltner_channels()
        
        # Calculate squeeze condition for all data points
        squeeze_condition = (lower_bb > lower_kc) & (upper_bb < upper_kc)
        
        # Calculate momentum
        momentum = self._calculate_momentum()
        
        # Get latest values for indicators
        squeeze_on = pd.Series([squeeze_condition.iloc[-1]])
        current_momentum = pd.Series([momentum.iloc[-1]])
        momentum_increasing = pd.Series([momentum.iloc[-1] > momentum.iloc[-2]])
        
        return {
            'squeeze_on': squeeze_on,
            'momentum': current_momentum,
            'momentum_increasing': momentum_increasing
        } 