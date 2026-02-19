"""
Market Data App SDK Test Script

Tests the new official marketdata-sdk-py package for fetching:
- Call and Put volume on Mag 7 stocks
- Underlying stock prices with 2-week historical lookback

For Momentum Strategy research - data stored in memory for now.

Environment Setup:
    pip install "marketdata-sdk-py[pandas]"

    API Token is read from settings.yaml (market_data_providers.providers.marketdataapp.api_key)
    Or set MARKETDATA_TOKEN environment variable as override.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import yaml

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Mag 7 stocks
MAG7_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]

# Data refresh interval recommendations for momentum strategy
# Based on options market dynamics and typical volume patterns
REFRESH_INTERVALS = {
    "intraday_active": 5,  # minutes - during high activity periods
    "intraday_normal": 15,  # minutes - standard trading hours
    "daily_summary": 1440,  # minutes (24h) - end of day consolidation
    "historical": 10080,  # minutes (1 week) - for trend analysis
}


@dataclass
class OptionsVolumeData:
    """Container for options volume data per symbol"""

    symbol: str
    timestamp: datetime
    call_volume: int = 0
    put_volume: int = 0
    call_open_interest: int = 0
    put_open_interest: int = 0
    put_call_ratio: float = 0.0
    underlying_price: float = 0.0

    def __post_init__(self):
        if self.call_volume > 0:
            self.put_call_ratio = self.put_volume / self.call_volume


@dataclass
class HistoricalStockData:
    """Container for historical stock candle data"""

    symbol: str
    candles: list = field(default_factory=list)  # List of OHLCV dicts
    start_date: datetime | None = None
    end_date: datetime | None = None


@dataclass
class MomentumDataStore:
    """In-memory data store for momentum strategy research"""

    options_volume: dict = field(default_factory=dict)  # symbol -> OptionsVolumeData
    historical_prices: dict = field(default_factory=dict)  # symbol -> HistoricalStockData
    last_refresh: datetime | None = None

    def add_options_volume(self, data: OptionsVolumeData):
        self.options_volume[data.symbol] = data

    def add_historical_prices(self, data: HistoricalStockData):
        self.historical_prices[data.symbol] = data

    def get_summary(self) -> dict:
        """Get summary of stored data"""
        return {
            "symbols_with_options": list(self.options_volume.keys()),
            "symbols_with_history": list(self.historical_prices.keys()),
            "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
            "total_call_volume": sum(d.call_volume for d in self.options_volume.values()),
            "total_put_volume": sum(d.put_volume for d in self.options_volume.values()),
        }


def get_api_token_from_settings() -> str | None:
    """Read API token from settings.yaml"""
    try:
        # Try to find settings.yaml - check multiple locations
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "..", "config", "settings.yaml"),
            os.path.join(os.path.dirname(__file__), "..", "..", "settings.yaml"),
            "settings.yaml",
        ]

        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                with open(abs_path) as f:
                    config = yaml.safe_load(f)
                token = config.get("market_data_providers", {}).get("providers", {}).get("marketdataapp", {}).get("api_key")
                if token and not token.startswith("YOUR_"):
                    logger.info(f"Found API token in {abs_path}")
                    return token

        return None
    except Exception as e:
        logger.warning(f"Could not read settings.yaml: {e}")
        return None


def test_sdk_connection():
    """Test basic SDK connection and authentication"""
    try:
        # Try to get token from settings.yaml if env var not set
        # Must be done BEFORE importing MarketDataClient
        if not os.environ.get("MARKETDATA_TOKEN"):
            token = get_api_token_from_settings()
            if token:
                os.environ["MARKETDATA_TOKEN"] = token
                logger.info("Set MARKETDATA_TOKEN from settings.yaml")

        from marketdata.client import MarketDataClient

        logger.info("Initializing MarketDataClient...")
        client = MarketDataClient()

        # Test with SPY (not AAPL - AAPL is free and doesn't verify auth)
        logger.info("Testing authentication with SPY quote...")
        quote = client.stocks.quotes("SPY")

        # Check if result is an error type
        if hasattr(quote, "error"):
            logger.error(f"Authentication failed: {quote.error}")
            return None

        logger.info("✓ SDK connected successfully! SPY quote received.")
        if hasattr(quote, "shape"):
            logger.info(f"  DataFrame shape: {quote.shape}")
        return client

    except ImportError as e:
        logger.error(f"marketdata-sdk-py import error: {e}")
        logger.error("Install with: pip install 'marketdata-sdk-py[pandas]'")
        return None
    except Exception as e:
        logger.error(f"Connection error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return None


def fetch_options_volume(client, symbol: str) -> OptionsVolumeData | None:
    """Fetch current options volume data for a symbol"""
    try:
        logger.info(f"Fetching options chain for {symbol}...")

        # Get all expirations, aggregate volume
        chain = client.options.chain(
            symbol,
            expiration="all",
        )

        # Check if result has error attribute (SDK error response)
        if hasattr(chain, "error"):
            logger.warning(f"  Error fetching {symbol} options: {chain.error}")
            return None

        if chain is None or (hasattr(chain, "empty") and chain.empty):
            logger.warning(f"  No options data for {symbol}")
            return None

        # Aggregate call and put volumes
        calls = chain[chain["side"] == "call"] if "side" in chain.columns else chain[chain.index.str.contains("C")]
        puts = chain[chain["side"] == "put"] if "side" in chain.columns else chain[chain.index.str.contains("P")]

        call_volume = int(calls["volume"].sum()) if "volume" in calls.columns else 0
        put_volume = int(puts["volume"].sum()) if "volume" in puts.columns else 0
        call_oi = int(calls["openInterest"].sum()) if "openInterest" in calls.columns else 0
        put_oi = int(puts["openInterest"].sum()) if "openInterest" in puts.columns else 0

        # Get underlying price
        underlying_price = float(chain["underlyingPrice"].iloc[0]) if "underlyingPrice" in chain.columns else 0.0

        data = OptionsVolumeData(
            symbol=symbol,
            timestamp=datetime.now(),
            call_volume=call_volume,
            put_volume=put_volume,
            call_open_interest=call_oi,
            put_open_interest=put_oi,
            underlying_price=underlying_price,
        )

        logger.info(f"  ✓ {symbol}: Calls={call_volume:,} Puts={put_volume:,} P/C={data.put_call_ratio:.2f}")
        return data

    except Exception as e:
        logger.error(f"  Error fetching {symbol}: {e}")
        return None


def fetch_historical_candles(client, symbol: str, lookback_days: int = 14) -> HistoricalStockData | None:
    """Fetch historical daily candles with lookback period"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)

        logger.info(f"Fetching {lookback_days}-day history for {symbol}...")

        candles = client.stocks.candles(
            symbol,
            resolution="D",  # Daily
            from_date=start_date.strftime("%Y-%m-%d"),
            to_date=end_date.strftime("%Y-%m-%d"),
        )

        # Check if result has error attribute (SDK error response)
        if hasattr(candles, "error"):
            logger.warning(f"  Error fetching {symbol} history: {candles.error}")
            return None

        if candles is None or (hasattr(candles, "empty") and candles.empty):
            logger.warning(f"  No historical data for {symbol}")
            return None

        # Convert to list of dicts for storage
        candle_list = candles.reset_index().to_dict("records")

        data = HistoricalStockData(symbol=symbol, candles=candle_list, start_date=start_date, end_date=end_date)

        logger.info(f"  ✓ {symbol}: {len(candle_list)} candles fetched")
        return data

    except Exception as e:
        logger.error(f"  Error fetching {symbol} history: {e}")
        return None


