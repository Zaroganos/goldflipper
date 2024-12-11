from .base import GreeksCalculator
import numpy as np
from scipy.stats import norm

class VommaCalculator(GreeksCalculator):
    """Calculator for option Vomma (Volga)
    
    Vomma measures the second derivative of the option price with respect to volatility,
    or the rate of change of vega with respect to volatility.
    
    For both calls and puts:
    vomma = vega * (d1 * d2) / σ
    
    where:
    - vega is the option's vega
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
        Calculate Vomma for either call or put option
        
        Args:
            option_type: str, either 'call' or 'put'
            
        Returns:
            float: The calculated Vomma value
        """
        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise ValueError("Option type must be either 'call' or 'put'")
        
        # Calculate d1 and d2
        d1 = (np.log(self.data.underlying_price / self.data.strike_price) + 
              (self.data.risk_free_rate - self.data.dividend_yield + 
               0.5 * self.data.volatility ** 2) * self.data.time_to_expiry) / \
             (self.data.volatility * np.sqrt(self.data.time_to_expiry))
        
        d2 = d1 - self.data.volatility * np.sqrt(self.data.time_to_expiry)
        
        # Calculate vega first
        from .vega import VegaCalculator
        vega_calc = VegaCalculator(self.data)
        vega = vega_calc.calculate(option_type)
        
        # Calculate vomma
        # Note: Vomma is the same for both calls and puts
        if self.data.volatility == 0:
            return 0.0
            
        vomma = vega * (d1 * d2) / self.data.volatility
        
        return vomma 