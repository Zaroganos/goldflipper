import pandas as pd
from typing import Dict, Optional
from .base import IndicatorCalculator, MarketData


class RSICalculator(IndicatorCalculator):
    """Calculator for Relative Strength Index (RSI) indicator
    
    RSI is a momentum oscillator that measures the speed and magnitude of 
    recent price changes to evaluate overbought or oversold conditions.
    
    RSI = 100 - (100 / (1 + RS))
    Where RS = Average Gain / Average Loss over the lookback period
    
    Standard interpretation:
    - RSI > 70: Overbought (potential sell signal)
    - RSI < 30: Oversold (potential buy signal)
    - RSI around 50: Neutral momentum
    """
    
    def __init__(self, market_data: MarketData, period: int = 14):
        """
        Initialize RSI Calculator
        
        Args:
            market_data: MarketData object containing price data
            period: Lookback period for RSI calculation (default: 14)
        """
        # Override the period in market_data for validation purposes
        market_data.period = period
        super().__init__(market_data)
        self.period = period
    
    def _calculate_rsi(self) -> pd.Series:
        """Calculate RSI using the standard Wilder's smoothing method"""
        # Calculate price changes
        delta = self.data.close.diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0.0)
        losses = (-delta).where(delta < 0, 0.0)
        
        # Use Wilder's smoothing (exponential moving average with alpha=1/period)
        # This is the traditional RSI calculation method
        avg_gain = gains.ewm(alpha=1/self.period, min_periods=self.period, adjust=False).mean()
        avg_loss = losses.ewm(alpha=1/self.period, min_periods=self.period, adjust=False).mean()
        
        # Calculate RS (Relative Strength)
        # Handle division by zero: when avg_loss is 0, RS approaches infinity → RSI = 100
        rs = avg_gain / avg_loss.replace(0, float('nan'))
        
        # Calculate RSI
        rsi = 100 - (100 / (1 + rs))
        
        # When there are no losses, RSI should be 100
        rsi = rsi.fillna(100)
        
        return rsi
    
    def calculate(self) -> Dict[str, pd.Series]:
        """
        Calculate RSI and related values
        
        Returns:
            Dict containing:
            - 'rsi': RSI values for each period
            - 'rsi_current': Current RSI value (single value)
            - 'rsi_overbought': Boolean indicating if RSI > 70
            - 'rsi_oversold': Boolean indicating if RSI < 30
            - 'rsi_increasing': Boolean indicating if RSI is increasing
            - 'rsi_zone': String indicating current zone ('overbought', 'oversold', 'neutral')
        """
        rsi = self._calculate_rsi()
        
        # Get current and previous RSI values
        current_rsi = rsi.iloc[-1] if len(rsi) > 0 else float('nan')
        previous_rsi = rsi.iloc[-2] if len(rsi) > 1 else float('nan')
        
        # Determine conditions
        is_overbought = current_rsi > 70
        is_oversold = current_rsi < 30
        is_increasing = current_rsi > previous_rsi
        
        # Determine zone
        if is_overbought:
            zone = 'overbought'
        elif is_oversold:
            zone = 'oversold'
        else:
            zone = 'neutral'
        
        return {
            'rsi': rsi,
            'rsi_current': pd.Series([current_rsi]),
            'rsi_overbought': pd.Series([is_overbought]),
            'rsi_oversold': pd.Series([is_oversold]),
            'rsi_increasing': pd.Series([is_increasing]),
            'rsi_zone': pd.Series([zone])
        }
    
    @staticmethod
    def calculate_from_prices(close_prices: pd.Series, period: int = 14) -> Optional[float]:
        """
        Convenience method to calculate current RSI from a price series.
        
        This is a static helper for quick RSI calculation without needing
        to construct a full MarketData object.
        
        Args:
            close_prices: Series of close prices
            period: RSI period (default: 14)
            
        Returns:
            Current RSI value or None if insufficient data
        """
        if close_prices is None or len(close_prices) < period + 1:
            return None
        
        # Calculate price changes
        delta = close_prices.diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0.0)
        losses = (-delta).where(delta < 0, 0.0)
        
        # Use Wilder's smoothing
        avg_gain = gains.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = losses.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        
        # Get final values
        final_avg_gain = avg_gain.iloc[-1]
        final_avg_loss = avg_loss.iloc[-1]
        
        # Calculate RSI
        if final_avg_loss == 0:
            return 100.0
        
        rs = final_avg_gain / final_avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)

