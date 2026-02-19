from abc import abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass
class MarketData:
    """Data structure for market data calculations"""

    high: pd.Series
    low: pd.Series
    close: pd.Series
    volume: pd.Series
    period: int = 20  # Default lookback period


class IndicatorCalculator:
    """Base class for calculating market indicators"""

    def __init__(self, market_data: MarketData):
        self.data = market_data
        self._validate_inputs()

    def _validate_inputs(self):
        """Validate input parameters"""
        if not all(isinstance(x, pd.Series) for x in [self.data.high, self.data.low, self.data.close, self.data.volume]):
            raise ValueError("Price and volume data must be pandas Series")

        if len(self.data.close) < self.data.period:
            raise ValueError(f"Insufficient data points. Need at least {self.data.period} points")

    @abstractmethod
    def calculate(self) -> dict[str, pd.Series]:
        """Calculate the indicator values"""
        pass
