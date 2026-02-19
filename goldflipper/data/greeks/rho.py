import numpy as np
from scipy.stats import norm

from .base import GreeksCalculator


class RhoCalculator(GreeksCalculator):
    """Calculator for option Rho"""

    def calculate_call_rho(self) -> float:
        """Calculate Rho for a call option"""
        d2 = self._calculate_d2()

        rho = self.data.strike_price * self.data.time_to_expiry * np.exp(-self.data.risk_free_rate * self.data.time_to_expiry) * norm.cdf(d2)

        # Convert to basis points (standard market convention)
        return rho / 100.0

    def calculate_put_rho(self) -> float:
        """Calculate Rho for a put option"""
        d2 = self._calculate_d2()

        rho = -self.data.strike_price * self.data.time_to_expiry * np.exp(-self.data.risk_free_rate * self.data.time_to_expiry) * norm.cdf(-d2)

        # Convert to basis points (standard market convention)
        return rho / 100.0

    def calculate(self, option_type: str) -> float:
        """
        Calculate Rho for either call or put option

        Args:
            option_type: str, either 'call' or 'put'

        Returns:
            float: The calculated Rho value (in basis points)
        """
        option_type = option_type.lower()
        if option_type not in ["call", "put"]:
            raise ValueError("Option type must be either 'call' or 'put'")

        if option_type == "call":
            return self.calculate_call_rho()
        return self.calculate_put_rho()
