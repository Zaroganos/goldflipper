from .base import GreeksCalculator
import numpy as np
from scipy.stats import norm

class VetaCalculator(GreeksCalculator):
    """Calculator for option Veta (DvegaDtime)
    
    Veta measures the rate of change of vega with respect to time.
    It tells us how vega changes as time passes.
    
    For both calls and puts:
    veta = -S * N'(d1) * √T * (d1 * d2 / (2 * T) - (r - q) / (σ * √T))
    
    where:
    - S is the underlying price
    - N'(x) is the standard normal PDF
    - T is time to expiry
    - d1 = (ln(S/K) + (r - q + σ²/2)T) / (σ√T)
    - d2 = d1 - σ√T
    - σ is volatility
    - r is risk-free rate
    - q is dividend yield
    """
    
    def calculate(self, option_type: str) -> float:
        """
        Calculate Veta for either call or put option
        
        Args:
            option_type: str, either 'call' or 'put'
            
        Returns:
            float: The calculated Veta value
        """
        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise ValueError("Option type must be either 'call' or 'put'")
        
        # Handle edge case of zero time to expiry
        if self.data.time_to_expiry == 0:
            return 0.0
            
        # Calculate d1 and d2
        sqrt_t = np.sqrt(self.data.time_to_expiry)
        d1 = (np.log(self.data.underlying_price / self.data.strike_price) + 
              (self.data.risk_free_rate - self.data.dividend_yield + 
               0.5 * self.data.volatility ** 2) * self.data.time_to_expiry) / \
             (self.data.volatility * sqrt_t)
        
        d2 = d1 - self.data.volatility * sqrt_t
        
        # Calculate veta
        # Note: Veta is the same for both calls and puts
        veta = -self.data.underlying_price * norm.pdf(d1) * sqrt_t * (
            (d1 * d2) / (2 * self.data.time_to_expiry) - 
            (self.data.risk_free_rate - self.data.dividend_yield) / 
            (self.data.volatility * sqrt_t)
        )
        
        return veta 