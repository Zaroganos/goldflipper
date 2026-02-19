import numpy as np
from scipy.stats import norm

from .base import GreeksCalculator


class DeltaCalculator(GreeksCalculator):
    """Calculator for option Delta"""

    def calculate_call_delta(self) -> float:
        """Calculate Delta for a call option"""
        d1 = self._calculate_d1()
        discount = np.exp(-self.data.dividend_yield * self.data.time_to_expiry)
        return discount * norm.cdf(d1)

    def calculate_put_delta(self) -> float:
        """Calculate Delta for a put option"""
        d1 = self._calculate_d1()
        discount = np.exp(-self.data.dividend_yield * self.data.time_to_expiry)
        return discount * (norm.cdf(d1) - 1)

    def calculate(self, option_type: str) -> float:
        """
        Calculate Delta for either call or put option

        Args:
            option_type: str, either 'call' or 'put'

        Returns:
            float: The calculated Delta value
        """
        option_type = option_type.lower()
        if option_type not in ["call", "put"]:
            raise ValueError("Option type must be either 'call' or 'put'")

        if option_type == "call":
            return self.calculate_call_delta()
        return self.calculate_put_delta()
