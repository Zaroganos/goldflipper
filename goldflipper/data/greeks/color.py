import numpy as np
from scipy.stats import norm

from .base import GreeksCalculator


class ColorCalculator(GreeksCalculator):
    """Calculator for option Color (Gamma Decay, DgammaDtime)

    Color measures the rate of change of gamma with respect to time.
    It shows how the convexity of the position changes as time passes.

    For both calls and puts:
    color = -N'(d1) * (e^(-q*T)/(2*S*σ*T*√T)) *
            (2*(r-q)*T + 1 + (2*σ^2*T - d1*σ*√T)*d1/(σ*√T))

    where:
    - N'(x) is the standard normal PDF
    - S is the underlying price
    - T is time to expiry
    - σ is volatility
    - r is risk-free rate
    - q is dividend yield
    - d1 = (ln(S/K) + (r - q + σ²/2)T) / (σ√T)
    """

    def calculate(self, option_type: str) -> float:
        """
        Calculate Color (Gamma Decay) for either call or put option

        Args:
            option_type: str, either 'call' or 'put'

        Returns:
            float: The calculated Color value
        """
        option_type = option_type.lower()
        if option_type not in ["call", "put"]:
            raise ValueError("Option type must be either 'call' or 'put'")

        # Handle edge cases
        if self.data.time_to_expiry == 0 or self.data.volatility == 0:
            return 0.0

        # Calculate d1
        sqrt_t = np.sqrt(self.data.time_to_expiry)
        d1 = (
            np.log(self.data.underlying_price / self.data.strike_price)
            + (self.data.risk_free_rate - self.data.dividend_yield + 0.5 * self.data.volatility**2) * self.data.time_to_expiry
        ) / (self.data.volatility * sqrt_t)

        # Calculate color (gamma decay)
        # Note: Color is the same for both calls and puts
        color = (
            -norm.pdf(d1)
            * (
                np.exp(-self.data.dividend_yield * self.data.time_to_expiry)
                / (2 * self.data.underlying_price * self.data.volatility * self.data.time_to_expiry * sqrt_t)
            )
            * (
                2 * (self.data.risk_free_rate - self.data.dividend_yield) * self.data.time_to_expiry
                + 1
                + (2 * self.data.volatility**2 * self.data.time_to_expiry - d1 * self.data.volatility * sqrt_t) * d1 / (self.data.volatility * sqrt_t)
            )
        )

        return color
