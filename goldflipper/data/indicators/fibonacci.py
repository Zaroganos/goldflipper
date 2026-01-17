"""
Fibonacci Retracement Calculator

Calculates Fibonacci retracement levels from swing high/low points.
Used for identifying Key Entry Points (KEPs) in the trading strategy.
"""

import pandas as pd
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass


@dataclass
class SwingPoint:
    """Represents a swing high or low point"""
    price: float
    index: int
    is_high: bool


class FibonacciCalculator:
    """Calculate Fibonacci retracement levels from swing high/low.
    
    Fibonacci retracement levels are horizontal lines that indicate potential
    support and resistance levels based on the Fibonacci sequence.
    
    Standard levels:
    - 23.6%: Shallow retracement
    - 38.2%: Moderate retracement (key level)
    - 50.0%: Half retracement
    - 61.8%: Deep retracement (golden ratio, key level)
    - 78.6%: Very deep retracement
    """
    
    LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]
    LEVEL_NAMES = {
        0.236: '23.6%',
        0.382: '38.2%',
        0.5: '50.0%',
        0.618: '61.8%',
        0.786: '78.6%'
    }
    
    @staticmethod
    def calculate(swing_high: float, swing_low: float, trend: str = 'up') -> Dict[str, float]:
        """
        Calculate Fibonacci retracement levels.
        
        Args:
            swing_high: Recent swing high price
            swing_low: Recent swing low price  
            trend: 'up' (retracement from high) or 'down' (retracement from low)
            
        Returns:
            Dict with fib_236, fib_382, fib_500, fib_618, fib_786 levels
        """
        if swing_high <= swing_low:
            raise ValueError("Swing high must be greater than swing low")
        
        diff = swing_high - swing_low
        levels = {}
        
        for level in FibonacciCalculator.LEVELS:
            level_key = f'fib_{int(level*1000)}'
            if trend == 'up':
                # Retracement down from high (for pullback entries in uptrend)
                levels[level_key] = swing_high - (diff * level)
            else:
                # Retracement up from low (for pullback entries in downtrend)
                levels[level_key] = swing_low + (diff * level)
        
        # Also include the swing points themselves
        levels['swing_high'] = swing_high
        levels['swing_low'] = swing_low
        levels['trend'] = trend
        levels['range'] = diff
        
        return levels
    
    @staticmethod
    def find_swing_points(ohlc_data: pd.DataFrame, lookback: int = 20) -> Tuple[float, float]:
        """
        Find recent swing high and low from OHLC data.
        
        Args:
            ohlc_data: DataFrame with 'high' and 'low' columns (lowercase)
            lookback: Number of periods to look back for swing points
            
        Returns:
            Tuple of (swing_high, swing_low)
        """
        if ohlc_data is None or len(ohlc_data) < lookback:
            raise ValueError(f"Need at least {lookback} data points")
        
        # Normalize column names to lowercase
        df = ohlc_data.copy()
        df.columns = df.columns.str.lower()
        
        recent = df.tail(lookback)
        swing_high = recent['high'].max()
        swing_low = recent['low'].min()
        
        return swing_high, swing_low
    
    @staticmethod
    def find_swing_points_advanced(
        ohlc_data: pd.DataFrame, 
        lookback: int = 20,
        min_swing_bars: int = 3
    ) -> List[SwingPoint]:
        """
        Find swing highs and lows using pivot point detection.
        
        A swing high is a high that is higher than the highs on both sides.
        A swing low is a low that is lower than the lows on both sides.
        
        Args:
            ohlc_data: DataFrame with high/low columns
            lookback: Number of periods to analyze
            min_swing_bars: Minimum bars on each side to confirm swing
            
        Returns:
            List of SwingPoint objects
        """
        df = ohlc_data.copy()
        df.columns = df.columns.str.lower()
        
        if len(df) < lookback:
            lookback = len(df)
        
        recent = df.tail(lookback).reset_index(drop=True)
        swing_points = []
        
        for i in range(min_swing_bars, len(recent) - min_swing_bars):
            # Check for swing high
            is_swing_high = True
            for j in range(1, min_swing_bars + 1):
                if recent['high'].iloc[i] <= recent['high'].iloc[i - j] or \
                   recent['high'].iloc[i] <= recent['high'].iloc[i + j]:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                swing_points.append(SwingPoint(
                    price=recent['high'].iloc[i],
                    index=i,
                    is_high=True
                ))
            
            # Check for swing low
            is_swing_low = True
            for j in range(1, min_swing_bars + 1):
                if recent['low'].iloc[i] >= recent['low'].iloc[i - j] or \
                   recent['low'].iloc[i] >= recent['low'].iloc[i + j]:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                swing_points.append(SwingPoint(
                    price=recent['low'].iloc[i],
                    index=i,
                    is_high=False
                ))
        
        return swing_points
    
    @staticmethod
    def determine_trend(ohlc_data: pd.DataFrame, lookback: int = 20) -> str:
        """
        Determine the recent trend direction based on price action.
        
        Args:
            ohlc_data: DataFrame with close prices
            lookback: Number of periods to analyze
            
        Returns:
            'up' if in uptrend, 'down' if in downtrend
        """
        df = ohlc_data.copy()
        df.columns = df.columns.str.lower()
        
        if len(df) < lookback:
            lookback = len(df)
        
        recent = df.tail(lookback)
        
        # Simple trend detection: compare first half to second half
        mid = len(recent) // 2
        first_half_avg = recent['close'].iloc[:mid].mean()
        second_half_avg = recent['close'].iloc[mid:].mean()
        
        return 'up' if second_half_avg > first_half_avg else 'down'
    
    @staticmethod
    def calculate_from_ohlc(
        ohlc_data: pd.DataFrame, 
        lookback: int = 20,
        auto_detect_trend: bool = True
    ) -> Optional[Dict[str, float]]:
        """
        Convenience method to calculate Fibonacci levels from OHLC data.
        
        Args:
            ohlc_data: DataFrame with OHLC data
            lookback: Number of periods to look back
            auto_detect_trend: If True, automatically detect trend direction
            
        Returns:
            Dict with Fibonacci levels or None if insufficient data
        """
        try:
            swing_high, swing_low = FibonacciCalculator.find_swing_points(ohlc_data, lookback)
            
            if auto_detect_trend:
                trend = FibonacciCalculator.determine_trend(ohlc_data, lookback)
            else:
                trend = 'up'  # Default to uptrend (retracement from high)
            
            return FibonacciCalculator.calculate(swing_high, swing_low, trend)
            
        except (ValueError, KeyError) as e:
            return None
    
    @staticmethod
    def get_nearest_fib_level(
        current_price: float, 
        fib_levels: Dict[str, float],
        threshold_pct: float = 0.02
    ) -> Optional[Dict[str, any]]:
        """
        Find the nearest Fibonacci level to the current price.
        
        Args:
            current_price: Current stock price
            fib_levels: Dict of Fibonacci levels from calculate()
            threshold_pct: Proximity threshold as decimal (default 2%)
            
        Returns:
            Dict with nearest level info or None if not near any level
        """
        nearest = None
        min_distance = float('inf')
        
        for key, level in fib_levels.items():
            if not key.startswith('fib_'):
                continue
            
            if not isinstance(level, (int, float)):
                continue
                
            distance = abs(current_price - level)
            distance_pct = distance / current_price
            
            if distance_pct <= threshold_pct and distance < min_distance:
                min_distance = distance
                level_pct = int(key.split('_')[1]) / 10  # Convert fib_382 to 38.2
                nearest = {
                    'level_key': key,
                    'level_name': f'{level_pct}%',
                    'level_price': level,
                    'distance': distance,
                    'distance_pct': distance_pct * 100,
                    'above': current_price > level
                }
        
        return nearest
