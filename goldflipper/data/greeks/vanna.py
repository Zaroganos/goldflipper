from .base import GreeksCalculator
import numpy as np
from scipy.stats import norm

class VannaCalculator(GreeksCalculator):
    """Calculator for option Vanna
    
    Vanna measures the change in delta with respect to volatility,
    or equivalently, the change in vega with respect to the underlying price.
    
    For a call option:
    vanna = -N'(d1) * d2 / (S * σ * √T)
    
    where:
    - N'(x) is the standard normal PDF
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
        Calculate Vanna for either call or put option
        
        Args:
            option_type: str, either 'call' or 'put'
            
        Returns:
            float: The calculated Vanna value
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
        
        # Calculate vanna
        # Note: Vanna is the same for both calls and puts
        vanna = -norm.pdf(d1) * d2 / (self.data.underlying_price * 
                                     self.data.volatility * 
                                     np.sqrt(self.data.time_to_expiry))
        
        return vanna 