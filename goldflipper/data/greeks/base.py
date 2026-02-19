from dataclasses import dataclass
from typing import Any, cast

import numpy as np


@dataclass
class OptionData:
    """Data structure for options calculations"""

    underlying_price: float
    strike_price: float
    time_to_expiry: float  # in years
    risk_free_rate: float
    volatility: float
    dividend_yield: float = 0.0
    option_price: float = 0.0


class GreeksCalculator:
    """Base class for calculating option Greeks"""

    def __init__(self, option_data: OptionData):
        self.data = option_data
        self._validate_inputs()

    def _validate_inputs(self):
        """Validate input parameters"""
        if not all(
            isinstance(cast(Any, x), (int, float))
            for x in [
                self.data.underlying_price,
                self.data.strike_price,
                self.data.time_to_expiry,
                self.data.risk_free_rate,
                self.data.volatility,
                self.data.dividend_yield,
            ]
        ):
            raise ValueError("All inputs must be numeric")

        if self.data.underlying_price <= 0:
            raise ValueError("Underlying price must be positive")
        if self.data.strike_price <= 0:
            raise ValueError("Strike price must be positive")
        if self.data.time_to_expiry <= 0:
            raise ValueError("Time to expiry must be positive")
        if self.data.volatility <= 0:
            raise ValueError("Volatility must be positive")

    def _calculate_d1(self) -> float:
        """Calculate d1 component of Black-Scholes formula"""
        numerator = (
            np.log(self.data.underlying_price / self.data.strike_price)
            + (self.data.risk_free_rate - self.data.dividend_yield + 0.5 * self.data.volatility**2) * self.data.time_to_expiry
        )
        denominator = self.data.volatility * np.sqrt(self.data.time_to_expiry)
        return numerator / denominator

    def _calculate_d2(self) -> float:
        """Calculate d2 component of Black-Scholes formula"""
        return self._calculate_d1() - self.data.volatility * np.sqrt(self.data.time_to_expiry)
