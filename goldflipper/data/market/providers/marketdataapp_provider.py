import requests
from datetime import datetime
from typing import Optional, Dict, Any
import pandas as pd
from .base import MarketDataProvider
import logging
import yaml

class MarketDataAppProvider(MarketDataProvider):
    """MarketDataApp implementation of market data provider"""

    def __init__(self, config_path: str):
        # Load the configuration file
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Extract the API key from the configuration
        self.api_key = config['market_data_providers']['providers']['marketdataapp']['api_key']
        self.base_url = "https://api.marketdata.app/v1"
        self.headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

    def get_stock_price(self, symbol: str) -> float:
        """Get current stock price"""
        url = f"{self.base_url}/stocks/quotes/{symbol}/"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            return data['price']  # Adjust based on actual response structure
        else:
            logging.error(f"Failed to get stock price for {symbol}: {response.status_code}")
            raise ValueError(f"Error fetching stock price for {symbol}")

    def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1m"
    ) -> pd.DataFrame:
        """Get historical price data"""
        url = f"{self.base_url}/stocks/historical/{symbol}/"
        params = {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d'),
            'interval': interval
        }
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            return pd.DataFrame(data)  # Adjust based on actual response structure
        else:
            logging.error(f"Failed to get historical data for {symbol}: {response.status_code}")
            raise ValueError(f"Error fetching historical data for {symbol}")

    def get_option_chain(
        self,
        symbol: str,
        expiration_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Get option chain data"""
        url = f"{self.base_url}/options/chain/{symbol}/"
        params = {'expiration': expiration_date} if expiration_date else {}
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            calls = pd.DataFrame(data['calls'])  # Adjust based on actual response structure
            puts = pd.DataFrame(data['puts'])    # Adjust based on actual response structure
            return {
                'calls': self.standardize_columns(calls),
                'puts': self.standardize_columns(puts)
            }
        else:
            logging.error(f"Failed to get option chain for {symbol}: {response.status_code}")
            raise ValueError(f"Error fetching option chain for {symbol}")

    def get_option_greeks(self, option_symbol: str) -> Dict[str, float]:
        """Get option Greeks"""
        url = f"{self.base_url}/options/quotes/{option_symbol}/"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'delta': data.get('delta', 0.0),
                'gamma': data.get('gamma', 0.0),
                'theta': data.get('theta', 0.0),
                'vega': data.get('vega', 0.0),
                'rho': data.get('rho', 0.0)
            }
        else:
            logging.error(f"Failed to get option Greeks for {option_symbol}: {response.status_code}")
            raise ValueError(f"Error fetching option Greeks for {option_symbol}")
