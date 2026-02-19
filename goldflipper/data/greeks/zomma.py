import numpy as np

from .base import GreeksCalculator


class ZommaCalculator(GreeksCalculator):
    """Calculator for option Zomma (DgammaDvol)

    Zomma measures the rate of change of gamma with respect to volatility.
    It shows how the convexity of the position changes as volatility changes.

    For both calls and puts:
    zomma = gamma * ((d1 * d2 - 1) / σ)

    where:
    - gamma is the option's gamma
    - d1 = (ln(S/K) + (r - q + σ²/2)T) / (σ√T)
    - d2 = d1 - σ√T
    - S is the underlying price
    - K is the strike price
    - σ is volatility
    - T is time to expiry
    - r is risk-free rate
    - q is dividend yield
    """

    def calculate(self, option_type: str) -> float:
        """
        Calculate Zomma for either call or put option

        Args:
            option_type: str, either 'call' or 'put'

        Returns:
            float: The calculated Zomma value
        """
        option_type = option_type.lower()
        if option_type not in ["call", "put"]:
            raise ValueError("Option type must be either 'call' or 'put'")

        # Handle edge cases
        if self.data.volatility == 0:
            return 0.0

        # Calculate d1 and d2
        sqrt_t = np.sqrt(self.data.time_to_expiry)
        d1 = (
            np.log(self.data.underlying_price / self.data.strike_price)
            + (self.data.risk_free_rate - self.data.dividend_yield + 0.5 * self.data.volatility**2) * self.data.time_to_expiry
        ) / (self.data.volatility * sqrt_t)

        d2 = d1 - self.data.volatility * sqrt_t

        # Calculate gamma first
        from .gamma import GammaCalculator

        gamma_calc = GammaCalculator(self.data)
        gamma = gamma_calc.calculate(option_type)

        # Calculate zomma
        # Note: Zomma is the same for both calls and puts
        zomma = gamma * ((d1 * d2 - 1) / self.data.volatility)

        return zomma
