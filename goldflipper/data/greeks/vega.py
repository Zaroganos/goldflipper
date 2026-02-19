import numpy as np
from scipy.stats import norm

from .base import GreeksCalculator


class VegaCalculator(GreeksCalculator):
    """Calculator for option Vega"""

    def calculate(self, option_type: str) -> float:
        """
        Calculate Vega (same for both calls and puts)

        Args:
            option_type: str, either 'call' or 'put' (not used for Vega)

        Returns:
            float: The calculated Vega value
        """
        d1 = self._calculate_d1()

        # Calculate vega (same formula for both calls and puts)
        vega = (
            self.data.underlying_price
            * np.exp(-self.data.dividend_yield * self.data.time_to_expiry)
            * np.sqrt(self.data.time_to_expiry)
            * norm.pdf(d1)
        )

        # Convert to percentage points (standard market convention)
        return vega / 100.0
