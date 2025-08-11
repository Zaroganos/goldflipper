import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timedelta
from time import sleep
import logging
import yaml
from typing import Optional, Dict, Any
import pandas as pd
from .base import MarketDataProvider

class MarketDataAppProvider(MarketDataProvider):
    """MarketDataApp implementation of market data provider"""
    
    COLUMN_MAPPING = {
        'optionSymbol': 'symbol',
        'strike': 'strike',
        'expiration': 'expiration',
        'bid': 'bid',
        'ask': 'ask',
        'last': 'last',
        'volume': 'volume',
        'openInterest': 'open_interest',
        'iv': 'implied_volatility',
        'inTheMoney': 'in_the_money',
        'delta': 'delta',
        'gamma': 'gamma',
        'theta': 'theta',
        'vega': 'vega',
        'rho': 'rho'
    }

    def __init__(self, provider_settings: Dict[str, Any]):
        """Initialize provider using settings from DuckDB (no YAML).

        Args:
            provider_settings: Dict containing provider configuration, e.g.,
                {'enabled': True, 'api_key': '...'}
        """
        self.api_key = provider_settings.get('api_key')
        if not self.api_key:
            raise ValueError("MarketDataAppProvider requires an API key from DB settings (market_data_providers.providers.marketdataapp.api_key)")
        self.base_url = "https://api.marketdata.app/v1"
        self.headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

        # Setup session with retry strategy
        self.session = requests.Session()
        retries = Retry(
            total=3,  # number of retries
            backoff_factor=0.5,  # wait 0.5, 1, 2 seconds between retries
            status_forcelist=[500, 502, 503, 504],  # retry only on these status codes
            allowed_methods=["GET"]  # only retry GET requests
        )
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        
        # Initialize rate limiting
        self.rate_limit = {
            'max_requests': 45,  # Keep below 50 for safety margin
            'window': 60,  # seconds
            'requests': 0,
            'window_start': datetime.now()
        }

    def _check_rate_limit(self):
        """Check and enforce rate limits"""
        now = datetime.now()
        window_elapsed = (now - self.rate_limit['window_start']).seconds
        
        # Reset counter if window has elapsed
        if window_elapsed > self.rate_limit['window']:
            self.rate_limit['requests'] = 0
            self.rate_limit['window_start'] = now
            return
        
        # If we're approaching the limit, sleep until the window resets
        if self.rate_limit['requests'] >= self.rate_limit['max_requests']:
            sleep_time = self.rate_limit['window'] - window_elapsed
            if sleep_time > 0:
                logging.warning(f"Rate limit approaching, sleeping for {sleep_time} seconds")
                sleep(sleep_time)
            self.rate_limit['requests'] = 0
            self.rate_limit['window_start'] = datetime.now()
        
        self.rate_limit['requests'] += 1

    def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Make a request with rate limiting and retries"""
        self._check_rate_limit()
        return self.session.get(url, headers=self.headers, params=params)

    def get_stock_price(self, symbol: str, regular_hours_only: bool = False) -> float:
        """Get current price for stocks or indices."""
        paths = [f"/stocks/quotes/{symbol}/"]
        if symbol.upper() in {"VIX", "SPX", "NDX", "RUT", "DJI"}:
            paths = [
                f"/indices/quotes/{symbol}/",
                f"/index/quotes/{symbol}/",
                f"/stocks/quotes/{symbol}/",
            ]

        params = {}
        if regular_hours_only:
            params['extended'] = 'false'

        last_error = None
        for suffix in paths:
            url = f"{self.base_url}{suffix}"
            resp = self._make_request(url, params)
            try:
                if resp.status_code in (200, 203):
                    data = resp.json()
                    if data.get('s') == 'ok' and 'last' in data and data['last']:
                        return float(data['last'][0])
                    last_error = data.get('errmsg', 'no last in payload')
                    continue
                elif resp.status_code in (204, 404):
                    last_error = f"status {resp.status_code}"
                    continue
                elif resp.status_code == 429:
                    if 'Concurrent request limit reached' in resp.text:
                        raise ValueError("Too many concurrent requests")
                    else:
                        raise ValueError("Daily request limit exceeded")
                elif resp.status_code == 402:
                    raise ValueError("Plan limit reached or feature not available")
                else:
                    last_error = f"status {resp.status_code}"
                    continue
            except Exception as e:
                last_error = str(e)
                continue

        logging.error(f"Failed to get price for {symbol}: {last_error}")
        raise ValueError(f"Error fetching price for {symbol}")

    def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1m"
    ) -> pd.DataFrame:
        """Get historical price data for stocks or indices (auto-endpoint selection)."""
        paths = [f"/stocks/candles/{interval}/{symbol}/"]
        # If this looks like an index (e.g., VIX), try indices endpoints as well
        if symbol.upper() in {"VIX", "SPX", "NDX", "RUT", "DJI"}:
            paths = [
                f"/indices/candles/{interval}/{symbol}/",
                f"/index/candles/{interval}/{symbol}/",
                f"/stocks/candles/{interval}/{symbol}/",
            ]

        params = {
            'from': start_date.strftime('%Y-%m-%d'),
            'to': end_date.strftime('%Y-%m-%d')
        }

        last_error = None
        for suffix in paths:
            url = f"{self.base_url}{suffix}"
            response = self._make_request(url, params)
            try:
                if response.status_code in (200, 203):
                    data = response.json()
                    if data.get('s') == 'ok' and all(k in data for k in ('t','o','h','l','c','v')):
                        df = pd.DataFrame({
                            'timestamp': pd.to_datetime(data['t'], unit='s'),
                            'open': data['o'],
                            'high': data['h'],
                            'low': data['l'],
                            'close': data['c'],
                            'volume': data['v']
                        })
                        if not df.empty:
                            return df
                        last_error = "empty dataframe"
                        continue
                    else:
                        last_error = data.get('errmsg', 'non-ok status or missing fields')
                        continue
                elif response.status_code in (204, 404):
                    last_error = f"status {response.status_code}"
                    continue
                elif response.status_code == 429:
                    if 'Concurrent request limit reached' in response.text:
                        raise ValueError("Too many concurrent requests")
                    else:
                        raise ValueError("Daily request limit exceeded")
                elif response.status_code == 402:
                    raise ValueError("Plan limit reached or feature not available")
                else:
                    last_error = f"status {response.status_code}"
                    continue
            except Exception as e:
                last_error = str(e)
                continue

        logging.error(f"Failed to get historical data for {symbol}: {last_error}")
        return pd.DataFrame()

    def get_available_expirations(self, symbol: str, date: Optional[str] = None, strike: Optional[float] = None) -> list[str]:
        """Return available option expiration dates for a symbol using MarketData.app.

        Endpoint: /v1/options/expirations/{underlyingSymbol}/ (GET)
        Optional params: date (ISO/unix), strike (number)
        Docs: `https://www.marketdata.app/docs/api/options/expirations`

        Notes for VIX:
        - VIX expirations are typically on Wednesdays (morning settlement), and
          MarketData.app returns those dates. We simply pass them through.
        """
        try:
            url = f"{self.base_url}/options/expirations/{symbol}/"
            params = {}
            if date:
                params['date'] = date
            if strike is not None:
                params['strike'] = strike
            resp = self._make_request(url, params)
            if resp.status_code not in (200, 203):
                logging.warning(f"expirations endpoint status {resp.status_code} for {symbol}")
                return []
            data = resp.json()
            # Common shapes: {'s':'ok','expirations':['YYYY-MM-DD', ...]}
            if isinstance(data, dict):
                for key in ("expirations", "expiration", "dates"):
                    if key in data and isinstance(data[key], list):
                        return [str(d) for d in data[key]]
                # Some APIs return a list directly at 'data'
                if 'data' in data and isinstance(data['data'], list):
                    return [str(d) for d in data['data']]
            elif isinstance(data, list):
                return [str(d) for d in data]
            logging.warning(f"Unrecognized expirations payload for {symbol}: keys={list(data.keys()) if isinstance(data, dict) else type(data)}")
            return []
        except Exception as e:
            logging.error(f"Error getting expirations for {symbol}: {e}")
            return []

    def get_option_chain(
        self,
        symbol: str,
        expiration_date: Optional[str] = None,
        date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Get option chain data (current) using documented HTTP endpoint.

        Args:
            symbol: Underlying symbol
            expiration_date: Filter by expiration date (YYYY-MM-DD). Required by MarketData.app for precise chains
            date: Ignored for MarketData.app (current only)

        Returns:
            Dictionary with 'calls' and 'puts' DataFrames
        """
        logging.info(f"MarketDataApp: Fetching option chain for {symbol}, expiry {expiration_date}")

        if not expiration_date:
            logging.warning("MarketDataApp chain requires expiration_date; returning empty chain")
            return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}

        # Build HTTP URL exactly as documented
        url_calls = f"{self.base_url}/options/chain/{symbol}/?expiration={expiration_date}&side=call"
        url_puts = f"{self.base_url}/options/chain/{symbol}/?expiration={expiration_date}&side=put"

        def fetch_side(url: str) -> pd.DataFrame:
            resp = self._make_request(url)
            if resp.status_code not in (200, 203):
                logging.warning(f"Chain side request status {resp.status_code} for {url}")
                return pd.DataFrame()
            data = resp.json()
            # Expect arrays per field per MarketData.app
            if not isinstance(data, dict) or not data.get('optionSymbol'):
                logging.warning(f"Unexpected chain payload for {url}: keys={list(data.keys()) if isinstance(data, dict) else type(data)}")
                return pd.DataFrame()
            length = len(data['optionSymbol'])
            def safe_list(k, default=0):
                v = data.get(k)
                if isinstance(v, list) and len(v) == length:
                    return v
                return [default] * length
            df = pd.DataFrame({
                'optionSymbol': data['optionSymbol'],
                'side': safe_list('side', 'call' if 'side=call' in url else 'put'),
                'strike': safe_list('strike', 0.0),
                'bid': safe_list('bid', 0.0),
                'ask': safe_list('ask', 0.0),
                'last': safe_list('last', 0.0),
                'volume': safe_list('volume', 0),
                'openInterest': safe_list('openInterest', 0),
                'iv': safe_list('iv', 0.0),
                'inTheMoney': safe_list('inTheMoney', False),
                'delta': safe_list('delta', 0.0),
                'gamma': safe_list('gamma', 0.0),
                'theta': safe_list('theta', 0.0),
                'vega': safe_list('vega', 0.0),
                'rho': safe_list('rho', 0.0),
            })
            return df

        calls_raw = fetch_side(url_calls)
        puts_raw = fetch_side(url_puts)

        if calls_raw.empty and puts_raw.empty:
            return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}

        # Standardize
        calls_df = self.standardize_columns(calls_raw) if not calls_raw.empty else pd.DataFrame()
        puts_df = self.standardize_columns(puts_raw) if not puts_raw.empty else pd.DataFrame()
        return {'calls': calls_df, 'puts': puts_df}

    def get_option_greeks(
        self,
        option_symbol: str
    ) -> Dict[str, float]:
        """Get option Greeks"""
        url = f"{self.base_url}/options/quotes/{option_symbol}/"
        response = self._make_request(url)
        
        if response.status_code in (200, 203):
            data = response.json()
            if data.get('s') == 'ok':
                # The API returns arrays, so we take the first element
                return {
                    'delta': data['delta'][0],
                    'gamma': data['gamma'][0],
                    'theta': data['theta'][0],
                    'vega': data['vega'][0],
                    'rho': data['rho'][0]
                }
            else:
                logging.error(f"API returned error status for {option_symbol}: {data.get('errmsg', 'Unknown error')}")
                raise ValueError(f"Error fetching option greeks for {option_symbol}")
        elif response.status_code == 204:
            logging.warning(f"No cached data available for {option_symbol}")
            raise ValueError(f"No cached data available for {option_symbol}")
        elif response.status_code == 429:
            if 'Concurrent request limit reached' in response.text:
                logging.error("Concurrent request limit (50) reached")
                raise ValueError("Too many concurrent requests")
            else:
                logging.error("Daily request limit exceeded")
                raise ValueError("Daily request limit exceeded")
        else:
            logging.error(f"Failed to get option greeks for {option_symbol}: {response.status_code}")
            raise ValueError(f"Error fetching option greeks for {option_symbol}")

    def standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names and formats"""
        logging.info(f"MarketDataApp: Pre-standardization columns: {df.columns.tolist()}")
        df = df.copy()
        
        # Rename columns using the class constant
        df = df.rename(columns={old: new for old, new in self.COLUMN_MAPPING.items() if old in df.columns})
        logging.info(f"MarketDataApp: Post-standardization columns: {df.columns.tolist()}")
        
        # Add missing columns with default values
        standard_columns = {
            'symbol': '',
            'strike': 0.0,
            'type': '',
            'expiration': '',
            'bid': 0.0,
            'ask': 0.0,
            'last': 0.0,
            'volume': 0.0,
            'open_interest': 0.0,
            'implied_volatility': 0.0,
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0
        }
        
        for col, default_value in standard_columns.items():
            if col not in df.columns:
                df[col] = default_value
        
        # Ensure numeric columns are float
        numeric_cols = ['strike', 'bid', 'ask', 'last', 'volume', 'open_interest', 
                       'implied_volatility', 'delta', 'gamma', 'theta', 'vega', 'rho']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
                
        return df

    def get_option_quote(self, option_symbol: str) -> pd.DataFrame:
        """Get quote for a specific option contract"""
        url = f"{self.base_url}/options/quotes/{option_symbol}/"
        response = self._make_request(url)
        
        if response.status_code in (200, 203):
            data = response.json()
            if data.get('s') == 'ok':
                # Create DataFrame with single row
                df_data = {
                    'optionSymbol': [data['optionSymbol'][0]],
                    'strike': [data['strike'][0]],
                    'bid': [data['bid'][0]],
                    'ask': [data['ask'][0]],
                    'last': [data['last'][0]],
                    'volume': [data['volume'][0]],
                    'openInterest': [data['openInterest'][0]],
                    'iv': [data['iv'][0]],
                    'inTheMoney': [data['inTheMoney'][0]],
                    'delta': [data.get('delta', [0])[0]],
                    'gamma': [data.get('gamma', [0])[0]],
                    'theta': [data.get('theta', [0])[0]],
                    'vega': [data.get('vega', [0])[0]],
                    'rho': [data.get('rho', [0])[0]]
                }
                
                df = pd.DataFrame(df_data)
                return self.standardize_columns(df)
            else:
                logging.error(f"API returned error status for {option_symbol}: {data.get('errmsg', 'Unknown error')}")
                raise ValueError(f"Error fetching option quote for {option_symbol}")
        elif response.status_code == 204:
            logging.warning(f"No cached data available for {option_symbol}")
            raise ValueError(f"No cached data available for {option_symbol}")
        elif response.status_code == 429:
            if 'Concurrent request limit reached' in response.text:
                logging.error("Concurrent request limit (50) reached")
                raise ValueError("Too many concurrent requests")
            else:
                logging.error("Daily request limit exceeded")
                raise ValueError("Daily request limit exceeded")
        else:
            logging.error(f"Failed to get option quote for {option_symbol}: {response.status_code}")
            raise ValueError(f"Error fetching option quote for {option_symbol}")