def run_momentum_data_fetch(symbols: list | None = None, lookback_days: int = 14) -> MomentumDataStore:
    """
    Main function to fetch all momentum-relevant data for given symbols.

    Args:
        symbols: List of stock symbols (defaults to MAG7)
        lookback_days: Historical lookback period (default 14 days = 2 weeks)

    Returns:
        MomentumDataStore with all fetched data
    """
    if symbols is None:
        symbols = MAG7_SYMBOLS

    logger.info("=" * 60)
    logger.info("MOMENTUM STRATEGY DATA FETCH")
    logger.info(f"Symbols: {', '.join(symbols)}")
    logger.info(f"Lookback: {lookback_days} days")
    logger.info("=" * 60)

    # Initialize data store
    store = MomentumDataStore()

    # Connect to SDK
    client = test_sdk_connection()
    if client is None:
        logger.error("Failed to connect to Market Data App SDK")
        return store

    logger.info("")
    logger.info("-" * 40)
    logger.info("FETCHING OPTIONS VOLUME DATA")
    logger.info("-" * 40)

    # Fetch options volume for each symbol
    for symbol in symbols:
        data = fetch_options_volume(client, symbol)
        if data:
            store.add_options_volume(data)

    logger.info("")
    logger.info("-" * 40)
    logger.info("FETCHING HISTORICAL PRICE DATA")
    logger.info("-" * 40)

    # Fetch historical candles for each symbol
    for symbol in symbols:
        data = fetch_historical_candles(client, symbol, lookback_days)
        if data:
            store.add_historical_prices(data)

    store.last_refresh = datetime.now()

    # Print summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("FETCH COMPLETE - SUMMARY")
    logger.info("=" * 60)

    summary = store.get_summary()
    logger.info(f"Options data for: {', '.join(summary['symbols_with_options'])}")
    logger.info(f"Historical data for: {', '.join(summary['symbols_with_history'])}")
    logger.info(f"Total Call Volume: {summary['total_call_volume']:,}")
    logger.info(f"Total Put Volume: {summary['total_put_volume']:,}")

    # Detailed volume breakdown
    if store.options_volume:
        logger.info("")
        logger.info("DETAILED OPTIONS VOLUME:")
        logger.info(f"{'Symbol':<8} {'Call Vol':>12} {'Put Vol':>12} {'Call OI':>12} {'Put OI':>12} {'P/C Ratio':>10} {'Price':>10}")
        logger.info("-" * 78)
        for _symbol, data in store.options_volume.items():
            logger.info(
                f"{data.symbol:<8} {data.call_volume:>12,} {data.put_volume:>12,} "
                f"{data.call_open_interest:>12,} {data.put_open_interest:>12,} "
                f"{data.put_call_ratio:>10.2f} ${data.underlying_price:>9.2f}"
            )

    # Refresh interval recommendations
    logger.info("")
    logger.info("RECOMMENDED REFRESH INTERVALS:")
    for interval_type, minutes in REFRESH_INTERVALS.items():
        if minutes >= 60:
            display = f"{minutes // 60}h" if minutes < 1440 else f"{minutes // 1440}d"
        else:
            display = f"{minutes}m"
        logger.info(f"  {interval_type}: {display}")

    return store


