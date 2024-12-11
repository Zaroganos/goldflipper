from .base import GreeksCalculator
import numpy as np
from scipy.stats import norm

class SpeedCalculator(GreeksCalculator):
    """Calculator for option Speed (DgammaDtime)
    
    Speed measures the rate of change of gamma with respect to time.
    It shows how the convexity of the position changes as time passes.
    
    For both calls and puts:
    speed = -(N'(d1) / (S²σ√T)) * (d1/(σ√T) + 1)
    
    where:
    - N'(x) is the standard normal PDF
    - S is the underlying price
    - σ is volatility
    - T is time to expiry
    - d1 = (ln(S/K) + (r - q + σ²/2)T) / (σ√T)
    """
    
    def calculate(self, option_type: str) -> float:
        """
        Calculate Speed for either call or put option
        
        Args:
            option_type: str, either 'call' or 'put'
            
        Returns:
            float: The calculated Speed value
        """
        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise ValueError("Option type must be either 'call' or 'put'")
            
        # Handle edge cases
        if self.data.time_to_expiry == 0 or self.data.volatility == 0:
            return 0.0
            
        # Calculate d1
        sqrt_t = np.sqrt(self.data.time_to_expiry)
        d1 = (np.log(self.data.underlying_price / self.data.strike_price) + 
              (self.data.risk_free_rate - self.data.dividend_yield + 
               0.5 * self.data.volatility ** 2) * self.data.time_to_expiry) / \
             (self.data.volatility * sqrt_t)
        
        # Calculate speed
        # Note: Speed is the same for both calls and puts
        speed = -(norm.pdf(d1) / 
                 (self.data.underlying_price ** 2 * 
                  self.data.volatility * sqrt_t)) * \
                (d1 / (self.data.volatility * sqrt_t) + 1)
        
        return speed 