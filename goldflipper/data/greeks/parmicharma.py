import numpy as np
from scipy.stats import norm

from .base import GreeksCalculator


class ParmicharmaCalculator(GreeksCalculator):
    """Calculator for option Parmicharma (DcharmDtime)

    Parmicharma measures the rate of change of charm with respect to time.
    It is the third derivative of option value with respect to time (twice)
    and underlying price (once).

    For calls:
    parmicharma = -(e^(-q*T)/(2*S*T*σ*√T)) * N'(d1) *
                  ((2*q*T + 1)*(2*q*T + d1/(σ*√T)) +
                   (2*(r-q)*T - d2*σ*√T)*(1 + d1/(σ*√T)))

    For puts:
    parmicharma = same as calls

    where:
    - N'(x) is the standard normal PDF
    - S is the underlying price
    - T is time to expiry
    - σ is volatility
    - r is risk-free rate
    - q is dividend yield
    - d1 = (ln(S/K) + (r - q + σ²/2)T) / (σ√T)
    - d2 = d1 - σ√T
    """

    def calculate(self, option_type: str) -> float:
        """
        Calculate Parmicharma for either call or put option

        Args:
            option_type: str, either 'call' or 'put'

        Returns:
            float: The calculated Parmicharma value
        """
        option_type = option_type.lower()
        if option_type not in ["call", "put"]:
            raise ValueError("Option type must be either 'call' or 'put'")

        # Handle edge cases
        if self.data.time_to_expiry == 0 or self.data.volatility == 0:
            return 0.0

        # Calculate d1 and d2
        sqrt_t = np.sqrt(self.data.time_to_expiry)
        d1 = (
            np.log(self.data.underlying_price / self.data.strike_price)
            + (self.data.risk_free_rate - self.data.dividend_yield + 0.5 * self.data.volatility**2) * self.data.time_to_expiry
        ) / (self.data.volatility * sqrt_t)

        d2 = d1 - self.data.volatility * sqrt_t

        # Calculate parmicharma
        # Note: Parmicharma is the same for both calls and puts
        parmicharma = (
            -(
                np.exp(-self.data.dividend_yield * self.data.time_to_expiry)
                / (2 * self.data.underlying_price * self.data.time_to_expiry * self.data.volatility * sqrt_t)
            )
            * norm.pdf(d1)
            * (
                (2 * self.data.dividend_yield * self.data.time_to_expiry + 1)
                * (2 * self.data.dividend_yield * self.data.time_to_expiry + d1 / (self.data.volatility * sqrt_t))
                + (2 * (self.data.risk_free_rate - self.data.dividend_yield) * self.data.time_to_expiry - d2 * self.data.volatility * sqrt_t)
                * (1 + d1 / (self.data.volatility * sqrt_t))
            )
        )

        return parmicharma