def analyze_put_call_ratios(store: MomentumDataStore):
    """Analyze put/call ratios for momentum signals"""
    if not store.options_volume:
        logger.warning("No options volume data to analyze")
        return

    logger.info("")
    logger.info("=" * 60)
    logger.info("PUT/CALL RATIO ANALYSIS")
    logger.info("=" * 60)

    # P/C Ratio thresholds for momentum signals
    # < 0.7 = Bullish (more calls than puts)
    # 0.7-1.0 = Neutral
    # > 1.0 = Bearish (more puts than calls)

    bullish = []
    neutral = []
    bearish = []

    for symbol, data in store.options_volume.items():
        if data.put_call_ratio < 0.7:
            bullish.append((symbol, data.put_call_ratio))
        elif data.put_call_ratio > 1.0:
            bearish.append((symbol, data.put_call_ratio))
        else:
            neutral.append((symbol, data.put_call_ratio))

    if bullish:
        logger.info(f"BULLISH (P/C < 0.7): {', '.join(f'{s} ({r:.2f})' for s, r in bullish)}")
    if neutral:
        logger.info(f"NEUTRAL (0.7-1.0): {', '.join(f'{s} ({r:.2f})' for s, r in neutral)}")
    if bearish:
        logger.info(f"BEARISH (P/C > 1.0): {', '.join(f'{s} ({r:.2f})' for s, r in bearish)}")


if __name__ == "__main__":
    # Check for MARKETDATA_TOKEN
    if not os.environ.get("MARKETDATA_TOKEN"):
        logger.warning("MARKETDATA_TOKEN environment variable not set!")
        logger.warning('Set it with: setx MARKETDATA_TOKEN "your_api_token" (Windows)')
        logger.warning('Or: export MARKETDATA_TOKEN="your_api_token" (Mac/Linux)')
        logger.warning("")
        logger.warning("Attempting to run anyway (may fail)...")

    # Run the fetch with 2-week lookback
    store = run_momentum_data_fetch(symbols=list(MAG7_SYMBOLS), lookback_days=14)

    # Analyze the results
    analyze_put_call_ratios(store)

    logger.info("")
    logger.info("Test complete. Data stored in memory (MomentumDataStore).")
