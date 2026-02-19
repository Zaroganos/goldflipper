import logging
from datetime import datetime

import pandas as pd
import yfinance as yf

from .base import MarketDataProvider


class YFinanceProvider(MarketDataProvider):
    """YFinance implementation of market data provider"""

    COLUMN_MAPPING = {
        "contractSymbol": "symbol",
        "strike": "strike",
        "lastPrice": "last",
        "bid": "bid",
        "ask": "ask",
        "volume": "volume",
        "openInterest": "open_interest",
        "impliedVolatility": "implied_volatility",
        "inTheMoney": "in_the_money",
    }

    def __init__(self, config_path: str | None = None):
        super().__init__(config_path)
        self._cache = {}  # Simple memory cache
        self.config_path = config_path

    def standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names and formats for yfinance data.

        yfinance returns columns like: contractSymbol, lastTradeDate, strike,
        lastPrice, bid, ask, change, percentChange, volume, openInterest,
        impliedVolatility, inTheMoney, contractSize, currency

        We need to map these to our standard columns and add missing ones.
        """
        df = df.copy()

        # Rename columns using the class mapping
        df = df.rename(columns={old: new for old, new in self.COLUMN_MAPPING.items() if old in df.columns})

        # Extract expiration from contractSymbol if available
        # OCC format: SYMBOL + YYMMDD + C/P + 8-digit strike
        if "symbol" in df.columns and "expiration" not in df.columns:

            def extract_expiration(sym):
                try:
                    # Find where the date portion starts (after ticker, before C/P)
                    # Standard OCC: SPY251219C00590000
                    for i, c in enumerate(sym):
                        if c.isdigit():
                            date_str = sym[i : i + 6]
                            if len(date_str) == 6 and date_str.isdigit():
                                return f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"
                    return ""
                except Exception:
                    return ""

            df["expiration"] = df["symbol"].apply(extract_expiration)

        # Determine option type from symbol
        if "symbol" in df.columns and "type" not in df.columns:

            def extract_type(sym):
                try:
                    # OCC format: TICKER + YYMMDD + C/P + 8-digit strike
                    # Find where digits start (after ticker), then skip 6 date digits
                    for i, c in enumerate(sym):
                        if c.isdigit():
                            # i is start of date, type char is at i+6
                            if i + 6 < len(sym):
                                type_char = sym[i + 6]
                                if type_char == "C":
                                    return "call"
                                elif type_char == "P":
                                    return "put"
                            break
                    return ""
                except Exception:
                    return ""

            df["type"] = df["symbol"].apply(extract_type)

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
                df.loc[:, col] = default_value

        # Ensure numeric columns are Python float (not numpy scalar)
        numeric_cols = ["strike", "bid", "ask", "last", "volume", "open_interest", "implied_volatility", "delta", "gamma", "theta", "vega", "rho"]
        for col in numeric_cols:
            if col in df.columns:
                df.loc[:, col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        return df

    def get_stock_price(self, symbol: str) -> float:
        """Get current stock price"""
        try:
            ticker = yf.Ticker(symbol)

            # Try multiple methods in order of reliability
            try:
                # Method 1: Fast info (most current)
                price = ticker.fast_info["lastPrice"]
                logging.info(f"YFinance: Using real-time price from fast_info for {symbol}")
                return float(price)

            except (KeyError, AttributeError):
                try:
                    # Method 2: Regular info
                    price = ticker.info.get("currentPrice") or ticker.info.get("regularMarketPrice")
                    if price:
                        logging.info(f"YFinance: Using currentPrice from stock.info for {symbol}")
                        return float(price)
                    raise KeyError("No price in info")

                except (KeyError, AttributeError) as e:
                    # Method 3: Latest minute data
                    history = ticker.history(period="1d", interval="1m")
                    if not history.empty:
                        price = history["Close"].iloc[-1]
                        logging.info(f"YFinance: Using most recent minute data for {symbol}")
                        return float(price)
                    else:
                        raise ValueError(f"No price data available for {symbol}") from e

        except Exception as e:
            logging.error(f"YFinance error getting price for {symbol}: {str(e)}")
            raise

    def get_historical_data(self, symbol: str, start_date: datetime, end_date: datetime, interval: str = "1m") -> pd.DataFrame:
        # Check cache first
        cache_key = f"{symbol}_{start_date}_{end_date}_{interval}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        data = yf.download(symbol, start=start_date, end=end_date, interval=interval)

        # Cache the result
        self._cache[cache_key] = data
        return data

    def get_option_chain(self, symbol: str, expiration_date: str | None = None) -> dict[str, pd.DataFrame]:
        try:
            ticker = yf.Ticker(symbol)

            if expiration_date:
                chain = ticker.option_chain(expiration_date)
            else:
                # Get the nearest expiration date
                dates = ticker.options
                if not dates:
                    return {"calls": pd.DataFrame(), "puts": pd.DataFrame()}
                chain = ticker.option_chain(dates[0])

            # Log the raw columns we get from YFinance
            logging.info(f"Raw columns from YFinance: {chain.calls.columns.tolist()}")

            # Standardize columns before returning
            calls = self.standardize_columns(chain.calls)
            puts = self.standardize_columns(chain.puts)

            # Log the standardized columns
            logging.info(f"Standardized columns: {calls.columns.tolist()}")

            return {
                "calls": calls.copy(),  # Use copy() to avoid SettingWithCopyWarning
                "puts": puts.copy(),
            }
        except Exception as e:
            logging.error(f"Error getting option chain for {symbol}: {str(e)}")
            return {"calls": pd.DataFrame(), "puts": pd.DataFrame()}

    def get_option_quote(self, contract_symbol: str, strike_price: float | None = None) -> pd.DataFrame:
        """Get option quote for a specific contract.

        Supports both OCC format (SPY251211C00590000) and underscore format (SPY_251211C00590000).
        """
        try:
            # Normalize: remove underscores if present
            normalized = contract_symbol.replace("_", "")

            # Parse OCC format: SYMBOL + YYMMDD + C/P + 8-digit strike
            # Find where date starts (first digit after ticker)
            ticker_end = 0
            for i, c in enumerate(normalized):
                if c.isdigit():
                    ticker_end = i
                    break

            if ticker_end == 0:
                logging.error(f"Could not parse contract symbol: {contract_symbol}")
                return pd.DataFrame()

            symbol = normalized[:ticker_end]
            date_str = normalized[ticker_end : ticker_end + 6]

            if len(date_str) != 6 or not date_str.isdigit():
                logging.error(f"Invalid date in contract symbol: {contract_symbol}")
                return pd.DataFrame()

            # Determine call/put from position after date
            type_char_pos = ticker_end + 6
            if type_char_pos >= len(normalized):
                logging.error(f"Contract symbol too short: {contract_symbol}")
                return pd.DataFrame()

            type_char = normalized[type_char_pos]
            is_call = type_char == "C"

            # Extract strike from 8-digit portion (in tenths of cents)
            strike_str = normalized[type_char_pos + 1 :]
            if len(strike_str) >= 8:
                extracted_strike = float(strike_str[:8]) / 1000
            else:
                extracted_strike = None

            # Convert date to yfinance format: YYYY-MM-DD
            exp_date = f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"

            logging.debug(f"Parsed contract: symbol={symbol}, exp={exp_date}, call={is_call}, strike={extracted_strike}")

            # Get option chain for that expiration
            chain = self.get_option_chain(symbol, exp_date)
            options_data = chain["calls"] if is_call else chain["puts"]

            if options_data.empty:
                logging.warning(f"No options data for {symbol} exp {exp_date}")
                return pd.DataFrame()

            # Filter by strike price
            use_strike = strike_price if strike_price is not None else extracted_strike
            if use_strike is not None:
                filtered_data = options_data[options_data["strike"] == use_strike]
            else:
                filtered_data = options_data

            if filtered_data.empty:
                logging.warning(f"No matching options found for {contract_symbol} (strike={use_strike})")
                return pd.DataFrame()

            return filtered_data.copy()

        except Exception as e:
            logging.error(f"Error getting option quote for {contract_symbol}: {str(e)}")
            return pd.DataFrame()

    def get_option_greeks(self, option_symbol: str) -> dict[str, float]:
        """Get option Greeks from yfinance"""
        # YFinance doesn't provide Greeks directly
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}

    def get_option_expirations(self, symbol: str) -> list:
        """Return available option expirations from yfinance."""
        try:
            ticker = yf.Ticker(symbol)
            dates = ticker.options or []
            return list(dates)
        except Exception as e:
            logging.error(f"YFinance: error getting expirations for {symbol}: {str(e)}")
            return []
