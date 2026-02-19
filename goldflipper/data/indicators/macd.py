from typing import cast

import pandas as pd

from .base import IndicatorCalculator, MarketData


class MACDCalculator(IndicatorCalculator):
    """Calculator for Moving Average Convergence Divergence (MACD) indicator"""

    def __init__(self, market_data: MarketData, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        """
        Initialize MACD Calculator

        Args:
            market_data: MarketData object containing price data
            fast_period: Period for fast EMA (default: 12)
            slow_period: Period for slow EMA (default: 26)
            signal_period: Period for signal line EMA (default: 9)
        """
        super().__init__(market_data)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def _calculate_ema(self, data: pd.Series, period: int) -> pd.Series:
        """Calculate EMA for a given period"""
        return cast(pd.Series, data.ewm(span=period, adjust=False).mean())

    def calculate(self) -> dict[str, pd.Series]:
        """
        Calculate MACD and related values

        Returns:
            Dict containing:
            - 'macd_line': MACD line (fast EMA - slow EMA)
            - 'signal_line': Signal line (EMA of MACD line)
            - 'macd_histogram': MACD histogram (MACD line - signal line)
            - 'macd_above_signal': Boolean indicating if MACD is above signal line
            - 'histogram_increasing': Boolean indicating if histogram is increasing
            - 'macd_increasing': Boolean indicating if MACD line is increasing
            - 'macd_crossover_up': Boolean indicating MACD crossing above signal line
            - 'macd_crossover_down': Boolean indicating MACD crossing below signal line
        """
        # Calculate EMAs
        fast_ema = self._calculate_ema(self.data.close, self.fast_period)
        slow_ema = self._calculate_ema(self.data.close, self.slow_period)

        # Calculate MACD line
        macd_line = fast_ema - slow_ema

        # Calculate signal line
        signal_line = self._calculate_ema(macd_line, self.signal_period)

        # Calculate histogram
        histogram = macd_line - signal_line

        # Get latest values for boolean indicators
        macd_above_signal = pd.Series([macd_line.iloc[-1] > signal_line.iloc[-1]])
        histogram_increasing = pd.Series([histogram.iloc[-1] > histogram.iloc[-2]])
        macd_increasing = pd.Series([macd_line.iloc[-1] > macd_line.iloc[-2]])

        # Calculate crossovers (for latest point)
        macd_crossover_up = pd.Series([(macd_line.iloc[-1] > signal_line.iloc[-1]) and (macd_line.iloc[-2] <= signal_line.iloc[-2])])
        macd_crossover_down = pd.Series([(macd_line.iloc[-1] < signal_line.iloc[-1]) and (macd_line.iloc[-2] >= signal_line.iloc[-2])])

        return {
            "macd_line": macd_line,
            "signal_line": signal_line,
            "macd_histogram": histogram,
            "macd_above_signal": macd_above_signal,
            "histogram_increasing": histogram_increasing,
            "macd_increasing": macd_increasing,
            "macd_crossover_up": macd_crossover_up,
            "macd_crossover_down": macd_crossover_down,
        }
