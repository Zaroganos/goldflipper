import os
import sys

# Get the absolute path to the project root directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Add the project root to Python path
sys.path.insert(0, project_root)

import json
import logging
from datetime import datetime
from typing import cast

import pandas as pd
import yaml
import yfinance as yf

from goldflipper.data.greeks.base import OptionData
from goldflipper.data.greeks.charm import CharmCalculator
from goldflipper.data.greeks.color import ColorCalculator
from goldflipper.data.greeks.delta import DeltaCalculator
from goldflipper.data.greeks.elasticity import ElasticityCalculator
from goldflipper.data.greeks.epsilon import EpsilonCalculator
from goldflipper.data.greeks.gamma import GammaCalculator
from goldflipper.data.greeks.parmicharma import ParmicharmaCalculator
from goldflipper.data.greeks.rho import RhoCalculator
from goldflipper.data.greeks.speed import SpeedCalculator
from goldflipper.data.greeks.theta import ThetaCalculator
from goldflipper.data.greeks.ultima import UltimaCalculator
from goldflipper.data.greeks.vanna import VannaCalculator
from goldflipper.data.greeks.vega import VegaCalculator
from goldflipper.data.greeks.vera import VeraCalculator
from goldflipper.data.greeks.veta import VetaCalculator
from goldflipper.data.greeks.vomma import VommaCalculator
from goldflipper.data.greeks.zomma import ZommaCalculator
from goldflipper.data.indicators.base import MarketData
from goldflipper.data.indicators.ema import EMACalculator
from goldflipper.data.indicators.macd import MACDCalculator
from goldflipper.data.indicators.ttm_squeeze import TTMSqueezeCalculator
from goldflipper.utils.display import TerminalDisplay as display
from goldflipper.utils.exe_utils import get_settings_path


def _as_series(data: pd.DataFrame, column: str) -> pd.Series:
    """Extract a single Series from potentially ambiguous pandas indexing."""
    values = data[column]
    if isinstance(values, pd.DataFrame):
        return cast(pd.Series, values.iloc[:, 0])
    return cast(pd.Series, values)


pd.set_option("display.max_rows", None)


def load_settings():
    """Load settings from yaml file."""
    # Use exe_utils for Nuitka-compatible path resolution
    settings_path = str(get_settings_path())
    with open(settings_path) as f:
        return yaml.safe_load(f)


def display_indicator_summary(indicator_data):
    """Display summary of technical indicators"""
    print("\nTechnical Indicators Summary:")

    # TTM Squeeze
    if "squeeze_on" in indicator_data.columns:
        print("\nTTM Squeeze:")
        try:
            squeeze_on = indicator_data["squeeze_on"].iloc[0]
            momentum = indicator_data["momentum"].iloc[0]
            momentum_increasing = indicator_data["momentum_increasing"].iloc[0]

            print(f"Status: {'ON (Compression)' if squeeze_on else 'OFF (No Squeeze)'}")
            print(f"Momentum: {momentum:.2f}")
            print(f"Momentum Trend: {'↑ INCREASING' if momentum_increasing else '↓ DECREASING'}")
        except Exception as e:
            print(f"Error processing TTM Squeeze data: {str(e)}")

    # EMAs
    ema_periods = [int(key.split("_")[1]) for key in indicator_data.columns if key.startswith("ema_")]
    if ema_periods:
        print("\nEMA Status:")
        for period in sorted(ema_periods):
            try:
                above_key = f"{period}_above"
                rising_key = f"{period}_rising"
                ema_key = f"ema_{period}"

                ema_value = indicator_data[ema_key].iloc[0]
                above_value = indicator_data[above_key].iloc[0]
                rising_value = indicator_data[rising_key].iloc[0]

                print(
                    f"EMA-{period}: {ema_value:.2f} | {'↑ ABOVE' if above_value else '↓ BELOW'} Price | {'↗ RISING' if rising_value else '↘ FALLING'}"
                )
            except Exception as e:
                print(f"Error processing EMA-{period}: {str(e)}")

        # Add 9/21 EMA Crossover check
        if "ema_9" in indicator_data.columns and "ema_21" in indicator_data.columns:
            ema9 = indicator_data["ema_9"].iloc[0]
            ema21 = indicator_data["ema_21"].iloc[0]
            print(f"\nEMA 9/21 Crossover: {'↑ BULLISH (9 > 21)' if ema9 > ema21 else '↓ BEARISH (9 < 21)'}")

    # MACD
    if "macd_line" in indicator_data.columns:
        print("\nMACD Status:")
        try:
            macd_value = indicator_data["macd_line"].iloc[0]
            signal_value = indicator_data["signal_line"].iloc[0]
            histogram_value = indicator_data["macd_histogram"].iloc[0]
            above_signal = indicator_data["macd_above_signal"].iloc[0]
            hist_increasing = indicator_data["histogram_increasing"].iloc[0]
            macd_increasing = indicator_data["macd_increasing"].iloc[0]
            crossover_up = indicator_data["macd_crossover_up"].iloc[0]
            crossover_down = indicator_data["macd_crossover_down"].iloc[0]

            print(f"MACD: {macd_value:.2f} ({'↑ ABOVE' if above_signal else '↓ BELOW'} Signal)")
            print(f"Signal: {signal_value:.2f}")
            print(f"Histogram: {histogram_value:.2f} ({'↗ INCREASING' if hist_increasing else '↘ DECREASING'})")
            print(f"MACD Trend: {'↗ RISING' if macd_increasing else '↘ FALLING'}")

            # Add crossover signals with explicit "no signal" message
            print("\nCrossover Status:", end=" ")
            if crossover_up:
                print("⚠️ BULLISH CROSSOVER SIGNAL ⚠️")
            elif crossover_down:
                print("⚠️ BEARISH CROSSOVER SIGNAL ⚠️")
            else:
                print("No MACD crossover signals detected")

        except Exception as e:
            print(f"Error processing MACD data: {str(e)}")

    print("-" * 50)


