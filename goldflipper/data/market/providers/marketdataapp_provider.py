from market_data_api.MarketDataAPI import MarketDataAPI, Stock, Index
from datetime import datetime
from typing import Optional, Dict, Any
import pandas as pd
from .base import MarketDataProvider
import logging
import yaml
import os

class MarketDataAppProvider(MarketDataProvider):
    """MarketDataApp implementation of market data provider"""

    COLUMN_MAPPING = {
        'symbol': 'symbol',
        'strike': 'strike',
        'expiration': 'expiration',
        'last': 'last',
        'bid': 'bid',
        'ask': 'ask',
        'volume': 'volume',
        'open_interest': 'open_interest',
        'implied_volatility': 'implied_volatility',
        'in_the_money': 'in_the_money'
    }

    def __init__(self):
        # Load settings from YAML
        self.settings = self._load_settings()
        
        # Get API key from settings
        api_key = self.settings['market_data_providers']['providers']['marketdataapp']['api_key']
        
        # Initialize the MarketDataAPI client with the API key
        self.client = MarketDataAPI(api_key=api_key)
        self._cache = {}  # Simple memory cache

    def _load_settings(self) -> dict:
        """Load settings from YAML file"""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        config_path = os.path.join(project_root, 'config', 'settings.yaml')
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    async def get_stock_price(self, symbol: str) -> float:
        """Get current stock price"""
        try:
            # Fetch stock price using MarketDataAPI client
            price = self.client.get_stock_price(symbol)
            logging.info(f"MarketDataApp: Retrieved stock price for {symbol}")
            return price
        except Exception as e:
            logging.error(f"MarketDataApp error getting price for {symbol}: {str(e)}")
            raise

    def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1m"
    ) -> pd.DataFrame:
        """Get historical price data"""
        try:
            # Fetch historical data using MarketDataAPI client
            data = self.client.get_historical_data(symbol, start_date, end_date, interval)
            logging.info(f"MarketDataApp: Retrieved historical data for {symbol}")
            return data
        except Exception as e:
            logging.error(f"MarketDataApp error getting historical data for {symbol}: {str(e)}")
            return pd.DataFrame()

    def get_option_chain(
        self,
        symbol: str,
        expiration_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Get option chain data"""
        try:
            # Fetch option chain using MarketDataAPI client
            chain = self.client.get_option_chain(symbol, expiration_date)
            logging.info(f"MarketDataApp: Retrieved option chain for {symbol}")
            return {
                'calls': self.standardize_columns(chain['calls']),
                'puts': self.standardize_columns(chain['puts'])
            }
        except Exception as e:
            logging.error(f"MarketDataApp error getting option chain for {symbol}: {str(e)}")
            return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}

    def get_option_greeks(self, option_symbol: str) -> Dict[str, float]:
        """Get option Greeks"""
        try:
            # Fetch option Greeks using MarketDataAPI client
            greeks = self.client.get_option_greeks(option_symbol)
            logging.info(f"MarketDataApp: Retrieved option Greeks for {option_symbol}")
            return greeks
        except Exception as e:
            logging.error(f"MarketDataApp error getting Greeks for {option_symbol}: {str(e)}")
            return {
                'delta': 0.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'rho': 0.0
            }
