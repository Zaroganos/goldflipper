import logging
from datetime import datetime
from time import sleep
from typing import Any

import pandas as pd
import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import MarketDataProvider


class MarketDataAppProvider(MarketDataProvider):
    """MarketDataApp implementation of market data provider"""

    COLUMN_MAPPING = {
        "optionSymbol": "symbol",
        "strike": "strike",
        "expiration": "expiration",
        "bid": "bid",
        "ask": "ask",
        "last": "last",
        "volume": "volume",
        "openInterest": "open_interest",
        "iv": "implied_volatility",
        "inTheMoney": "in_the_money",
        "delta": "delta",
        "gamma": "gamma",
        "theta": "theta",
        "vega": "vega",
        "rho": "rho",
    }

    def __init__(self, config_path: str):
        # Load the configuration file
        with open(config_path) as file:
            config = yaml.safe_load(file)

        # Extract the API key from the configuration
        self.api_key = config["market_data_providers"]["providers"]["marketdataapp"]["api_key"]
        self.base_url = "https://api.marketdata.app/v1"
        self.headers = {"Accept": "application/json", "Authorization": f"Bearer {self.api_key}"}

        # Setup session with retry strategy
        self.session = requests.Session()
        retries = Retry(
            total=3,  # number of retries
            backoff_factor=0.5,  # wait 0.5, 1, 2 seconds between retries
            status_forcelist=[500, 502, 503, 504],  # retry only on these status codes
            allowed_methods=["GET"],  # only retry GET requests
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

        # Initialize rate limiting
        self.rate_limit = {
            "max_requests": 45,  # Keep below 50 for safety margin
            "window": 60,  # seconds
            "requests": 0,
            "window_start": datetime.now(),
        }

    def _check_rate_limit(self):
        """Check and enforce rate limits"""
        now = datetime.now()
        window_elapsed = (now - self.rate_limit["window_start"]).seconds

        # Reset counter if window has elapsed
        if window_elapsed > self.rate_limit["window"]:
            self.rate_limit["requests"] = 0
            self.rate_limit["window_start"] = now
            return

        # If we're approaching the limit, sleep until the window resets
        if self.rate_limit["requests"] >= self.rate_limit["max_requests"]:
            sleep_time = self.rate_limit["window"] - window_elapsed
            if sleep_time > 0:
                logging.warning(f"Rate limit approaching, sleeping for {sleep_time} seconds")
                sleep(sleep_time)
            self.rate_limit["requests"] = 0
            self.rate_limit["window_start"] = datetime.now()

        self.rate_limit["requests"] += 1

    def _make_request(self, url: str, params: dict[str, Any] | None = None) -> requests.Response:
        """Make a request with rate limiting and retries"""
        self._check_rate_limit()
        return self.session.get(url, headers=self.headers, params=params)

    def get_stock_price(self, symbol: str) -> float:
        """Get current stock price"""
        url = f"{self.base_url}/stocks/quotes/{symbol}/"
        response = self._make_request(url)

        if response.status_code in (200, 203):
            data = response.json()
            if data.get("s") == "ok":
                # The API returns arrays, so we take the first element
                if "last" in data and data["last"]:
                    return float(data["last"][0])
                else:
                    logging.error(f"No last price available for {symbol}")
                    raise ValueError(f"No last price available for {symbol}")
            else:
                logging.error(f"API returned error status for {symbol}: {data.get('errmsg', 'Unknown error')}")
                raise ValueError(f"Error fetching stock price for {symbol}")
        elif response.status_code == 204:
            logging.warning(f"No cached data available for {symbol}, retry with live data")
            raise ValueError(f"No cached data available for {symbol}")
        elif response.status_code == 429:
            if "Concurrent request limit reached" in response.text:
                logging.error("Concurrent request limit (50) reached")
                raise ValueError("Too many concurrent requests")
            else:
                logging.error("Daily request limit exceeded")
                raise ValueError("Daily request limit exceeded")
        elif response.status_code == 402:
            logging.error("Plan limit reached or feature not available in current plan")
            raise ValueError("Plan limit reached or feature not available")
        else:
            logging.error(f"Failed to get stock price for {symbol}: {response.status_code}")
            raise ValueError(f"Error fetching stock price for {symbol}")

    def get_next_earnings_date(self, symbol: str):
        """Get the next upcoming earnings report date for a symbol, if available.

        Returns a datetime.date instance for the earliest future earnings report
        on or after today, or None if no such report is available.
        """
        url = f"{self.base_url}/stocks/earnings/{symbol}/"

        # Limit to future calendar by using today's date as the lower bound
        params = {
            "from": datetime.utcnow().strftime("%Y-%m-%d"),
        }

        response = self._make_request(url, params=params)

        if response.status_code in (200, 203):
            data = response.json()
            status = data.get("s")
            if status == "ok":
                report_dates = data.get("reportDate") or []
                if not report_dates:
                    return None

                today = datetime.utcnow().date()
                next_date = None

                for ts in report_dates:
                    try:
                        er_date = datetime.utcfromtimestamp(ts).date()
                    except Exception:
                        continue

                    if er_date < today:
                        continue

                    if next_date is None or er_date < next_date:
                        next_date = er_date

                return next_date

            if status == "no_data":
                return None

            logging.error(f"API returned error status for earnings {symbol}: {data.get('errmsg', 'Unknown error')}")
            return None

        if response.status_code == 204:
            logging.warning(f"No cached earnings data available for {symbol}")
            return None
        if response.status_code == 429:
            if "Concurrent request limit reached" in response.text:
                logging.error("Concurrent request limit (50) reached while fetching earnings")
            else:
                logging.error("Daily request limit exceeded while fetching earnings")
            return None
        if response.status_code == 402:
            logging.error("Plan limit reached or feature not available while fetching earnings")
            return None

        logging.error(f"Failed to get earnings data for {symbol}: {response.status_code}")
        return None

    def get_historical_data(self, symbol: str, start_date: datetime, end_date: datetime, interval: str = "1m") -> pd.DataFrame:
        """Get historical price data"""
        url = f"{self.base_url}/stocks/candles/{interval}/{symbol}/"
        params = {"from": start_date.strftime("%Y-%m-%d"), "to": end_date.strftime("%Y-%m-%d")}

        response = self._make_request(url, params)

        # Updated status code handling to include 203
        if response.status_code in (200, 203):
            data = response.json()
            if data.get("s") == "ok":
                # Create DataFrame from the candle data
                df = pd.DataFrame(
                    {
                        "timestamp": pd.to_datetime(data["t"], unit="s"),
                        "open": data["o"],
                        "high": data["h"],
                        "low": data["l"],
                        "close": data["c"],
                        "volume": data["v"],
                    }
                )
                return df
            else:
                logging.error(f"API returned error status for {symbol}: {data.get('errmsg', 'Unknown error')}")
                raise ValueError(f"Error fetching historical data for {symbol}")
        elif response.status_code == 204:
            logging.warning(f"No cached data available for {symbol}, retry with live data")
            raise ValueError(f"No cached data available for {symbol}")
        elif response.status_code == 429:
            if "Concurrent request limit reached" in response.text:
                logging.error("Concurrent request limit (50) reached")
                raise ValueError("Too many concurrent requests")
            else:
                logging.error("Daily request limit exceeded")
                raise ValueError("Daily request limit exceeded")
        elif response.status_code == 402:
            logging.error("Plan limit reached or feature not available in current plan")
            raise ValueError("Plan limit reached or feature not available")
        else:
            logging.error(f"Failed to get historical data for {symbol}: {response.status_code}")
            raise ValueError(f"Error fetching historical data for {symbol}")

    def get_option_chain(self, symbol: str, expiration_date: str | None = None) -> dict[str, pd.DataFrame]:
        """Get option chain data"""
        logging.info(f"MarketDataApp: Fetching option chain for {symbol}, expiry {expiration_date}")

        url = f"{self.base_url}/options/chain/{symbol}/"
        if expiration_date:
            url += f"?expiration={expiration_date}"

        response = self._make_request(url)
        logging.info(f"MarketDataApp: Got response status {response.status_code}")

        if response.status_code in (200, 203):
            data = response.json()
            logging.info(f"MarketDataApp: Response data keys: {data.keys()}")
            if data.get("s") == "ok":
                logging.info(f"MarketDataApp: Found {len(data.get('optionSymbol', []))} options")

                # Create DataFrame with all fields
                df_data = {
                    "optionSymbol": data["optionSymbol"],
                    "strike": data["strike"],  # Make sure we include strike
                    "bid": data["bid"],
                    "ask": data["ask"],
                    "last": data["last"],
                    "volume": data["volume"],
                    "openInterest": data["openInterest"],
                    "iv": data["iv"],  # Changed from impliedVolatility to iv
                    "inTheMoney": data["inTheMoney"],
                    "delta": data.get("delta", [0] * len(data["optionSymbol"])),
                    "gamma": data.get("gamma", [0] * len(data["optionSymbol"])),
                    "theta": data.get("theta", [0] * len(data["optionSymbol"])),
                    "vega": data.get("vega", [0] * len(data["optionSymbol"])),
                    "rho": data.get("rho", [0] * len(data["optionSymbol"])),
                }

                df = pd.DataFrame(df_data)

                # Split into calls and puts based on option symbol
                calls_df = df[df["optionSymbol"].str.contains("C")]
                puts_df = df[df["optionSymbol"].str.contains("P")]

                # Standardize column names
                calls_df = self.standardize_columns(calls_df)
                puts_df = self.standardize_columns(puts_df)

                return {"calls": calls_df, "puts": puts_df}
            else:
                logging.error(f"API returned error status for {symbol}: {data.get('errmsg', 'Unknown error')}")
                raise ValueError(f"Error fetching option chain for {symbol}")
        elif response.status_code == 204:
            logging.warning(f"No cached data available for {symbol}, retry with live data")
            raise ValueError(f"No cached data available for {symbol}")
        elif response.status_code == 429:
            if "Concurrent request limit reached" in response.text:
                logging.error("Concurrent request limit (50) reached")
                raise ValueError("Too many concurrent requests")
            else:
                logging.error("Daily request limit exceeded")
                raise ValueError("Daily request limit exceeded")
        else:
            logging.error(f"Failed to get option chain for {symbol}: {response.status_code}")
            raise ValueError(f"Error fetching option chain for {symbol}")

    def get_option_expirations(self, symbol: str) -> list:
        """Get available option expiration dates using MarketDataApp expirations endpoint."""
        try:
            url = f"{self.base_url}/options/expirations/{symbol}/"
            response = self._make_request(url)
            if response.status_code in (200, 203):
                data = response.json()
                if data.get("s") == "ok":
                    return data.get("expirations", [])
                if data.get("s") == "no_data":
                    return []
                logging.error(f"MarketDataApp: Error status for expirations {symbol}: {data.get('errmsg', 'Unknown error')}")
                return []
            elif response.status_code == 204:
                logging.warning(f"MarketDataApp: No cached expirations for {symbol}")
                return []
            else:
                logging.error(f"MarketDataApp: Failed to get expirations for {symbol}: {response.status_code}")
                return []
        except Exception as e:
            logging.error(f"Error getting expirations for {symbol}: {str(e)}")
            return []

    def get_option_greeks(self, option_symbol: str) -> dict[str, float]:
        """Get option Greeks"""
        url = f"{self.base_url}/options/quotes/{option_symbol}/"
        response = self._make_request(url)

        if response.status_code in (200, 203):
            data = response.json()
            if data.get("s") == "ok":
                # The API returns arrays, so we take the first element
                return {
                    "delta": data["delta"][0],
                    "gamma": data["gamma"][0],
                    "theta": data["theta"][0],
                    "vega": data["vega"][0],
                    "rho": data["rho"][0],
                }
            else:
                logging.error(f"API returned error status for {option_symbol}: {data.get('errmsg', 'Unknown error')}")
                raise ValueError(f"Error fetching option greeks for {option_symbol}")
        elif response.status_code == 204:
            logging.warning(f"No cached data available for {option_symbol}")
            raise ValueError(f"No cached data available for {option_symbol}")
        elif response.status_code == 429:
            if "Concurrent request limit reached" in response.text:
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
            "symbol": "",
            "strike": 0.0,
            "type": "",
            "expiration": "",
            "bid": 0.0,
            "ask": 0.0,
            "last": 0.0,
            "volume": 0.0,
            "open_interest": 0.0,
            "implied_volatility": 0.0,
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "rho": 0.0,
        }

        for col, default_value in standard_columns.items():
            if col not in df.columns:
                df[col] = default_value

        # Ensure numeric columns are float
        numeric_cols = ["strike", "bid", "ask", "last", "volume", "open_interest", "implied_volatility", "delta", "gamma", "theta", "vega", "rho"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        return df

    def get_option_quote(self, contract_symbol: str) -> pd.DataFrame:
        """Get quote for a specific option contract"""
        url = f"{self.base_url}/options/quotes/{contract_symbol}/"
        response = self._make_request(url)

        if response.status_code in (200, 203):
            data = response.json()
            if data.get("s") == "ok":
                # Create DataFrame with single row
                df_data = {
                    "optionSymbol": [data["optionSymbol"][0]],
                    "strike": [data["strike"][0]],
                    "bid": [data["bid"][0]],
                    "ask": [data["ask"][0]],
                    "last": [data["last"][0]],
                    "volume": [data["volume"][0]],
                    "openInterest": [data["openInterest"][0]],
                    "iv": [data["iv"][0]],
                    "inTheMoney": [data["inTheMoney"][0]],
                    "delta": [data.get("delta", [0])[0]],
                    "gamma": [data.get("gamma", [0])[0]],
                    "theta": [data.get("theta", [0])[0]],
                    "vega": [data.get("vega", [0])[0]],
                    "rho": [data.get("rho", [0])[0]],
                }

                df = pd.DataFrame(df_data)
                return self.standardize_columns(df)
            else:
                logging.error(f"API returned error status for {contract_symbol}: {data.get('errmsg', 'Unknown error')}")
                raise ValueError(f"Error fetching option quote for {contract_symbol}")
        elif response.status_code == 204:
            logging.warning(f"No cached data available for {contract_symbol}")
            raise ValueError(f"No cached data available for {contract_symbol}")
        elif response.status_code == 429:
            if "Concurrent request limit reached" in response.text:
                logging.error("Concurrent request limit (50) reached")
                raise ValueError("Too many concurrent requests")
            else:
                logging.error("Daily request limit exceeded")
                raise ValueError("Daily request limit exceeded")
        else:
            logging.error(f"Failed to get option quote for {contract_symbol}: {response.status_code}")
            raise ValueError(f"Error fetching option quote for {contract_symbol}")
