from .base import GreeksCalculator
import numpy as np
from scipy.stats import norm

class VeraCalculator(GreeksCalculator):
    """Calculator for option Vera (Rhova)
    
    Vera measures the rate of change of rho with respect to volatility.
    It shows how interest rate sensitivity changes with volatility changes.
    
    For a call option:
    vera = T * K * e^(-rT) * N'(d2) * d1 / σ
    
    For a put option:
    vera = -T * K * e^(-rT) * N'(-d2) * d1 / σ
    
    where:
    - T is time to expiry
    - K is strike price
    - r is risk-free rate
    - N'(x) is the standard normal PDF
    - d1 = (ln(S/K) + (r - q + σ²/2)T) / (σ√T)
    - d2 = d1 - σ√T
    - σ is volatility
    """
    
    def calculate(self, option_type: str) -> float:
        """
        Calculate Vera for either call or put option
        
        Args:
            option_type: str, either 'call' or 'put'
            
        Returns:
            float: The calculated Vera value
        """
        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise ValueError("Option type must be either 'call' or 'put'")
            
        # Handle edge cases
        if self.data.time_to_expiry == 0 or self.data.volatility == 0:
            return 0.0
            
        # Calculate d1 and d2
        sqrt_t = np.sqrt(self.data.time_to_expiry)
        d1 = (np.log(self.data.underlying_price / self.data.strike_price) + 
              (self.data.risk_free_rate - self.data.dividend_yield + 
               0.5 * self.data.volatility ** 2) * self.data.time_to_expiry) / \
             (self.data.volatility * sqrt_t)
        
        d2 = d1 - self.data.volatility * sqrt_t
        
        # Calculate vera
        vera = (self.data.time_to_expiry * self.data.strike_price * 
                np.exp(-self.data.risk_free_rate * self.data.time_to_expiry) * 
                norm.pdf(d2 if option_type == 'call' else -d2) * d1 / 
                self.data.volatility)
        
        # Adjust sign for put options
        if option_type == 'put':
            vera = -vera
            
        return vera 