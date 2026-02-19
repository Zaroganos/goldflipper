from .base import GreeksCalculator


class EpsilonCalculator(GreeksCalculator):
    """Calculator for option Epsilon (ε)

    Epsilon measures the percentage change in option value
    for a 1% change in implied volatility.

    ε = (dV/V)/(dσ/σ) = (vega * σ)/V
    where:
    - V is option price
    - σ (sigma) is implied volatility
    - vega is the option's vega
    """

    def calculate(self, option_type: str) -> float:
        """
        Calculate Epsilon for either call or put option

        Args:
            option_type: str, either 'call' or 'put'

        Returns:
            float: The calculated Epsilon value
        """
        option_type = option_type.lower()
        if option_type not in ["call", "put"]:
            raise ValueError("Option type must be either 'call' or 'put'")

        # Calculate vega first
        from .vega import VegaCalculator

        vega_calc = VegaCalculator(self.data)
        vega = vega_calc.calculate(option_type)

        # Calculate epsilon using the formula: (vega * σ)/V
        # where σ is volatility and V is option price
        epsilon = (vega * self.data.volatility) / self.data.option_price

        return epsilon
