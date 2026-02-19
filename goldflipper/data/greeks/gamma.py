import numpy as np
from scipy.stats import norm

from .base import GreeksCalculator


class GammaCalculator(GreeksCalculator):
    """Calculator for option Gamma"""

    def calculate(self, option_type: str) -> float:
        """
        Calculate Gamma (same for both calls and puts)

        Args:
            option_type: str, either 'call' or 'put' (not used for Gamma)

        Returns:
            float: The calculated Gamma value
        """
        d1 = self._calculate_d1()

        # Calculate gamma (same formula for both calls and puts)
        discount = np.exp(-self.data.dividend_yield * self.data.time_to_expiry)
        numerator = discount * norm.pdf(d1)
        denominator = self.data.underlying_price * self.data.volatility * np.sqrt(self.data.time_to_expiry)

        return numerator / denominator
