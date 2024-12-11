from .base import GreeksCalculator
import numpy as np
from scipy.stats import norm

class CharmCalculator(GreeksCalculator):
    """Calculator for option Charm (Delta Decay)
    
    Charm measures the instantaneous rate of change of delta with respect to time.
    It is the second derivative of value with respect to time and price.
    
    For a call option:
    charm = -N'(d1) * (2*(r-q)*T - d2*σ*√T) / (2*T*σ*√T)
    
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
        Calculate Charm for either call or put option
        
        Args:
            option_type: str, either 'call' or 'put'
            
        Returns:
            float: The calculated Charm value
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
        
        # Calculate charm
        if self.data.time_to_expiry == 0:
            return 0.0
            
        charm = -norm.pdf(d1) * (
            2 * (self.data.risk_free_rate - self.data.dividend_yield) * 
            self.data.time_to_expiry - d2 * self.data.volatility * 
            np.sqrt(self.data.time_to_expiry)
        ) / (2 * self.data.time_to_expiry * self.data.volatility * 
             np.sqrt(self.data.time_to_expiry))
        
        # Adjust for puts (charm is negative for puts)
        if option_type == 'put':
            charm = -charm
            
        return charm 