from .base import GreeksCalculator
import numpy as np
from scipy.stats import norm

class UltimaCalculator(GreeksCalculator):
    """Calculator for option Ultima (DvommaDvol)
    
    Ultima measures the rate of change of vomma with respect to volatility.
    It is the third derivative of option value with respect to volatility.
    
    For both calls and puts:
    ultima = -(vega / σ³) * (d1 * d2 * (d1² + d2² - 3) + d1 * d2)
    
    where:
    - vega is the option's vega
    - σ is volatility
    - d1 = (ln(S/K) + (r - q + σ²/2)T) / (σ√T)
    - d2 = d1 - σ√T
    """
    
    def calculate(self, option_type: str) -> float:
        """
        Calculate Ultima for either call or put option
        
        Args:
            option_type: str, either 'call' or 'put'
            
        Returns:
            float: The calculated Ultima value
        """
        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise ValueError("Option type must be either 'call' or 'put'")
            
        # Handle edge cases
        if self.data.volatility == 0:
            return 0.0
            
        # Calculate d1 and d2
        sqrt_t = np.sqrt(self.data.time_to_expiry)
        d1 = (np.log(self.data.underlying_price / self.data.strike_price) + 
              (self.data.risk_free_rate - self.data.dividend_yield + 
               0.5 * self.data.volatility ** 2) * self.data.time_to_expiry) / \
             (self.data.volatility * sqrt_t)
        
        d2 = d1 - self.data.volatility * sqrt_t
        
        # Calculate vega first
        from .vega import VegaCalculator
        vega_calc = VegaCalculator(self.data)
        vega = vega_calc.calculate(option_type)
        
        # Calculate ultima
        # Note: Ultima is the same for both calls and puts
        ultima = -(vega / (self.data.volatility ** 3)) * \
                (d1 * d2 * (d1 ** 2 + d2 ** 2 - 3) + d1 * d2)
        
        return ultima 