def display_options_chain(chain_data, indicator_data=None):
    """Display formatted options chain data with configurable columns."""
    settings = load_settings()
    display_config = settings["market_data"]["option_chain_display"]

    # Combine default columns with Greeks if enabled
    columns_to_display = display_config["default_columns"]
    if display_config["greeks"]["enabled"]:
        columns_to_display.extend(display_config["greeks"]["columns"])

    # Filter columns that exist in the data
    available_columns = [col for col in columns_to_display if col in chain_data.columns]

    # Display indicator summary if available
    if indicator_data is not None:
        display_indicator_summary(indicator_data)

    print("\nOptions Chain:")
    print(chain_data[available_columns].to_string(index=False))


def get_user_input():
    """Get user input for option parameters."""
    while True:
        try:
            ticker = input("Enter ticker symbol (e.g. SPY) or press Enter to return to main menu: ").upper()
            if not ticker:
                return None, None, None

            stock = yf.Ticker(ticker)
            available_dates = stock.options

            if not available_dates:
                print(f"\nNo option data available for {ticker}")
                continue

            # Show available expiration dates
            print("\nAvailable expiration dates:")
            for i, date in enumerate(stock.options, 1):
                print(f"{i}. {date}")

            date_choice = input("\nSelect expiration date number (or press Enter to return to main menu): ")
            if not date_choice:
                return None, None, None

            try:
                date_choice = int(date_choice) - 1
                if not (0 <= date_choice < len(available_dates)):
                    print("Invalid date selection")
                    continue
                selected_date = stock.options[date_choice]
            except ValueError:
                print("Invalid input. Please enter a number.")
                continue

            # Get option type
            option_type = input("\nEnter option type (call/put) or press Enter to return to main menu: ").lower()
            if not option_type:
                return None, None, None

            if option_type not in ["call", "put"]:
                print("Invalid option type")
                continue

            return ticker, selected_date, option_type

        except Exception as e:
            print(f"\nError occurred: {str(e)}")
            print("Returning to main menu...")
            return None, None, None


