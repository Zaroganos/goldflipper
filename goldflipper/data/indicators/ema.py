import pandas as pd

from .base import IndicatorCalculator, MarketData


class EMACalculator(IndicatorCalculator):
    """Calculator for Exponential Moving Average (EMA) indicator"""

    def __init__(self, market_data: MarketData, periods: list[int] = None):
        """
        Initialize EMA Calculator

        Args:
            market_data: MarketData object containing price data
            periods: List of periods for calculating multiple EMAs
        """
        if periods is None:
            periods = [9, 21, 55, 200]
        super().__init__(market_data)
        self.periods = periods

    def _calculate_single_ema(self, period: int) -> pd.Series:
        """Calculate EMA for a single period"""
        return self.data.close.ewm(span=period, adjust=False).mean()

    def _determine_trends(self, emas: dict[str, pd.Series]) -> dict[str, bool]:
        """Determine if price is above/below each EMA and trend direction"""
        current_price = self.data.close.iloc[-1]
        trends = {}

        for ema_key, ema_values in emas.items():
            # Extract period number from the ema_key (e.g., 'ema_9' -> '9')
            period = ema_key.split("_")[1]
            current_ema = ema_values.iloc[-1]
            prev_ema = ema_values.iloc[-2]

            # Use period number in trend keys to match display function expectations
            trends[f"{period}_above"] = current_price > current_ema
            trends[f"{period}_rising"] = current_ema > prev_ema

        # Add 9/21 EMA crossover check if both periods exist
        if "ema_9" in emas and "ema_21" in emas:
            trends["9_21_crossover_bullish"] = emas["ema_9"].iloc[-1] > emas["ema_21"].iloc[-1]
            # Also add previous state to detect crossover events
            trends["9_21_crossover_up"] = (emas["ema_9"].iloc[-1] > emas["ema_21"].iloc[-1]) and (emas["ema_9"].iloc[-2] <= emas["ema_21"].iloc[-2])
            trends["9_21_crossover_down"] = (emas["ema_9"].iloc[-1] < emas["ema_21"].iloc[-1]) and (emas["ema_9"].iloc[-2] >= emas["ema_21"].iloc[-2])

        return trends

    def calculate(self) -> dict[str, pd.Series]:
        """
        Calculate EMAs and their trends

        Returns:
            Dict containing:
            - 'ema_{period}': EMA values for each period
            - '{period}_above': Boolean indicating if price is above EMA
            - '{period}_rising': Boolean indicating if EMA is rising
        """
        # Calculate EMAs for each period
        emas = {f"ema_{period}": self._calculate_single_ema(period) for period in self.periods}

        # Get current trends
        trends = self._determine_trends(emas)

        # Combine EMAs and trends
        results = {**emas}

        # Add latest trend values as single-value series
        for trend_key, trend_value in trends.items():
            results[trend_key] = pd.Series([trend_value])

        return results
