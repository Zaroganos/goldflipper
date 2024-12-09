from .base import GreeksCalculator
from scipy.stats import norm
import numpy as np

class ThetaCalculator(GreeksCalculator):
    """Calculator for option Theta"""
    
    def calculate_call_theta(self) -> float:
        """Calculate Theta for a call option"""
        d1 = self._calculate_d1()
        d2 = self._calculate_d2()
        
        term1 = -(self.data.underlying_price * self.data.volatility * 
                 np.exp(-self.data.dividend_yield * self.data.time_to_expiry) * 
                 norm.pdf(d1)) / (2 * np.sqrt(self.data.time_to_expiry))
        
        term2 = -self.data.risk_free_rate * self.data.strike_price * \
                np.exp(-self.data.risk_free_rate * self.data.time_to_expiry) * \
                norm.cdf(d2)
        
        term3 = self.data.dividend_yield * self.data.underlying_price * \
                np.exp(-self.data.dividend_yield * self.data.time_to_expiry) * \
                norm.cdf(d1)
                
        return term1 + term2 + term3
    
    def calculate_put_theta(self) -> float:
        """Calculate Theta for a put option"""
        d1 = self._calculate_d1()
        d2 = self._calculate_d2()
        
        term1 = -(self.data.underlying_price * self.data.volatility * 
                 np.exp(-self.data.dividend_yield * self.data.time_to_expiry) * 
                 norm.pdf(d1)) / (2 * np.sqrt(self.data.time_to_expiry))
        
        term2 = self.data.risk_free_rate * self.data.strike_price * \
                np.exp(-self.data.risk_free_rate * self.data.time_to_expiry) * \
                norm.cdf(-d2)
        
        term3 = -self.data.dividend_yield * self.data.underlying_price * \
                np.exp(-self.data.dividend_yield * self.data.time_to_expiry) * \
                norm.cdf(-d1)
                
        return term1 + term2 + term3
    
    def calculate(self, option_type: str) -> float:
        """
        Calculate Theta for either call or put option
        
        Args:
            option_type: str, either 'call' or 'put'
            
        Returns:
            float: The calculated Theta value (annualized)
        """
        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise ValueError("Option type must be either 'call' or 'put'")
        
        # Calculate annualized theta
        theta = self.calculate_call_theta() if option_type == 'call' else self.calculate_put_theta()
        
        # Convert to daily theta (standard market convention)
        return theta / 365.0 