def get_option_premium_data(ticker, expiration_date=None, strike_price=None, option_type="call"):
    """
    Fetch option premium data for a specific option contract.

    Parameters:
    - ticker (str): Stock symbol
    - expiration_date (str, optional): Option expiration date in 'YYYY-MM-DD' format
    - strike_price (float, optional): Strike price of the option
    - option_type (str): 'call' or 'put', defaults to 'call'

    Returns:
    - dict: Option premium data including bid, ask, last price and volume
           Returns None if data unavailable
    """
    logging.info(f"Fetching option premium data for {ticker}...")
    display.info(f"Fetching option premium data for {ticker}...")

    try:
        stock = yf.Ticker(ticker)

        # Get available expiration dates
        available_dates = stock.options
        if not available_dates:
            logging.error(f"No option data available for {ticker}")
            display.error(f"No option data available for {ticker}")
            return None

        # Use provided expiration date or default to nearest
        target_date = expiration_date if expiration_date in available_dates else available_dates[0]

        # Get option chain
        chain = stock.option_chain(target_date)

        # Select calls or puts
        options_data = chain.calls if option_type.lower() == "call" else chain.puts

        # Filter by strike price if provided
        if strike_price:
            options_data = options_data[options_data["strike"] == float(strike_price)]

        if options_data.empty:
            logging.warning(f"No matching options found for {ticker} with given parameters")
            display.error(f"No matching options found for {ticker} with given parameters")
            return None

        # Get first matching option
        option = options_data.iloc[0]

        premium_data = {
            "bid": option.bid,
            "ask": option.ask,
            "last_price": option.lastPrice,
            "volume": option.volume,
            "strike": option.strike,
            "expiration": target_date,
        }

        logging.info(f"Option premium data fetched successfully for {ticker}")
        display.info(f"Option premium data fetched successfully for {ticker}")
        return premium_data

    except Exception as e:
        logging.error(f"Error fetching option premium data for {ticker}: {str(e)}")
        display.error(f"Error fetching option premium data for {ticker}: {str(e)}")
        return None


def get_all_plays():
    """Get all plays from various play folders."""
    from goldflipper.utils.exe_utils import get_plays_dir

    play_folders = ["new", "open", "temp"]
    plays = []
    base_path = str(get_plays_dir())  # Account-aware, exe-aware path

    for folder in play_folders:
        folder_path = os.path.join(base_path, folder)
        if os.path.exists(folder_path):
            for filename in os.listdir(folder_path):
                if filename.endswith(".json"):
                    filepath = os.path.join(folder_path, filename)
                    try:
                        with open(filepath) as f:
                            play_data = json.load(f)
                            plays.append({"folder": folder, "filename": filename, "data": play_data})
                    except json.JSONDecodeError as e:
                        logging.error(f"Invalid JSON in file {filepath}: {str(e)}")
                        display.error(f"Skipping invalid play file: {filename}")
                        continue
                    except Exception as e:
                        logging.error(f"Error reading file {filepath}: {str(e)}")
                        display.error(f"Error reading file: {filename}")
                        continue
    return plays


def display_plays(plays):
    """Display available plays for selection."""
    print("\nAvailable Plays:")
    for i, play in enumerate(plays, 1):
        data = play["data"]
        print(f"{i}. [{play['folder']}] {data['symbol']} {data['trade_type']} ${data['strike_price']} exp:{data['expiration_date']}")


def get_play_selection():
    """Get user input for play selection."""
    plays = get_all_plays()
    if not plays:
        print("No plays found")
        return None

    display_plays(plays)

    selection = input("\nSelect play number (or press Enter for manual input): ")
    if not selection:
        return None

    try:
        index = int(selection) - 1
        if 0 <= index < len(plays):
            return plays[index]
    except ValueError:
        pass

    print("Invalid selection, defaulting to manual input")
    return None


def prepare_option_data(row, underlying_price, expiration_date, risk_free_rate=0.05) -> OptionData:
    """Prepare option data for Greeks calculation."""
    current_date = datetime.now()
    expiry = datetime.strptime(expiration_date, "%Y-%m-%d")
    time_to_expiry = (expiry - current_date).days / 365.0

    return OptionData(
        underlying_price=underlying_price,
        strike_price=float(row["strike"]),
        time_to_expiry=time_to_expiry,
        risk_free_rate=risk_free_rate,
        volatility=float(row["impliedVolatility"]),
        dividend_yield=0.0,  # Could be made configurable in settings.yaml
        option_price=float(row["lastPrice"]),  # Add this line
    )


