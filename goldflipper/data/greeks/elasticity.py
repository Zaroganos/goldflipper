from .base import GreeksCalculator
import numpy as np

class ElasticityCalculator(GreeksCalculator):
    """Calculator for option Elasticity (Lambda)"""
    
    def calculate(self, option_type: str) -> float:
        """
        Calculate Elasticity (Lambda) for either call or put option
        
        Lambda = (dV/V)/(dS/S) = (Delta * S)/(V)
        where:
        - V is option price (using last price as approximation)
        - S is underlying price
        - Delta is the option's delta
        
        Args:
            option_type: str, either 'call' or 'put'
            
        Returns:
            float: The calculated Elasticity value
        """
        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise ValueError("Option type must be either 'call' or 'put'")
        
        # Calculate delta first
        from .delta import DeltaCalculator
        delta_calc = DeltaCalculator(self.data)
        delta = delta_calc.calculate(option_type)
        
        # Calculate elasticity using the formula: (Delta * S)/V
        # where S is underlying price and V is option price
        elasticity = (delta * self.data.underlying_price) / self.data.option_price
        
        return elasticity 