def calculate_greeks(options_data, underlying_price, expiration_date):
    """Calculate Greeks for the options chain."""
    # Create a copy of the DataFrame to avoid SettingWithCopyWarning
    options_data = options_data.copy()

    # Initialize new columns for Greeks
    options_data["delta"] = None
    options_data["gamma"] = None
    options_data["theta"] = None
    options_data["vega"] = None
    options_data["rho"] = None
    options_data["elasticity"] = None
    options_data["epsilon"] = None
    options_data["vanna"] = None
    options_data["charm"] = None
    options_data["vomma"] = None
    options_data["veta"] = None
    options_data["vera"] = None
    options_data["speed"] = None
    options_data["zomma"] = None
    options_data["color"] = None
    options_data["ultima"] = None
    options_data["parmicharma"] = None

    for idx, row in options_data.iterrows():
        try:
            # Prepare option data
            option_data = prepare_option_data(row, underlying_price, expiration_date)

            # Calculate Greeks using .loc to avoid warnings
            options_data.loc[idx, "delta"] = DeltaCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "gamma"] = GammaCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "theta"] = ThetaCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "vega"] = VegaCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "rho"] = RhoCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "elasticity"] = ElasticityCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "epsilon"] = EpsilonCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "vanna"] = VannaCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "charm"] = CharmCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "vomma"] = VommaCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "veta"] = VetaCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "vera"] = VeraCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "speed"] = SpeedCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "zomma"] = ZommaCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "color"] = ColorCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "ultima"] = UltimaCalculator(option_data).calculate(row["option_type"])
            options_data.loc[idx, "parmicharma"] = ParmicharmaCalculator(option_data).calculate(row["option_type"])

        except Exception as e:
            logging.warning(f"Error calculating Greeks for strike {row['strike']}: {str(e)}")
            display.error(f"Error calculating Greeks for strike {row['strike']}: {str(e)}")
            continue

    return options_data


def get_current_stock_price(stock):
    """Get current stock price from yfinance."""
    try:
        # First attempt: try to get lastPrice from fast_info
        price = stock.fast_info["lastPrice"]
        logging.info("Using real-time price from fast_info")
        display.info("For Stock data: using yfinance real-time price from fast_info", show_timestamp=False)
        return price
    except (KeyError, AttributeError):
        try:
            # Second attempt: try regular info
            price = stock.info["currentPrice"]
            logging.info("Using fallback method 1: currentPrice from stock.info")
            display.warning("Using fallback method 1: Price data may be slightly delayed")
            return price
        except (KeyError, AttributeError):
            try:
                # Last resort: get most recent price from today's data
                price = stock.history(period="1d", interval="1m")["Close"].iloc[-1]
                logging.warning("Using fallback method 2: Most recent minute data")
                display.warning("Using fallback method 2: Price data may be stale (from most recent minute)")
                return price
            except Exception as e:
                raise Exception(f"Could not fetch stock price using any method: {str(e)}") from e


def calculate_indicators(ticker: str, settings: dict) -> pd.DataFrame:
    """Calculate technical indicators for the underlying stock"""
    stock = yf.Ticker(ticker)

    # Get historical data
    hist = stock.history(period="1y")

    # Prepare market data
    market_data = MarketData(
        high=_as_series(hist, "High"),
        low=_as_series(hist, "Low"),
        close=_as_series(hist, "Close"),
        volume=_as_series(hist, "Volume"),
        period=settings["indicators"]["ttm_squeeze"]["period"],
    )

    indicators_dict = {}

    try:
        # Calculate TTM Squeeze
        if settings["indicators"]["ttm_squeeze"]["enabled"]:
            ttm_calc = TTMSqueezeCalculator(
                market_data,
                bb_mult=float(settings["indicators"]["ttm_squeeze"]["bb_multiplier"]),
                kc_mult=float(settings["indicators"]["ttm_squeeze"]["kc_multiplier"]),
            )
            ttm_indicators = ttm_calc.calculate()
            # Extract single values from Series
            indicators_dict.update(
                {
                    "squeeze_on": ttm_indicators["squeeze_on"].iloc[0],
                    "momentum": ttm_indicators["momentum"].iloc[0],
                    "momentum_increasing": ttm_indicators["momentum_increasing"].iloc[0],
                }
            )

        # Calculate EMAs
        if settings["indicators"]["ema"]["enabled"]:
            ema_calc = EMACalculator(market_data, periods=settings["indicators"]["ema"]["periods"])
            ema_indicators = ema_calc.calculate()
            # Extract single values from Series
            for key, value in ema_indicators.items():
                if key.startswith("ema_"):
                    indicators_dict[key] = value.iloc[-1]  # Get last value for EMAs
                else:
                    indicators_dict[key] = value.iloc[0]  # Get first value for boolean indicators

        # Calculate MACD
        if settings["indicators"]["macd"]["enabled"]:
            macd_calc = MACDCalculator(
                market_data,
                fast_period=settings["indicators"]["macd"]["fast_period"],
                slow_period=settings["indicators"]["macd"]["slow_period"],
                signal_period=settings["indicators"]["macd"]["signal_period"],
            )
            macd_indicators = macd_calc.calculate()
            # Extract single values from Series
            indicators_dict.update(
                {
                    "macd_line": macd_indicators["macd_line"].iloc[-1],
                    "signal_line": macd_indicators["signal_line"].iloc[-1],
                    "macd_histogram": macd_indicators["macd_histogram"].iloc[-1],
                    "macd_above_signal": macd_indicators["macd_above_signal"].iloc[0],
                    "histogram_increasing": macd_indicators["histogram_increasing"].iloc[0],
                    "macd_increasing": macd_indicators["macd_increasing"].iloc[0],
                    "macd_crossover_up": macd_indicators["macd_crossover_up"].iloc[0],
                    "macd_crossover_down": macd_indicators["macd_crossover_down"].iloc[0],
                }
            )

        # Convert all indicators to a DataFrame
        result_df = pd.DataFrame([indicators_dict])
        logging.debug(f"Calculated indicators: {list(result_df.columns)}")
        return result_df

    except Exception as e:
        logging.error(f"Error calculating indicators: {str(e)}")
        raise Exception(f"Error calculating indicators: {str(e)}") from e


def main():
    """Main function to fetch and display option data."""
    while True:
        play_data = get_play_selection()

        if play_data:
            # Extract data from selected play
            try:
                data = play_data["data"]
                ticker = data["symbol"]
                expiration_date = datetime.strptime(data["expiration_date"], "%m/%d/%Y").strftime("%Y-%m-%d")
                strike_price = float(data["strike_price"])
                option_type = data["trade_type"].lower()
            except Exception as e:
                print(f"\nError processing play data: {str(e)}")
                print("Please try again...")
                continue
        else:
            # Get manual input if no play selected
            input_data = get_user_input()
            if input_data == (None, None, None):
                print("\nReturning to main menu...")
                return
            ticker, expiration_date, option_type = input_data

        try:
            # Load settings
            settings = load_settings()

            if not ticker:
                print("\nTicker symbol is missing. Please try again...")
                continue

            # Calculate indicators first
            indicator_data = None
            if settings["indicators"]["enabled"]:
                try:
                    indicator_data = calculate_indicators(ticker, settings)
                    logging.info(f"Calculated indicators for {ticker}")
                    display.info(f"Calculated indicators for {ticker}")
                except Exception as e:
                    logging.warning(f"Failed to calculate indicators: {str(e)}")
                    display.error(f"Failed to calculate indicators: {str(e)}")

            # Fetch option data
            stock = yf.Ticker(ticker)
            logging.info("Using yfinance method: stock.option_chain()")
            display.info("For Options data: using yfinance method: stock.option_chain()", show_timestamp=False)
            chain = stock.option_chain(expiration_date)
            underlying_price = get_current_stock_price(stock)

            # Get appropriate chain
            options_data = chain.calls if option_type == "call" else chain.puts
            options_data["option_type"] = option_type

            # Filter by strike if from play
            if play_data and strike_price:
                options_data = options_data[(options_data["strike"] >= strike_price - 1) & (options_data["strike"] <= strike_price + 1)]

            if options_data.empty:
                print("\nNo matching options found")
                continue

            # Calculate Greeks
            options_data = calculate_greeks(options_data, underlying_price, expiration_date)

            # Display chain with indicators
            display_options_chain(options_data, indicator_data)

            choice = input("\nFetch more option data? (y/n): ").lower()
            if choice != "y":
                break

        except Exception as e:
            print(f"\nError fetching option data: {str(e)}")
            print("Please try again...")
            continue


if __name__ == "__main__":
    main()
